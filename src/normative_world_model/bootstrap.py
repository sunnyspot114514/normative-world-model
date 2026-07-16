"""Scenario-cluster bootstrap helpers for discovery-phase evaluation."""

from __future__ import annotations

import random
from typing import Any


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot take a quantile of an empty sample")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def scenario_cluster_bootstrap(
    scores_by_arm: dict[str, dict[str, float]],
    *,
    samples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap scenario scores and recompute the arm envelope per replicate."""

    if samples <= 0:
        raise ValueError("bootstrap sample count must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must lie strictly between zero and one")
    if not scores_by_arm:
        raise ValueError("at least one arm is required")
    cluster_sets = {frozenset(scores) for scores in scores_by_arm.values()}
    if len(cluster_sets) != 1:
        raise ValueError("every arm must contain the same scenario clusters")
    clusters = sorted(next(iter(cluster_sets)))
    if not clusters:
        raise ValueError("at least one scenario cluster is required")

    point = {
        arm: sum(scores.values()) / len(scores)
        for arm, scores in scores_by_arm.items()
    }
    draws = {arm: [] for arm in scores_by_arm}
    envelope_draws: list[float] = []
    rng = random.Random(seed)
    for _ in range(samples):
        sampled = [rng.choice(clusters) for _ in clusters]
        replicate = {
            arm: sum(scores[cluster] for cluster in sampled) / len(sampled)
            for arm, scores in scores_by_arm.items()
        }
        for arm, value in replicate.items():
            draws[arm].append(value)
        envelope_draws.append(max(replicate.values()))

    alpha = 1.0 - confidence_level
    intervals = {
        arm: {
            "point": point[arm],
            "lower": _quantile(values, alpha / 2),
            "upper": _quantile(values, 1.0 - alpha / 2),
        }
        for arm, values in draws.items()
    }
    intervals["static_envelope"] = {
        "point": max(point.values()),
        "lower": _quantile(envelope_draws, alpha / 2),
        "upper": _quantile(envelope_draws, 1.0 - alpha / 2),
        "recomputed_inside_each_replicate": True,
    }
    return {
        "cluster_count": len(clusters),
        "samples": samples,
        "confidence_level": confidence_level,
        "seed": seed,
        "intervals": intervals,
    }


def cluster_bootstrap_means(
    metrics_by_scenario: dict[str, dict[str, float]],
    *,
    samples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap several scenario-macro means with one shared cluster draw."""

    if not metrics_by_scenario:
        raise ValueError("at least one scenario is required")
    if samples <= 0:
        raise ValueError("bootstrap sample count must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must lie strictly between zero and one")
    names = sorted(
        {
            name
            for metrics in metrics_by_scenario.values()
            for name in metrics
        }
    )
    if any(
        set(metrics) != set(names)
        for metrics in metrics_by_scenario.values()
    ):
        raise ValueError("every scenario must contain the same metric names")
    scenarios = sorted(metrics_by_scenario)
    points = {
        name: sum(
            metrics_by_scenario[scenario][name]
            for scenario in scenarios
        )
        / len(scenarios)
        for name in names
    }
    draws = {name: [] for name in names}
    rng = random.Random(seed)
    for _ in range(samples):
        sampled = [rng.choice(scenarios) for _ in scenarios]
        for name in names:
            draws[name].append(
                sum(
                    metrics_by_scenario[scenario][name]
                    for scenario in sampled
                )
                / len(sampled)
            )
    alpha = 1.0 - confidence_level
    return {
        "cluster_count": len(scenarios),
        "samples": samples,
        "confidence_level": confidence_level,
        "seed": seed,
        "intervals": {
            name: {
                "point": points[name],
                "lower": _quantile(values, alpha / 2),
                "upper": _quantile(values, 1.0 - alpha / 2),
            }
            for name, values in draws.items()
        },
    }


def paired_cluster_bootstrap_difference(
    left_by_scenario: dict[str, float],
    right_by_scenario: dict[str, float],
    *,
    samples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap a paired left-minus-right scenario-macro difference."""

    if set(left_by_scenario) != set(right_by_scenario):
        raise ValueError("paired arms must contain the same scenario clusters")
    metrics = {
        scenario: {
            "difference": (
                left_by_scenario[scenario] - right_by_scenario[scenario]
            )
        }
        for scenario in left_by_scenario
    }
    report = cluster_bootstrap_means(
        metrics,
        samples=samples,
        confidence_level=confidence_level,
        seed=seed,
    )
    return {
        **report,
        "estimand": "left_minus_right",
        "interval": report["intervals"]["difference"],
    }
