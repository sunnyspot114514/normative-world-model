from __future__ import annotations

import unittest

from normative_world_model.comparators import (
    continuous_equal,
    event_records_equal,
    parse_finite_decimal,
)


class ComparatorContractTests(unittest.TestCase):
    def test_numeric_spellings_normalize_before_comparison(self) -> None:
        self.assertEqual(parse_finite_decimal("0.1"), parse_finite_decimal("0.10"))
        self.assertEqual(parse_finite_decimal(".1"), parse_finite_decimal(0.1))

    def test_tolerance_boundary_is_inclusive(self) -> None:
        self.assertTrue(continuous_equal("0.100", "0.105"))
        self.assertFalse(continuous_equal("0.100", "0.105001"))

    def test_non_finite_and_malformed_values_fail(self) -> None:
        for value in (float("nan"), float("inf"), "NaN", "one tenth"):
            with self.assertRaises(ValueError):
                parse_finite_decimal(value)

    def test_same_nested_comparator_applies_at_every_rollout_horizon(self) -> None:
        target = {
            "authorized": True,
            "stakeholder_count": 2,
            "uncertainty": 0.2,
            "impact_vector": {"safety": -0.25, "trust": 0.4},
        }
        for _horizon in (1, 3, 5):
            prediction = {
                "authorized": True,
                "stakeholder_count": 2,
                "uncertainty": ".204",
                "impact_vector": {"safety": "-0.246", "trust": "0.400"},
            }
            self.assertTrue(event_records_equal(prediction, target))
        wrong = {**target, "stakeholder_count": 3}
        self.assertFalse(event_records_equal(wrong, target))


if __name__ == "__main__":
    unittest.main()

