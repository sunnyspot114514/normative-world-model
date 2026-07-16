"""Four-way environment transfer manifests and support diagnostics."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Iterable

ENVIRONMENT_ALIASES = {"A": "game", "B": "organization"}
INPUT_CONDITIONS = ("structured", "natural_language")
TARGET_PROFILE_PAIRS = (
    ("harm_averse", "efficiency_tolerant"),
    ("procedure_preserving", "autonomy_preserving"),
    ("procedure_preserving", "harm_averse"),
)
IMPACT_DIMENSIONS = (
    "safety",
    "privacy",
    "autonomy",
    "trust",
    "efficiency",
    "fairness",
    "commitment",
)


def _id_hash(ids: list[str]) -> str:
    preimage = "".join(f"{value}\n" for value in sorted(ids))
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _environment_support(
    rows: list[dict[str, Any]],
    minimum_fraction: float,
) -> dict[str, Any]:
    discretionary = [
        row
        for row in rows
        if not row["primary"]["policy_result"]["hard_violations"]
        and len(
            {
                result["decision"]
                for result in row["primary"]["evaluations"].values()
            }
        )
        > 1
    ]
    denominator = len(discretionary)
    dimension_sign = {}
    for dimension in IMPACT_DIMENSIONS:
        positive = sum(
            row["primary"]["event_record"]["impact_vector"][dimension] > 0
            for row in discretionary
        )
        negative = sum(
            row["primary"]["event_record"]["impact_vector"][dimension] < 0
            for row in discretionary
        )
        dimension_sign[dimension] = {
            "positive_fraction": positive / denominator if denominator else 0.0,
            "negative_fraction": negative / denominator if denominator else 0.0,
        }
    pair_support = {}
    for left, right in TARGET_PROFILE_PAIRS:
        flip_count = sum(
            row["primary"]["evaluations"][left]["decision"]
            != row["primary"]["evaluations"][right]["decision"]
            for row in discretionary
        )
        pair_support[f"{left}|{right}"] = {
            "flip_count": flip_count,
            "flip_fraction": flip_count / denominator if denominator else 0.0,
        }
    reason_counts = Counter(
        result["reason"]
        for row in rows
        for result in row["primary"]["evaluations"].values()
    )
    insufficient = [
        f"{dimension}:{sign}"
        for dimension, values in dimension_sign.items()
        for sign in ("positive", "negative")
        if values[f"{sign}_fraction"] < minimum_fraction
    ]
    return {
        "scenario_count": len(rows),
        "discretionary_divergent_count": denominator,
        "minimum_dimension_sign_fraction": minimum_fraction,
        "dimension_sign_coverage": dimension_sign,
        "target_profile_pair_support": pair_support,
        "oracle_reason_counts": dict(sorted(reason_counts.items())),
        "status": "IDENTIFIED" if not insufficient else "UNIDENTIFIED",
        "insufficient_dimension_sign_cells": insufficient,
    }

def build_transfer_manifest(
    families: Iterable[dict[str, Any]],
    *,
    minimum_dimension_sign_fraction: float = 0.05,
) -> dict[str, Any]:
    rows = list(families)
    by_environment = {
        environment: [
            row for row in rows if row["environment"] == environment
        ]
        for environment in ENVIRONMENT_ALIASES.values()
    }
    cells = {}
    for train_alias, train_environment in ENVIRONMENT_ALIASES.items():
        train_ids = [
            row["scenario_id"]
            for row in by_environment[train_environment]
            if row["split"] == "train"
        ]
        for test_alias, test_environment in ENVIRONMENT_ALIASES.items():
            test_ids = [
                row["scenario_id"]
                for row in by_environment[test_environment]
                if row["split"] == "development"
            ]
            for condition in INPUT_CONDITIONS:
                key = f"{train_alias}->{test_alias}:{condition}"
                overlap = sorted(set(train_ids) & set(test_ids))
                cells[key] = {
                    "train_environment": train_environment,
                    "test_environment": test_environment,
                    "input_condition": condition,
                    "purpose": (
                        "in_domain_reference"
                        if train_environment == test_environment
                        else "cross_environment_transfer"
                    ),
                    "train_scenario_count": len(train_ids),
                    "test_scenario_count": len(test_ids),
                    "train_scenario_ids_sha256": _id_hash(train_ids),
                    "test_scenario_ids_sha256": _id_hash(test_ids),
                    "train_test_overlap_count": len(overlap),
                    "status": (
                        "READY"
                        if not overlap
                        else "INVALID_SPLIT_OVERLAP"
                    ),
                }
    support = {
        environment: _environment_support(
            environment_rows,
            minimum_dimension_sign_fraction,
        )
        for environment, environment_rows in by_environment.items()
    }
    unidentified = [
        environment
        for environment, report in support.items()
        if report["status"] != "IDENTIFIED"
    ]
    return {
        "status": (
            "READY"
            if all(cell["status"] == "READY" for cell in cells.values())
            and not unidentified
            else "UNIDENTIFIED"
        ),
        "effective_unit": "scenario_family",
        "matrix": cells,
        "environment_support": support,
        "unidentified_environments": unidentified,
        "interpretation": (
            "structured diagnoses abstraction transfer; natural_language adds "
            "rendering and domain-language shift"
        ),
    }
