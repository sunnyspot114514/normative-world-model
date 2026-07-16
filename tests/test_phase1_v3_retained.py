from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.retained_v3 import validate_v3_external_acceptance


def _write(path: Path, value: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: dict) -> str:
    return _write(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
    )


class PhaseOneV3RetainedTests(unittest.TestCase):
    def _accepted_root(self, root: Path) -> None:
        source_lock = {}
        for index in range(29):
            relative = f"frozen/input_{index:02d}.txt"
            source_lock[relative] = _write(
                root / relative,
                f"frozen-{index}\n".encode(),
            )
        _write_json(root / "configs/phase1_v3_source_lock.json", source_lock)

        game_path = root / "data/generated/phase1_v3_smoke/game.jsonl"
        organization_path = (
            root / "data/generated/phase1_v3_smoke/organization.jsonl"
        )
        game_hash = _write(game_path, b'{"environment":"game"}\n')
        organization_hash = _write(
            organization_path,
            b'{"environment":"organization"}\n',
        )
        report = {
            "status": "PASS",
            "run_kind": "v3_internal_smoke",
            "preregistration_version": 3,
            "generator_revision": 1,
            "total_discovery_families": 600,
            "temporary_fixture_family_count": 0,
            "confirmation": {"status": "RESERVED_NOT_GENERATED"},
            "internal_review": {"authorizes_retained_generation": False},
        }
        report_path = root / "artifacts/phase1_v3_smoke/phase1_exit_report.json"
        report_hash = _write_json(report_path, report)
        manifest = {
            "run_kind": "v3_internal_smoke",
            "family_count": 600,
            "files": {
                "data/generated/phase1_v3_smoke/game.jsonl": game_hash,
                "data/generated/phase1_v3_smoke/organization.jsonl": (
                    organization_hash
                ),
                "artifacts/phase1_v3_smoke/phase1_exit_report.json": report_hash,
            },
            "inputs": source_lock,
        }
        manifest_path = root / "artifacts/phase1_v3_smoke/provenance_manifest.json"
        manifest_hash = _write_json(manifest_path, manifest)
        acceptance = {
            "status": "EXTERNAL_ACCEPTED",
            "unconditional": True,
            "preregistration_version": 3,
            "generator_revision": 1,
            "run_kind": "v3_internal_smoke",
            "reviewer": "external reviewer",
            "reviewed_at": "2026-07-16T17:24:32Z",
            "provenance_manifest_sha256": manifest_hash,
            "corpus_sha256": {
                "data/generated/phase1_v3_smoke/game.jsonl": game_hash,
                "data/generated/phase1_v3_smoke/organization.jsonl": (
                    organization_hash
                ),
            },
            "blocking_findings": [],
        }
        _write_json(
            root / "artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json",
            acceptance,
        )

    def test_external_acceptance_binds_all_frozen_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._accepted_root(root)
            failures = validate_v3_external_acceptance(root)
            self.assertEqual(failures, [])

    def test_external_acceptance_rejects_changed_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._accepted_root(root)
            _write(
                root / "data/generated/phase1_v3_smoke/game.jsonl",
                b'{"environment":"changed"}\n',
            )
            failures = validate_v3_external_acceptance(root)
            self.assertTrue(
                any("accepted smoke corpus hash mismatch" in item for item in failures)
            )


if __name__ == "__main__":
    unittest.main()
