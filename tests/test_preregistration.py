from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


class PreregistrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).resolve().parents[1] / "configs" / "preregistration.toml"
        with path.open("rb") as handle:
            cls.document = tomllib.load(handle)

    def test_effect_margins_are_not_pilot_tunable(self) -> None:
        self.assertFalse(self.document["sample_size"]["pilot_may_change_practical_margins"])
        self.assertTrue(self.document["must_freeze_before_discovery"])

    def test_leakage_bands_leave_an_inconclusive_region(self) -> None:
        leakage = self.document["leakage"]
        self.assertGreater(
            leakage["stable_leakage_margin"],
            leakage["practical_invariance_upper_margin"],
        )

    def test_confirmation_replacement_is_forbidden(self) -> None:
        self.assertFalse(self.document["stopping"]["replace_failed_confirmation_scenarios"])
        self.assertFalse(self.document["stopping"]["allow_post_confirmation_threshold_changes"])

    def test_leakage_targets_and_structured_sham_are_explicit(self) -> None:
        leakage = self.document["leakage"]
        self.assertEqual(
            set(leakage["report_targets_separately"]),
            {"physical_delta", "event_record"},
        )
        self.assertIn("same_typed_values", leakage["structured_surface_sham"])

    def test_gate_c_is_environment_specific(self) -> None:
        language = self.document["phase1_v2_language"]
        self.assertTrue(language["gate_c_must_pass_each_environment"])
        self.assertTrue(language["pooled_gate_c_cannot_override_environment_failure"])

    def test_margin_and_generator_diversity_thresholds_are_frozen_fields(self) -> None:
        margins = self.document["normative_margin_strata"]
        diversity = self.document["generator_diversity"]
        self.assertLess(margins["boundary_maximum"], margins["intermediate_maximum"])
        self.assertEqual(diversity["maximum_reason_pair_signature_share"], 0.40)
        self.assertEqual(diversity["minimum_weighted_score_flip_fraction"], 0.20)
        self.assertEqual(
            diversity["minimum_dimension_sign_coverage_fraction"], 0.05
        )
        self.assertEqual(
            diversity["minimum_uncertainty_divergent_family_fraction"], 0.03
        )


if __name__ == "__main__":
    unittest.main()
