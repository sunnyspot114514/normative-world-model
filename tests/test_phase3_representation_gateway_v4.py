from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PhaseThreeRepresentationGatewayV4ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (ROOT / "configs/phase3_representation_gateway_v4.toml").open(
            "rb"
        ) as handle:
            cls.config = tomllib.load(handle)
        with (ROOT / "configs/phase3_diversity_gateway_v3.toml").open(
            "rb"
        ) as handle:
            cls.v3 = tomllib.load(handle)
        cls.selection = json.loads(
            (
                ROOT / "configs/phase3_representation_gateway_v4_selection_lock.json"
            ).read_text(encoding="utf-8")
        )
        cls.input_lock = json.loads(
            (
                ROOT / "configs/phase3_representation_gateway_v4_input_lock.json"
            ).read_text(encoding="utf-8")
        )

    def test_v3_is_bound_and_remains_blocked(self) -> None:
        contract = self.config["base_contract"]
        for name in (
            "comparison_config",
            "comparison_selection_lock",
            "v3_config",
            "v3_selection_lock",
            "v3_result_lock",
        ):
            self.assertEqual(_sha256(ROOT / contract[name]), contract[f"{name}_sha256"])
        result = json.loads(
            (ROOT / contract["v3_result_lock"]).read_text(encoding="utf-8")
        )
        self.assertEqual(result["status"], "BLOCKED")

    def test_population_is_exact_reserved_fallback(self) -> None:
        v3_selection = json.loads(
            (
                ROOT / "configs/phase3_diversity_gateway_v3_selection_lock.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            self.selection["v4_evaluation"], v3_selection["fallback_reservation"]
        )
        self.assertEqual(self.selection["formal_training"], v3_selection["formal_training"])
        self.assertTrue(all(self.selection["checks"].values()))

    def test_repaired_v3_numeric_gates_are_not_relaxed(self) -> None:
        keys = (
            "fixed_training_probe_pairs",
            "minimum_fixed_probe_loss_improvement_fraction",
            "minimum_normative_accuracy",
            "minimum_normative_recall_per_class",
            "maximum_single_predicted_decision_share",
            "minimum_rows_with_nonzero_impact_fraction",
            "minimum_nonempty_physical_delta_fraction",
            "minimum_event_mae_improvement_over_training_constant",
            "minimum_physical_field_f1_improvement_over_training_constant",
            "minimum_event_field_f1_improvement_over_training_constant",
            "require_strict_schema_coverage",
            "maximum_peak_memory_fraction",
        )
        for key in keys:
            self.assertEqual(self.config["gate"][key], self.v3["gate"][key])

    def test_training_only_transforms_and_future_mapping_are_explicit(self) -> None:
        self.assertTrue(
            all(
                item["count"] == 2048
                for item in self.selection["continuous_statistics"].values()
            )
        )
        self.assertAlmostEqual(
            self.selection["normative_class_weights"]["exposure_weighted_mean"],
            1.0,
        )
        mapping = self.config["future_formal_mapping"]
        self.assertEqual(
            mapping["factorized_normative_prompt_function"],
            "factorized_normative_input_text",
        )
        self.assertEqual(
            mapping["evaluation_factorized_normative_context"],
            "factorized_factual_prediction_plus_recomputed_policy_oracle",
        )
        self.assertEqual(
            mapping["status"], "contract_only_not_authorized_for_execution"
        )

    def test_v4_cannot_open_formal_or_confirmation(self) -> None:
        governance = self.config["governance"]
        self.assertFalse(governance["formal_arm_comparison_started"])
        self.assertFalse(governance["confirmation_generation_authorized"])
        self.assertEqual(
            governance["confirmation_status"], "RESERVED_NOT_GENERATED"
        )
        self.assertFalse(governance["server_rental_authorized"])

    def test_execution_lock_binds_code_data_and_marker_audit(self) -> None:
        self.assertEqual(
            self.input_lock["status"], "FROZEN_BEFORE_V4_EXECUTION"
        )
        for relative, expected in self.input_lock["bound_hashes"].items():
            self.assertEqual(_sha256(ROOT / relative), expected)
        self.assertEqual(
            self.input_lock["selection_lock_sha256"],
            _sha256(
                ROOT
                / "configs/phase3_representation_gateway_v4_selection_lock.json"
            ),
        )
        marker = self.input_lock["marker_audit"]
        self.assertEqual(marker["presentation_count"], 2096)
        self.assertEqual(marker["reserved_marker_occurrences_in_source"], 0)
        self.assertEqual(marker["truncated_presentations"], 0)
        self.assertLessEqual(marker["maximum_prompt_plus_suffix_tokens"], 1536)
        self.assertFalse(self.input_lock["formal_arm_comparison_started"])
        self.assertEqual(
            self.input_lock["confirmation_status"], "RESERVED_NOT_GENERATED"
        )


if __name__ == "__main__":
    unittest.main()
