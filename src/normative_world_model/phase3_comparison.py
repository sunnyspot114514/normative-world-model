"""Deterministic selections for the retained one-step arm comparison."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from .local_pilot import ConsistencyPair, build_consistency_pairs


def _rank(seed: int, *parts: object) -> str:
    preimage = "\t".join((str(seed), *(str(part) for part in parts)))
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _pair_bucket(pair: ConsistencyPair) -> tuple[str, str, str, str]:
    profile_signature = (
        f"{pair.left['profile_id']}|{pair.right['profile_id']}"
        if pair.pair_type == "semantic_evaluator"
        else str(pair.left["profile_id"])
    )
    return (
        pair.pair_type,
        str(pair.left["environment"]),
        str(pair.left["input_condition"]),
        profile_signature,
    )


def select_comparison_pairs(
    records: Iterable[dict[str, Any]],
    *,
    seed: int,
    maximum: int,
    split: str = "train",
) -> list[ConsistencyPair]:
    """Hash-rank and round-robin pairs without length or label ordering."""

    eligible = [record for record in records if record.get("split") == split]
    buckets: dict[tuple[str, str, str, str], list[ConsistencyPair]] = (
        defaultdict(list)
    )
    for pair in build_consistency_pairs(eligible):
        buckets[_pair_bucket(pair)].append(pair)
    for bucket in buckets.values():
        bucket.sort(
            key=lambda pair: _rank(
                seed,
                pair.pair_type,
                pair.left["record_id"],
                pair.right["record_id"],
            )
        )
    selected: list[ConsistencyPair] = []
    seen_scenarios: set[str] = set()
    positions = {name: 0 for name in buckets}
    while len(selected) < maximum:
        progress = False
        for name in sorted(buckets):
            bucket = buckets[name]
            while positions[name] < len(bucket):
                pair = bucket[positions[name]]
                positions[name] += 1
                scenario_id = str(pair.left["scenario_id"])
                if scenario_id in seen_scenarios:
                    continue
                selected.append(pair)
                seen_scenarios.add(scenario_id)
                progress = True
                break
            if len(selected) == maximum:
                break
        if not progress:
            break
    if len(selected) != maximum:
        raise ValueError(
            f"requested {maximum} comparison pairs, found {len(selected)}"
        )
    return selected


def _decision(record: dict[str, Any]) -> str:
    target = json.loads(str(record["target_text"]))
    return str(target["normative_decision"])


def _evaluation_bucket(
    record: dict[str, Any],
) -> tuple[str, str, str, str]:
    return (
        str(record["environment"]),
        str(record["input_condition"]),
        _decision(record),
        str(record["profile_id"]),
    )


def select_balanced_evaluation_records(
    records: Iterable[dict[str, Any]],
    *,
    seed: int,
    per_bucket: int,
    excluded_scenarios: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Select unique development families across environment/input/label/profile."""

    excluded = set(excluded_scenarios)
    buckets: dict[tuple[str, str, str, str], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for record in records:
        if (
            record.get("split") == "development"
            and record.get("profile_surface_variant") == 0
            and record.get("scenario_id") not in excluded
        ):
            buckets[_evaluation_bucket(record)].append(record)
    expected = {
        (environment, condition, decision, profile)
        for environment in ("game", "organization")
        for condition in ("structured", "natural_language")
        for decision in ("allow", "reject", "escalate")
        for profile in (
            "autonomy_preserving",
            "efficiency_tolerant",
            "harm_averse",
            "procedure_preserving",
        )
    }
    if set(buckets) != expected:
        missing = expected - set(buckets)
        raise ValueError(f"evaluation buckets are incomplete: {sorted(missing)}")
    for name, bucket in buckets.items():
        bucket.sort(
            key=lambda record: _rank(
                seed,
                *name,
                record["scenario_id"],
                record["record_id"],
            )
        )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in sorted(buckets):
        count = 0
        for record in buckets[name]:
            scenario_id = str(record["scenario_id"])
            if scenario_id in seen:
                continue
            selected.append(record)
            seen.add(scenario_id)
            count += 1
            if count == per_bucket:
                break
        if count != per_bucket:
            raise ValueError(
                f"insufficient unique development scenarios in {name}"
            )
    return selected


def canonical_digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def pair_binding(pairs: Iterable[ConsistencyPair]) -> dict[str, Any]:
    rows = [
        {
            "pair_type": pair.pair_type,
            "left": pair.left["record_id"],
            "right": pair.right["record_id"],
            "scenario_id": pair.left["scenario_id"],
            "bucket": "|".join(_pair_bucket(pair)),
        }
        for pair in pairs
    ]
    return {
        "count": len(rows),
        "unique_scenario_count": len(
            {str(row["scenario_id"]) for row in rows}
        ),
        "order_sha256": canonical_digest(rows),
        "bucket_counts": dict(
            sorted(Counter(str(row["bucket"]) for row in rows).items())
        ),
    }


def evaluation_binding(
    records: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        {
            "record_id": record["record_id"],
            "scenario_id": record["scenario_id"],
            "bucket": "|".join(_evaluation_bucket(record)),
        }
        for record in records
    ]
    return {
        "count": len(rows),
        "unique_scenario_count": len(
            {str(row["scenario_id"]) for row in rows}
        ),
        "order_sha256": canonical_digest(rows),
        "bucket_counts": dict(
            sorted(Counter(str(row["bucket"]) for row in rows).items())
        ),
    }


def compact_binding(binding: dict[str, Any]) -> dict[str, Any]:
    """Keep exact selection identity without copying every bucket into locks."""

    counts = binding.get("bucket_counts")
    if not isinstance(counts, dict) or not counts:
        raise ValueError("binding has no bucket counts")
    values = [int(value) for value in counts.values()]
    return {
        "count": int(binding["count"]),
        "unique_scenario_count": int(binding["unique_scenario_count"]),
        "order_sha256": str(binding["order_sha256"]),
        "bucket_count": len(counts),
        "minimum_bucket_count": min(values),
        "maximum_bucket_count": max(values),
        "bucket_counts_sha256": canonical_digest(counts),
    }


def anti_collapse_checks(
    metrics: dict[str, float | bool],
    thresholds: dict[str, float],
) -> dict[str, bool]:
    """Evaluate the frozen engineering gate with explicit inclusive bounds."""

    return {
        "loss_window_improvement": float(
            metrics["loss_window_improvement_fraction"]
        )
        >= float(thresholds["minimum_loss_window_improvement_fraction"]),
        "normative_accuracy": float(metrics["normative_accuracy"])
        >= float(thresholds["minimum_normative_accuracy"]),
        "decision_not_collapsed": float(
            metrics["maximum_predicted_decision_share"]
        )
        <= float(thresholds["maximum_single_predicted_decision_share"]),
        "impact_not_collapsed": float(
            metrics["rows_with_nonzero_impact_fraction"]
        )
        >= float(thresholds["minimum_rows_with_nonzero_impact_fraction"]),
        "physical_not_empty": float(
            metrics["nonempty_physical_delta_fraction"]
        )
        >= float(thresholds["minimum_nonempty_physical_delta_fraction"]),
        "event_mae_beats_zero": float(
            metrics["event_mae_improvement_over_zero"]
        )
        >= float(thresholds["minimum_event_mae_improvement_over_zero"]),
        "strict_schema_coverage": float(metrics["strict_schema_coverage"])
        >= float(thresholds["require_strict_schema_coverage"]),
        "resource_status": metrics["resource_status_pass"] is True,
    }
