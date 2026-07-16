from __future__ import annotations

import unittest

from normative_world_model.calibration import (
    load_calibration_document,
    run_calibration_cases,
)
from normative_world_model.normative_oracle import (
    NormativeInput,
    evaluate,
    load_profiles,
    validate_profiles,
)
from normative_world_model.ontology import (
    load_predicate_contract,
    validate_predicate_contract,
)
from normative_world_model.policy_oracle import PolicyOracleInput, evaluate_policy


class NormativeContractTests(unittest.TestCase):
    def test_both_environments_cover_the_same_predicates(self) -> None:
        contract = load_predicate_contract()
        self.assertEqual(validate_predicate_contract(contract), [])

    def test_profiles_are_complete_and_normalized(self) -> None:
        contract = load_predicate_contract()
        dimensions = set(contract["impact_dimensions"]["names"])
        self.assertEqual(validate_profiles(load_profiles(), dimensions), [])

    def test_veto_reason_uses_frozen_dimension_order(self) -> None:
        contract = load_predicate_contract()
        dimensions = tuple(contract["impact_dimensions"]["names"])
        profiles = load_profiles()
        for profile in profiles.values():
            self.assertEqual(tuple(profile.veto_floor), dimensions)
        profile = profiles["procedure_preserving"]
        policy_result = evaluate_policy(
            PolicyOracleInput(
                authorized=True,
                approval_required=False,
                approval_present=True,
                persistent_change=False,
                private_information_exposed=False,
                prohibited_private_disclosure=False,
                third_party_impact=False,
                consent_present=True,
                safety_impact=0.0,
                nonconsensual_harm_threshold=-0.45,
                policy_minimum_evidence_count=0,
                observed_evidence_count=1,
                conflicting_evidence=False,
            )
        )
        impacts = {dimension: 0.0 for dimension in dimensions}
        impacts["safety"] = -0.60
        impacts["privacy"] = -0.40
        result = evaluate(
            profile,
            NormativeInput(
                impacts=impacts,
                reversibility=1.0,
                policy_result=policy_result,
                policy_minimum_evidence_count=0,
                required_evidence_count=1,
                observed_evidence_count=1,
                conflicting_evidence=False,
            ),
        )
        self.assertEqual(result.reason, "veto:safety")

    def test_density_gate_profile_pairs_reference_known_profiles(self) -> None:
        contract = load_predicate_contract()
        profile_ids = set(load_profiles())
        for pair in contract["density_gates"]["target_profile_pairs"]:
            left, right = pair.split("|")
            self.assertIn(left, profile_ids)
            self.assertIn(right, profile_ids)
            self.assertNotEqual(left, right)

    def test_structured_input_excludes_all_post_transition_targets(self) -> None:
        structured = load_predicate_contract()["input_contract"]["structured"]
        allowed = set(structured["allowed"])
        forbidden = set(structured["forbidden"])
        self.assertFalse(allowed & forbidden)
        self.assertTrue(
            {
                "physical_delta",
                "event_record",
                "impact_vector",
                "reversibility",
                "uncertainty",
                "normative_decision",
            }.issubset(forbidden)
        )

    def test_diversity_and_support_gates_are_bounded(self) -> None:
        gates = load_predicate_contract()["density_gates"]
        self.assertLessEqual(gates["maximum_reason_pair_signature_share"], 0.40)
        self.assertGreaterEqual(gates["minimum_weighted_score_flip_fraction"], 0.20)
        self.assertGreaterEqual(
            gates["minimum_dimension_sign_coverage_fraction"], 0.05
        )

    def test_each_target_profile_pair_has_a_calibration_flip(self) -> None:
        contract = load_predicate_contract()
        document = load_calibration_document()
        for pair in contract["density_gates"]["target_profile_pairs"]:
            left, right = pair.split("|")
            has_flip = any(
                case["expected"]["decisions"][left]
                != case["expected"]["decisions"][right]
                for case in document["cases"]
                if not case["expected"]["hard_violations"]
            )
            self.assertTrue(has_flip, msg=f"no calibration flip for {pair}")

    def test_calibration_cases_are_end_to_end_reachable(self) -> None:
        result = run_calibration_cases()
        self.assertEqual(result["status"], "PASS", msg=result["failures"])
        self.assertEqual(result["temporary_fixture_allowlist"], [])

    def test_evidence_minimum_has_hit_and_near_miss(self) -> None:
        base = dict(
            authorized=True,
            approval_required=False,
            approval_present=True,
            persistent_change=False,
            private_information_exposed=False,
            prohibited_private_disclosure=False,
            third_party_impact=False,
            consent_present=True,
            safety_impact=0.0,
            nonconsensual_harm_threshold=-0.45,
            policy_minimum_evidence_count=2,
            conflicting_evidence=False,
            conflict_blocking=False,
        )
        miss = evaluate_policy(PolicyOracleInput(observed_evidence_count=1, **base))
        boundary = evaluate_policy(PolicyOracleInput(observed_evidence_count=2, **base))
        self.assertIn("below_policy_minimum_evidence", miss.hard_violations)
        self.assertNotIn("below_policy_minimum_evidence", boundary.hard_violations)

    def test_conflict_is_discretionary_unless_policy_explicitly_blocks_it(self) -> None:
        base = dict(
            authorized=True,
            approval_required=False,
            approval_present=True,
            persistent_change=False,
            private_information_exposed=False,
            prohibited_private_disclosure=False,
            third_party_impact=False,
            consent_present=True,
            safety_impact=0.0,
            nonconsensual_harm_threshold=-0.45,
            policy_minimum_evidence_count=1,
            observed_evidence_count=1,
            conflicting_evidence=True,
        )
        discretionary = evaluate_policy(PolicyOracleInput(conflict_blocking=False, **base))
        blocked = evaluate_policy(PolicyOracleInput(conflict_blocking=True, **base))
        self.assertEqual(discretionary.hard_violations, ())
        self.assertIn("policy_blocks_conflicting_evidence", blocked.hard_violations)

    def test_uncertainty_is_derived_from_evidence_state(self) -> None:
        dimensions = next(iter(load_profiles().values())).weights
        policy_result = evaluate_policy(
            PolicyOracleInput(
                authorized=True,
                approval_required=False,
                approval_present=True,
                persistent_change=False,
                private_information_exposed=False,
                prohibited_private_disclosure=False,
                third_party_impact=False,
                consent_present=True,
                safety_impact=0.0,
                nonconsensual_harm_threshold=-0.45,
                policy_minimum_evidence_count=1,
                observed_evidence_count=1,
                conflicting_evidence=True,
            )
        )
        item = NormativeInput(
            impacts={dimension: 0.0 for dimension in dimensions},
            reversibility=1.0,
            policy_result=policy_result,
            policy_minimum_evidence_count=1,
            required_evidence_count=4,
            observed_evidence_count=1,
            conflicting_evidence=True,
        )
        self.assertAlmostEqual(item.uncertainty, 0.8)
        self.assertTrue(item.minimum_evidence_present)
        self.assertFalse(item.evidence_complete_and_consistent)

    def test_weighted_results_report_margin_but_vetoes_do_not(self) -> None:
        profiles = load_profiles()
        policy_result = evaluate_policy(
            PolicyOracleInput(
                authorized=True,
                approval_required=False,
                approval_present=True,
                persistent_change=False,
                private_information_exposed=False,
                prohibited_private_disclosure=False,
                third_party_impact=False,
                consent_present=True,
                safety_impact=-0.35,
                nonconsensual_harm_threshold=-0.45,
                policy_minimum_evidence_count=0,
                observed_evidence_count=1,
                conflicting_evidence=False,
            )
        )
        impacts = {dimension: 0.0 for dimension in profiles["procedure_preserving"].weights}
        impacts.update({"safety": -0.35, "efficiency": 0.8})
        weighted_item = NormativeInput(
            impacts=impacts,
            reversibility=0.9,
            policy_result=policy_result,
            policy_minimum_evidence_count=0,
            required_evidence_count=1,
            observed_evidence_count=1,
            conflicting_evidence=False,
        )
        weighted = evaluate(profiles["procedure_preserving"], weighted_item)
        veto = evaluate(profiles["harm_averse"], weighted_item)
        self.assertIsNotNone(weighted.score_margin_to_boundary)
        self.assertIsNone(veto.score_margin_to_boundary)

    def test_score_band_boundaries_use_exact_decimal_semantics(self) -> None:
        profiles = load_profiles()
        profile = profiles["procedure_preserving"]
        policy_result = evaluate_policy(
            PolicyOracleInput(
                authorized=True,
                approval_required=False,
                approval_present=True,
                persistent_change=False,
                private_information_exposed=False,
                prohibited_private_disclosure=False,
                third_party_impact=False,
                consent_present=True,
                safety_impact=0.0,
                nonconsensual_harm_threshold=-0.45,
                policy_minimum_evidence_count=0,
                observed_evidence_count=1,
                conflicting_evidence=False,
            )
        )
        common = dict(
            reversibility=1.0,
            policy_result=policy_result,
            policy_minimum_evidence_count=0,
            required_evidence_count=1,
            observed_evidence_count=1,
            conflicting_evidence=False,
        )
        upper = evaluate(
            profile,
            NormativeInput(
                impacts={dimension: 0.10 for dimension in profile.weights},
                **common,
            ),
        )
        lower = evaluate(
            profile,
            NormativeInput(
                impacts={dimension: -0.08 for dimension in profile.weights},
                **common,
            ),
        )
        self.assertEqual((upper.decision, upper.score, upper.score_margin_to_boundary), ("allow", 0.1, 0.0))
        self.assertEqual((lower.decision, lower.score, lower.score_margin_to_boundary), ("reject", -0.08, 0.0))


if __name__ == "__main__":
    unittest.main()
