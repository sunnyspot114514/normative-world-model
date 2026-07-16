from __future__ import annotations

import copy
import unittest

from normative_world_model.baselines import (
    _fieldwise_factual_vote,
    _parsed_static_output,
    _scenario_joint_scores,
)
from normative_world_model.phase2_dataset import (
    PHYSICAL_DELTA_SCHEMAS,
    Phase2Example,
)

PROFILES = (
    "procedure_preserving",
    "harm_averse",
    "autonomy_preserving",
    "efficiency_tolerant",
)


def _example(profile_id: str, decision: str) -> Phase2Example:
    target = {
        "physical_delta": {
            "count_delta": 1,
            "persistent_flags_added": [],
        },
        "event_record": {
            "authorized": True,
            "uncertainty": 0.2,
            "impact_vector": {"safety": -0.25, "trust": 0.4},
        },
        "normative_decision": decision,
        "escalation_required": decision == "escalate",
        "rollout": [],
    }
    return Phase2Example(
        example_id=f"example-{profile_id}",
        scenario_id="scenario-1",
        environment="game",
        split="development",
        input_condition="structured",
        scenario_surface_variant=None,
        profile_surface_variant=0,
        profile_id=profile_id,
        prompt="prompt",
        target=target,
    )


class StaticBaselineEstimandTests(unittest.TestCase):
    def test_fieldwise_vote_uses_majority_and_continuous_median(self) -> None:
        neighbors = [
            {
                "physical_delta": {"count_delta": count, "flags": flags},
                "event_record": {
                    "authorized": authorized,
                    "uncertainty": uncertainty,
                    "impact_vector": {"safety": safety},
                },
            }
            for count, flags, authorized, uncertainty, safety in (
                (1, [], True, 0.2, -0.5),
                (1, [], True, 0.4, -0.25),
                (2, ["x"], False, 0.6, 0.0),
            )
        ]
        prediction = _fieldwise_factual_vote(neighbors)
        self.assertEqual(prediction["physical_delta"]["count_delta"], 1)
        self.assertEqual(prediction["physical_delta"]["flags"], [])
        self.assertTrue(prediction["event_record"]["authorized"])
        self.assertEqual(prediction["event_record"]["uncertainty"], 0.4)
        self.assertEqual(
            prediction["event_record"]["impact_vector"]["safety"],
            -0.25,
        )

    def test_static_baseline_uses_joint_pair_success_not_classification_only(
        self,
    ) -> None:
        decisions = {
            "procedure_preserving": "allow",
            "harm_averse": "reject",
            "autonomy_preserving": "reject",
            "efficiency_tolerant": "allow",
        }
        examples = [
            _example(profile_id, decisions[profile_id])
            for profile_id in PROFILES
        ]
        factual = {
            "physical_delta": examples[0].target["physical_delta"],
            "event_record": examples[0].target["event_record"],
        }
        perfect = _scenario_joint_scores(
            examples,
            [decisions[example.profile_id] for example in examples],
            {("scenario-1", None): factual},
        )
        self.assertEqual(
            perfect["scenario-1"]["joint_pair_success"],
            1.0,
        )

        wrong_factual = copy.deepcopy(factual)
        wrong_factual["physical_delta"]["count_delta"] = 0
        wrong = _scenario_joint_scores(
            examples,
            [decisions[example.profile_id] for example in examples],
            {("scenario-1", None): wrong_factual},
        )
        self.assertEqual(
            wrong["scenario-1"]["normative_pair_accuracy"],
            1.0,
        )
        self.assertEqual(
            wrong["scenario-1"]["joint_pair_success"],
            0.0,
        )

    def test_cross_environment_static_output_uses_target_schema_without_values(
        self,
    ) -> None:
        example = _example("harm_averse", "reject")
        example = Phase2Example(
            **{
                **example.__dict__,
                "environment": "organization",
                "target": {
                    **example.target,
                    "physical_delta": {
                        field: ([] if kind == "array[string]" else 1)
                        for field, kind in PHYSICAL_DELTA_SCHEMAS[
                            "organization"
                        ].items()
                    },
                },
            }
        )
        factual = {
            "physical_delta": {
                field: ([] if kind == "array[string]" else -2)
                for field, kind in PHYSICAL_DELTA_SCHEMAS["game"].items()
            },
            "event_record": example.target["event_record"],
        }
        parsed = _parsed_static_output(example, "reject", factual)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(
            parsed.one_step.physical_delta,
            {
                field: ([] if kind == "array[string]" else 0)
                for field, kind in PHYSICAL_DELTA_SCHEMAS[
                    "organization"
                ].items()
            },
        )


if __name__ == "__main__":
    unittest.main()
