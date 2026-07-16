from __future__ import annotations

import json
import unittest

from normative_world_model.model_arms import (
    build_factorized_factual_records,
    build_factorized_normative_records,
    build_joint_records,
    evaluator_visibility_failures,
    factorized_normative_input_text,
    recompute_factorized_policy_result,
)
from normative_world_model.phase1_v3 import generate_v3_environment_families
from normative_world_model.phase2_dataset import PHYSICAL_DELTA_SCHEMAS


class ModelArmDatasetTests(unittest.TestCase):
    def test_arm_record_counts_and_factorized_visibility(self) -> None:
        family = generate_v3_environment_families("game", 1, 801)
        joint = build_joint_records(family)
        factual = build_factorized_factual_records(family)
        normative = build_factorized_normative_records(family)
        self.assertEqual(len(joint), 24)
        self.assertEqual(len(factual), 3)
        self.assertEqual(len(normative), 16)
        self.assertEqual(evaluator_visibility_failures(factual), [])
        self.assertTrue(
            all(
                record["arm_views"]
                == ["joint_naive", "joint_consistency"]
                for record in joint
            )
        )
        expected_schema = json.dumps(
            PHYSICAL_DELTA_SCHEMAS["game"],
            sort_keys=True,
            separators=(",", ":"),
        )
        self.assertTrue(
            all(expected_schema in record["input_text"] for record in joint)
        )
        self.assertTrue(
            all(expected_schema in record["input_text"] for record in factual)
        )

    def test_consistency_groups_separate_semantic_and_surface_pairs(self) -> None:
        family = generate_v3_environment_families("organization", 1, 802)
        joint = build_joint_records(family)
        structured = [
            record
            for record in joint
            if record["input_condition"] == "structured"
        ]
        semantic_groups = {}
        surface_groups = {}
        for record in structured:
            semantic_groups.setdefault(
                record["semantic_pair_group"],
                set(),
            ).add(record["profile_id"])
            surface_groups.setdefault(
                record["surface_sham_group"],
                set(),
            ).add(record["profile_surface_variant"])
        self.assertTrue(all(len(values) == 4 for values in semantic_groups.values()))
        self.assertTrue(all(values == {0, 1} for values in surface_groups.values()))

    def test_one_step_views_remove_rollout_targets(self) -> None:
        family = generate_v3_environment_families("game", 1, 803)
        joint = build_joint_records(family, include_rollout=False)
        factual = build_factorized_factual_records(
            family,
            include_rollout=False,
        )
        self.assertEqual(json.loads(joint[0]["target_text"])["rollout"], [])
        self.assertEqual(json.loads(factual[0]["target_text"])["rollout"], [])
        self.assertTrue(joint[0]["target_text"].startswith('{"physical_delta":'))
        self.assertTrue(factual[0]["target_text"].startswith('{"physical_delta":'))
        self.assertEqual(
            joint[0]["factual_prefix_text"]
            + joint[0]["normative_suffix_text"],
            joint[0]["target_text"],
        )
        self.assertEqual(joint[0]["horizon_mode"], "one_step")
        self.assertEqual(factual[0]["horizon_mode"], "one_step")

    def test_factorized_policy_recomputation_matches_primary_oracle(self) -> None:
        family = generate_v3_environment_families("game", 1, 804)[0]
        recomputed = recompute_factorized_policy_result(
            family["model_input"],
            family["primary"]["event_record"],
        )
        self.assertEqual(
            recomputed,
            family["primary"]["policy_result"],
        )

    def test_factorized_normative_prompt_matches_exported_record(self) -> None:
        family = generate_v3_environment_families("organization", 1, 805)[0]
        records = build_factorized_normative_records([family])
        record = records[0]
        factual_context = {
            "event_record": family["primary"]["event_record"],
            "policy_result": family["primary"]["policy_result"],
        }
        self.assertEqual(
            record["input_text"],
            factorized_normative_input_text(
                factual_context,
                family["evaluator_twins"][record["profile_id"]],
                condition=record["input_condition"],
                profile_variant=record["profile_surface_variant"],
            ),
        )


if __name__ == "__main__":
    unittest.main()
