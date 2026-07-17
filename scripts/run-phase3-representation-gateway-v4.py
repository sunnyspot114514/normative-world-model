"""Run the frozen role-query Phase-3 V4 engineering gateway."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import time
import tomllib
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any

import torch
from safetensors.torch import save_file
from transformers import set_seed

from normative_world_model.gateway_v3_result_lock import (
    verify_phase3_diversity_gateway_v3_result,
)
from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_metrics import score_one_step
from normative_world_model.phase3_gateway import (
    build_training_constant_baselines,
    normative_recall_by_class,
    score_training_constant_baselines,
)
from normative_world_model.phase3_gateway_v4 import (
    ROLE_ORDER,
    build_continuous_statistics,
    build_normative_class_weights,
    build_role_query_head_bank,
    decode_slot_predictions_v4,
    gateway_v4_checks,
    role_query_batch,
    role_query_hidden,
    slot_objective_v4,
)
from normative_world_model.slot_objective import load_slot_inventory

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("configs/phase3_representation_gateway_v4.toml")
SELECTION_LOCK_PATH = Path(
    "configs/phase3_representation_gateway_v4_selection_lock.json"
)
INPUT_LOCK_PATH = Path("configs/phase3_representation_gateway_v4_input_lock.json")
BASE_CONFIG_PATH = Path("configs/phase3_retained_arm_comparison.toml")
V3_CONFIG_PATH = Path("configs/phase3_diversity_gateway_v3.toml")
V3_RESULT_LOCK_PATH = Path("configs/phase3_diversity_gateway_v3_result_lock.json")
RESULT_PATH = Path("artifacts/phase3_representation_gateway_v4/result.json")
RUN_PATH = Path("runs/phase3_representation_gateway_v4")
FORMAL_RUN_PATH = Path("runs/phase3_retained_arm_comparison")
FORMAL_RESULT_PATH = Path("artifacts/phase3_retained_arm_comparison")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one object")
    return value


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _load_script(relative: str, name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _v1_runner() -> ModuleType:
    return _load_script("scripts/run-phase3-anti-collapse-smoke.py", "_nwm_v4_v1")


def _selection_builder() -> ModuleType:
    return _load_script(
        "scripts/build-phase3-representation-gateway-v4-selection-lock.py",
        "_nwm_v4_selection",
    )


def _git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _markers(config: dict[str, Any]) -> dict[str, str]:
    representation = config["representation"]
    return {
        "physical": str(representation["physical_query_marker"]),
        "event": str(representation["event_query_marker"]),
        "normative": str(representation["normative_query_marker"]),
    }


def _marker_audit(
    config: dict[str, Any],
    tokenizer: Any,
    pairs: list[Any],
    evaluation: list[dict[str, Any]],
) -> dict[str, Any]:
    texts = [
        str(record["input_text"])
        for pair in pairs
        for record in (pair.left, pair.right)
    ] + [str(record["input_text"]) for record in evaluation]
    maximum = int(config["representation"]["max_prompt_plus_suffix_tokens"])
    markers = _markers(config)
    lengths: list[int] = []
    position_rows: list[list[int]] = []
    batch_size = 128
    for offset in range(0, len(texts), batch_size):
        batch = role_query_batch(
            tokenizer,
            texts[offset : offset + batch_size],
            maximum=maximum,
            markers=markers,
            device=None,
        )
        lengths.extend(int(value) for value in batch["attention_mask"].sum(dim=1))
        position_rows.extend(batch["query_positions"].tolist())
    preimage = json.dumps(
        {"lengths": lengths, "positions": position_rows},
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "presentation_count": len(texts),
        "training_presentation_count": 2 * len(pairs),
        "evaluation_presentation_count": len(evaluation),
        "maximum_prompt_plus_suffix_tokens": max(lengths),
        "minimum_prompt_plus_suffix_tokens": min(lengths),
        "length_and_query_position_sha256": hashlib.sha256(preimage).hexdigest(),
        "reserved_marker_occurrences_in_source": 0,
        "truncated_presentations": 0,
    }


def _verify_hash_map(values: object) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["V4 bound hash map is missing"]
    failures = []
    for relative, expected in values.items():
        path = ROOT / str(relative)
        if not path.is_file():
            failures.append(f"missing V4 input: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"V4 input hash mismatch: {relative}")
    return failures


def _uncommitted_inputs(lock: dict[str, Any]) -> list[str]:
    paths = [*lock.get("bound_hashes", {}), INPUT_LOCK_PATH.as_posix()]
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *paths],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify committed V4 inputs"]
    return [line for line in result.stdout.splitlines() if line]


def _threshold_equivalence(
    config: dict[str, Any], v3: dict[str, Any]
) -> list[str]:
    keys = (
        "fixed_training_probe_pairs",
        "minimum_fixed_probe_loss_improvement_fraction",
        "minimum_normative_accuracy",
        "minimum_normative_recall_per_class",
        "maximum_single_predicted_decision_share",
        "impact_activity_absolute_threshold",
        "minimum_rows_with_nonzero_impact_fraction",
        "minimum_nonempty_physical_delta_fraction",
        "minimum_event_mae_improvement_over_training_constant",
        "minimum_physical_field_f1_improvement_over_training_constant",
        "minimum_event_field_f1_improvement_over_training_constant",
        "require_strict_schema_coverage",
        "maximum_peak_memory_fraction",
    )
    return [
        f"V4 gate differs from repaired V3 gate: {key}"
        for key in keys
        if config["gate"].get(key) != v3["gate"].get(key)
    ]


def validate_inputs(*, require_committed: bool) -> list[str]:
    failures = verify_phase3_diversity_gateway_v3_result(ROOT)
    try:
        config = _load_toml(ROOT / CONFIG_PATH)
        base = _load_toml(ROOT / BASE_CONFIG_PATH)
        v3 = _load_toml(ROOT / V3_CONFIG_PATH)
        selection_lock = _load_json(ROOT / SELECTION_LOCK_PATH)
        input_lock = _load_json(ROOT / INPUT_LOCK_PATH)
    except (OSError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        return [*failures, f"cannot load V4 contracts: {error}"]
    if config.get("status") != "frozen_before_phase3_representation_gateway_v4":
        failures.append("V4 config is not frozen")
    v3_result = _load_json(ROOT / V3_RESULT_LOCK_PATH)
    if v3_result.get("status") != "BLOCKED":
        failures.append("V3 is not preserved as BLOCKED")
    for name in (
        "comparison_config",
        "comparison_selection_lock",
        "v3_config",
        "v3_selection_lock",
        "v3_result_lock",
    ):
        relative = config["base_contract"].get(name)
        expected = config["base_contract"].get(f"{name}_sha256")
        path = ROOT / str(relative)
        if not isinstance(relative, str) or not path.is_file():
            failures.append(f"missing V4 base contract: {name}")
        elif _sha256(path) != expected:
            failures.append(f"V4 base-contract hash mismatch: {name}")
    try:
        rebuilt = _selection_builder().build_lock()
        if rebuilt != selection_lock:
            failures.append("V4 selection lock differs from deterministic rebuild")
    except (OSError, RuntimeError, ValueError) as error:
        failures.append(f"cannot rebuild V4 selection lock: {error}")
    if selection_lock.get("status") != "PASS":
        failures.append("V4 selection lock is not PASS")
    if not all(selection_lock.get("checks", {}).values()):
        failures.append("V4 selection lock contains a failed check")
    failures.extend(_threshold_equivalence(config, v3))
    if input_lock.get("status") != "FROZEN_BEFORE_V4_EXECUTION":
        failures.append("V4 execution input lock status is invalid")
    failures.extend(_verify_hash_map(input_lock.get("bound_hashes")))
    if input_lock.get("selection_lock_sha256") != _sha256(ROOT / SELECTION_LOCK_PATH):
        failures.append("V4 selection/input lock hash mismatch")
    if input_lock.get("training_order_sha256") != selection_lock.get(
        "formal_training", {}
    ).get("order_sha256"):
        failures.append("V4 input lock training order mismatch")
    if input_lock.get("evaluation_order_sha256") != selection_lock.get(
        "v4_evaluation", {}
    ).get("order_sha256"):
        failures.append("V4 input lock evaluation order mismatch")
    if input_lock.get("continuous_statistics_sha256") != selection_lock.get(
        "continuous_statistics_sha256"
    ):
        failures.append("V4 input lock continuous-statistics mismatch")
    if input_lock.get("normative_class_weights_sha256") != selection_lock.get(
        "normative_class_weights_sha256"
    ):
        failures.append("V4 input lock normative-weight mismatch")
    if tuple(config["representation"].get("query_role_order", ())) != ROLE_ORDER:
        failures.append("V4 query role order differs from executable contract")
    if int(config["training"]["unique_pairs"]) != 1024:
        failures.append("V4 training pair count is not 1024")
    if int(config["training"]["optimizer_steps"]) != 1024:
        failures.append("V4 optimizer step count is not 1024")
    if float(config["training"]["consistency_lambda"]) != 0.0:
        failures.append("V4 engineering gateway must use consistency lambda zero")
    frozen_training = input_lock.get("training", {})
    if frozen_training != {
        "unique_pairs": int(config["training"]["unique_pairs"]),
        "optimizer_steps": int(config["training"]["optimizer_steps"]),
        "consistency_lambda": float(config["training"]["consistency_lambda"]),
        "fixed_probe_pairs": int(config["gate"]["fixed_training_probe_pairs"]),
    }:
        failures.append("V4 input-lock training contract mismatch")
    governance = input_lock.get("governance", {})
    if not (
        governance.get("v3_status_remains") == "BLOCKED"
        and governance.get("formal_evaluation_may_not_be_opened_by_v4") is True
        and governance.get("confirmation_generation_authorized") is False
        and governance.get("no_fifth_diagnostic_population") is True
        and governance.get("pass_requires_a_separate_formal_runner_freeze") is True
        and input_lock.get("formal_arm_comparison_started") is False
        and input_lock.get("confirmation_status") == "RESERVED_NOT_GENERATED"
    ):
        failures.append("V4 input-lock governance boundary is invalid")
    if require_committed:
        failures.extend(_uncommitted_inputs(input_lock))
    if (ROOT / FORMAL_RUN_PATH).exists() or (ROOT / FORMAL_RESULT_PATH).exists():
        failures.append("formal comparison exists before V4 gateway")
    if (ROOT / RUN_PATH).exists() or (ROOT / RESULT_PATH).exists():
        failures.append("V4 gateway output already exists")
    if not torch.cuda.is_available():
        failures.append("frozen CUDA device is unavailable")
    if failures:
        return failures
    pairs, evaluation = _selection_builder().select_v4_populations()
    tokenizer = _v1_runner()._tokenizer(base)
    actual_audit = _marker_audit(config, tokenizer, pairs, evaluation)
    if actual_audit != input_lock.get("marker_audit"):
        failures.append("V4 marker/token audit differs from frozen input lock")
    return failures


def _objective(
    config: dict[str, Any],
    inventory: Any,
    statistics: dict[str, Any],
    weights: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
    pair: Any,
) -> Any:
    return slot_objective_v4(
        left,
        right,
        [json.loads(str(pair.left["target_text"]))],
        [json.loads(str(pair.right["target_text"]))],
        [str(pair.left["environment"])],
        inventory,
        statistics,
        weights,
        smooth_l1_beta=float(config["continuous_objective"]["smooth_l1_beta_z_units"]),
        consistency_lambda=float(config["training"]["consistency_lambda"]),
    )


def _probe_loss(
    config: dict[str, Any],
    pairs: list[Any],
    tokenizer: Any,
    model: Any,
    heads: Any,
    inventory: Any,
    statistics: dict[str, Any],
    weights: dict[str, Any],
) -> float:
    was_model_training = model.training
    was_heads_training = heads.training
    model.eval()
    heads.eval()
    losses = []
    with torch.inference_mode():
        for pair in pairs:
            batch = role_query_batch(
                tokenizer,
                [str(pair.left["input_text"]), str(pair.right["input_text"])],
                maximum=int(config["representation"]["max_prompt_plus_suffix_tokens"]),
                markers=_markers(config),
                device="cuda",
            )
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                hidden = role_query_hidden(model, batch)
                predictions = heads(hidden)
                objective = _objective(
                    config,
                    inventory,
                    statistics,
                    weights,
                    {path: value[0:1] for path, value in predictions.items()},
                    {path: value[1:2] for path, value in predictions.items()},
                    pair,
                )
            losses.append(float(objective.total.detach().cpu()))
            del batch, hidden, predictions, objective
    model.train(was_model_training)
    heads.train(was_heads_training)
    return sum(losses) / len(losses)


def _train(
    config: dict[str, Any],
    base: dict[str, Any],
    pairs: list[Any],
    tokenizer: Any,
    staging: Path,
    statistics: dict[str, Any],
    weights: dict[str, Any],
) -> tuple[Any, Any, dict[str, Any]]:
    optimization = base["optimization"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(bool(optimization["deterministic_algorithms"]))
    torch.backends.cudnn.benchmark = bool(optimization["cudnn_benchmark"])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    set_seed(int(config["model"]["initialization_seed"]))
    torch.cuda.empty_cache()
    model = _v1_runner()._model(base)
    inventory = load_slot_inventory(ROOT / config["representation"]["slot_inventory"])
    if int(model.config.hidden_size) != int(config["representation"]["hidden_size"]):
        raise ValueError("model hidden size differs from V4 contract")
    heads = build_role_query_head_bank(
        int(model.config.hidden_size),
        int(config["representation"]["role_trunk_width"]),
        inventory,
    ).to("cuda")
    model_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    head_parameters = list(heads.parameters())
    optimizer = torch.optim.AdamW(
        [
            {
                "params": model_parameters,
                "lr": float(config["training"]["lora_learning_rate"]),
            },
            {
                "params": head_parameters,
                "lr": float(config["training"]["head_learning_rate"]),
            },
        ],
        weight_decay=float(config["training"]["weight_decay"]),
    )
    probe_pairs = pairs[: int(config["gate"]["fixed_training_probe_pairs"])]
    probe_before = _probe_loss(
        config, pairs=probe_pairs, tokenizer=tokenizer, model=model, heads=heads,
        inventory=inventory, statistics=statistics, weights=weights
    )
    torch.cuda.reset_peak_memory_stats()
    losses: list[float] = []
    component_rows: list[dict[str, float]] = []
    prompt_tokens = 0
    if len(pairs) != int(config["training"]["optimizer_steps"]):
        raise ValueError("V4 requires one optimizer step per unique pair")
    started = time.perf_counter()
    model.train()
    heads.train()
    for step, pair in enumerate(pairs):
        batch = role_query_batch(
            tokenizer,
            [str(pair.left["input_text"]), str(pair.right["input_text"])],
            maximum=int(config["representation"]["max_prompt_plus_suffix_tokens"]),
            markers=_markers(config),
            device="cuda",
        )
        prompt_tokens += int(batch["attention_mask"].sum().item())
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            hidden = role_query_hidden(model, batch)
            predictions = heads(hidden)
            objective = _objective(
                config,
                inventory,
                statistics,
                weights,
                {path: value[0:1] for path, value in predictions.items()},
                {path: value[1:2] for path, value in predictions.items()},
                pair,
            )
        if not torch.isfinite(objective.total):
            raise RuntimeError(f"non-finite V4 loss at step {step}")
        objective.total.backward()
        torch.nn.utils.clip_grad_norm_(
            [*model_parameters, *head_parameters],
            float(config["training"]["gradient_clip_norm"]),
        )
        optimizer.step()
        losses.append(float(objective.total.detach().cpu()))
        component_rows.append(
            {
                "physical": float(objective.physical_supervised.detach().cpu()),
                "event": float(objective.event_supervised.detach().cpu()),
                "normative": float(objective.normative_supervised.detach().cpu()),
            }
        )
        del batch, hidden, predictions, objective
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    probe_after = _probe_loss(
        config, pairs=probe_pairs, tokenizer=tokenizer, model=model, heads=heads,
        inventory=inventory, statistics=statistics, weights=weights
    )
    peak = int(torch.cuda.max_memory_allocated())
    total_memory = int(torch.cuda.get_device_properties(0).total_memory)
    adapter = staging / "adapter"
    adapter.mkdir(parents=True)
    model.save_pretrained(adapter)
    save_file(
        {
            name: value.detach().cpu().contiguous()
            for name, value in heads.state_dict().items()
        },
        staging / "role_query_heads.safetensors",
    )
    training_contract = {
        "continuous_statistics": statistics,
        "normative_class_weights": weights,
    }
    (staging / "training_contract.json").write_text(
        json.dumps(training_contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return model, heads, {
        "optimizer_steps": len(pairs),
        "unique_training_pairs": len(pairs),
        "training_epochs": 1,
        "prompt_tokens_seen_including_query_suffix": prompt_tokens,
        "fixed_probe_pairs": len(probe_pairs),
        "fixed_probe_loss_before": probe_before,
        "fixed_probe_loss_after": probe_after,
        "fixed_probe_loss_improvement_fraction": (probe_before - probe_after) / probe_before,
        "online_loss_first_window_mean": sum(losses[:32]) / 32,
        "online_loss_last_window_mean": sum(losses[-32:]) / 32,
        "loss_minimum": min(losses),
        "component_loss_last": component_rows[-1],
        "wall_clock_seconds": elapsed,
        "peak_allocated_bytes": peak,
        "device_total_memory_bytes": total_memory,
        "peak_allocated_fraction": peak / total_memory,
        "trainable_model_parameters": sum(p.numel() for p in model_parameters),
        "trainable_head_parameters": sum(p.numel() for p in head_parameters),
        "cuda_device": torch.cuda.get_device_name(0),
    }


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for component in path.split("."):
        current = current[component]
    return current


def _nonempty_physical(value: dict[str, Any]) -> bool:
    return any(bool(item) if isinstance(item, list) else item != 0 for item in value.values())


def _entropy(values: list[str]) -> float:
    counts = Counter(values)
    total = len(values)
    return -sum((count / total) * math.log(count / total) for count in counts.values())


def _evaluate(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    tokenizer: Any,
    model: Any,
    heads: Any,
    inventory: Any,
    statistics: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model.gradient_checkpointing_disable()
    model.eval()
    heads.eval()
    rows: list[dict[str, Any]] = []
    values_by_slot: dict[str, list[str]] = defaultdict(list)
    continuous = [slot for slot in inventory.slots if slot.kind == "continuous"]
    with torch.inference_mode():
        for record in records:
            batch = role_query_batch(
                tokenizer,
                [str(record["input_text"])],
                maximum=int(config["representation"]["max_prompt_plus_suffix_tokens"]),
                markers=_markers(config),
                device="cuda",
            )
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                hidden = role_query_hidden(model, batch)
                predictions = heads(hidden)
            decoded = decode_slot_predictions_v4(
                predictions,
                inventory,
                statistics,
                environment=str(record["environment"]),
            )
            expected = json.loads(str(record["target_text"]))
            text = json.dumps(
                decoded,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            parsed = parse_model_output(text, expected)
            score = score_one_step(parsed.output if parsed.ok else None, expected)
            absolute_error = [
                abs(float(_nested(decoded, slot.path)) - float(_nested(expected, slot.path)))
                for slot in continuous
            ]
            zero_error = [abs(float(_nested(expected, slot.path))) for slot in continuous]
            for slot in inventory.slots:
                if (
                    record["environment"] in slot.environments
                    and slot.kind in {"categorical", "set"}
                ):
                    values_by_slot[slot.path].append(
                        json.dumps(_nested(decoded, slot.path), ensure_ascii=False, sort_keys=True)
                    )
            rows.append(
                {
                    "record_id": record["record_id"],
                    "scenario_id": record["scenario_id"],
                    "environment": record["environment"],
                    "input_condition": record["input_condition"],
                    "profile_id": record["profile_id"],
                    "target_decision": expected["normative_decision"],
                    "predicted_decision": decoded["normative_decision"],
                    "parse_ok": parsed.ok,
                    "physical_field_f1": score.physical.f1,
                    "event_field_f1": score.event_record.f1,
                    "normative_correct": score.normative_correct,
                    "nonempty_physical_delta": _nonempty_physical(decoded["physical_delta"]),
                    "nonzero_impact": any(
                        abs(float(value))
                        > float(config["gate"]["impact_activity_absolute_threshold"])
                        for value in decoded["event_record"]["impact_vector"].values()
                    ),
                    "continuous_absolute_error_mean": sum(absolute_error) / len(absolute_error),
                    "continuous_zero_error_mean": sum(zero_error) / len(zero_error),
                    "prediction": decoded,
                }
            )
            del batch, hidden, predictions
    count = len(rows)
    decisions = Counter(row["predicted_decision"] for row in rows)
    model_mae = sum(row["continuous_absolute_error_mean"] for row in rows) / count
    zero_mae = sum(row["continuous_zero_error_mean"] for row in rows) / count
    return {
        "evaluation_records": count,
        "strict_schema_coverage": sum(row["parse_ok"] for row in rows) / count,
        "normative_accuracy": sum(row["normative_correct"] for row in rows) / count,
        "predicted_decision_counts": dict(sorted(decisions.items())),
        "maximum_predicted_decision_share": max(decisions.values()) / count,
        "rows_with_nonzero_impact_fraction": (
            sum(row["nonzero_impact"] for row in rows) / count
        ),
        "nonempty_physical_delta_fraction": (
            sum(row["nonempty_physical_delta"] for row in rows) / count
        ),
        "event_continuous_mae": model_mae,
        "event_zero_predictor_mae": zero_mae,
        "event_mae_improvement_over_zero": zero_mae - model_mae,
        "mean_physical_field_f1": (
            sum(row["physical_field_f1"] for row in rows) / count
        ),
        "mean_event_field_f1": sum(row["event_field_f1"] for row in rows) / count,
        "categorical_constant_slot_fraction": (
            sum(len(set(values)) == 1 for values in values_by_slot.values())
            / len(values_by_slot)
        ),
        "categorical_output_entropy_by_slot": {
            path: _entropy(values) for path, values in values_by_slot.items()
        },
    }, rows


def _run_file_hashes(staging: Path) -> dict[str, str]:
    return {
        (RUN_PATH / path.relative_to(staging)).as_posix(): _sha256(path)
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }


def _promote(staging_run: Path, staging_report: Path) -> None:
    final_run = ROOT / RUN_PATH
    final_report = ROOT / RESULT_PATH
    if final_run.exists() or final_report.exists():
        raise FileExistsError("V4 gateway outputs already exist")
    final_run.parent.mkdir(parents=True, exist_ok=True)
    final_report.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_run, final_run)
    try:
        os.replace(staging_report, final_report)
    except OSError:
        if final_run.exists() and not staging_run.exists():
            os.replace(final_run, staging_run)
        raise


def run_gateway() -> dict[str, Any]:
    failures = validate_inputs(require_committed=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    config = _load_toml(ROOT / CONFIG_PATH)
    base = _load_toml(ROOT / BASE_CONFIG_PATH)
    selection_lock = _load_json(ROOT / SELECTION_LOCK_PATH)
    input_lock = _load_json(ROOT / INPUT_LOCK_PATH)
    pairs, evaluation_records = _selection_builder().select_v4_populations()
    v1 = _v1_runner()
    tokenizer = v1._tokenizer(base)
    inventory = load_slot_inventory(ROOT / config["representation"]["slot_inventory"])
    statistics = build_continuous_statistics(
        pairs,
        inventory,
        standard_deviation_floor=float(
            config["continuous_objective"]["standard_deviation_floor"]
        ),
    )
    weights = build_normative_class_weights(
        pairs,
        inventory,
        exponent=float(config["normative_weighting"]["raw_exponent"]),
        cap=float(config["normative_weighting"]["pre_renormalization_cap"]),
    )
    if statistics != selection_lock["continuous_statistics"]:
        raise RuntimeError("training continuous statistics differ from selection lock")
    if weights != selection_lock["normative_class_weights"]:
        raise RuntimeError("training normative weights differ from selection lock")
    baselines = build_training_constant_baselines(pairs, inventory)
    staging_root = ROOT / ".tmp/phase3_representation_gateway_v4" / uuid.uuid4().hex
    staging_run = staging_root / "run"
    staging_run.mkdir(parents=True)
    model, heads, training = _train(
        config, base, pairs, tokenizer, staging_run, statistics, weights
    )
    training["output_files"] = _run_file_hashes(staging_run)
    evaluation, rows = _evaluate(
        config,
        evaluation_records,
        tokenizer,
        model,
        heads,
        inventory,
        statistics,
    )
    baseline_metrics = score_training_constant_baselines(
        evaluation_records, baselines, inventory
    )
    evaluation.update(baseline_metrics)
    recalls = normative_recall_by_class(rows)
    evaluation["normative_recall_by_class"] = recalls
    evaluation["minimum_normative_recall"] = min(recalls.values())
    evaluation["event_mae_improvement_over_training_constant"] = (
        baseline_metrics["training_constant_event_continuous_mae"]
        - evaluation["event_continuous_mae"]
    )
    evaluation["physical_field_f1_improvement_over_training_constant"] = (
        evaluation["mean_physical_field_f1"]
        - baseline_metrics["training_constant_physical_field_f1"]
    )
    evaluation["event_field_f1_improvement_over_training_constant"] = (
        evaluation["mean_event_field_f1"]
        - baseline_metrics["training_constant_event_field_f1"]
    )
    evaluation["fixed_probe_loss_improvement_fraction"] = training[
        "fixed_probe_loss_improvement_fraction"
    ]
    evaluation["resource_status_pass"] = training["peak_allocated_fraction"] <= float(
        config["gate"]["maximum_peak_memory_fraction"]
    )
    evaluation["deterministic_training_contract"] = True
    checks = gateway_v4_checks(evaluation, config["gate"])
    status = "PASS" if all(checks.values()) else "BLOCKED"
    del model, heads
    gc.collect()
    torch.cuda.empty_cache()
    report = {
        "status": status,
        "run_kind": config["run_kind"],
        "scientific_arm_comparison": False,
        "mechanism_attribution": False,
        "v1_status_preserved": "BLOCKED",
        "v2_status_preserved": "BLOCKED",
        "v3_status_preserved": "BLOCKED",
        "git_head_before_execution": _git_head(),
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "selection": {
            "formal_training": selection_lock["formal_training"],
            "v4_evaluation": selection_lock["v4_evaluation"],
        },
        "training_contract": {
            "continuous_statistics": statistics,
            "normative_class_weights": weights,
            "marker_audit": input_lock["marker_audit"],
        },
        "training": training,
        "training_constant_baselines": baselines,
        "evaluation": evaluation,
        "gate_checks": checks,
        "thresholds": config["gate"],
        "rows": rows,
        "bound_hashes": input_lock["bound_hashes"],
        "formal_arm_comparison_started": False,
        "next_action": (
            "preserve_candidate_and_freeze_separate_formal_runner"
            if status == "PASS"
            else "terminate_local_qwen3_1_7b_path_as_engineering_null"
        ),
    }
    staging_report = staging_root / "result.json"
    staging_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _promote(staging_run, staging_report)
    try:
        staging_root.rmdir()
        staging_root.parent.rmdir()
    except OSError:
        pass
    return {
        "status": status,
        "failures": [name for name, passed in checks.items() if not passed],
        "result_path": RESULT_PATH.as_posix(),
        "formal_arm_comparison_started": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validate", "run"), default="validate")
    args = parser.parse_args()
    if args.mode == "validate":
        failures = validate_inputs(require_committed=False)
        result = {
            "status": "PASS" if not failures else "FAIL",
            "failures": failures,
            "training_started": False,
        }
    else:
        try:
            result = run_gateway()
        except (FileExistsError, OSError, RuntimeError, ValueError) as error:
            result = {"status": "FAIL", "failures": [str(error)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
