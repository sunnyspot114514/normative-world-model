from __future__ import annotations

import json
import unittest

from normative_world_model.model_output import parse_model_output
from normative_world_model.phase1_v3 import generate_v3_environment_families
from normative_world_model.phase2_dataset import (
    PHYSICAL_DELTA_SCHEMAS,
    build_phase2_examples,
    validate_physical_delta_schema,
)
from normative_world_model.transfer_matrix import build_transfer_manifest


class Phase2DatasetTests(unittest.TestCase):
    def test_each_family_has_paired_structured_and_natural_presentations(self) -> None:
        family = generate_v3_environment_families("game", 1, 701)[0]
        examples = build_phase2_examples([family])
        self.assertEqual(len(examples), 24)
        structured = [
            example
            for example in examples
            if example.input_condition == "structured"
        ]
        natural = [
            example
            for example in examples
            if example.input_condition == "natural_language"
        ]
        self.assertEqual(len(structured), 8)
        self.assertEqual(len(natural), 16)
        self.assertEqual(len({example.example_id for example in examples}), 24)
        for example in examples:
            self.assertNotIn('"impact_vector"', example.prompt)
            self.assertNotIn('"hard_violations"', example.prompt)
            result = parse_model_output(
                json.dumps(example.target),
                example.target,
            )
            self.assertTrue(result.ok, msg=result.error_detail)
            self.assertIn(
                json.dumps(
                    PHYSICAL_DELTA_SCHEMAS["game"],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                example.prompt,
            )

    def test_target_schema_metadata_is_value_free_and_environment_specific(
        self,
    ) -> None:
        families = [
            generate_v3_environment_families(environment, 1, 708)[0]
            for environment in ("game", "organization")
        ]
        examples = build_phase2_examples(families)
        for example in examples:
            expected_schema = json.dumps(
                PHYSICAL_DELTA_SCHEMAS[example.environment],
                sort_keys=True,
                separators=(",", ":"),
            )
            other_environment = (
                "organization"
                if example.environment == "game"
                else "game"
            )
            other_schema = json.dumps(
                PHYSICAL_DELTA_SCHEMAS[other_environment],
                sort_keys=True,
                separators=(",", ":"),
            )
            self.assertIn(expected_schema, example.prompt)
            self.assertNotIn(other_schema, example.prompt)
            for value in example.target["physical_delta"].values():
                if isinstance(value, int) and value != 0:
                    self.assertNotIn(
                        f'":{value},',
                        expected_schema,
                    )

    def test_public_physical_schema_rejects_missing_or_mistyped_fields(
        self,
    ) -> None:
        valid = {
            field: ([] if kind == "array[string]" else 0)
            for field, kind in PHYSICAL_DELTA_SCHEMAS["game"].items()
        }
        validate_physical_delta_schema("game", valid)
        missing = dict(valid)
        missing.pop("trust_level_delta")
        with self.assertRaises(ValueError):
            validate_physical_delta_schema("game", missing)
        mistyped = dict(valid)
        mistyped["trust_level_delta"] = True
        with self.assertRaises(ValueError):
            validate_physical_delta_schema("game", mistyped)

    def test_transfer_manifest_has_all_eight_cells_and_no_overlap(self) -> None:
        dimensions = {
            name: 0.2
            for name in (
                "safety",
                "privacy",
                "autonomy",
                "trust",
                "efficiency",
                "fairness",
                "commitment",
            )
        }
        evaluations = {
            "harm_averse": {"decision": "reject", "reason": "weighted_score"},
            "efficiency_tolerant": {
                "decision": "allow",
                "reason": "weighted_score",
            },
            "procedure_preserving": {
                "decision": "allow",
                "reason": "weighted_score",
            },
            "autonomy_preserving": {
                "decision": "reject",
                "reason": "weighted_score",
            },
        }
        rows = []
        for environment in ("game", "organization"):
            for split in ("train", "development"):
                rows.append(
                    {
                        "scenario_id": f"{environment}-{split}",
                        "environment": environment,
                        "split": split,
                        "primary": {
                            "policy_result": {"hard_violations": []},
                            "event_record": {"impact_vector": dimensions},
                            "evaluations": evaluations,
                        },
                    }
                )
        manifest = build_transfer_manifest(
            rows,
            minimum_dimension_sign_fraction=0.0,
        )
        self.assertEqual(manifest["status"], "READY")
        self.assertEqual(len(manifest["matrix"]), 8)
        self.assertTrue(
            all(
                cell["train_test_overlap_count"] == 0
                for cell in manifest["matrix"].values()
            )
        )
        self.assertEqual(
            manifest["support_population"],
            "destination_development_families",
        )
        self.assertTrue(
            all(
                report["scenario_count"] == 1
                for report in manifest["environment_support"].values()
            )
        )

    def test_transfer_support_cannot_be_borrowed_from_training_rows(self) -> None:
        evaluations = {
            "harm_averse": {"decision": "reject", "reason": "weighted_score"},
            "efficiency_tolerant": {
                "decision": "allow",
                "reason": "weighted_score",
            },
            "procedure_preserving": {
                "decision": "allow",
                "reason": "weighted_score",
            },
            "autonomy_preserving": {
                "decision": "reject",
                "reason": "weighted_score",
            },
        }
        rows = []
        for environment in ("game", "organization"):
            for split, sign in (("train", -0.2), ("development", 0.2)):
                rows.append(
                    {
                        "scenario_id": f"{environment}-{split}",
                        "environment": environment,
                        "split": split,
                        "primary": {
                            "policy_result": {"hard_violations": []},
                            "event_record": {
                                "impact_vector": {
                                    dimension: sign
                                    for dimension in (
                                        "safety",
                                        "privacy",
                                        "autonomy",
                                        "trust",
                                        "efficiency",
                                        "fairness",
                                        "commitment",
                                    )
                                }
                            },
                            "evaluations": evaluations,
                        },
                    }
                )
        manifest = build_transfer_manifest(
            rows,
            minimum_dimension_sign_fraction=0.25,
        )
        self.assertEqual(manifest["status"], "UNIDENTIFIED")
        self.assertTrue(
            all(
                report["scenario_count"] == 1
                and report["insufficient_dimension_sign_cells"]
                for report in manifest["environment_support"].values()
            )
        )


if __name__ == "__main__":
    unittest.main()
