"""Training-only baselines and repaired gates for Phase-3 gateway v3."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .local_pilot import ConsistencyPair
from .phase2_metrics import score_fields
from .slot_objective import SlotInventory, SlotSpec


def _nested(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for component in path.split("."):
        current = current[component]
    return current


def _set_nested(value: dict[str, Any], path: str, item: Any) -> None:
    components = path.split(".")
    current = value
    for component in components[:-1]:
        current = current.setdefault(component, {})
    current[components[-1]] = item


def _typed_key(value: Any) -> str:
    return f"{type(value).__name__}:{json.dumps(value, sort_keys=True)}"


def _categorical_mode(slot: SlotSpec, values: list[Any]) -> Any:
    counts = Counter(_typed_key(value) for value in values)
    return max(
        slot.values,
        key=lambda candidate: (
            counts[_typed_key(candidate)],
            -slot.values.index(candidate),
        ),
    )


def build_training_constant_baselines(
    pairs: Iterable[ConsistencyPair],
    inventory: SlotInventory,
) -> dict[str, dict[str, Any]]:
    """Build environment-only constants without reading development targets."""

    targets: dict[str, list[dict[str, Any]]] = {
        "game": [],
        "organization": [],
    }
    for pair in pairs:
        for record in (pair.left, pair.right):
            targets[str(record["environment"])].append(
                json.loads(str(record["target_text"]))
            )
    output: dict[str, dict[str, Any]] = {}
    for environment, rows in targets.items():
        if not rows:
            raise ValueError(f"no training targets for {environment}")
        baseline: dict[str, Any] = {
            "physical_delta": {},
            "event_record": {},
        }
        for slot in inventory.slots:
            if slot.role not in {"physical", "event"}:
                continue
            if environment not in slot.environments:
                continue
            values = [_nested(row, slot.path) for row in rows]
            if slot.kind == "categorical":
                prediction = _categorical_mode(slot, values)
            elif slot.kind == "set":
                prediction = [
                    member
                    for member in slot.values
                    if 2
                    * sum(member in set(value) for value in values)
                    >= len(values)
                ]
            else:
                prediction = float(
                    statistics.median(float(value) for value in values)
                )
            _set_nested(baseline, slot.path, prediction)
        output[environment] = baseline
    return output


def score_training_constant_baselines(
    records: Iterable[Mapping[str, Any]],
    baselines: Mapping[str, Mapping[str, Any]],
    inventory: SlotInventory,
) -> dict[str, float]:
    physical: list[float] = []
    event: list[float] = []
    continuous_errors: list[float] = []
    continuous = [
        slot
        for slot in inventory.slots
        if slot.role == "event" and slot.kind == "continuous"
    ]
    for record in records:
        expected = json.loads(str(record["target_text"]))
        baseline = baselines[str(record["environment"])]
        physical.append(
            score_fields(
                baseline["physical_delta"],
                expected["physical_delta"],
                component="physical_delta",
            ).f1
        )
        event.append(
            score_fields(
                baseline["event_record"],
                expected["event_record"],
                component="event_record",
            ).f1
        )
        continuous_errors.append(
            sum(
                abs(
                    float(_nested(baseline, slot.path))
                    - float(_nested(expected, slot.path))
                )
                for slot in continuous
            )
            / len(continuous)
        )
    if not physical:
        raise ValueError("cannot score an empty evaluation population")
    return {
        "training_constant_physical_field_f1": statistics.mean(physical),
        "training_constant_event_field_f1": statistics.mean(event),
        "training_constant_event_continuous_mae": statistics.mean(
            continuous_errors
        ),
    }


def normative_recall_by_class(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, float]:
    values = list(rows)
    recalls: dict[str, float] = {}
    for decision in ("allow", "reject", "escalate"):
        selected = [row for row in values if row["target_decision"] == decision]
        if not selected:
            raise ValueError(f"no evaluation targets for {decision}")
        recalls[decision] = sum(
            row["predicted_decision"] == decision for row in selected
        ) / len(selected)
    return recalls


def gateway_v3_checks(
    metrics: Mapping[str, Any],
    thresholds: Mapping[str, Any],
) -> dict[str, bool]:
    """Apply every repaired V3 blocking check with inclusive boundaries."""

    recalls = metrics["normative_recall_by_class"]
    return {
        "fixed_probe_loss_improvement": float(
            metrics["fixed_probe_loss_improvement_fraction"]
        )
        >= float(thresholds["minimum_fixed_probe_loss_improvement_fraction"]),
        "normative_accuracy": float(metrics["normative_accuracy"])
        >= float(thresholds["minimum_normative_accuracy"]),
        "normative_recall_per_class": min(float(v) for v in recalls.values())
        >= float(thresholds["minimum_normative_recall_per_class"]),
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
        "event_mae_beats_training_constant": float(
            metrics["event_mae_improvement_over_training_constant"]
        )
        >= float(
            thresholds["minimum_event_mae_improvement_over_training_constant"]
        ),
        "physical_f1_beats_training_constant": float(
            metrics["physical_field_f1_improvement_over_training_constant"]
        )
        >= float(
            thresholds[
                "minimum_physical_field_f1_improvement_over_training_constant"
            ]
        ),
        "event_f1_beats_training_constant": float(
            metrics["event_field_f1_improvement_over_training_constant"]
        )
        >= float(
            thresholds[
                "minimum_event_field_f1_improvement_over_training_constant"
            ]
        ),
        "strict_schema_coverage": float(metrics["strict_schema_coverage"])
        >= float(thresholds["require_strict_schema_coverage"]),
        "resource_status": metrics["resource_status_pass"] is True,
        "deterministic_prefix_replay": (
            metrics["deterministic_prefix_replay"] is True
        ),
    }
