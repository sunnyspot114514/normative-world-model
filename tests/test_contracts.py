from __future__ import annotations

import unittest

from normative_world_model.contracts import EvaluatorContext, Prediction, WorldState


class ContractTests(unittest.TestCase):
    def test_actor_and_evaluator_values_have_distinct_contracts(self) -> None:
        state = WorldState(
            scenario_id="scenario-1",
            observable_facts={"file_exists": True},
            actor_values={"privacy": 0.8},
        )
        evaluator = EvaluatorContext(
            profile_id="audit-profile",
            evaluator_values={"safety": 1.0},
        )

        self.assertIn("privacy", state.actor_values)
        self.assertNotIn("safety", state.actor_values)
        self.assertIn("safety", evaluator.evaluator_values)

    def test_prediction_rejects_invalid_confidence(self) -> None:
        with self.assertRaises(ValueError):
            Prediction({}, {}, "escalate", confidence=1.1)


if __name__ == "__main__":
    unittest.main()
