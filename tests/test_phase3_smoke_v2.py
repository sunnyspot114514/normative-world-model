from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PhaseThreeSmokeV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "configs/phase3_anti_collapse_smoke_v2.toml").open(
            "rb"
        ) as handle:
            cls.v2 = tomllib.load(handle)
        with (ROOT / "configs/phase3_retained_arm_comparison.toml").open(
            "rb"
        ) as handle:
            cls.base = tomllib.load(handle)
        cls.selection = json.loads(
            (
                ROOT
                / "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"
            ).read_text(encoding="utf-8")
        )

    def test_redesign_changes_only_the_declared_schedule_field(self) -> None:
        self.assertEqual(
            self.v2["single_change"],
            {
                "field": "optimization.smoke_optimizer_steps",
                "v1_value": 256,
                "v2_value": 1024,
                "rationale": (
                    "match_the_already_frozen_formal_joint_arm_budget_after_"
                    "v1_failed_to_separate_training_labels"
                ),
            },
        )
        self.assertEqual(self.base["optimization"]["smoke_optimizer_steps"], 256)
        self.assertEqual(self.base["optimization"]["joint_optimizer_steps"], 1024)
        self.assertEqual(self.v2["unchanged"]["training_pair_count"], 128)
        self.assertEqual(self.v2["unchanged"]["consistency_lambda"], 0.0)

    def test_base_contract_and_blocked_v1_are_hash_bound(self) -> None:
        contract = self.v2["base_contract"]
        for name in (
            "comparison_config",
            "selection_lock",
            "v1_input_lock",
            "v1_result_lock",
            "v1_runner",
        ):
            path = ROOT / contract[name]
            self.assertEqual(_sha256(path), contract[f"{name}_sha256"])
        result_lock = json.loads(
            (ROOT / contract["v1_result_lock"]).read_text(encoding="utf-8")
        )
        self.assertEqual(result_lock["status"], "BLOCKED")
        self.assertFalse(
            result_lock["governance"]["formal_arm_comparison_started"]
        )

    def test_v2_selection_is_balanced_and_declares_all_exclusions(self) -> None:
        binding = self.selection["v2_evaluation"]
        self.assertEqual(
            (
                binding["count"],
                binding["unique_scenario_count"],
                binding["bucket_count"],
                binding["minimum_bucket_count"],
                binding["maximum_bucket_count"],
            ),
            (48, 48, 48, 1, 1),
        )
        self.assertEqual(
            self.selection["excluded"],
            {"schema_gate": 16, "v1_smoke": 48, "reserved_formal": 96},
        )
        self.assertTrue(
            self.selection["checks"][
                "v2_is_disjoint_from_all_prior_development"
            ]
        )
        self.assertEqual(
            self.v2["governance"]["confirmation_status"],
            "RESERVED_NOT_GENERATED",
        )


if __name__ == "__main__":
    unittest.main()
