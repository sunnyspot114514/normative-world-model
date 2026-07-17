"""Role-query representation and objectives for the Phase-3 V4 gateway."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .local_pilot import ConsistencyPair
from .phase3_gateway import gateway_v3_checks
from .slot_objective import (
    SlotInventory,
    SlotObjectiveResult,
    SlotSpec,
    symmetric_bernoulli_js,
    symmetric_js_from_logits,
)

ROLE_ORDER = ("physical", "event", "normative")
DEFAULT_QUERY_MARKERS = {
    "physical": "\n[PHYSICAL_TRANSITION_QUERY]",
    "event": "\n[EVENT_RECORD_QUERY]",
    "normative": "\n[NORMATIVE_DECISION_QUERY]",
}


def _torch_modules() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch import nn
        from torch.nn import functional
    except ImportError as error:  # pragma: no cover - model extra is optional
        raise RuntimeError("V4 gateway requires requirements-model.txt") from error
    return torch, nn, functional


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


def _typed_equal(left: Any, right: Any) -> bool:
    return type(left) is type(right) and left == right


def _value_index(values: tuple[Any, ...], target: Any) -> int:
    for index, candidate in enumerate(values):
        if _typed_equal(candidate, target):
            return index
    raise ValueError(f"target {target!r} is outside frozen support")


def _targets(pairs: Iterable[ConsistencyPair]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for pair in pairs:
        for record in (pair.left, pair.right):
            target = json.loads(str(record["target_text"]))
            if not isinstance(target, dict):
                raise ValueError("target_text must decode to an object")
            output.append(target)
    if not output:
        raise ValueError("training pairs cannot be empty")
    return output


def build_continuous_statistics(
    pairs: Iterable[ConsistencyPair],
    inventory: SlotInventory,
    *,
    standard_deviation_floor: float = 1e-6,
) -> dict[str, dict[str, float | int]]:
    """Compute per-slot population statistics from training presentations only."""

    if standard_deviation_floor <= 0:
        raise ValueError("standard-deviation floor must be positive")
    targets = _targets(pairs)
    output: dict[str, dict[str, float | int]] = {}
    for slot in inventory.slots:
        if slot.kind != "continuous":
            continue
        values = [float(_nested(target, slot.path)) for target in targets]
        mean = statistics.fmean(values)
        variance = statistics.fmean((value - mean) ** 2 for value in values)
        output[slot.path] = {
            "count": len(values),
            "mean": mean,
            "standard_deviation": max(math.sqrt(variance), standard_deviation_floor),
        }
    return output


def build_normative_class_weights(
    pairs: Iterable[ConsistencyPair],
    inventory: SlotInventory,
    *,
    exponent: float = -0.5,
    cap: float = 2.0,
) -> dict[str, Any]:
    """Build the frozen exposure-weight-normalized inverse-frequency weights."""

    if cap <= 0:
        raise ValueError("class-weight cap must be positive")
    normative = [slot for slot in inventory.slots if slot.role == "normative"]
    if len(normative) != 1:
        raise ValueError("inventory must contain exactly one normative slot")
    slot = normative[0]
    targets = _targets(pairs)
    counts = Counter(str(_nested(target, slot.path)) for target in targets)
    if set(counts) != set(slot.values) or any(counts[str(value)] <= 0 for value in slot.values):
        raise ValueError("every normative class must occur in training")
    total = sum(counts.values())
    raw = {str(value): counts[str(value)] ** exponent for value in slot.values}
    first_mean = sum(counts[name] * raw[name] for name in raw) / total
    capped = {name: min(raw[name] / first_mean, cap) for name in raw}
    second_mean = sum(counts[name] * capped[name] for name in capped) / total
    weights = {name: capped[name] / second_mean for name in capped}
    return {
        "counts": {str(value): counts[str(value)] for value in slot.values},
        "weights": {str(value): weights[str(value)] for value in slot.values},
        "exponent": exponent,
        "pre_renormalization_cap": cap,
        "exposure_weighted_mean": (
            sum(counts[name] * weights[name] for name in weights) / total
        ),
    }


def role_query_batch(
    tokenizer: Any,
    texts: list[str],
    *,
    maximum: int,
    markers: Mapping[str, str] = DEFAULT_QUERY_MARKERS,
    device: str | None = "cuda",
) -> dict[str, Any]:
    """Tokenize without truncation and bind the last token of each role marker."""

    torch, _, _ = _torch_modules()
    if maximum <= 0 or not texts:
        raise ValueError("maximum and texts must be nonempty")
    if tuple(markers) != ROLE_ORDER:
        raise ValueError("query markers must use the frozen role order")
    if len(set(markers.values())) != len(ROLE_ORDER) or any(
        not value for value in markers.values()
    ):
        raise ValueError("query marker literals must be unique and nonempty")
    marker_ids: dict[str, list[int]] = {}
    for role in ROLE_ORDER:
        encoded = tokenizer(markers[role], add_special_tokens=False)
        ids = list(encoded["input_ids"])
        if not ids:
            raise ValueError(f"query marker has no tokens: {role}")
        marker_ids[role] = ids
    rows: list[list[int]] = []
    positions: list[list[int]] = []
    for text in texts:
        if any(text.count(literal) != 0 for literal in markers.values()):
            raise ValueError("source prompt contains a reserved query marker")
        source = list(tokenizer(text, add_special_tokens=False)["input_ids"])
        combined = list(source)
        row_positions: list[int] = []
        for role in ROLE_ORDER:
            combined.extend(marker_ids[role])
            row_positions.append(len(combined) - 1)
        if len(combined) > maximum:
            raise ValueError("prompt plus query suffix exceeds frozen maximum")
        rows.append(combined)
        positions.append(row_positions)
    width = max(len(row) for row in rows)
    pad_token_id = tokenizer.pad_token_id
    if pad_token_id is None:
        raise ValueError("tokenizer must define pad_token_id")
    input_ids = torch.full((len(rows), width), int(pad_token_id), dtype=torch.long)
    attention_mask = torch.zeros((len(rows), width), dtype=torch.long)
    for index, row in enumerate(rows):
        input_ids[index, : len(row)] = torch.tensor(row, dtype=torch.long)
        attention_mask[index, : len(row)] = 1
    query_positions = torch.tensor(positions, dtype=torch.long)
    result = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "query_positions": query_positions,
    }
    if device is not None:
        result = {name: value.to(device) for name, value in result.items()}
    return result


def role_query_hidden(model: Any, batch: Mapping[str, Any]) -> dict[str, Any]:
    """Return the three causal hidden states named by the frozen markers."""

    torch, _, _ = _torch_modules()
    output = model(
        input_ids=batch["input_ids"],
        attention_mask=batch["attention_mask"],
        use_cache=False,
        return_dict=True,
    )
    hidden = output.last_hidden_state
    positions = batch["query_positions"]
    rows = torch.arange(hidden.shape[0], device=hidden.device)
    return {
        role: hidden[rows, positions[:, index]]
        for index, role in enumerate(ROLE_ORDER)
    }


def build_role_query_head_bank(
    hidden_size: int,
    trunk_width: int,
    inventory: SlotInventory,
) -> Any:
    """Create role-specific MLP trunks followed by schema-native slot heads."""

    _, nn, _ = _torch_modules()
    if hidden_size <= 0 or trunk_width <= 0:
        raise ValueError("hidden and trunk widths must be positive")

    class RoleQueryHeadBank(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.specs = inventory.slots
            self.names = {
                slot.path: f"slot_{index:03d}" for index, slot in enumerate(self.specs)
            }
            self.trunks = nn.ModuleDict(
                {
                    role: nn.Sequential(
                        nn.LayerNorm(hidden_size),
                        nn.Linear(hidden_size, trunk_width),
                        nn.GELU(),
                    )
                    for role in ROLE_ORDER
                }
            )
            self.heads = nn.ModuleDict()
            for slot in self.specs:
                width = 1 if slot.kind == "continuous" else len(slot.values)
                self.heads[self.names[slot.path]] = nn.Linear(trunk_width, width)

        def forward(self, hidden_by_role: Mapping[str, Any]) -> dict[str, Any]:
            if set(hidden_by_role) != set(ROLE_ORDER):
                raise ValueError("one hidden state is required for every frozen role")
            trunks = {role: self.trunks[role](hidden_by_role[role]) for role in ROLE_ORDER}
            output: dict[str, Any] = {}
            for slot in self.specs:
                raw = self.heads[self.names[slot.path]](trunks[slot.role])
                output[slot.path] = raw[:, 0] if slot.kind == "continuous" else raw
            return output

    return RoleQueryHeadBank()


def _active_indices(slot: SlotSpec, environments: list[str]) -> list[int]:
    return [
        index
        for index, environment in enumerate(environments)
        if environment in slot.environments
    ]


def _zero(predictions: Mapping[str, Any]) -> Any:
    torch, _, _ = _torch_modules()
    first = next(iter(predictions.values()))
    return torch.zeros((), dtype=torch.float32, device=first.device)


def normative_weighted_cross_entropy(
    logits: Any,
    expected: Any,
    class_weights: Any,
) -> Any:
    """Weight examples without PyTorch's per-batch weight renormalization."""

    _, _, functional = _torch_modules()
    per_example = functional.cross_entropy(
        logits.float(), expected, reduction="none"
    )
    return (per_example * class_weights[expected]).mean()


