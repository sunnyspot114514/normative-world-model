from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class PhaseOneSourceLockTests(unittest.TestCase):
    def test_committed_v3_source_lock_matches_exact_bytes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        lock_path = root / "configs" / "phase1_v3_source_lock.json"
        locked = json.loads(lock_path.read_text(encoding="utf-8"))
        mismatches = {}
        for relative, expected in locked.items():
            path = root / relative
            actual = (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if path.exists()
                else None
            )
            if actual != expected:
                mismatches[relative] = {
                    "expected": expected,
                    "actual": actual,
                }
        self.assertEqual(mismatches, {})


if __name__ == "__main__":
    unittest.main()
