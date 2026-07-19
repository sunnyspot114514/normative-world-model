from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError

from normative_world_model.phase5_preflight import load_phase5_config
from normative_world_model.phase5_public_metadata import (
    PER_FILE_MAX_BYTES,
    FetchResult,
    FrozenPublicCheckpoint,
    _download_frozen_sources_to_root,
    _frozen_public_checkpoints,
    _parse_content_length,
    _publisher_file_plan,
    validate_huggingface_url,
)

REVISION = "a" * 40
SOURCE = FrozenPublicCheckpoint("base", "Qwen/Test-Base", REVISION)


def _public_files() -> dict[str, bytes]:
    return {
        "config.json": b'{"model_type":"test"}\n',
        "model.safetensors.index.json": b'{"metadata":{"total_size":1},"weight_map":{}}\n',
        "tokenizer.json": b'{"model":{"vocab":{"a":0}}}\n',
        "tokenizer_config.json": b'{"chat_template":"template"}\n',
    }


def _api_body(files: dict[str, bytes], *, revision: str = REVISION) -> bytes:
    siblings = []
    for relative, body in files.items():
        git_blob = hashlib.sha1(
            f"blob {len(body)}\0".encode("ascii") + body,
            usedforsecurity=False,
        ).hexdigest()
        row = {
            "rfilename": relative,
            "size": len(body),
            "blobId": git_blob,
        }
        if relative == "tokenizer.json":
            row["lfs"] = {
                "oid": "sha256:" + hashlib.sha256(body).hexdigest(),
                "size": len(body),
            }
        siblings.append(row)
    siblings.append(
        {
            "rfilename": "model-00001-of-00001.safetensors",
            "size": 123,
            "lfs": {"sha256": "f" * 64, "size": 123},
        }
    )
    return json.dumps({"sha": revision, "siblings": siblings}, sort_keys=True).encode("utf-8")


class _FixtureFetcher:
    def __init__(
        self,
        files: dict[str, bytes],
        *,
        api_revision: str = REVISION,
        external_redirect: bool = False,
        corrupt_tokenizer: bool = False,
        fail_first: bool = False,
    ) -> None:
        self.files = files
        self.api = _api_body(files, revision=api_revision)
        self.external_redirect = external_redirect
        self.corrupt_tokenizer = corrupt_tokenizer
        self.fail_first = fail_first
        self.calls = 0

    def __call__(self, url: str, maximum_bytes: int) -> FetchResult:
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise URLError("synthetic transient")
        if "/api/models/" in url:
            body = self.api
        else:
            relative = next(name for name in self.files if f"/{name}?" in url)
            body = self.files[relative]
            if self.corrupt_tokenizer and relative == "tokenizer.json":
                body = body[:-1] + (b"x" if body[-1:] != b"x" else b"y")
        if len(body) > maximum_bytes:
            raise ValueError("fixture obeys caller caps")
        final_url = url
        redirects: tuple[str, ...] = ()
        if "tokenizer.json?" in url:
            final_url = (
                "https://evil.example/object"
                if self.external_redirect
                else "https://us.aws.cdn.hf.co/object"
            )
            redirects = (final_url,)
        return FetchResult(body, final_url, redirects, len(body))


