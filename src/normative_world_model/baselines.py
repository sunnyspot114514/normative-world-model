"""Cheap Phase-2 discovery baselines over a generated smoke corpus."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .audits import (
    _centroid_scores,
    _dense_rows,
    _fit_depth_tree,
    _flatten_features,
    _tree_predict,
)
from .bootstrap import scenario_cluster_bootstrap


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _classification_summary(
    actual: list[str],
    predicted: list[str],
) -> dict[str, Any]:
    labels = sorted(set(actual) | set(predicted))
    recall = {}
    for label in labels:
        indices = [index for index, value in enumerate(actual) if value == label]
        recall[label] = (
            sum(predicted[index] == label for index in indices) / len(indices)
            if indices
            else None
        )
    valid_recall = [value for value in recall.values() if value is not None]
    return {
        "accuracy": sum(
            left == right for left, right in zip(actual, predicted, strict=True)
        )
        / max(len(actual), 1),
        "balanced_accuracy": sum(valid_recall) / max(len(valid_recall), 1),
        "recall_by_class": recall,
        "support_by_class": dict(Counter(actual)),
    }


def _example_rows(
    families: list[dict[str, Any]],
    split: str,
) -> list[dict[str, Any]]:
    rows = []
    for family in families:
        if family["split"] != split:
            continue
        base_features = _flatten_features(family["model_input"])
        for profile_id, target in family["primary"]["evaluations"].items():
            features = dict(base_features)
            features[f"profile={profile_id}"] = 1.0
            rows.append(
                {
                    "scenario_id": family["scenario_id"],
                    "profile_id": profile_id,
                    "features": features,
                    "text": (
                        family["surface_twins"][0]["natural_language"]
                        + " Evaluator contract: "
                        + family["evaluator_twins"][profile_id][
                            "natural_language_profile_shams"
                        ][0]
                    ),
                    "target": target["decision"],
                }
            )
    return rows


def _majority_predictions(
    train: list[dict[str, Any]],
    development: list[dict[str, Any]],
) -> list[str]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in train:
        counts[row["profile_id"]][row["target"]] += 1
    return [
        counts[row["profile_id"]].most_common(1)[0][0]
        for row in development
    ]


def _structured_tree_predictions(
    train: list[dict[str, Any]],
    development: list[dict[str, Any]],
) -> list[str]:
    names = sorted(
        {
            name
            for row in train
            for name in row["features"]
        }
    )
    train_x = _dense_rows([row["features"] for row in train], names)
    development_x = _dense_rows(
        [row["features"] for row in development],
        names,
    )
    tree = _fit_depth_tree(
        train_x,
        [row["target"] for row in train],
        list(range(len(train_x))),
        3,
        True,
    )
    return [_tree_predict(tree, row) for row in development_x]


def _tfidf_predictions(
    train: list[dict[str, Any]],
    development: list[dict[str, Any]],
    mode: str,
) -> list[str]:
    labels, scores = _centroid_scores(
        [(row["text"], row["target"]) for row in train],
        [(row["text"], row["target"]) for row in development],
        mode,
    )
    return [
        max(labels, key=lambda label: (scores[label][index], label))
        for index in range(len(development))
    ]


def _scenario_scores(
    rows: list[dict[str, Any]],
    predictions: list[str],
) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row, predicted in zip(rows, predictions, strict=True):
        values[row["scenario_id"]].append(float(predicted == row["target"]))
    return {
        scenario_id: sum(scores) / len(scores)
        for scenario_id, scores in values.items()
    }


def run_smoke_baselines(
    data_dir: Path,
    *,
    bootstrap_samples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 20260916,
) -> dict[str, Any]:
    environments: dict[str, Any] = {}
    for offset, environment in enumerate(("game", "organization")):
        families = _load_jsonl(data_dir / f"{environment}.jsonl")
        train = _example_rows(families, "train")
        development = _example_rows(families, "development")
        actual = [row["target"] for row in development]
        predictions = {
            "profile_majority": _majority_predictions(train, development),
            "structured_depth3": _structured_tree_predictions(train, development),
            "word_tfidf_centroid": _tfidf_predictions(
                train,
                development,
                "word",
            ),
            "char4_tfidf_centroid": _tfidf_predictions(
                train,
                development,
                "char",
            ),
        }
        scenario_scores = {
            name: _scenario_scores(development, predicted)
            for name, predicted in predictions.items()
        }
        environments[environment] = {
            "train_scenario_count": len(
                {row["scenario_id"] for row in train}
            ),
            "development_scenario_count": len(
                {row["scenario_id"] for row in development}
            ),
            "development_example_count": len(development),
            "metrics": {
                name: _classification_summary(actual, predicted)
                for name, predicted in predictions.items()
            },
            "scenario_cluster_bootstrap": scenario_cluster_bootstrap(
                scenario_scores,
                samples=bootstrap_samples,
                confidence_level=confidence_level,
                seed=seed + offset * 100_003,
            ),
        }
    return {
        "status": "EXPLORATORY_SMOKE_ONLY",
        "retained_or_confirmation_result": False,
        "data_scope": str(data_dir.as_posix()),
        "effective_unit": "scenario_family",
        "static_envelope_rule": (
            "maximum baseline scenario-macro accuracy recomputed inside "
            "each bootstrap replicate"
        ),
        "environments": environments,
    }
