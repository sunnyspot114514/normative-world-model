from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from normative_world_model.result_lock import (
    sha256_file,
    verify_phase3_schema_gate_result,
)


class PhaseThreeResultLockTests(unittest.TestCase):
    def test_sha256_file_streams_expected_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.bin"
            path.write_bytes(b"phase-three")
            self.assertEqual(
                sha256_file(path),
                hashlib.sha256(b"phase-three").hexdigest(),
            )

    def test_verifier_rejects_a_tampered_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / (
                "artifacts/phase3_retained_schema_gate/schema_gate_result.json"
            )
            lock_path = root / (
                "configs/phase3_retained_schema_gate_result_lock.json"
            )
            result_path.parent.mkdir(parents=True)
            lock_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps({"status": "PASS"}) + "\n",
                encoding="utf-8",
            )
            lock_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "result_sha256": "0" * 64,
                        "input_locks": {},
                        "adapter_files": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            failures = verify_phase3_schema_gate_result(root)
            self.assertIn("Phase-3 result hash mismatch", failures)

    def test_git_blob_is_checked_at_execution_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / (
                "artifacts/phase3_retained_schema_gate/schema_gate_result.json"
            )
            lock_path = root / (
                "configs/phase3_retained_schema_gate_result_lock.json"
            )
            source_path = root / "source.json"
            adapter_path = root / "adapter.bin"
            input_path = root / "input.json"
            for path, payload in (
                (source_path, b"source\n"),
                (adapter_path, b"adapter\n"),
                (input_path, b"input\n"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            result = {
                "status": "PASS",
                "run_kind": "phase3_retained_discovery_schema_gate",
                "git_head_before_execution": "abc123",
                "scope": "retained_discovery_schema_convergence_only",
                "confirmation_status": "RESERVED_NOT_GENERATED",
                "scientific_arm_comparison": False,
                "gate_checks": {"strict_parse_rate": True},
                "source_hashes": {"source.json": sha256_file(source_path)},
                "adapter_files": {
                    "adapter.bin": sha256_file(adapter_path),
                },
                "bound_input_hashes": {
                    "historical.py": hashlib.sha256(b"historical\n").hexdigest(),
                },
            }
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(
                json.dumps(result, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            lock = {
                "status": "PASS",
                "run_kind": result["run_kind"],
                "git_head_before_execution": "abc123",
                "scope": result["scope"],
                "confirmation_status": "RESERVED_NOT_GENERATED",
                "scientific_arm_comparison": False,
                "result_sha256": sha256_file(result_path),
                "input_locks": {"input.json": sha256_file(input_path)},
                "adapter_files": {
                    "adapter.bin": sha256_file(adapter_path),
                },
            }
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text(json.dumps(lock) + "\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=b"historical\n",
                stderr=b"",
            )
            with patch(
                "normative_world_model.result_lock.subprocess.run",
                return_value=completed,
            ):
                self.assertEqual(
                    verify_phase3_schema_gate_result(root),
                    [],
                )


if __name__ == "__main__":
    unittest.main()
