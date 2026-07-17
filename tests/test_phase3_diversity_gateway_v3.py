from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PhaseThreeDiversityGatewayV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "configs/phase3_diversity_gateway_v3.toml").open(
            "rb"
        ) as handle:
            cls.gateway = tomllib.load(handle)
        cls.lock = json.loads(
            (
                ROOT
                / "configs/phase3_diversity_gateway_v3_selection_lock.json"
            ).read_text(encoding="utf-8")
        )
        cls.input_lock = json.loads(
            (
                ROOT
                / "configs/phase3_diversity_gateway_v3_input_lock.json"
            ).read_text(encoding="utf-8")
        )

    def test_historical_inputs_are_hash_bound_and_v2_remains_blocked(self) -> None:
        contract = self.gateway["base_contract"]
        for name in (
            "comparison_config",
            "comparison_selection_lock",
            "v2_config",
            "v2_selection_lock",
            "v2_result_lock",
        ):
            self.assertEqual(_sha256(ROOT / contract[name]), contract[f"{name}_sha256"])
        result = json.loads(
            (ROOT / contract["v2_result_lock"]).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_only_diversity_schedule_changes_from_v2(self) -> None:
        change = self.gateway["single_change_from_v2"]
        self.assertEqual(change["field"], "training.unique_pair_schedule")
        self.assertEqual(self.gateway["training"]["unique_pairs"], 1024)
        self.assertEqual(self.gateway["training"]["optimizer_steps"], 1024)
        self.assertEqual(self.gateway["training"]["epochs"], 1)
        self.assertEqual(self.gateway["unchanged_from_v2"]["consistency_lambda"], 0.0)

    def test_training_and_two_evaluations_are_bound_and_disjoint(self) -> None:
        self.assertEqual(
            _sha256(ROOT / "configs/phase3_diversity_gateway_v3.toml"),
            self.lock["gateway_config_sha256"],
        )
        self.assertTrue(all(self.lock["checks"].values()))
        training = self.lock["formal_training"]
        self.assertEqual((training["count"], training["unique_scenario_count"]), (1024, 1024))
        for name in ("gateway_evaluation", "fallback_reservation"):
            binding = self.lock[name]
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
        self.assertTrue(
            self.lock["checks"][
                "all_development_populations_are_scenario_disjoint"
            ]
        )

    def test_fallback_is_predeclared_but_not_authorized(self) -> None:
        fallback = self.gateway["fallback_v4"]
        self.assertEqual(
            fallback["status"], "design_sketch_only_not_an_authorized_fallback"
        )
        self.assertEqual(fallback["minimum_normative_recall_per_class"], 0.20)
        self.assertEqual(
            fallback["minimum_event_mae_improvement_over_training_slot_median"],
            0.02,
        )
        self.assertTrue(
            self.gateway["governance"][
                "no_training_authorized_by_this_design_file_alone"
            ]
        )
        self.assertEqual(
            self.gateway["governance"]["allowed_population_claim"],
            "precommitted_unopened_not_blind",
        )

    def test_repaired_gate_and_execution_inputs_are_frozen(self) -> None:
        gate = self.gateway["gate"]
        self.assertEqual(gate["fixed_training_probe_pairs"], 32)
        self.assertEqual(gate["minimum_normative_recall_per_class"], 0.20)
        self.assertEqual(
            gate["minimum_event_mae_improvement_over_training_constant"],
            0.02,
        )
        self.assertEqual(
            gate[
                "minimum_physical_field_f1_improvement_over_training_constant"
            ],
            0.02,
        )
        self.assertEqual(
            self.input_lock["status"],
            "FROZEN_BEFORE_GATEWAY_V3_REVISION_1",
        )
        local_only = set(
            self.input_lock["locally_regenerated_or_ignored_paths"]
        )
        for relative, expected in self.input_lock["bound_hashes"].items():
            path = ROOT / relative
            if relative in local_only and not path.is_file():
                continue
            self.assertEqual(_sha256(path), expected)
        self.assertFalse(
            self.input_lock["governance"]["v4_automatic_fallback_authorized"]
        )


if __name__ == "__main__":
    unittest.main()
