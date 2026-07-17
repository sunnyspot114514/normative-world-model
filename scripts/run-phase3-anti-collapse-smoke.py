"""Run the frozen schema-native anti-collapse smoke on retained discovery."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import time
import tomllib
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, TaskType, get_peft_model
from safetensors.torch import save_file
from transformers import AutoModel, AutoTokenizer, set_seed

from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_metrics import score_one_step
from normative_world_model.phase3_comparison import (
    anti_collapse_checks,
    canonical_digest,
    compact_binding,
    evaluation_binding,
    pair_binding,
    select_balanced_evaluation_records,
    select_comparison_pairs,
)
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)
from normative_world_model.result_lock import (
    verify_phase3_schema_gate_result,
)
from normative_world_model.slot_objective import (
    decode_slot_predictions,
    load_slot_inventory,
    slot_objective,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("configs/phase3_retained_arm_comparison.toml")
SELECTION_LOCK_PATH = Path(
    "configs/phase3_retained_arm_selection_lock.json"
)
SMOKE_LOCK_PATH = Path("configs/phase3_anti_collapse_smoke_lock.json")
RESULT_PATH = Path(
    "artifacts/phase3_anti_collapse_smoke/result.json"
)
RUN_PATH = Path("runs/phase3_anti_collapse_smoke")
MODEL_MANIFEST_PATH = Path(
    "artifacts/phase3_internal/model_snapshot_manifest.json"
)
CONFIRMATION_PATH = Path(
    "data/generated/phase1_discovery_v3/confirmation_reservation.json"
)
SOURCE_HASH_PATHS = {
    "joint": Path(
        "data/generated/phase3_retained_schema_gate/arms/"
        "joint_one_step.jsonl.gz"
    ),
    "factorized_factual": Path(
        "data/generated/phase3_retained_schema_gate/arms/"
        "factorized_factual_one_step.jsonl.gz"
    ),
    "factorized_normative": Path(
        "data/generated/phase3_retained_schema_gate/arms/"
        "factorized_normative.jsonl.gz"
    ),
    "model_snapshot_manifest": MODEL_MANIFEST_PATH,
    "schema_gate_result_lock": Path(
        "configs/phase3_retained_schema_gate_result_lock.json"
    ),
    "estimand_amendment": Path("configs/phase3_estimand_amendment.json"),
    "selector_implementation": Path(
        "src/normative_world_model/phase3_comparison.py"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _load_config() -> dict[str, Any]:
    with (ROOT / CONFIG_PATH).open("rb") as handle:
        return tomllib.load(handle)


def _load_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _selection_state(
    config: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[Any], list[dict[str, Any]], dict[str, Any]]:
    selection = config["selection"]
    formal_pairs = select_comparison_pairs(
        records,
        seed=int(selection["pair_seed"]),
        maximum=int(selection["formal_training_pairs"]),
    )
    smoke_pairs = formal_pairs[: int(selection["smoke_training_pairs"])]
    schema_records = select_unique_development_records(records)
    schema_scenarios = {
        str(record["scenario_id"]) for record in schema_records
    }
    smoke_evaluation = select_balanced_evaluation_records(
        records,
        seed=int(selection["smoke_evaluation_seed"]),
        per_bucket=int(selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios,
    )
    smoke_scenarios = {
        str(record["scenario_id"]) for record in smoke_evaluation
    }
    formal_evaluation = select_balanced_evaluation_records(
        records,
        seed=int(selection["formal_evaluation_seed"]),
        per_bucket=int(selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios | smoke_scenarios,
    )
    state = {
        "schema_gate_consumed_development": {
            "count": len(schema_records),
            "scenario_order_sha256": canonical_digest(
                [record["scenario_id"] for record in schema_records]
            ),
        },
        "smoke_training": compact_binding(pair_binding(smoke_pairs)),
        "formal_training": compact_binding(pair_binding(formal_pairs)),
        "smoke_evaluation": compact_binding(
            evaluation_binding(smoke_evaluation)
        ),
        "formal_evaluation": compact_binding(
            evaluation_binding(formal_evaluation)
        ),
    }
    return smoke_pairs, smoke_evaluation, state


def _verify_model_snapshot(
    config: dict[str, Any],
    manifest: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    model_dir = ROOT / config["model"]["local_dir"]
    if manifest.get("status") != "PASS":
        failures.append("model snapshot manifest is not PASS")
    if manifest.get("resolved_revision") != config["model"]["revision"]:
        failures.append("model revision differs from the frozen comparison")
    for relative, metadata in manifest.get("files", {}).items():
        path = model_dir / relative
        if not path.is_file():
            failures.append(f"missing model file: {relative}")
        elif _sha256(path) != metadata.get("sha256"):
            failures.append(f"model file hash mismatch: {relative}")
    for package, expected in manifest.get("packages", {}).items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"missing model package: {package}")
            continue
        if actual != expected:
            failures.append(
                f"model package {package} is {actual}, expected {expected}"
            )
    return failures


def _uncommitted_bound_inputs(lock: dict[str, Any]) -> list[str]:
    paths = [*lock.get("bound_hashes", {}), SMOKE_LOCK_PATH.as_posix()]
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *paths],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify committed smoke inputs"]
    return [line for line in result.stdout.splitlines() if line]


def validate_inputs(*, require_committed: bool) -> list[str]:
    failures: list[str] = []
    try:
        config = _load_config()
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"invalid comparison config: {error}"]
    if config.get("status") != "frozen_before_phase3_anti_collapse_smoke":
        failures.append("comparison config is not frozen for the smoke")
    if not (ROOT / SMOKE_LOCK_PATH).is_file():
        return ["anti-collapse smoke lock is missing"]
    lock = _load_json(ROOT / SMOKE_LOCK_PATH)
    if lock.get("status") != "FROZEN_BEFORE_SMOKE":
        failures.append("anti-collapse smoke lock status is invalid")
    for relative, expected in lock.get("bound_hashes", {}).items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing smoke input: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"smoke input hash mismatch: {relative}")
    architecture = config.get("architecture", {})
    architecture_hashes = {
        Path(str(architecture.get("slot_inventory", ""))): architecture.get(
            "slot_inventory_sha256"
        ),
        Path(
            str(architecture.get("objective_implementation", ""))
        ): architecture.get("objective_implementation_sha256"),
    }
    for path, expected in architecture_hashes.items():
        absolute = ROOT / path
        if not path.as_posix() or not absolute.is_file():
            failures.append(f"missing architecture input: {path.as_posix()}")
        elif _sha256(absolute) != expected:
            failures.append(
                f"architecture hash mismatch: {path.as_posix()}"
            )
    source_hashes = config.get("source_hashes", {})
    if set(source_hashes) != set(SOURCE_HASH_PATHS):
        failures.append("comparison source hash keys are incomplete")
    for name, path in SOURCE_HASH_PATHS.items():
        absolute = ROOT / path
        if not absolute.is_file():
            failures.append(f"missing comparison source: {path.as_posix()}")
        elif source_hashes.get(name) != _sha256(absolute):
            failures.append(f"comparison source hash mismatch: {name}")
    try:
        selection_lock = _load_json(ROOT / SELECTION_LOCK_PATH)
        records = _load_records(ROOT / config["data"]["joint"])
        _, _, state = _selection_state(config, records)
        selection_expected = {
            "config_sha256": _sha256(ROOT / CONFIG_PATH),
            "joint_data_sha256": _sha256(
                ROOT / config["data"]["joint"]
            ),
            "selector_sha256": _sha256(
                ROOT / SOURCE_HASH_PATHS["selector_implementation"]
            ),
        }
        if selection_lock.get("status") != "PASS":
            failures.append("selection lock is not PASS")
        for name, expected in selection_expected.items():
            if selection_lock.get(name) != expected:
                failures.append(f"selection lock hash mismatch: {name}")
        for name, actual in state.items():
            if actual != selection_lock.get(name):
                failures.append(f"selection lock mismatch: {name}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        failures.append(f"cannot rebuild frozen selections: {error}")
    failures.extend(verify_phase3_schema_gate_result(ROOT))
    if (ROOT / MODEL_MANIFEST_PATH).is_file():
        failures.extend(
            _verify_model_snapshot(
                config,
                _load_json(ROOT / MODEL_MANIFEST_PATH),
            )
        )
    else:
        failures.append("model snapshot manifest is missing")
    if not (ROOT / CONFIRMATION_PATH).is_file():
        failures.append("confirmation reservation is missing")
    elif _load_json(ROOT / CONFIRMATION_PATH).get("status") != (
        "RESERVED_NOT_GENERATED"
    ):
        failures.append("confirmation is no longer safely reserved")
    if not torch.cuda.is_available():
        failures.append("frozen CUDA device is unavailable")
    if require_committed:
        failures.extend(_uncommitted_bound_inputs(lock))
    return failures


def _tokenizer(config: dict[str, Any]) -> Any:
    tokenizer = AutoTokenizer.from_pretrained(
        ROOT / config["model"]["local_dir"],
        local_files_only=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def _model(config: dict[str, Any]) -> Any:
    base = AutoModel.from_pretrained(
        ROOT / config["model"]["local_dir"],
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.float16,
        attn_implementation=config["model"]["attention_implementation"],
    ).to("cuda")
    base.config.use_cache = False
    if config["optimization"]["gradient_checkpointing"]:
        base.gradient_checkpointing_enable()
    lora = config["lora"]
    model = get_peft_model(
        base,
        LoraConfig(
            task_type=TaskType.FEATURE_EXTRACTION,
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            target_modules=list(lora["target_modules"]),
            bias="none",
        ),
    )
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    return model


def _prompt_batch(
    tokenizer: Any,
    texts: list[str],
    *,
    maximum: int,
) -> dict[str, Any]:
    encoded = tokenizer(
        [text.rstrip() + "\n" for text in texts],
        add_special_tokens=False,
        padding=True,
        return_tensors="pt",
    )
    if int(encoded["attention_mask"].sum(dim=1).max().item()) > maximum:
        raise ValueError("prompt exceeds frozen maximum token count")
    return {key: value.to("cuda") for key, value in encoded.items()}


def _prompt_hidden(model: Any, batch: dict[str, Any]) -> Any:
    output = model(**batch, use_cache=False, return_dict=True)
    hidden = output.last_hidden_state
    last = batch["attention_mask"].sum(dim=1).long() - 1
    return hidden[torch.arange(hidden.shape[0], device=hidden.device), last]


def _train(
    config: dict[str, Any],
    pairs: list[Any],
    tokenizer: Any,
    staging: Path,
) -> tuple[Any, Any, dict[str, Any]]:
    from normative_world_model.slot_objective import build_slot_head_bank

    optimization = config["optimization"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(
        bool(optimization["deterministic_algorithms"])
    )
    torch.backends.cudnn.benchmark = bool(
        optimization["cudnn_benchmark"]
    )
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    set_seed(int(optimization["seed"]))
    torch.cuda.empty_cache()
    model = _model(config)
    inventory = load_slot_inventory(ROOT / config["architecture"]["slot_inventory"])
    hidden_size = int(model.config.hidden_size)
    heads = build_slot_head_bank(hidden_size, inventory).to("cuda")
    model_parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    head_parameters = list(heads.parameters())
    optimizer = torch.optim.AdamW(
        [
            {
                "params": model_parameters,
                "lr": float(optimization["lora_learning_rate"]),
            },
            {
                "params": head_parameters,
                "lr": float(optimization["head_learning_rate"]),
            },
        ],
        weight_decay=float(optimization["weight_decay"]),
    )
    torch.cuda.reset_peak_memory_stats()
    losses: list[float] = []
    component_rows: list[dict[str, float]] = []
    prompt_tokens = 0
    steps = int(optimization["smoke_optimizer_steps"])
    started = time.perf_counter()
    model.train()
    heads.train()
    for step in range(steps):
        pair = pairs[step % len(pairs)]
        batch = _prompt_batch(
            tokenizer,
            [pair.left["input_text"], pair.right["input_text"]],
            maximum=int(config["data"]["max_prompt_tokens"]),
        )
        prompt_tokens += int(batch["attention_mask"].sum().item())
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            hidden = _prompt_hidden(model, batch)
            left_predictions = heads(hidden[0:1])
            right_predictions = heads(hidden[1:2])
            objective = slot_objective(
                left_predictions,
                right_predictions,
                [json.loads(pair.left["target_text"])],
                [json.loads(pair.right["target_text"])],
                [str(pair.left["environment"])],
                inventory,
                consistency_lambda=0.0,
            )
        if not torch.isfinite(objective.total):
            raise RuntimeError(f"non-finite smoke loss at step {step}")
        objective.total.backward()
        torch.nn.utils.clip_grad_norm_(
            [*model_parameters, *head_parameters],
            float(optimization["gradient_clip_norm"]),
        )
        optimizer.step()
        losses.append(float(objective.total.detach().cpu()))
        component_rows.append(
            {
                "physical": float(
                    objective.physical_supervised.detach().cpu()
                ),
                "event": float(objective.event_supervised.detach().cpu()),
                "normative": float(
                    objective.normative_supervised.detach().cpu()
                ),
            }
        )
        del batch, hidden, left_predictions, right_predictions, objective
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    peak = int(torch.cuda.max_memory_allocated())
    total_memory = int(torch.cuda.get_device_properties(0).total_memory)
    adapter = staging / "adapter"
    adapter.mkdir(parents=True)
    model.save_pretrained(adapter)
    head_path = staging / "slot_heads.safetensors"
    save_file(
        {
            name: value.detach().cpu().contiguous()
            for name, value in heads.state_dict().items()
        },
        head_path,
    )
    window = min(32, len(losses) // 2)
    first = sum(losses[:window]) / window
    last = sum(losses[-window:]) / window
    output_files = {
        (RUN_PATH / path.relative_to(staging)).as_posix(): _sha256(path)
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }
    training = {
        "optimizer_steps": steps,
        "unique_training_pairs": len(pairs),
        "prompt_tokens_seen": prompt_tokens,
        "loss_first_window_mean": first,
        "loss_last_window_mean": last,
        "loss_window_improvement_fraction": (first - last) / first,
        "loss_minimum": min(losses),
        "component_loss_last": component_rows[-1],
        "wall_clock_seconds": elapsed,
        "peak_allocated_bytes": peak,
        "device_total_memory_bytes": total_memory,
        "peak_allocated_fraction": peak / total_memory,
        "trainable_model_parameters": sum(
            parameter.numel() for parameter in model_parameters
        ),
        "trainable_head_parameters": sum(
            parameter.numel() for parameter in head_parameters
        ),
        "output_files": output_files,
        "cuda_device": torch.cuda.get_device_name(0),
    }
    return model, heads, training


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for component in path.split("."):
        current = current[component]
    return current


def _nonempty_physical(value: dict[str, Any]) -> bool:
    return any(
        bool(item) if isinstance(item, list) else item != 0
        for item in value.values()
    )


def _entropy(values: list[str]) -> float:
    counts = Counter(values)
    total = len(values)
    return -sum(
        (count / total) * math.log(count / total)
        for count in counts.values()
    )


def _evaluate(
    config: dict[str, Any],
    records: list[dict[str, Any]],
    tokenizer: Any,
    model: Any,
    heads: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inventory = load_slot_inventory(ROOT / config["architecture"]["slot_inventory"])
    model.gradient_checkpointing_disable()
    model.eval()
    heads.eval()
    rows: list[dict[str, Any]] = []
    values_by_slot: dict[str, list[str]] = defaultdict(list)
    continuous = [slot for slot in inventory.slots if slot.kind == "continuous"]
    with torch.inference_mode():
        for record in records:
            batch = _prompt_batch(
                tokenizer,
                [record["input_text"]],
                maximum=int(config["data"]["max_prompt_tokens"]),
            )
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                hidden = _prompt_hidden(model, batch)
                predictions = heads(hidden)
            decoded = decode_slot_predictions(
                predictions,
                inventory,
                environment=str(record["environment"]),
            )
            expected = json.loads(record["target_text"])
            text = json.dumps(
                decoded,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            parsed = parse_model_output(text, expected)
            score = score_one_step(
                parsed.output if parsed.ok else None,
                expected,
            )
            absolute_error = []
            zero_error = []
            for slot in continuous:
                predicted_value = float(_nested(decoded, slot.path))
                expected_value = float(_nested(expected, slot.path))
                absolute_error.append(abs(predicted_value - expected_value))
                zero_error.append(abs(expected_value))
            for slot in inventory.slots:
                if (
                    record["environment"] in slot.environments
                    and slot.kind in {"categorical", "set"}
                ):
                    values_by_slot[slot.path].append(
                        json.dumps(
                            _nested(decoded, slot.path),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
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
                    "nonempty_physical_delta": _nonempty_physical(
                        decoded["physical_delta"]
                    ),
                    "nonzero_impact": any(
                        abs(float(value))
                        > float(
                            config["anti_collapse_smoke"][
                                "impact_activity_absolute_threshold"
                            ]
                        )
                        for value in decoded["event_record"][
                            "impact_vector"
                        ].values()
                    ),
                    "continuous_absolute_error_mean": (
                        sum(absolute_error) / len(absolute_error)
                    ),
                    "continuous_zero_error_mean": (
                        sum(zero_error) / len(zero_error)
                    ),
                    "prediction": decoded,
                }
            )
            del batch, hidden, predictions
    count = len(rows)
    decisions = Counter(row["predicted_decision"] for row in rows)
    model_mae = sum(
        row["continuous_absolute_error_mean"] for row in rows
    ) / count
    zero_mae = sum(row["continuous_zero_error_mean"] for row in rows) / count
    entropies = {path: _entropy(values) for path, values in values_by_slot.items()}
    metrics: dict[str, Any] = {
        "evaluation_records": count,
        "strict_schema_coverage": sum(row["parse_ok"] for row in rows) / count,
        "normative_accuracy": sum(
            row["normative_correct"] for row in rows
        )
        / count,
        "predicted_decision_counts": dict(sorted(decisions.items())),
        "maximum_predicted_decision_share": max(decisions.values()) / count,
        "rows_with_nonzero_impact_fraction": sum(
            row["nonzero_impact"] for row in rows
        )
        / count,
        "nonempty_physical_delta_fraction": sum(
            row["nonempty_physical_delta"] for row in rows
        )
        / count,
        "event_continuous_mae": model_mae,
        "event_zero_predictor_mae": zero_mae,
        "event_mae_improvement_over_zero": zero_mae - model_mae,
        "mean_physical_field_f1": sum(
            row["physical_field_f1"] for row in rows
        )
        / count,
        "mean_event_field_f1": sum(
            row["event_field_f1"] for row in rows
        )
        / count,
        "categorical_constant_slot_fraction": sum(
            len(set(values)) == 1 for values in values_by_slot.values()
        )
        / len(values_by_slot),
        "categorical_output_entropy_by_slot": entropies,
    }
    return metrics, rows


def _promote(staging: Path, report_path: Path) -> None:
    final_run = ROOT / RUN_PATH
    final_report = ROOT / RESULT_PATH
    if final_run.exists() or final_report.exists():
        raise FileExistsError("anti-collapse smoke outputs already exist")
    final_run.parent.mkdir(parents=True, exist_ok=True)
    final_report.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final_run)
    final_report.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(report_path, final_report)
    except OSError:
        if final_run.exists() and not staging.exists():
            os.replace(final_run, staging)
        raise


def run_smoke() -> dict[str, Any]:
    failures = validate_inputs(require_committed=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    if (ROOT / RUN_PATH).exists() or (ROOT / RESULT_PATH).exists():
        raise FileExistsError("anti-collapse smoke outputs already exist")
    config = _load_config()
    records = _load_records(ROOT / config["data"]["joint"])
    pairs, evaluation_records, selection_state = _selection_state(
        config,
        records,
    )
    tokenizer = _tokenizer(config)
    staging_root = ROOT / ".tmp/phase3_anti_collapse_smoke" / uuid.uuid4().hex
    staging_run = staging_root / "run"
    staging_run.mkdir(parents=True)
    model, heads, training = _train(
        config,
        pairs,
        tokenizer,
        staging_run,
    )
    evaluation, rows = _evaluate(
        config,
        evaluation_records,
        tokenizer,
        model,
        heads,
    )
    evaluation["loss_window_improvement_fraction"] = training[
        "loss_window_improvement_fraction"
    ]
    evaluation["resource_status_pass"] = training[
        "peak_allocated_fraction"
    ] <= float(config["optimization"]["maximum_peak_memory_fraction"])
    gate = anti_collapse_checks(
        evaluation,
        config["anti_collapse_smoke"],
    )
    status = "PASS" if all(gate.values()) else "BLOCKED"
    del model, heads
    gc.collect()
    torch.cuda.empty_cache()
    lock = _load_json(ROOT / SMOKE_LOCK_PATH)
    report = {
        "status": status,
        "run_kind": "phase3_retained_discovery_anti_collapse_smoke",
        "scientific_arm_comparison": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "git_head_before_execution": _git_head(),
        "selection": {
            "smoke_training": selection_state["smoke_training"],
            "smoke_evaluation": selection_state["smoke_evaluation"],
        },
        "training": training,
        "evaluation": evaluation,
        "gate_checks": gate,
        "thresholds": config["anti_collapse_smoke"],
        "rows": rows,
        "bound_hashes": lock["bound_hashes"],
        "next_action": (
            "freeze_and_run_formal_one_step_arm_comparison"
            if status == "PASS"
            else config["anti_collapse_smoke"]["failure_action"]
        ),
    }
    staging_report = staging_root / "result.json"
    staging_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
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
        "failures": [name for name, passed in gate.items() if not passed],
        "result_path": RESULT_PATH.as_posix(),
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
            result = run_smoke()
        except (FileExistsError, OSError, RuntimeError, ValueError) as error:
            result = {"status": "FAIL", "failures": [str(error)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
