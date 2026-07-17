"""Schema-native slot heads and the retained JS/Huber objective."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SlotSpec:
    path: str
    role: str
    kind: str
    environments: tuple[str, ...]
    values: tuple[Any, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class SlotInventory:
    version: str
    status: str
    representation: str
    output_mode: str
    loss: dict[str, Any]
    slots: tuple[SlotSpec, ...]


@dataclass(frozen=True)
class SlotObjectiveResult:
    total: Any
    physical_supervised: Any
    event_supervised: Any
    normative_supervised: Any
    physical_invariance: Any
    event_invariance: Any


def default_inventory_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "phase3_slot_inventory.json"
    )


def _typed_equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _unique_typed(values: tuple[Any, ...]) -> bool:
    for index, value in enumerate(values):
        if any(_typed_equal(value, other) for other in values[index + 1 :]):
            return False
    return True


def load_slot_inventory(path: Path | None = None) -> SlotInventory:
    source = path or default_inventory_path()
    raw = json.loads(source.read_text(encoding="utf-8"))
    slots = tuple(
        SlotSpec(
            path=str(item["path"]),
            role=str(item["role"]),
            kind=str(item["kind"]),
            environments=tuple(str(value) for value in item["environments"]),
            values=tuple(item.get("values", ())),
            minimum=(
                float(item["minimum"]) if "minimum" in item else None
            ),
            maximum=(
                float(item["maximum"]) if "maximum" in item else None
            ),
        )
        for item in raw["slots"]
    )
    inventory = SlotInventory(
        version=str(raw["version"]),
        status=str(raw["status"]),
        representation=str(raw["representation"]),
        output_mode=str(raw["output_mode"]),
        loss=dict(raw["loss"]),
        slots=slots,
    )
    failures = validate_slot_inventory(inventory)
    if failures:
        raise ValueError("; ".join(failures))
    return inventory


def validate_slot_inventory(inventory: SlotInventory) -> list[str]:
    failures: list[str] = []
    paths = [slot.path for slot in inventory.slots]
    if len(paths) != len(set(paths)):
        failures.append("slot paths must be unique")
    for slot in inventory.slots:
        if slot.role not in {"physical", "event", "normative"}:
            failures.append(f"invalid role for {slot.path}")
        if slot.kind not in {"categorical", "set", "continuous"}:
            failures.append(f"invalid kind for {slot.path}")
        if not slot.environments or not set(slot.environments) <= {
            "game",
            "organization",
        }:
            failures.append(f"invalid environments for {slot.path}")
        if slot.kind in {"categorical", "set"}:
            if not slot.values or not _unique_typed(slot.values):
                failures.append(f"invalid finite support for {slot.path}")
        elif (
            slot.minimum is None
            or slot.maximum is None
            or not slot.minimum < slot.maximum
        ):
            failures.append(f"invalid continuous range for {slot.path}")
    normative = [
        slot for slot in inventory.slots if slot.role == "normative"
    ]
    if [slot.path for slot in normative] != ["normative_decision"]:
        failures.append(
            "normative_decision must be the sole learned normative slot"
        )
    if "escalation_required" in paths:
        failures.append("escalation_required must be derived from the decision")
    return failures


def _torch_modules() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch import nn
        from torch.nn import functional
    except ImportError as error:  # pragma: no cover - model extra is optional
        raise RuntimeError(
            "slot objective requires requirements-model.txt"
        ) from error
    return torch, nn, functional


def build_slot_head_bank(hidden_size: int, inventory: SlotInventory) -> Any:
    """Create identical schema-native heads for every learned model arm."""

    torch, nn, _ = _torch_modules()

    class SlotHeadBank(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.specs = inventory.slots
            self.names = {
                slot.path: f"slot_{index:03d}"
                for index, slot in enumerate(self.specs)
            }
            self.heads = nn.ModuleDict()
            for slot in self.specs:
                width = 2 if slot.kind == "continuous" else len(slot.values)
                self.heads[self.names[slot.path]] = nn.Linear(
                    hidden_size,
                    width,
                )

        def forward(self, hidden: Any) -> dict[str, Any]:
            outputs: dict[str, Any] = {}
            minimum_variance = float(
                inventory.loss["minimum_normalized_variance"]
            )
            maximum_variance = float(
                inventory.loss["maximum_normalized_variance"]
            )
            log_minimum = math.log(minimum_variance)
            log_maximum = math.log(maximum_variance)
            for slot in self.specs:
                raw = self.heads[self.names[slot.path]](hidden)
                if slot.kind != "continuous":
                    outputs[slot.path] = raw
                    continue
                mean_normalized = torch.sigmoid(raw[:, 0])
                log_variance = log_minimum + (
                    log_maximum - log_minimum
                ) * torch.sigmoid(raw[:, 1])
                mean = slot.minimum + mean_normalized * (
                    slot.maximum - slot.minimum
                )
                outputs[slot.path] = {
                    "mean": mean,
                    "mean_normalized": mean_normalized,
                    "variance_normalized": torch.exp(log_variance),
                }
            return outputs

    return SlotHeadBank()


def _nested_value(target: dict[str, Any], path: str) -> Any:
    value: Any = target
    for component in path.split("."):
        value = value[component]
    return value


def _value_index(values: tuple[Any, ...], target: Any) -> int:
    for index, candidate in enumerate(values):
        if _typed_equal(candidate, target):
            return index
    raise ValueError(f"target {target!r} is outside frozen support")


def symmetric_js_from_logits(left: Any, right: Any) -> Any:
    torch, _, _ = _torch_modules()
    left_log = torch.log_softmax(left.float(), dim=-1)
    right_log = torch.log_softmax(right.float(), dim=-1)
    left_probability = left_log.exp()
    right_probability = right_log.exp()
    midpoint = 0.5 * (left_probability + right_probability)
    midpoint_log = midpoint.clamp_min(1e-12).log()
    return 0.5 * (
        (left_probability * (left_log - midpoint_log)).sum(dim=-1)
        + (right_probability * (right_log - midpoint_log)).sum(dim=-1)
    )


def symmetric_bernoulli_js(left: Any, right: Any) -> Any:
    torch, _, _ = _torch_modules()
    left_probability = torch.sigmoid(left.float())
    right_probability = torch.sigmoid(right.float())
    left_logits = torch.stack(
        (left_probability, 1.0 - left_probability),
        dim=-1,
    ).clamp_min(1e-12).log()
    right_logits = torch.stack(
        (right_probability, 1.0 - right_probability),
        dim=-1,
    ).clamp_min(1e-12).log()
    return symmetric_js_from_logits(left_logits, right_logits).mean(dim=-1)


def _active_indices(
    slot: SlotSpec,
    environments: list[str],
) -> list[int]:
    return [
        index
        for index, environment in enumerate(environments)
        if environment in slot.environments
    ]


def _zero_from_predictions(predictions: dict[str, Any]) -> Any:
    torch, _, _ = _torch_modules()
    first = next(iter(predictions.values()))
    tensor = first["mean"] if isinstance(first, dict) else first
    return torch.zeros((), dtype=torch.float32, device=tensor.device)


def supervised_slot_losses(
    predictions: dict[str, Any],
    targets: list[dict[str, Any]],
    environments: list[str],
    inventory: SlotInventory,
) -> dict[str, Any]:
    """Return macro slot losses without summing over schema width."""

    torch, _, functional = _torch_modules()
    if len(targets) != len(environments):
        raise ValueError("target and environment batch lengths differ")
    losses: dict[str, list[Any]] = {
        "physical": [],
        "event": [],
        "normative": [],
    }
    delta = float(inventory.loss["continuous_huber_delta"])
    calibration_weight = float(
        inventory.loss["continuous_calibration_weight"]
    )
    for slot in inventory.slots:
        indices = _active_indices(slot, environments)
        if not indices:
            continue
        prediction = predictions[slot.path]
        if slot.kind == "categorical":
            expected = torch.tensor(
                [
                    _value_index(
                        slot.values,
                        _nested_value(targets[index], slot.path),
                    )
                    for index in indices
                ],
                dtype=torch.long,
                device=prediction.device,
            )
            field_loss = functional.cross_entropy(
                prediction[indices].float(),
                expected,
            )
        elif slot.kind == "set":
            expected = torch.zeros(
                (len(indices), len(slot.values)),
                dtype=torch.float32,
                device=prediction.device,
            )
            for row, index in enumerate(indices):
                members = _nested_value(targets[index], slot.path)
                if not isinstance(members, list):
                    raise ValueError(f"{slot.path} target must be a list")
                for member in members:
                    expected[row, _value_index(slot.values, member)] = 1.0
            field_loss = functional.binary_cross_entropy_with_logits(
                prediction[indices].float(),
                expected,
            )
        else:
            expected = torch.tensor(
                [
                    float(_nested_value(targets[index], slot.path))
                    for index in indices
                ],
                dtype=torch.float32,
                device=prediction["mean"].device,
            )
            expected_normalized = (expected - slot.minimum) / (
                slot.maximum - slot.minimum
            )
            mean = prediction["mean_normalized"][indices].float()
            variance = prediction["variance_normalized"][indices].float()
            huber = functional.huber_loss(
                mean,
                expected_normalized,
                delta=delta,
            )
            squared_error = (mean - expected_normalized).square().detach()
            calibration = (
                variance + squared_error / variance.clamp_min(1e-12)
            ).mean()
            field_loss = huber + calibration_weight * calibration
        losses[slot.role].append(field_loss)

    zero = _zero_from_predictions(predictions)
    return {
        role: torch.stack(values).mean() if values else zero
        for role, values in losses.items()
    }


def invariance_slot_losses(
    left: dict[str, Any],
    right: dict[str, Any],
    environments: list[str],
    inventory: SlotInventory,
) -> dict[str, Any]:
    """Compute evaluator/surface-twin divergence on factual slots only."""

    torch, _, functional = _torch_modules()
    losses: dict[str, list[Any]] = {"physical": [], "event": []}
    delta = float(inventory.loss["continuous_huber_delta"])
    for slot in inventory.slots:
        if slot.role not in losses:
            continue
        indices = _active_indices(slot, environments)
        if not indices:
            continue
        left_value = left[slot.path]
        right_value = right[slot.path]
        if slot.kind == "categorical":
            loss = symmetric_js_from_logits(
                left_value[indices],
                right_value[indices],
            ).mean()
        elif slot.kind == "set":
            loss = symmetric_bernoulli_js(
                left_value[indices],
                right_value[indices],
            ).mean()
        else:
            loss = functional.huber_loss(
                left_value["mean_normalized"][indices].float(),
                right_value["mean_normalized"][indices].float(),
                delta=delta,
            )
        losses[slot.role].append(loss)
    zero = _zero_from_predictions(left)
    return {
        role: torch.stack(values).mean() if values else zero
        for role, values in losses.items()
    }


def slot_objective(
    left_predictions: dict[str, Any],
    right_predictions: dict[str, Any],
    left_targets: list[dict[str, Any]],
    right_targets: list[dict[str, Any]],
    environments: list[str],
    inventory: SlotInventory,
    *,
    consistency_lambda: float,
) -> SlotObjectiveResult:
    if consistency_lambda < 0:
        raise ValueError("consistency lambda must be nonnegative")
    left = supervised_slot_losses(
        left_predictions,
        left_targets,
        environments,
        inventory,
    )
    right = supervised_slot_losses(
        right_predictions,
        right_targets,
        environments,
        inventory,
    )
    supervised = {
        role: 0.5 * (left[role] + right[role])
        for role in ("physical", "event", "normative")
    }
    invariance = invariance_slot_losses(
        left_predictions,
        right_predictions,
        environments,
        inventory,
    )
    total = (
        supervised["physical"]
        + supervised["event"]
        + supervised["normative"]
        + consistency_lambda
        * (invariance["physical"] + invariance["event"])
    )
    return SlotObjectiveResult(
        total=total,
        physical_supervised=supervised["physical"],
        event_supervised=supervised["event"],
        normative_supervised=supervised["normative"],
        physical_invariance=invariance["physical"],
        event_invariance=invariance["event"],
    )


def decode_slot_predictions(
    predictions: dict[str, Any],
    inventory: SlotInventory,
    *,
    environment: str,
    row: int = 0,
    set_threshold: float = 0.5,
) -> dict[str, Any]:
    """Decode one row to a strict one-step model output."""

    torch, _, _ = _torch_modules()
    output: dict[str, Any] = {
        "physical_delta": {},
        "event_record": {"impact_vector": {}},
    }
    for slot in inventory.slots:
        if environment not in slot.environments:
            continue
        prediction = predictions[slot.path]
        if slot.kind == "categorical":
            index = int(torch.argmax(prediction[row]).item())
            value = slot.values[index]
        elif slot.kind == "set":
            probabilities = torch.sigmoid(prediction[row].float())
            value = [
                candidate
                for candidate, probability in zip(
                    slot.values,
                    probabilities.tolist(),
                    strict=True,
                )
                if probability >= set_threshold
            ]
        else:
            value = round(float(prediction["mean"][row].item()), 6)
        container = output
        components = slot.path.split(".")
        for component in components[:-1]:
            container = container.setdefault(component, {})
        container[components[-1]] = value
    decision = output["normative_decision"]
    output["escalation_required"] = decision == "escalate"
    output["rollout"] = []
    return output
