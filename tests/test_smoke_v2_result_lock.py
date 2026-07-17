from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.result_lock import sha256_file
from normative_world_model.smoke_v2_result_lock import (
    verify_phase3_anti_collapse_smoke_v2_result,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class AntiCollapseSmokeV2ResultLockTests(unittest.TestCase):
    def test_verifier_rejects_v2_result_hash_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            v2_result = root / (
                "artifacts/phase3_anti_collapse_smoke_v2/result.json"
            )
            v2_input = root / (
                "configs/phase3_anti_collapse_smoke_v2_lock.json"
            )
            v2_lock = root / (
                "configs/phase3_anti_collapse_smoke_v2_result_lock.json"
            )
            _write_json(v2_result, {"status": "BLOCKED"})
            _write_json(v2_input, {"bound_hashes": {}})
            _write_json(
                v2_lock,
                {
                    "status": "BLOCKED",
                    "result_sha256": hashlib.sha256(b"other").hexdigest(),
                    "input_lock_sha256": sha256_file(v2_input),
                },
            )
            failures = verify_phase3_anti_collapse_smoke_v2_result(root)
            self.assertIn("anti-collapse v2 result hash mismatch", failures)


if __name__ == "__main__":
    unittest.main()