def supervised_v4_losses(
    predictions: Mapping[str, Any],
    targets: list[dict[str, Any]],
    environments: list[str],
    inventory: SlotInventory,
    continuous_statistics: Mapping[str, Mapping[str, float | int]],
    normative_class_weights: Mapping[str, Any],
    *,
    smooth_l1_beta: float,
) -> dict[str, Any]:
    """Compute macro role losses under the V4 training-only contracts."""

    torch, _, functional = _torch_modules()
    if len(targets) != len(environments):
        raise ValueError("target and environment batch lengths differ")
    if smooth_l1_beta <= 0:
        raise ValueError("Smooth L1 beta must be positive")
    losses: dict[str, list[Any]] = {role: [] for role in ROLE_ORDER}
    weight_map = normative_class_weights["weights"]
    for slot in inventory.slots:
        indices = _active_indices(slot, environments)
        if not indices:
            continue
        prediction = predictions[slot.path]
        if slot.kind == "categorical":
            expected = torch.tensor(
                [
                    _value_index(slot.values, _nested(targets[index], slot.path))
                    for index in indices
                ],
                dtype=torch.long,
                device=prediction.device,
            )
            if slot.role == "normative":
                weight = torch.tensor(
                    [float(weight_map[str(value)]) for value in slot.values],
                    dtype=torch.float32,
                    device=prediction.device,
                )
                field_loss = normative_weighted_cross_entropy(
                    prediction[indices], expected, weight
                )
            else:
                field_loss = functional.cross_entropy(
                    prediction[indices].float(), expected
                )
        elif slot.kind == "set":
            expected = torch.zeros(
                (len(indices), len(slot.values)),
                dtype=torch.float32,
                device=prediction.device,
            )
            for row, index in enumerate(indices):
                members = _nested(targets[index], slot.path)
                if not isinstance(members, list):
                    raise ValueError(f"{slot.path} target must be a list")
                for member in members:
                    expected[row, _value_index(slot.values, member)] = 1.0
            field_loss = functional.binary_cross_entropy_with_logits(
                prediction[indices].float(), expected
            )
        else:
            stats = continuous_statistics[slot.path]
            expected = torch.tensor(
                [float(_nested(targets[index], slot.path)) for index in indices],
                dtype=torch.float32,
                device=prediction.device,
            )
            expected_z = (expected - float(stats["mean"])) / float(
                stats["standard_deviation"]
            )
            field_loss = functional.smooth_l1_loss(
                prediction[indices].float(), expected_z, beta=smooth_l1_beta
            )
        losses[slot.role].append(field_loss)
    zero = _zero(predictions)
    return {
        role: torch.stack(values).mean() if values else zero
        for role, values in losses.items()
    }


