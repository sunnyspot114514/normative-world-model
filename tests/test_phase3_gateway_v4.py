from __future__ import annotations

import json
import math
import unittest

from normative_world_model.local_pilot import ConsistencyPair
from normative_world_model.phase3_gateway_v4 import (
    DEFAULT_QUERY_MARKERS,
    build_continuous_statistics,
    build_normative_class_weights,
    build_role_query_head_bank,
    decode_slot_predictions_v4,
    gateway_v4_checks,
    normative_weighted_cross_entropy,
    role_query_batch,
)
from normative_world_model.slot_objective import load_slot_inventory


class _CharacterTokenizer:
    pad_token_id = 0

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        if add_special_tokens:
            raise AssertionError("the V4 contract forbids implicit special tokens")
        return {"input_ids": [ord(character) for character in text]}


def _target(decision: str, continuous_value: float) -> dict[str, object]:
    inventory = load_slot_inventory()
    value: dict[str, object] = {
        "physical_delta": {},
        "event_record": {"impact_vector": {}},
        "normative_decision": decision,
        "escalation_required": decision == "escalate",
        "rollout": [],
    }
    for slot in inventory.slots:
        if slot.role == "normative":
            continue
        item: object
        if slot.kind == "categorical":
            item = slot.values[0]
        elif slot.kind == "set":
            item = []
        else:
            item = min(max(continuous_value, float(slot.minimum)), float(slot.maximum))
        current = value
        components = slot.path.split(".")
        for component in components[:-1]:
            current = current.setdefault(component, {})  # type: ignore[assignment]
        current[components[-1]] = item
    return value


def _pair(left: dict[str, object], right: dict[str, object]) -> ConsistencyPair:
    return ConsistencyPair(
        "semantic_evaluator",
        {"target_text": json.dumps(left)},
        {"target_text": json.dumps(right)},
    )


class PhaseThreeGatewayV4Tests(unittest.TestCase):
    def test_query_positions_are_unique_present_and_not_truncated(self) -> None:
        batch = role_query_batch(
            _CharacterTokenizer(),
            ["source one", "source two"],
            maximum=256,
            device=None,
        )
        positions = batch["query_positions"].tolist()
        self.assertEqual(len(positions), 2)
        self.assertTrue(all(left < middle < right for left, middle, right in positions))
        self.assertTrue(
            all(
                int(batch["attention_mask"][row, position].item()) == 1
                for row, row_positions in enumerate(positions)
                for position in row_positions
            )
        )
        with self.assertRaisesRegex(ValueError, "reserved query marker"):
            role_query_batch(
                _CharacterTokenizer(),
                [f"source{DEFAULT_QUERY_MARKERS['event']}"],
                maximum=256,
                device=None,
            )
        with self.assertRaisesRegex(ValueError, "exceeds frozen maximum"):
            role_query_batch(
                _CharacterTokenizer(), ["source"], maximum=10, device=None
            )

    def test_training_statistics_use_population_ddof_zero_and_floor(self) -> None:
        inventory = load_slot_inventory()
        pairs = [
            _pair(_target("allow", -0.5), _target("reject", 0.5)),
            _pair(_target("escalate", -0.5), _target("allow", 0.5)),
        ]
        statistics = build_continuous_statistics(pairs, inventory)
        impact = statistics["event_record.impact_vector.autonomy"]
        self.assertEqual(impact["count"], 4)
        self.assertAlmostEqual(float(impact["mean"]), 0.0)
        self.assertAlmostEqual(float(impact["standard_deviation"]), 0.5)
        constant = build_continuous_statistics(
            [_pair(_target("allow", 0.0), _target("reject", 0.0))], inventory
        )
        self.assertEqual(
            constant["event_record.impact_vector.autonomy"]["standard_deviation"],
            1e-6,
        )

    def test_class_weights_have_exposure_weighted_mean_one(self) -> None:
        inventory = load_slot_inventory()
        pairs = [
            _pair(_target("allow", 0.0), _target("allow", 0.0)),
            _pair(_target("allow", 0.0), _target("reject", 0.0)),
            _pair(_target("allow", 0.0), _target("escalate", 0.0)),
        ]
        contract = build_normative_class_weights(pairs, inventory)
        self.assertAlmostEqual(contract["exposure_weighted_mean"], 1.0)
        self.assertGreater(
            contract["weights"]["escalate"], contract["weights"]["allow"]
        )

    def test_class_weight_does_not_cancel_for_batch_size_one(self) -> None:
        import torch

        logits = torch.zeros((1, 3))
        common = normative_weighted_cross_entropy(
            logits, torch.tensor([0]), torch.tensor([0.5, 1.0, 2.0])
        )
        rare = normative_weighted_cross_entropy(
            logits, torch.tensor([2]), torch.tensor([0.5, 1.0, 2.0])
        )
        self.assertAlmostEqual(float((rare / common).item()), 4.0)

    def test_role_trunks_prevent_cross_role_head_input(self) -> None:
        import torch

        inventory = load_slot_inventory()
        torch.manual_seed(7)
        heads = build_role_query_head_bank(8, 4, inventory)
        hidden = {role: torch.zeros((1, 8)) for role in ("physical", "event", "normative")}
        base = heads(hidden)
        changed = dict(hidden)
        changed["physical"] = torch.ones((1, 8))
        altered = heads(changed)
        for slot in inventory.slots:
            if slot.role == "physical":
                continue
            self.assertTrue(torch.equal(base[slot.path], altered[slot.path]))

    def test_continuous_decode_uses_training_statistics_and_clips(self) -> None:
        import torch

        inventory = load_slot_inventory()
        statistics = {
            slot.path: {"count": 1, "mean": 0.25, "standard_deviation": 0.5}
            for slot in inventory.slots
            if slot.kind == "continuous"
        }
        predictions = {}
        for slot in inventory.slots:
            if slot.kind == "continuous":
                predictions[slot.path] = torch.tensor([10.0])
            else:
                predictions[slot.path] = torch.zeros((1, len(slot.values)))
        decoded = decode_slot_predictions_v4(
            predictions, inventory, statistics, environment="game"
        )
        self.assertEqual(decoded["event_record"]["impact_vector"]["autonomy"], 1.0)
        self.assertFalse(decoded["escalation_required"])

    def test_v4_gate_keeps_repaired_constant_baselines_blocking(self) -> None:
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
            "fixed_probe_loss_improvement_fraction": 0.5,
            "normative_accuracy": 0.5,
            "normative_recall_by_class": {"allow": 0.5, "reject": 0.5, "escalate": 0.5},
            "maximum_predicted_decision_share": 0.5,
            "rows_with_nonzero_impact_fraction": 1.0,
            "nonempty_physical_delta_fraction": 1.0,
            "event_mae_improvement_over_training_constant": 0.01,
            "physical_field_f1_improvement_over_training_constant": 0.03,
            "event_field_f1_improvement_over_training_constant": -0.01,
            "strict_schema_coverage": 1.0,
            "resource_status_pass": True,
            "deterministic_training_contract": True,
        }
        checks = gateway_v4_checks(metrics, thresholds)
        self.assertFalse(checks["event_mae_beats_training_constant"])
        self.assertFalse(checks["event_f1_beats_training_constant"])
        self.assertTrue(checks["deterministic_training_contract"])
        self.assertFalse(math.prod(checks.values()))


if __name__ == "__main__":
    unittest.main()
