"""Deterministic selection helpers for the retained schema-convergence gate."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

PROFILES = (
    "autonomy_preserving",
    "efficiency_tolerant",
    "harm_averse",
    "procedure_preserving",
)
ENVIRONMENTS = ("game", "organization")


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def select_unique_development_records(
    records: Iterable[dict[str, Any]],
    *,
    per_environment_profile: int = 2,
) -> list[dict[str, Any]]:
    """Select balanced structured records with one profile per scenario."""

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if (
            record.get("split") == "development"
            and record.get("input_condition") == "structured"
            and record.get("profile_surface_variant") == 0
            and record.get("environment") in ENVIRONMENTS
            and record.get("profile_id") in PROFILES
        ):
            buckets[
                (str(record["environment"]), str(record["profile_id"]))
            ].append(record)
    expected_buckets = {
        (environment, profile)
        for environment in ENVIRONMENTS
        for profile in PROFILES
    }
    if set(buckets) != expected_buckets:
        raise ValueError("development selection buckets are incomplete")
    for bucket in buckets.values():
        bucket.sort(
            key=lambda record: (
                str(record["scenario_id"]),
                str(record["record_id"]),
            )
        )

    selected: list[dict[str, Any]] = []
    seen_scenarios: set[str] = set()
    for bucket_name in sorted(buckets):
        bucket_selected = 0
        for record in buckets[bucket_name]:
            scenario_id = str(record["scenario_id"])
            if scenario_id in seen_scenarios:
                continue
            selected.append(record)
            seen_scenarios.add(scenario_id)
            bucket_selected += 1
            if bucket_selected == per_environment_profile:
                break
        if bucket_selected != per_environment_profile:
            raise ValueError(
                f"insufficient unique scenarios in bucket {bucket_name}"
            )
    return selected


def development_selection_binding(
    records: Iterable[dict[str, Any]],
    *,
    per_environment_profile: int = 2,
) -> dict[str, Any]:
    selected = select_unique_development_records(
        records,
        per_environment_profile=per_environment_profile,
    )
    return {
        "development_generation_count": len(selected),
        "development_scenario_count": len(
            {str(record["scenario_id"]) for record in selected}
        ),
        "development_record_order_sha256": canonical_digest(
            [str(record["record_id"]) for record in selected]
        ),
        "development_bucket_counts": {
            f"{environment}|{profile}": sum(
                record["environment"] == environment
                and record["profile_id"] == profile
                for record in selected
            )
            for environment in ENVIRONMENTS
            for profile in PROFILES
        },
    }
