from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.gateway_v3_result_lock import (
    verify_phase3_diversity_gateway_v3_result,
)

ROOT = Path(__file__).resolve().parents[1]


class GatewayV3ResultLockTests(unittest.TestCase):
    def test_preserved_local_result_verifies(self) -> None:
        if not (
            ROOT / "artifacts/phase3_diversity_gateway_v3/result.json"
        ).is_file():
            self.skipTest("ignored local gateway result is absent")
        self.assertEqual(verify_phase3_diversity_gateway_v3_result(ROOT), [])

    def test_result_hash_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "artifacts/phase3_diversity_gateway_v3/result.json"
            input_lock = root / (
                "configs/phase3_diversity_gateway_v3_input_lock.json"
            )
            result_lock = root / (
                "configs/phase3_diversity_gateway_v3_result_lock.json"
            )
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
            self.assertIn(
                "gateway result hash mismatch",
                verify_phase3_diversity_gateway_v3_result(root),
            )


if __name__ == "__main__":
    unittest.main()

