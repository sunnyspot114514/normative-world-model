from __future__ import annotations

import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase5_public_metadata import _canonical_sha256
from normative_world_model.phase5_public_weight_plan import (
    WEIGHT_PLAN_FORMAT_VERSION,
    _artifact_sha256,
)
from normative_world_model.phase5_weight_snapshot import (
    verify_downloaded_weight_snapshots,
)


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _fixture(root: Path) -> tuple[dict, dict, dict[str, Path]]:
    checkpoints = []
    snapshots = []
    roots = {}
    total_weight = 0
    for checkpoint in ("agentworld", "base"):
        revision = f"{checkpoint}-revision"
        repo_id = f"Qwen/{checkpoint}"
        weight_body = f"{checkpoint}-weight".encode()
        metadata_body = f"{checkpoint}-config".encode()
        snapshot_root = root / checkpoint
        snapshot_root.mkdir()
        (snapshot_root / "model.safetensors").write_bytes(weight_body)
        (snapshot_root / "config.json").write_bytes(metadata_body)
        roots[checkpoint] = snapshot_root
        weight_row = {
            "path": "model.safetensors",
            "bytes": len(weight_body),
            "sha256": _sha(weight_body),
        }
        metadata_row = {
            "path": "config.json",
            "bytes": len(metadata_body),
            "sha256": _sha(metadata_body),
        }
        checkpoints.append(
            {
                "checkpoint": checkpoint,
                "repo_id": repo_id,
                "revision": revision,
                "weight_plan": {"files": [weight_row]},
            }
        )
        snapshots.append(
            {
                "checkpoint": checkpoint,
                "repo_id": repo_id,
                "revision": revision,
                "files": [metadata_row],
            }
        )
        total_weight += len(weight_body)
    weight_plan = {
        "format_version": WEIGHT_PLAN_FORMAT_VERSION,
        "status": "PASS_METADATA_ONLY_NO_WEIGHT_BYTES",
        "authorization": {
            "model_download": False,
            "remote_fetch_performed": False,
            "weight_bytes_present": False,
        },
        "checkpoints": checkpoints,
        "totals": {
            "checkpoint_count": 2,
            "weight_file_count": 2,
            "publisher_weight_bytes": total_weight,
        },
    }
    weight_plan["artifact_sha256"] = _artifact_sha256(weight_plan)
    metadata = {
        "format_version": "phase5-public-metadata-v1",
        "snapshots": snapshots,
    }
    metadata["manifest_sha256"] = _canonical_sha256(metadata)
    return weight_plan, metadata, roots


def _verify(weight_plan: dict, metadata: dict, roots: dict[str, Path]) -> dict:
    return verify_downloaded_weight_snapshots(
        weight_plan,
        metadata,
        roots,
        expected_weight_plan_sha256=weight_plan["artifact_sha256"],
        expected_metadata_manifest_sha256=metadata["manifest_sha256"],
    )


class Phase5WeightSnapshotTests(unittest.TestCase):
    def test_exact_two_checkpoint_snapshot_passes_and_is_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            result = _verify(weight_plan, metadata, roots)
            self.assertEqual(result["status"], "PASS_EXACT_DOWNLOADED_SNAPSHOT_BYTES")
            self.assertEqual(result["totals"]["checkpoint_count"], 2)
            self.assertEqual(result["totals"]["file_count"], 4)
            self.assertEqual(
                result["snapshot_bundle_sha256"],
                _canonical_sha256(
                    {key: value for key, value in result.items() if key != "snapshot_bundle_sha256"}
                ),
            )

    def test_missing_extra_size_and_digest_drift_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            (roots["agentworld"] / "extra.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exact file set"):
                _verify(weight_plan, metadata, roots)
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            (roots["base"] / "model.safetensors").write_bytes(b"same-size-wrong")
            with self.assertRaisesRegex(ValueError, "size differs|digest differs"):
                _verify(weight_plan, metadata, roots)
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            (roots["base"] / "config.json").unlink()
            with self.assertRaisesRegex(ValueError, "exact file set"):
                _verify(weight_plan, metadata, roots)

    def test_plan_and_metadata_tamper_fail_before_snapshot_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            tampered = copy.deepcopy(weight_plan)
            tampered["checkpoints"][0]["revision"] = "changed"
            with self.assertRaisesRegex(ValueError, "weight plan"):
                verify_downloaded_weight_snapshots(
                    tampered,
                    metadata,
                    roots,
                    expected_weight_plan_sha256=weight_plan["artifact_sha256"],
                    expected_metadata_manifest_sha256=metadata["manifest_sha256"],
                )
            tampered_metadata = copy.deepcopy(metadata)
            tampered_metadata["snapshots"][0]["revision"] = "changed"
            with self.assertRaisesRegex(ValueError, "metadata manifest"):
                verify_downloaded_weight_snapshots(
                    weight_plan,
                    tampered_metadata,
                    roots,
                    expected_weight_plan_sha256=weight_plan["artifact_sha256"],
                    expected_metadata_manifest_sha256=metadata["manifest_sha256"],
                )

    def test_hard_links_and_path_tricks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            source = roots["agentworld"] / "config.json"
            linked = roots["agentworld"] / "linked.json"
            os.link(source, linked)
            with self.assertRaisesRegex(ValueError, "multiple hard links"):
                _verify(weight_plan, metadata, roots)
        with tempfile.TemporaryDirectory() as temporary:
            weight_plan, metadata, roots = _fixture(Path(temporary))
            malicious = copy.deepcopy(weight_plan)
            malicious["checkpoints"][0]["weight_plan"]["files"][0]["path"] = "../model.safetensors"
            malicious["artifact_sha256"] = _artifact_sha256(
                {key: value for key, value in malicious.items() if key != "artifact_sha256"}
            )
            with self.assertRaisesRegex(ValueError, "canonical relative path"):
                verify_downloaded_weight_snapshots(
                    malicious,
                    metadata,
                    roots,
                    expected_weight_plan_sha256=malicious["artifact_sha256"],
                    expected_metadata_manifest_sha256=metadata["manifest_sha256"],
                )

    def test_verifier_has_no_download_network_or_execution_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_weight_snapshot.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess",
            "import socket",
            "import requests",
            "import httpx",
            "urllib.request",
            "snapshot_download",
            "hf_hub_download",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
