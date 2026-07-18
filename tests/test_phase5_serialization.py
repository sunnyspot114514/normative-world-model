from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase5_serialization import (
    inspect_tokenizer_packages,
    prove_common_prompt_token_equality,
    render_common_base_prompt,
    resolve_publisher_weight_plan,
    validate_public_metadata_path,
)


class _Tokenizer:
    def __init__(self, *, offset: int = 0) -> None:
        self.offset = offset
        self.render_calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.render_calls.append((messages, kwargs))
        return "<common>" + "|".join(item["content"] for item in messages)

    def encode(self, text: str, *, add_special_tokens: bool):
        if add_special_tokens:
            raise AssertionError("special tokens must not be added by encode")
        return [ord(character) + self.offset for character in text]


def _write_tokenizer_package(root: Path, *, extra: bool) -> None:
    added = [{"id": 3, "content": "<shared>"}]
    if extra:
        added.append({"id": 4, "content": "<think>"})
    tokenizer = {
        "model": {"type": "BPE", "vocab": {"a": 0, "b": 1}},
        "normalizer": None,
        "pre_tokenizer": {"type": "ByteLevel"},
        "post_processor": None,
        "decoder": {"type": "ByteLevel"},
        "added_tokens": added,
    }
    (root / "tokenizer.json").write_text(
        json.dumps(tokenizer, sort_keys=True), encoding="utf-8"
    )
    (root / "tokenizer_config.json").write_text(
        json.dumps({"chat_template": "template-extra" if extra else "template-base"}),
        encoding="utf-8",
    )


class Phase5TokenizerPackageTests(unittest.TestCase):
    def test_package_inspection_binds_files_and_reports_only_extras(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            report = inspect_tokenizer_packages(base, agent)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["core_vocab_entries"], 2)
            self.assertEqual(report["agentworld_only_added_tokens"], {"4": "<think>"})
            self.assertFalse(report["chat_templates_identical"])

    def test_core_token_id_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            document = json.loads((agent / "tokenizer.json").read_text(encoding="utf-8"))
            document["model"]["vocab"]["b"] = 2
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "core vocabularies"):
                inspect_tokenizer_packages(base, agent)

    def test_bpe_model_change_outside_vocab_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / "base"
            agent = root / "agent"
            base.mkdir()
            agent.mkdir()
            _write_tokenizer_package(base, extra=False)
            _write_tokenizer_package(agent, extra=True)
            document = json.loads((agent / "tokenizer.json").read_text(encoding="utf-8"))
            document["model"]["byte_fallback"] = True
            (agent / "tokenizer.json").write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "section differs: model"):
                inspect_tokenizer_packages(base, agent)


class Phase5CommonSerializationTests(unittest.TestCase):
    def test_renderer_disables_thinking_and_proof_keeps_all_token_ids(self) -> None:
        base = _Tokenizer()
        agent = _Tokenizer()
        messages = [
            {"role": "system", "content": "synthetic system"},
            {"role": "user", "content": "synthetic user"},
        ]
        rendered = render_common_base_prompt(base, messages)
        kwargs = base.render_calls[0][1]
        self.assertFalse(kwargs["enable_thinking"])
        self.assertTrue(kwargs["add_generation_prompt"])
        proof = prove_common_prompt_token_equality(
            [("prompt-1", rendered)],
            base_tokenizer=base,
            agentworld_tokenizer=agent,
        )
        self.assertEqual(proof["prompt_count"], 1)
        self.assertEqual(proof["rows"][0]["token_count"], len(rendered))
        self.assertEqual(len(proof["rows"][0]["token_ids"]), len(rendered))

    def test_single_token_mismatch_stops_the_proof(self) -> None:
        with self.assertRaisesRegex(ValueError, "token-ID mismatch"):
            prove_common_prompt_token_equality(
                [("prompt-1", "synthetic")],
                base_tokenizer=_Tokenizer(),
                agentworld_tokenizer=_Tokenizer(offset=1),
            )


class Phase5PublisherPlanTests(unittest.TestCase):
    def test_weight_plan_is_manifest_driven(self) -> None:
        index = {
            "weight_map": {
                "layer.0": "model-00001-of-00002.safetensors",
                "layer.1": "model-00002-of-00002.safetensors",
            }
        }
        siblings = [
            {
                "rfilename": "model-00002-of-00002.safetensors",
                "size": 20,
                "lfs_sha256": "b" * 64,
            },
            {
                "rfilename": "model-00001-of-00002.safetensors",
                "size": 10,
                "lfs_sha256": "a" * 64,
            },
        ]
        plan = resolve_publisher_weight_plan(index, reversed(siblings))
        self.assertEqual(plan["weight_file_count"], 2)
        self.assertEqual(plan["total_weight_bytes"], 30)
        self.assertEqual([row["bytes"] for row in plan["files"]], [10, 20])

    def test_missing_publisher_weight_or_bad_digest_fails(self) -> None:
        index = {"weight_map": {"layer": "model.safetensors"}}
        with self.assertRaisesRegex(ValueError, "lacks referenced weight"):
            resolve_publisher_weight_plan(index, [])
        with self.assertRaisesRegex(ValueError, "lacks a lowercase SHA-256"):
            resolve_publisher_weight_plan(
                index,
                [{"rfilename": "model.safetensors", "size": 1, "lfs_sha256": "bad"}],
            )

    def test_public_metadata_allowlist_excludes_weights_and_path_tricks(self) -> None:
        self.assertEqual(
            validate_public_metadata_path("tokenizer/tokenizer.json"),
            "tokenizer/tokenizer.json",
        )
        for value in ("model.safetensors", "../tokenizer.json", "README.md"):
            with self.assertRaises(ValueError):
                validate_public_metadata_path(value)


if __name__ == "__main__":
    unittest.main()