def invariance_v4_losses(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    environments: list[str],
    inventory: SlotInventory,
    *,
    smooth_l1_beta: float,
) -> dict[str, Any]:
    """Compute factual consistency on schema outputs, including z-space scalars."""

    torch, _, functional = _torch_modules()
    losses: dict[str, list[Any]] = {"physical": [], "event": []}
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
                left_value[indices], right_value[indices]
            ).mean()
        elif slot.kind == "set":
            loss = symmetric_bernoulli_js(
                left_value[indices], right_value[indices]
            ).mean()
        else:
            loss = functional.smooth_l1_loss(
                left_value[indices].float(),
                right_value[indices].float(),
                beta=smooth_l1_beta,
            )
        losses[slot.role].append(loss)
    zero = _zero(left)
    return {
        role: torch.stack(values).mean() if values else zero
        for role, values in losses.items()
    }


def slot_objective_v4(
    left_predictions: Mapping[str, Any],
    right_predictions: Mapping[str, Any],
    left_targets: list[dict[str, Any]],
    right_targets: list[dict[str, Any]],
    environments: list[str],
    inventory: SlotInventory,
    continuous_statistics: Mapping[str, Mapping[str, float | int]],
    normative_class_weights: Mapping[str, Any],
    *,
    smooth_l1_beta: float,
    consistency_lambda: float,
) -> SlotObjectiveResult:
    if consistency_lambda < 0:
        raise ValueError("consistency lambda must be nonnegative")
    left_loss = supervised_v4_losses(
        left_predictions,
        left_targets,
        environments,
        inventory,
        continuous_statistics,
        normative_class_weights,
        smooth_l1_beta=smooth_l1_beta,
    )
    right_loss = supervised_v4_losses(
        right_predictions,
        right_targets,
        environments,
        inventory,
        continuous_statistics,
        normative_class_weights,
        smooth_l1_beta=smooth_l1_beta,
    )
    supervised = {
        role: 0.5 * (left_loss[role] + right_loss[role]) for role in ROLE_ORDER
    }
    invariance = invariance_v4_losses(
        left_predictions,
        right_predictions,
        environments,
        inventory,
        smooth_l1_beta=smooth_l1_beta,
    )
    total = (
        supervised["physical"]
        + supervised["event"]
        + supervised["normative"]
        + consistency_lambda * (invariance["physical"] + invariance["event"])
    )
    return SlotObjectiveResult(
        total=total,
        physical_supervised=supervised["physical"],
        event_supervised=supervised["event"],
        normative_supervised=supervised["normative"],
        physical_invariance=invariance["physical"],
        event_invariance=invariance["event"],
    )


