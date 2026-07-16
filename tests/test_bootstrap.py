from __future__ import annotations

import unittest

from normative_world_model.bootstrap import (
    cluster_bootstrap_means,
    paired_cluster_bootstrap_difference,
    scenario_cluster_bootstrap,
)


class ScenarioClusterBootstrapTests(unittest.TestCase):
    def test_bootstrap_is_deterministic_and_recomputes_envelope(self) -> None:
        scores = {
            "left": {"a": 1.0, "b": 0.0, "c": 0.5},
            "right": {"a": 0.0, "b": 1.0, "c": 0.5},
        }
        first = scenario_cluster_bootstrap(
            scores,
            samples=500,
            confidence_level=0.95,
            seed=17,
        )
        second = scenario_cluster_bootstrap(
            scores,
            samples=500,
            confidence_level=0.95,
            seed=17,
        )
        self.assertEqual(first, second)
        envelope = first["intervals"]["static_envelope"]
        self.assertTrue(envelope["recomputed_inside_each_replicate"])
        self.assertEqual(envelope["point"], 0.5)
        self.assertGreaterEqual(envelope["lower"], 0.5)

    def test_bootstrap_rejects_mismatched_cluster_sets(self) -> None:
        with self.assertRaises(ValueError):
            scenario_cluster_bootstrap(
                {
                    "left": {"a": 1.0},
                    "right": {"b": 1.0},
                },
                samples=10,
                confidence_level=0.95,
                seed=1,
            )

    def test_metric_and_paired_bootstraps_preserve_scenario_pairing(self) -> None:
        metrics = {
            "a": {"accuracy": 1.0, "leakage": 0.0},
            "b": {"accuracy": 0.0, "leakage": 1.0},
        }
        report = cluster_bootstrap_means(
            metrics,
            samples=200,
            confidence_level=0.95,
            seed=9,
        )
        self.assertEqual(report["intervals"]["accuracy"]["point"], 0.5)
        paired = paired_cluster_bootstrap_difference(
            {"a": 1.0, "b": 0.5},
            {"a": 0.5, "b": 0.5},
            samples=200,
            confidence_level=0.95,
            seed=9,
        )
        self.assertEqual(paired["interval"]["point"], 0.25)


if __name__ == "__main__":
    unittest.main()
