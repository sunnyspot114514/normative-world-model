from __future__ import annotations

import json
import unittest

from normative_world_model.local_pilot import ConsistencyPair
from normative_world_model.phase3_gateway import (
    build_training_constant_baselines,
    gateway_v3_checks,
    normative_recall_by_class,
)
from normative_world_model.slot_objective import load_slot_inventory


class PhaseThreeGatewayTests(unittest.TestCase):
    def test_training_constants_use_only_training_targets(self) -> None:
        inventory = load_slot_inventory()
        targets = {}
        pairs = []
        for environment in ("game", "organization"):
            target = {
                "physical_delta": {
                    slot.path.split(".")[-1]: (
                        [] if slot.kind == "set" else slot.values[0]
                    )
                    for slot in inventory.slots
                    if slot.role == "physical"
                    and environment in slot.environments
                },
                "event_record": {},
                "normative_decision": "allow",
                "escalation_required": False,
                "rollout": [],
            }
            for slot in inventory.slots:
                if slot.role != "event":
                    continue
                value = (
                    slot.values[0]
                    if slot.kind == "categorical"
                    else []
                    if slot.kind == "set"
                    else slot.minimum
                )
                current = target
                parts = slot.path.split(".")
                for part in parts[:-1]:
                    current = current.setdefault(part, {})
                current[parts[-1]] = value
            record = {
                "environment": environment,
                "target_text": json.dumps(target),
            }
            targets[environment] = target
            pairs.append(ConsistencyPair("surface_sham", record, record))
        baseline = build_training_constant_baselines(pairs, inventory)
        for environment, target in targets.items():
            self.assertEqual(
                baseline[environment]["physical_delta"],
                target["physical_delta"],
            )
            self.assertEqual(
                baseline[environment]["event_record"],
                target["event_record"],
            )

    def test_zero_recall_for_one_class_is_reported(self) -> None:
        rows = [
            {"target_decision": target, "predicted_decision": predicted}
            for target, predicted in (
                ("allow", "allow"),
                ("reject", "reject"),
                ("escalate", "reject"),
            )
        ]
        self.assertEqual(
            normative_recall_by_class(rows),
            {"allow": 1.0, "reject": 1.0, "escalate": 0.0},
        )

    def test_constant_false_pass_is_blocked(self) -> None:
        thresholds = {
            "minimum_fixed_probe_loss_improvement_fraction": 0.20,
            "minimum_normative_accuracy": 0.40,
            "minimum_normative_recall_per_class": 0.20,
            "maximum_single_predicted_decision_share": 0.85,
            "minimum_rows_with_nonzero_impact_fraction": 0.50,
            "minimum_nonempty_physical_delta_fraction": 0.50,
            "minimum_event_mae_improvement_over_training_constant": 0.02,
            "minimum_physical_field_f1_improvement_over_training_constant": 0.02,
            "minimum_event_field_f1_improvement_over_training_constant": 0.02,
            "require_strict_schema_coverage": 1.0,
        }
        metrics = {
            "fixed_probe_loss_improvement_fraction": 0.50,
            "normative_accuracy": 2 / 3,
            "normative_recall_by_class": {
                "allow": 1.0,
                "reject": 1.0,
                "escalate": 0.0,
            },
            "maximum_predicted_decision_share": 2 / 3,
            "rows_with_nonzero_impact_fraction": 1.0,
            "nonempty_physical_delta_fraction": 1.0,
            "event_mae_improvement_over_training_constant": 0.0,
            "physical_field_f1_improvement_over_training_constant": 0.0,
            "event_field_f1_improvement_over_training_constant": 0.0,
            "strict_schema_coverage": 1.0,
            "resource_status_pass": True,
            "deterministic_prefix_replay": True,
        }
        checks = gateway_v3_checks(metrics, thresholds)
        self.assertFalse(checks["normative_recall_per_class"])
        self.assertFalse(checks["event_mae_beats_training_constant"])
        self.assertFalse(checks["physical_f1_beats_training_constant"])
        self.assertFalse(checks["event_f1_beats_training_constant"])


if __name__ == "__main__":
    unittest.main()