def decode_slot_predictions_v4(
    predictions: Mapping[str, Any],
    inventory: SlotInventory,
    continuous_statistics: Mapping[str, Mapping[str, float | int]],
    *,
    environment: str,
    row: int = 0,
    set_threshold: float = 0.5,
) -> dict[str, Any]:
    """Decode one role-query row to the unchanged strict output schema."""

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
            value = slot.values[int(torch.argmax(prediction[row]).item())]
        elif slot.kind == "set":
            probabilities = torch.sigmoid(prediction[row].float())
            value = [
                candidate
                for candidate, probability in zip(
                    slot.values, probabilities.tolist(), strict=True
                )
                if probability >= set_threshold
            ]
        else:
            stats = continuous_statistics[slot.path]
            decoded = float(stats["mean"]) + float(stats["standard_deviation"]) * float(
                prediction[row].item()
            )
            value = round(min(max(decoded, float(slot.minimum)), float(slot.maximum)), 6)
        _set_nested(output, slot.path, value)
    decision = output["normative_decision"]
    output["escalation_required"] = decision == "escalate"
    output["rollout"] = []
    return output


def gateway_v4_checks(
    metrics: Mapping[str, Any], thresholds: Mapping[str, Any]
) -> dict[str, bool]:
    """Reuse every repaired V3 ability gate and replace only its replay check."""

    bridged = dict(metrics)
    bridged["deterministic_prefix_replay"] = bool(
        metrics["deterministic_training_contract"]
    )
    checks = gateway_v3_checks(bridged, thresholds)
    checks["deterministic_training_contract"] = checks.pop(
        "deterministic_prefix_replay"
    )
    return checks
