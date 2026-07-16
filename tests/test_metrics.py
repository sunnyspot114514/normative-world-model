from __future__ import annotations

import unittest

from normative_world_model.contracts import Prediction
from normative_world_model.metrics import score_counterfactual_pair


class PairMetricTests(unittest.TestCase):
    def test_joint_success_requires_correct_facts_and_normative_flip(self) -> None:
        target_a = Prediction(
            {"deleted": True}, {"safety": -0.2, "policy_events": ["policy-a"]}, "reject"
        )
        target_b = Prediction(
            {"deleted": True}, {"safety": -0.2, "policy_events": ["policy-a"]}, "allow"
        )

        score = score_counterfactual_pair(target_a, target_b, target_a, target_b)

        self.assertTrue(score.physical_consistent_and_correct)
        self.assertTrue(score.event_record_consistent_and_correct)
        self.assertTrue(score.normative_flip_required)
        self.assertTrue(score.normative_flip_observed)
        self.assertTrue(score.joint_pair_success)

    def test_consistently_wrong_facts_do_not_receive_consistency_credit(self) -> None:
        prediction_a = Prediction(
            {"deleted": False}, {"safety": 0.0}, "reject"
        )
        prediction_b = Prediction({"deleted": False}, {"safety": 0.0}, "allow")
        target_a = Prediction(
            {"deleted": True}, {"safety": -0.2}, "reject"
        )
        target_b = Prediction({"deleted": True}, {"safety": -0.2}, "allow")

        score = score_counterfactual_pair(
            prediction_a,
            prediction_b,
            target_a,
            target_b,
        )

        self.assertTrue(score.physical_invariant)
        self.assertFalse(score.physical_consistent_and_correct)
        self.assertTrue(score.event_record_invariant)
        self.assertFalse(score.event_record_consistent_and_correct)
        self.assertFalse(score.joint_pair_success)

    def test_event_record_error_fails_joint_success_even_when_physics_is_correct(self) -> None:
        prediction_a = Prediction({"deleted": True}, {"safety": 0.0}, "reject")
        prediction_b = Prediction({"deleted": True}, {"safety": 0.0}, "allow")
        target_a = Prediction({"deleted": True}, {"safety": -0.2}, "reject")
        target_b = Prediction({"deleted": True}, {"safety": -0.2}, "allow")

        score = score_counterfactual_pair(
            prediction_a, prediction_b, target_a, target_b
        )

        self.assertTrue(score.physical_consistent_and_correct)
        self.assertFalse(score.event_record_consistent_and_correct)
        self.assertFalse(score.joint_pair_success)


if __name__ == "__main__":
    unittest.main()
