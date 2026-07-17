from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from normative_world_model.result_lock import sha256_file
from normative_world_model.smoke_result_lock import (
    verify_phase3_anti_collapse_smoke_result,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class AntiCollapseSmokeResultLockTests(unittest.TestCase):
    def test_verifier_accepts_a_consistent_blocked_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bound = root / "bound.bin"
            run_file = root / "run.bin"
            confirmation = root / (
                "data/generated/phase1_discovery_v3/"
                "confirmation_reservation.json"
            )
            bound.write_bytes(b"bound\n")
            run_file.write_bytes(b"run\n")
            _write_json(
                confirmation,
                {"status": "RESERVED_NOT_GENERATED"},
            )
            training = {
                "optimizer_steps": 1,
                "output_files": {"run.bin": sha256_file(run_file)},
            }
            evaluation = {"evaluation_records": 1, "normative_accuracy": 0.0}
            gate = {"normative_accuracy": False}
            result = {
                "status": "BLOCKED",
                "run_kind": "phase3_retained_discovery_anti_collapse_smoke",
                "scientific_arm_comparison": False,
                "git_head_before_execution": "abc123",
                "confirmation_status": "RESERVED_NOT_GENERATED",
                "next_action": "stop_before_formal_arm_comparison",
                "training": training,
                "evaluation": evaluation,
                "gate_checks": gate,
                "bound_hashes": {"bound.bin": sha256_file(bound)},
            }
            result_path = root / (
                "artifacts/phase3_anti_collapse_smoke/result.json"
            )
            input_lock_path = root / (
                "configs/phase3_anti_collapse_smoke_lock.json"
            )
            result_lock_path = root / (
                "configs/phase3_anti_collapse_smoke_result_lock.json"
            )
            _write_json(result_path, result)
            _write_json(
                input_lock_path,
                {"bound_hashes": result["bound_hashes"]},
            )
            _write_json(
                result_lock_path,
                {
                    "status": "BLOCKED",
                    "run_kind": result["run_kind"],
                    "scientific_arm_comparison": False,
                    "git_head_before_execution": "abc123",
                    "confirmation_status": "RESERVED_NOT_GENERATED",
                    "input_lock_sha256": sha256_file(input_lock_path),
                    "result_sha256": sha256_file(result_path),
                    "run_files": training["output_files"],
                    "training": {"optimizer_steps": 1},
                    "evaluation": {"records": 1, "normative_accuracy": 0.0},
                    "gate_checks": gate,
                },
            )
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout=b"",
                stderr=b"not tracked",
            )
            with patch(
                "normative_world_model.smoke_result_lock.subprocess.run",
                return_value=completed,
            ):
                self.assertEqual(
                    verify_phase3_anti_collapse_smoke_result(root),
                    [],
                )

    def test_verifier_rejects_result_hash_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / (
                "artifacts/phase3_anti_collapse_smoke/result.json"
            )
            input_lock_path = root / (
                "configs/phase3_anti_collapse_smoke_lock.json"
            )
            lock_path = root / (
                "configs/phase3_anti_collapse_smoke_result_lock.json"
            )
            _write_json(result_path, {"status": "BLOCKED"})
            _write_json(input_lock_path, {"bound_hashes": {}})
            _write_json(
                lock_path,
                {
                    "status": "BLOCKED",
                    "result_sha256": hashlib.sha256(b"other").hexdigest(),
                    "input_lock_sha256": sha256_file(input_lock_path),
                },
            )
            failures = verify_phase3_anti_collapse_smoke_result(root)
            self.assertIn("anti-collapse smoke result hash mismatch", failures)


if __name__ == "__main__":
    unittest.main()
