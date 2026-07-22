from __future__ import annotations

import json
from pathlib import Path
import unittest

from normative_world_model.phase5_public_metadata import _canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "configs" / "phase5_public_synthetic_preflight_result_20260722.json"


class Phase5PublicSyntheticResultTests(unittest.TestCase):
    def test_preserved_failure_is_hash_bound_and_cannot_unlock_science(self) -> None:
        record = json.loads(RESULT.read_text(encoding="utf-8"))
        expected_hash = record.pop("result_sha256")
        self.assertEqual(expected_hash, _canonical_sha256(record))
        self.assertEqual(record["status"], "FAIL_PRECOMMITTED_SEMANTIC_GATE")
        self.assertEqual(
            record["primary_failure"]["classification"],
            "DETERMINISTIC_REASONING_ENVELOPE_LEAKAGE_ON_TEXT_COMPLETION_PATH",
        )
        self.assertFalse(record["primary_failure"]["post_hoc_normalization_applied"])
        self.assertFalse(record["governance"]["formal_scientific_execution_started"])
        self.assertEqual(record["governance"]["confirmation_status"], "RESERVED_NOT_GENERATED")
        self.assertEqual(
            record["governance"]["next_stage"],
            "BLOCKED_PENDING_VERSIONED_PREFLIGHT_DECISION",
        )


if __name__ == "__main__":
    unittest.main()