class Phase5PublicMetadataContractTests(unittest.TestCase):
    def test_url_boundary_distinguishes_initial_and_official_redirect_hosts(self) -> None:
        self.assertEqual(
            validate_huggingface_url("https://huggingface.co/api/models/x", initial=True),
            "https://huggingface.co/api/models/x",
        )
        validate_huggingface_url("https://us.aws.cdn.hf.co/object?signature=x", initial=False)
        validate_huggingface_url("https://cdn-lfs.huggingface.co/object", initial=False)
        for value, initial in (
            ("http://huggingface.co/file", True),
            ("https://sub.huggingface.co/file", True),
            ("https://huggingface.co.evil.example/file", False),
            ("https://user@huggingface.co/file", True),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_huggingface_url(value, initial=initial)

    def test_content_length_cap_is_strict(self) -> None:
        self.assertEqual(_parse_content_length("10", maximum_bytes=10), 10)
        self.assertIsNone(_parse_content_length(None, maximum_bytes=10))
        for value in ("11", "-1", "1.0", " 1"):
            with self.assertRaises(ValueError):
                _parse_content_length(value, maximum_bytes=10)

    def test_committed_config_yields_only_two_exact_frozen_sources(self) -> None:
        sources = _frozen_public_checkpoints(load_phase5_config())
        self.assertEqual([source.checkpoint for source in sources], ["agentworld", "base"])
        self.assertTrue(all(len(source.revision) == 40 for source in sources))
        self.assertNotEqual(sources[0].repo_id, sources[1].repo_id)

    def test_publisher_plan_requires_revision_required_files_and_caps(self) -> None:
        files = _public_files()
        _, plan = _publisher_file_plan(SOURCE, _api_body(files))
        self.assertEqual({row["path"] for row in plan}, set(files))
        self.assertNotIn("model-00001-of-00001.safetensors", {row["path"] for row in plan})
        with self.assertRaisesRegex(ValueError, "revision mismatch"):
            _publisher_file_plan(SOURCE, _api_body(files, revision="b" * 40))
        missing = dict(files)
        missing.pop("tokenizer.json")
        with self.assertRaisesRegex(ValueError, "lacks required metadata"):
            _publisher_file_plan(SOURCE, _api_body(missing))

        document = json.loads(_api_body(files))
        target = next(row for row in document["siblings"] if row["rfilename"] == "config.json")
        target["size"] = PER_FILE_MAX_BYTES + 1
        with self.assertRaisesRegex(ValueError, "violates cap"):
            _publisher_file_plan(SOURCE, json.dumps(document).encode("utf-8"))


class Phase5PublicMetadataDownloadTests(unittest.TestCase):
    def test_fixture_download_is_exact_hash_bound_and_weight_free(self) -> None:
        files = _public_files()
        fetcher = _FixtureFetcher(files, fail_first=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            manifest = _download_frozen_sources_to_root((SOURCE,), root, fetcher)
            self.assertTrue((root / "manifest.json").is_file())
            self.assertTrue((root / "base" / "publisher_api_response.json").is_file())
            self.assertEqual(manifest["snapshots"][0]["file_count"], 4)
            self.assertGreaterEqual(fetcher.calls, 6)
            for relative, body in files.items():
                self.assertEqual((root / "base" / "files" / relative).read_bytes(), body)
            self.assertFalse(any(path.suffix == ".safetensors" for path in root.rglob("*")))
            tokenizer_row = next(
                row
                for row in manifest["snapshots"][0]["files"]
                if row["path"] == "tokenizer.json"
            )
            self.assertEqual(tokenizer_row["sha256"], tokenizer_row["publisher_lfs_sha256"])
            config_row = next(
                row
                for row in manifest["snapshots"][0]["files"]
                if row["path"] == "config.json"
            )
            self.assertEqual(config_row["publisher_verification_kind"], "git_blob_sha1")
            self.assertEqual(tokenizer_row["redirect_chain"], ["https://us.aws.cdn.hf.co/object"])

    def test_external_redirect_and_lfs_mismatch_fail_and_remove_partial_root(self) -> None:
        files = _public_files()
        for fetcher, message in (
            (_FixtureFetcher(files, external_redirect=True), "redirect host"),
            (_FixtureFetcher(files, corrupt_tokenizer=True), "SHA-256 differs"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "metadata"
                with self.assertRaisesRegex(ValueError, message):
                    _download_frozen_sources_to_root((SOURCE,), root, fetcher)
                self.assertFalse(root.exists())

    def test_existing_output_root_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            root.mkdir()
            marker = root / "marker"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                _download_frozen_sources_to_root(
                    (SOURCE,),
                    root,
                    _FixtureFetcher(_public_files()),
                )
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_duplicate_json_keys_are_rejected_after_publisher_hash_verification(self) -> None:
        files = _public_files()
        files["config.json"] = b'{"model_type":"a","model_type":"b"}\n'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "metadata"
            with self.assertRaisesRegex(ValueError, "duplicate key"):
                _download_frozen_sources_to_root(
                    (SOURCE,),
                    root,
                    _FixtureFetcher(files),
                )
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
