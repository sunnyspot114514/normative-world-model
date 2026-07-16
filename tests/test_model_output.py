from __future__ import annotations

import copy
import json
import unittest

from normative_world_model.model_output import parse_model_output


def target() -> dict:
    return {
        "physical_delta": {
            "count_delta": 1,
            "flags_added": [],
        },
        "event_record": {
            "authorized": True,
            "stakeholder_count": 2,
            "uncertainty": 0.2,
            "impact_vector": {"safety": -0.25, "trust": 0.4},
        },
        "normative_decision": "escalate",
        "escalation_required": True,
        "rollout": [
            {
                "horizon": 1,
                "physical_delta": {
                    "count_delta": 1,
                    "flags_added": [],
                },
                "event_record": {
                    "authorized": True,
                    "stakeholder_count": 2,
                    "uncertainty": 0.2,
                    "impact_vector": {"safety": -0.25, "trust": 0.4},
                },
            }
        ],
    }


class ModelOutputParserTests(unittest.TestCase):
    def test_exact_json_and_single_json_fence_are_accepted(self) -> None:
        payload = target()
        plain = parse_model_output(json.dumps(payload), payload)
        fenced = parse_model_output(
            f"```json\n{json.dumps(payload)}\n```",
            payload,
        )
        self.assertTrue(plain.ok)
        self.assertTrue(fenced.ok)
        self.assertEqual(set(plain.output.rollout), {1})

    def test_continuous_numeric_spellings_are_accepted(self) -> None:
        payload = target()
        payload["event_record"]["uncertainty"] = ".20"
        payload["event_record"]["impact_vector"]["safety"] = "-.25"
        result = parse_model_output(json.dumps(payload), target())
        self.assertTrue(result.ok, msg=result.error_detail)

    def test_prose_missing_keys_and_discrete_type_coercion_fail(self) -> None:
        self.assertEqual(
            parse_model_output("Result: {}", target()).error_code,
            "invalid_json",
        )
        missing = target()
        missing.pop("event_record")
        self.assertEqual(
            parse_model_output(json.dumps(missing), target()).error_code,
            "top_level_keys",
        )
        wrong_type = target()
        wrong_type["physical_delta"]["count_delta"] = "1"
        self.assertEqual(
            parse_model_output(json.dumps(wrong_type), target()).error_code,
            "type_error",
        )

    def test_decision_and_rollout_contracts_are_strict(self) -> None:
        inconsistent = target()
        inconsistent["escalation_required"] = False
        self.assertEqual(
            parse_model_output(
                json.dumps(inconsistent),
                target(),
            ).error_code,
            "decision_consistency",
        )
        wrong_horizon = copy.deepcopy(target())
        wrong_horizon["rollout"][0]["horizon"] = 3
        self.assertEqual(
            parse_model_output(
                json.dumps(wrong_horizon),
                target(),
            ).error_code,
            "rollout_horizons",
        )


if __name__ == "__main__":
    unittest.main()
