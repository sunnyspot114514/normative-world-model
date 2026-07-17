from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path

from normative_world_model.phase3_comparison import (
    anti_collapse_checks,
    compact_binding,
    evaluation_binding,
    pair_binding,
    select_balanced_evaluation_records,
    select_comparison_pairs,
)

PROFILES = (
    "autonomy_preserving",
    "efficiency_tolerant",
    "harm_averse",
    "procedure_preserving",
)


def _record(
    scenario: str,
    profile: str,
    *,
    environment: str,
    condition: str,
    decision: str,
    split: str,
    profile_variant: int,
) -> dict:
    return {
        "record_id": (
            f"{scenario}-{condition}-{profile}-{profile_variant}"
        ),
        "scenario_id": scenario,
        "environment": environment,
        "split": split,
        "input_condition": condition,
        "profile_id": profile,
        "profile_surface_variant": profile_variant,
        "semantic_pair_group": f"semantic-{scenario}-{condition}-{profile_variant}",
        "surface_sham_group": f"surface-{scenario}-{condition}-{profile}",
        "target_text": json.dumps(
            {"normative_decision": decision},
            separators=(",", ":"),
        ),
    }


class PhaseThreeComparisonSelectionTests(unittest.TestCase):
    def test_pair_selection_is_deterministic_balanced_and_unique(self) -> None:
        records = []
        for environment in ("game", "organization"):
            for index in range(100):
                scenario = f"{environment}-{index:03d}"
                for condition in ("structured", "natural_language"):
                    for profile in PROFILES:
                        for variant in (0, 1):
                            records.append(
                                _record(
                                    scenario,
                                    profile,
                                    environment=environment,
                                    condition=condition,
                                    decision="allow",
                                    split="train",
                                    profile_variant=variant,
                                )
                            )
        first = select_comparison_pairs(records, seed=17, maximum=64)
        second = select_comparison_pairs(
            list(reversed(records)),
            seed=17,
            maximum=64,
        )
        self.assertEqual(pair_binding(first), pair_binding(second))
        self.assertEqual(
            len({pair.left["scenario_id"] for pair in first}),
            64,
        )
        counts = pair_binding(first)["bucket_counts"].values()
        self.assertLessEqual(max(counts) - min(counts), 1)
        compact = compact_binding(pair_binding(first))
        self.assertEqual(compact["count"], 64)
        self.assertEqual(compact["bucket_count"], 28)

    def test_evaluation_selection_covers_every_declared_bucket(self) -> None:
        records = []
        for environment in ("game", "organization"):
            for condition in ("structured", "natural_language"):
                for decision in ("allow", "reject", "escalate"):
                    for profile in PROFILES:
                        for index in range(3):
                            scenario = (
                                f"{environment}-{condition}-{decision}-{profile}-{index}"
                            )
                            records.append(
                                _record(
                                    scenario,
                                    profile,
                                    environment=environment,
                                    condition=condition,
                                    decision=decision,
                                    split="development",
                                    profile_variant=0,
                                )
                            )
        selected = select_balanced_evaluation_records(
            records,
            seed=23,
            per_bucket=2,
        )
        binding = evaluation_binding(selected)
        self.assertEqual(binding["count"], 96)
        self.assertEqual(binding["unique_scenario_count"], 96)
        self.assertEqual(set(binding["bucket_counts"].values()), {2})


class PhaseThreeComparisonContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        with (
            self.root / "configs/phase3_retained_arm_comparison.toml"
        ).open("rb") as handle:
            self.config = tomllib.load(handle)

    def test_estimands_and_governance_are_unambiguous(self) -> None:
        amendment = json.loads(
            (
                self.root / "configs/phase3_estimand_amendment.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            amendment["cells"],
            {
                "A->A": "joint_pair_success",
                "A->B": "event_normative_pair_success",
                "B->B": "joint_pair_success",
                "B->A": "event_normative_pair_success",
            },
        )
        self.assertFalse(amendment["practical_margins_changed"])
        self.assertEqual(
            amendment["confirmation_status"],
            "RESERVED_NOT_GENERATED",
        )
        self.assertFalse(
            self.config["governance"]["confirmation_generation_authorized"]
        )
        self.assertEqual(
            self.config["governance"]["h5_rollout_status"],
            "UNIDENTIFIED",
        )

    def test_config_binds_objective_inventory_and_selection(self) -> None:
        def digest(relative: str) -> str:
            return hashlib.sha256(
                (self.root / relative).read_bytes()
            ).hexdigest()

        architecture = self.config["architecture"]
        self.assertEqual(
            digest(architecture["slot_inventory"]),
            architecture["slot_inventory_sha256"],
        )
        self.assertEqual(
            digest(architecture["objective_implementation"]),
            architecture["objective_implementation_sha256"],
        )
        lock = json.loads(
            (
                self.root / "configs/phase3_retained_arm_selection_lock.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            lock["config_sha256"],
            digest("configs/phase3_retained_arm_comparison.toml"),
        )
        self.assertTrue(all(lock["checks"].values()))

    def test_budget_and_lambda_grid_are_frozen(self) -> None:
        self.assertEqual(
            self.config["lambda_selection"]["grid"],
            [0.0, 0.05, 0.1, 0.25, 0.5],
        )
        optimization = self.config["optimization"]
        self.assertEqual(optimization["joint_optimizer_steps"], 1024)
        self.assertEqual(
            optimization["factorized_factual_optimizer_steps"],
            2048,
        )
        self.assertEqual(
            optimization["factorized_normative_optimizer_steps"],
            1024,
        )
        self.assertEqual(
            self.config["budget"]["primary_match"],
            "scenario_presentation_and_supervised_slot_exposure",
        )

    def test_anti_collapse_bounds_are_inclusive(self) -> None:
        thresholds = self.config["anti_collapse_smoke"]
        metrics = {
            "loss_window_improvement_fraction": thresholds[
                "minimum_loss_window_improvement_fraction"
            ],
            "normative_accuracy": thresholds["minimum_normative_accuracy"],
            "maximum_predicted_decision_share": thresholds[
                "maximum_single_predicted_decision_share"
            ],
            "rows_with_nonzero_impact_fraction": thresholds[
                "minimum_rows_with_nonzero_impact_fraction"
            ],
            "nonempty_physical_delta_fraction": thresholds[
                "minimum_nonempty_physical_delta_fraction"
            ],
            "event_mae_improvement_over_zero": thresholds[
                "minimum_event_mae_improvement_over_zero"
            ],
            "strict_schema_coverage": thresholds[
                "require_strict_schema_coverage"
            ],
            "resource_status_pass": True,
        }
        self.assertTrue(all(anti_collapse_checks(metrics, thresholds).values()))
        metrics["normative_accuracy"] = 0.0
        self.assertFalse(
            anti_collapse_checks(metrics, thresholds)["normative_accuracy"]
        )


if __name__ == "__main__":
    unittest.main()
