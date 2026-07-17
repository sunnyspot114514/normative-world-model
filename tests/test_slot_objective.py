from __future__ import annotations

import importlib.util
import json
import unittest
from dataclasses import fields

from normative_world_model.phase2_dataset import PHYSICAL_DELTA_SCHEMAS
from normative_world_model.simulation import EventRecord
from normative_world_model.slot_objective import (
    build_slot_head_bank,
    decode_slot_predictions,
    invariance_slot_losses,
    load_slot_inventory,
    slot_objective,
    supervised_slot_losses,
    symmetric_bernoulli_js,
    symmetric_js_from_logits,
)

HAS_TORCH = importlib.util.find_spec("torch") is not None


def _target(environment: str) -> dict:
    inventory = load_slot_inventory()
    target: dict = {
        "physical_delta": {},
        "event_record": {"impact_vector": {}},
        "normative_decision": "allow",
        "escalation_required": False,
        "rollout": [],
    }
    for slot in inventory.slots:
        if environment not in slot.environments:
            continue
        if slot.kind == "set":
            value = []
        elif slot.kind == "categorical":
            value = slot.values[0]
        else:
            value = 0.0
        container = target
        parts = slot.path.split(".")
        for part in parts[:-1]:
            container = container.setdefault(part, {})
        container[parts[-1]] = value
    return target


class SlotInventoryTests(unittest.TestCase):
    def test_inventory_covers_exact_public_one_step_schema(self) -> None:
        inventory = load_slot_inventory()
        for environment, schema in PHYSICAL_DELTA_SCHEMAS.items():
            actual = {
                slot.path.split(".", 1)[1]
                for slot in inventory.slots
                if slot.role == "physical"
                and environment in slot.environments
            }
            self.assertEqual(actual, set(schema))

        event_top_level = {
            slot.path.split(".")[1]
            for slot in inventory.slots
            if slot.role == "event"
        }
        self.assertEqual(
            event_top_level,
            {field.name for field in fields(EventRecord)},
        )
        impact_dimensions = {
            slot.path.rsplit(".", 1)[1]
            for slot in inventory.slots
            if slot.path.startswith("event_record.impact_vector.")
        }
        self.assertEqual(
            impact_dimensions,
            {
                "safety",
                "privacy",
                "autonomy",
                "trust",
                "efficiency",
                "fairness",
                "commitment",
            },
        )

    def test_inventory_covers_frozen_reachable_boundaries(self) -> None:
        inventory = load_slot_inventory()
        by_path = {slot.path: slot for slot in inventory.slots}
        self.assertIn(
            8,
            by_path["event_record.required_evidence_count"].values,
        )
        self.assertEqual(
            by_path["physical_delta.budget_remaining_delta"].values,
            (-3, -2, -1, 0),
        )
        self.assertEqual(
            [slot.path for slot in inventory.slots if slot.role == "normative"],
            ["normative_decision"],
        )


@unittest.skipUnless(HAS_TORCH, "model extras are not installed")
class SlotObjectiveTorchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import torch

        cls.torch = torch
        cls.inventory = load_slot_inventory()

    def test_js_is_symmetric_zero_only_for_equal_distributions(self) -> None:
        torch = self.torch
        left = torch.tensor([[4.0, -2.0]])
        same = symmetric_js_from_logits(left, left)
        right = torch.tensor([[-2.0, 4.0]])
        forward = symmetric_js_from_logits(left, right)
        reverse = symmetric_js_from_logits(right, left)
        self.assertAlmostEqual(float(same.item()), 0.0, places=7)
        self.assertGreater(float(forward.item()), 0.0)
        self.assertTrue(torch.allclose(forward, reverse))
        set_divergence = symmetric_bernoulli_js(left, right)
        self.assertGreater(float(set_divergence.item()), 0.0)

    def test_normative_logits_do_not_enter_factual_invariance(self) -> None:
        torch = self.torch
        head = build_slot_head_bank(8, self.inventory)
        hidden = torch.ones((1, 8))
        left = head(hidden)
        right = {
            path: (
                {key: value.clone() for key, value in output.items()}
                if isinstance(output, dict)
                else output.clone()
            )
            for path, output in left.items()
        }
        right["normative_decision"] = torch.tensor(
            [[-9.0, 9.0, -9.0]]
        )
        losses = invariance_slot_losses(
            left,
            right,
            ["game"],
            self.inventory,
        )
        self.assertAlmostEqual(float(losses["physical"].item()), 0.0, places=7)
        self.assertAlmostEqual(float(losses["event"].item()), 0.0, places=7)

    def test_full_slot_objective_is_finite_and_backpropagates(self) -> None:
        torch = self.torch
        head = build_slot_head_bank(16, self.inventory)
        left_hidden = torch.randn((2, 16), requires_grad=True)
        right_hidden = torch.randn((2, 16), requires_grad=True)
        left = head(left_hidden)
        right = head(right_hidden)
        targets = [_target("game"), _target("organization")]
        result = slot_objective(
            left,
            right,
            targets,
            targets,
            ["game", "organization"],
            self.inventory,
            consistency_lambda=0.1,
        )
        self.assertTrue(torch.isfinite(result.total))
        self.assertGreater(float(result.physical_supervised.item()), 0.0)
        self.assertGreater(float(result.event_supervised.item()), 0.0)
        self.assertGreater(float(result.normative_supervised.item()), 0.0)
        result.total.backward()
        self.assertIsNotNone(left_hidden.grad)
        self.assertIsNotNone(right_hidden.grad)
        self.assertGreater(float(left_hidden.grad.abs().sum().item()), 0.0)

    def test_decode_is_strict_and_escalation_is_derived(self) -> None:
        torch = self.torch
        head = build_slot_head_bank(4, self.inventory)
        predictions = head(torch.zeros((1, 4)))
        predictions["normative_decision"] = torch.tensor(
            [[-10.0, -10.0, 10.0]]
        )
        decoded = decode_slot_predictions(
            predictions,
            self.inventory,
            environment="game",
        )
        self.assertEqual(decoded["normative_decision"], "escalate")
        self.assertTrue(decoded["escalation_required"])
        self.assertEqual(decoded["rollout"], [])
        self.assertEqual(
            set(decoded["physical_delta"]),
            set(PHYSICAL_DELTA_SCHEMAS["game"]),
        )
        json.dumps(decoded, allow_nan=False)

    def test_supervision_rejects_out_of_support_targets(self) -> None:
        torch = self.torch
        head = build_slot_head_bank(4, self.inventory)
        predictions = head(torch.zeros((1, 4)))
        target = _target("game")
        target["physical_delta"]["health_level_delta"] = 99
        with self.assertRaisesRegex(ValueError, "outside frozen support"):
            supervised_slot_losses(
                predictions,
                [target],
                ["game"],
                self.inventory,
            )


if __name__ == "__main__":
    unittest.main()
