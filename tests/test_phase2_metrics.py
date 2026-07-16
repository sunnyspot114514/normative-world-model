from __future__ import annotations

import copy
import json
import unittest

from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_metrics import (
    evaluate_anti_gaming_gate,
    evaluate_rollout_gate,
    information_diagnostics,
    normative_stratum,
    oracle_fixture_metrics_are_perfect,
    score_evaluator_pair,
    score_factual_twin,
    score_fields,
    score_leakage,
    score_one_step,
    score_rollout,
)


def output_target(decision: str = "reject") -> dict:
    return {
        "physical_delta": {
            "count_delta": 1,
            "flags_added": [],
        },
        "event_record": {
            "authorized": True,
            "uncertainty": 0.2,
            "impact_vector": {"safety": -0.25, "trust": 0.4},
        },
        "normative_decision": decision,
        "escalation_required": decision == "escalate",
        "rollout": [
            {
                "horizon": 1,
                "physical_delta": {
                    "count_delta": 1,
                    "flags_added": [],
                },
                "event_record": {
                    "authorized": True,
                    "uncertainty": 0.2,
                    "impact_vector": {"safety": -0.25, "trust": 0.4},
                },
            },
            {
                "horizon": 3,
                "physical_delta": {
                    "count_delta": -1,
                    "flags_added": ["done"],
                },
                "event_record": {
                    "authorized": True,
                    "uncertainty": 0.4,
                    "impact_vector": {"safety": 0.1, "trust": 0.2},
                },
            },
        ],
    }


def parsed(target: dict):
    result = parse_model_output(json.dumps(target), target)
    assert result.ok
    return result.output


class Phase2MetricTests(unittest.TestCase):
    def test_oracle_fixture_gate_requires_exactly_one(self) -> None:
        self.assertTrue(oracle_fixture_metrics_are_perfect([1.0, 1, True]))
        self.assertFalse(
            oracle_fixture_metrics_are_perfect([1.0, 0.01, 1.0])
        )

    def test_exact_output_receives_full_one_step_and_rollout_credit(self) -> None:
        target = output_target()
        prediction = parsed(target)
        one_step = score_one_step(prediction, target)
        rollout = score_rollout(prediction, target)
        self.assertTrue(one_step.all_correct)
        self.assertEqual(one_step.physical.f1, 1.0)
        self.assertTrue(rollout[1]["joint_exact_match"])
        self.assertTrue(rollout[3]["joint_exact_match"])

    def test_continuous_tolerance_is_shared_with_field_scoring(self) -> None:
        score = score_fields(
            {"uncertainty": ".204"},
            {"uncertainty": 0.2},
            component="event_record",
        )
        self.assertEqual(score.f1, 1.0)

    def test_evaluator_pair_requires_correct_facts_and_correct_flip(self) -> None:
        left = output_target("reject")
        right = output_target("allow")
        score = score_evaluator_pair(
            parsed(left),
            parsed(right),
            left,
            right,
        )
        self.assertTrue(score.normative_flip_recalled)
        self.assertTrue(score.joint_pair_success)

        wrong = copy.deepcopy(left)
        wrong["physical_delta"]["count_delta"] = 0
        wrong_prediction = parse_model_output(
            json.dumps(wrong),
            left,
        ).output
        failed = score_evaluator_pair(
            wrong_prediction,
            parsed(right),
            left,
            right,
        )
        self.assertFalse(failed.physical_consistent_and_correct)
        self.assertFalse(failed.joint_pair_success)

    def test_parse_failure_is_not_invariance_credit(self) -> None:
        target = output_target()
        score = score_evaluator_pair(None, None, target, target)
        leakage = score_leakage(None, None, None, None)
        self.assertFalse(score.parse_complete)
        self.assertFalse(score.physical_invariant)
        self.assertEqual(leakage.semantic_physical_divergence, 1.0)
        self.assertEqual(leakage.surface_physical_divergence, 1.0)
        self.assertEqual(leakage.physical_delta_leak, 0.0)

    def test_factual_twin_change_metrics_penalize_suppression(self) -> None:
        base = output_target()
        twin = copy.deepcopy(base)
        twin["physical_delta"]["count_delta"] = -1
        twin["event_record"]["impact_vector"]["trust"] = -0.4
        exact = score_factual_twin(
            parsed(base),
            parsed(twin),
            base,
            twin,
        )
        suppressed = score_factual_twin(
            parsed(base),
            parsed(base),
            base,
            twin,
        )
        self.assertEqual(exact.changed_field_macro_f1, 1.0)
        self.assertTrue(exact.physical_twin_sensitive)
        self.assertEqual(suppressed.changed_field_macro_f1, 0.0)
        self.assertFalse(suppressed.physical_twin_sensitive)

    def test_information_and_rollout_gate_report_missing_h5(self) -> None:
        target = output_target()
        prediction = parsed(target)
        diagnostics = information_diagnostics([prediction, None])
        self.assertEqual(diagnostics["parse_coverage"], 0.5)
        self.assertEqual(
            evaluate_rollout_gate({1: 1.0, 3: 0.9})["status"],
            "UNIDENTIFIED",
        )

    def test_normative_strata_and_anti_gaming_gate_are_explicit(self) -> None:
        self.assertEqual(
            normative_stratum(
                {
                    "reason": "weighted_score",
                    "score_margin_to_boundary": 0.02,
                }
            ),
            "score_boundary",
        )
        self.assertEqual(
            normative_stratum(
                {
                    "reason": "veto:safety",
                    "score_margin_to_boundary": None,
                }
            ),
            "dimension_veto",
        )
        target = output_target()
        info = information_diagnostics([parsed(target)])
        gate = evaluate_anti_gaming_gate(
            candidate_information=info,
            baseline_information=info,
            gold_information=info,
            candidate_changed_field_f1=1.0,
            baseline_changed_field_f1=1.0,
            candidate_physical_twin_sensitivity=1.0,
            baseline_physical_twin_sensitivity=1.0,
            candidate_normative_pair_accuracy=1.0,
            baseline_normative_pair_accuracy=1.0,
        )
        self.assertEqual(gate["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
