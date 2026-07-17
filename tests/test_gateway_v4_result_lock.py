from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.gateway_v4_result_lock import (
    verify_phase3_representation_gateway_v4_result,
)


class GatewayV4ResultLockTests(unittest.TestCase):
    def test_preserved_local_result_verifies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        if not (
            root / "artifacts/phase3_representation_gateway_v4/result.json"
        ).is_file():
            self.skipTest("ignored local V4 gateway result is absent")
        self.assertEqual(
            verify_phase3_representation_gateway_v4_result(root), []
        )

    def test_missing_result_is_not_silently_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            failures = verify_phase3_representation_gateway_v4_result(
                Path(directory)
            )
        self.assertIn("missing V4 gateway result", failures)

    def test_result_hash_tampering_is_rejected_before_gate_interpretation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "artifacts/phase3_representation_gateway_v4/result.json"
            input_lock = root / "configs/phase3_representation_gateway_v4_input_lock.json"
            result_lock = root / "configs/phase3_representation_gateway_v4_result_lock.json"
            result.parent.mkdir(parents=True)
            input_lock.parent.mkdir(parents=True)
            result.write_text("{}\n", encoding="utf-8")
            input_lock.write_text("{}\n", encoding="utf-8")
            result_lock.write_text(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "result_sha256": hashlib.sha256(b"other").hexdigest(),
                        "input_lock_sha256": hashlib.sha256(
                            input_lock.read_bytes()
                        ).hexdigest(),
                        "gate_checks": {},
                        "run_files": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            failures = verify_phase3_representation_gateway_v4_result(root)
        self.assertIn("V4 result hash mismatch", failures)


if __name__ == "__main__":
    unittest.main()
