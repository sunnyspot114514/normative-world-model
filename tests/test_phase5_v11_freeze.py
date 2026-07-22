from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from normative_world_model.phase5_public_metadata import _canonical_sha256
from normative_world_model.phase5_synthetic_client_plan import (
    PUBLIC_REQUEST_SEED,
    PUBLIC_TOY_EXPECTED,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE_PATH = ROOT / "configs" / "phase5_v11_estimand_freeze.json"


class Phase5V11EstimandFreezeTests(unittest.TestCase):
    def test_freeze_is_self_bound_closed_and_preserves_v10_failure(self) -> None:
        record = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        without_hash = {key: value for key, value in record.items() if key != "freeze_sha256"}
        self.assertEqual(record["freeze_sha256"], _canonical_sha256(without_hash))
        self.assertEqual(
            record["status"],
            "V11_ESTIMAND_FROZEN_EXECUTION_NOT_AUTHORIZED",
        )
        self.assertFalse(any(record["authorization"].values()))
        self.assertEqual(
            record["supersession"]["v10_status_remains"],
            "FAIL_PRECOMMITTED_SEMANTIC_GATE",
        )
        self.assertTrue(record["supersession"]["retroactive_relabeling_forbidden"])
        previous = ROOT / record["supersession"]["v10_result_file"]
        self.assertEqual(
            hashlib.sha256(previous.read_bytes()).hexdigest(),
            record["supersession"]["v10_result_file_sha256"],
        )

    def test_unseen_toy_and_two_track_gate_match_implementation(self) -> None:
        record = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(record["unseen_public_probe"]["seed"], PUBLIC_REQUEST_SEED)
        self.assertEqual(record["unseen_public_probe"]["expected"], PUBLIC_TOY_EXPECTED)
        self.assertEqual(record["estimand"]["formal_gate_mode"], "native_package")
        self.assertFalse(record["estimand"]["diagnostic_tail_may_authorize_science"])
        self.assertTrue(record["gates"]["native_strict_json_exact_oracle_required"])
        self.assertFalse(record["gates"]["common_classification_is_pass_predicate"])

    def test_local_plan_matches_freeze_when_present(self) -> None:
        record = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
        path = ROOT / record["client_plan"]["relative_path"]
        if not path.is_file():
            self.skipTest("ignored V11 plan is not present in this checkout")
        plan = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            record["client_plan"]["client_plan_file_sha256"],
        )
        self.assertEqual(
            plan["client_plan_sha256"],
            record["client_plan"]["client_plan_sha256"],
        )
        self.assertEqual(plan["request_count"], record["client_plan"]["request_count"])


if __name__ == "__main__":
    unittest.main()
