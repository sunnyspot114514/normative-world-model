"""Run the repaired full-diversity Phase-3 engineering gateway."""

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
from pathlib import Path
from types import ModuleType
from typing import Any

import torch
from safetensors.torch import save_file
from transformers import set_seed

from normative_world_model.phase3_comparison import (
    compact_binding,
    evaluation_binding,
    pair_binding,
    select_balanced_evaluation_records,
    select_comparison_pairs,
)
from normative_world_model.phase3_gateway import (
    build_training_constant_baselines,
    gateway_v3_checks,
    normative_recall_by_class,
    score_training_constant_baselines,
)
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)
from normative_world_model.slot_objective import (
    build_slot_head_bank,
    load_slot_inventory,
    slot_objective,
)
from normative_world_model.smoke_v2_result_lock import (
    verify_phase3_anti_collapse_smoke_v2_result,
)

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_CONFIG_PATH = Path("configs/phase3_diversity_gateway_v3.toml")
GATEWAY_SELECTION_PATH = Path(
    "configs/phase3_diversity_gateway_v3_selection_lock.json"
)
GATEWAY_INPUT_LOCK_PATH = Path(
    "configs/phase3_diversity_gateway_v3_input_lock.json"
)
BASE_CONFIG_PATH = Path("configs/phase3_retained_arm_comparison.toml")
BASE_SELECTION_PATH = Path("configs/phase3_retained_arm_selection_lock.json")
V2_SELECTION_PATH = Path(
    "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"
)
V1_RESULT_LOCK_PATH = Path(
    "configs/phase3_anti_collapse_smoke_result_lock.json"
)
RESULT_PATH = Path("artifacts/phase3_diversity_gateway_v3/result.json")
RUN_PATH = Path("runs/phase3_diversity_gateway_v3")
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
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _load_v1_runner() -> ModuleType:
    path = ROOT / "scripts/run-phase3-anti-collapse-smoke.py"
    spec = importlib.util.spec_from_file_location("_nwm_gateway_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the locked v1 smoke runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _selections(
    gateway: dict[str, Any],
    base: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[Any], list[dict[str, Any]], dict[str, Any]]:
    pairs = select_comparison_pairs(
        records,
        seed=int(gateway["training"]["pair_seed"]),
        maximum=int(gateway["training"]["unique_pairs"]),
    )
    base_selection = base["selection"]
    schema = select_unique_development_records(records)
    schema_ids = {str(row["scenario_id"]) for row in schema}
    v1 = select_balanced_evaluation_records(
        records,
        seed=int(base_selection["smoke_evaluation_seed"]),
        per_bucket=int(base_selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_ids,
    )
    v1_ids = {str(row["scenario_id"]) for row in v1}
    formal = select_balanced_evaluation_records(
        records,
        seed=int(base_selection["formal_evaluation_seed"]),
        per_bucket=int(base_selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_ids | v1_ids,
    )
    formal_ids = {str(row["scenario_id"]) for row in formal}
    v2_lock = _load_json(ROOT / V2_SELECTION_PATH)
    v2 = select_balanced_evaluation_records(
        records,
        seed=int(v2_lock["seed"]),
        per_bucket=1,
        excluded_scenarios=schema_ids | v1_ids | formal_ids,
    )
    v2_ids = {str(row["scenario_id"]) for row in v2}
    evaluation = select_balanced_evaluation_records(
        records,
        seed=int(gateway["evaluation"]["gateway_seed"]),
        per_bucket=int(gateway["evaluation"]["records_per_bucket"]),
        excluded_scenarios=schema_ids | v1_ids | formal_ids | v2_ids,
    )
    return pairs, evaluation, {
        "formal_training": compact_binding(pair_binding(pairs)),
        "gateway_evaluation": compact_binding(
            evaluation_binding(evaluation)
        ),
    }


def _verify_hash_map(values: object) -> list[str]:
    if not isinstance(values, dict) or not values:
        return ["gateway bound hash map is missing"]
    failures = []
    for relative, expected in values.items():
        path = ROOT / str(relative)
        if not path.is_file():
            failures.append(f"missing gateway input: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"gateway input hash mismatch: {relative}")
    return failures


def _uncommitted_inputs(lock: dict[str, Any]) -> list[str]:
    paths = [
        *lock.get("bound_hashes", {}),
        GATEWAY_INPUT_LOCK_PATH.as_posix(),
    ]
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *paths],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify committed gateway inputs"]
    return [line for line in result.stdout.splitlines() if line]


def validate_inputs(*, require_committed: bool) -> list[str]:
    failures = verify_phase3_anti_collapse_smoke_v2_result(ROOT)
    try:
        gateway = _load_toml(ROOT / GATEWAY_CONFIG_PATH)
        base = _load_toml(ROOT / BASE_CONFIG_PATH)
        v1 = _load_v1_runner()
    except (OSError, RuntimeError, tomllib.TOMLDecodeError) as error:
        return [*failures, f"cannot load gateway contracts: {error}"]
    failures.extend(v1.validate_inputs(require_committed=False))
    if gateway.get("status") != (
        "frozen_before_phase3_diversity_gateway_v3_revision_1"
    ):
        failures.append("gateway config is not frozen at revision 1")
    for name in (
        "comparison_config",
        "comparison_selection_lock",
        "v2_config",
        "v2_selection_lock",
        "v2_result_lock",
    ):
        contract = gateway.get("base_contract", {})
        relative = contract.get(name)
        expected = contract.get(f"{name}_sha256")
        path = ROOT / str(relative)
        if not isinstance(relative, str) or not path.is_file():
            failures.append(f"missing gateway base contract: {name}")
        elif _sha256(path) != expected:
            failures.append(f"gateway base-contract hash mismatch: {name}")
    if not (ROOT / GATEWAY_SELECTION_PATH).is_file():
        failures.append("gateway selection lock is missing")
    else:
        try:
            selection_lock = _load_json(ROOT / GATEWAY_SELECTION_PATH)
            records = _load_records(ROOT / base["data"]["joint"])
            _, _, bindings = _selections(gateway, base, records)
            if selection_lock.get("status") != "PASS":
                failures.append("gateway selection lock is not PASS")
            if selection_lock.get("gateway_config_sha256") != _sha256(
                ROOT / GATEWAY_CONFIG_PATH
            ):
                failures.append("gateway config/selection hash mismatch")
            if selection_lock.get("joint_data_sha256") != _sha256(
                ROOT / base["data"]["joint"]
            ):
                failures.append("gateway joint-data hash mismatch")
            for name, binding in bindings.items():
                if selection_lock.get(name) != binding:
                    failures.append(f"gateway selection mismatch: {name}")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"cannot rebuild gateway selections: {error}")
    if not (ROOT / GATEWAY_INPUT_LOCK_PATH).is_file():
        failures.append("gateway input lock is missing")
    else:
        lock = _load_json(ROOT / GATEWAY_INPUT_LOCK_PATH)
        if lock.get("status") != "FROZEN_BEFORE_GATEWAY_V3_REVISION_1":
            failures.append("gateway input lock status is invalid")
        failures.extend(_verify_hash_map(lock.get("bound_hashes")))
        if require_committed:
            failures.extend(_uncommitted_inputs(lock))
    if int(gateway["training"]["unique_pairs"]) != 1024:
        failures.append("gateway training pair count is not 1024")
    if int(gateway["training"]["optimizer_steps"]) != 1024:
        failures.append("gateway optimizer step count is not 1024")
    if gateway["fallback_v4"]["status"] != (
        "design_sketch_only_not_an_authorized_fallback"
    ):
        failures.append("V4 is no longer an unauthorized design sketch")
    if (ROOT / FORMAL_RUN_PATH).exists() or (ROOT / FORMAL_RESULT_PATH).exists():
        failures.append("formal comparison already exists before gateway")
    if not torch.cuda.is_available():
        failures.append("frozen CUDA device is unavailable")
    return failures


def _probe_loss(
    v1: ModuleType,
    base: dict[str, Any],
    pairs: list[Any],
    tokenizer: Any,
    model: Any,
    heads: Any,
) -> float:
    inventory = load_slot_inventory(
        ROOT / base["architecture"]["slot_inventory"]
    )
    was_model_training = model.training
    was_heads_training = heads.training
    model.eval()
    heads.eval()
    losses = []
    with torch.inference_mode():
        for pair in pairs:
            batch = v1._prompt_batch(
                tokenizer,
                [pair.left["input_text"], pair.right["input_text"]],
                maximum=int(base["data"]["max_prompt_tokens"]),
            )
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                hidden = v1._prompt_hidden(model, batch)
                objective = slot_objective(
                    heads(hidden[0:1]),
                    heads(hidden[1:2]),
                    [json.loads(str(pair.left["target_text"]))],
                    [json.loads(str(pair.right["target_text"]))],
                    [str(pair.left["environment"])],
                    inventory,
                    consistency_lambda=0.0,
                )
            losses.append(float(objective.total.detach().cpu()))
            del batch, hidden, objective
    model.train(was_model_training)
    heads.train(was_heads_training)
    return sum(losses) / len(losses)


def _run_file_hashes(staging: Path) -> dict[str, str]:
    return {
        (RUN_PATH / path.relative_to(staging)).as_posix(): _sha256(path)
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }


def _train(
    gateway: dict[str, Any],
    base: dict[str, Any],
    pairs: list[Any],
    tokenizer: Any,
    staging: Path,
) -> tuple[Any, Any, dict[str, Any]]:
    v1 = _load_v1_runner()
    optimization = base["optimization"]
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(
        bool(optimization["deterministic_algorithms"])
    )
    torch.backends.cudnn.benchmark = bool(optimization["cudnn_benchmark"])
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    set_seed(int(optimization["seed"]))
    torch.cuda.empty_cache()
    model = v1._model(base)
    inventory = load_slot_inventory(
        ROOT / base["architecture"]["slot_inventory"]
    )
    heads = build_slot_head_bank(
        int(model.config.hidden_size), inventory
    ).to("cuda")
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
    probe_count = int(gateway["gate"]["fixed_training_probe_pairs"])
    probe_pairs = pairs[:probe_count]
    probe_before = _probe_loss(
        v1, base, probe_pairs, tokenizer, model, heads
    )
    torch.cuda.reset_peak_memory_stats()
    losses: list[float] = []
    component_rows: list[dict[str, float]] = []
    prompt_tokens = 0
    steps = int(gateway["training"]["optimizer_steps"])
    if steps != len(pairs):
        raise ValueError("gateway requires exactly one optimizer step per pair")
    started = time.perf_counter()
    model.train()
    heads.train()
    for step, pair in enumerate(pairs):
        batch = v1._prompt_batch(
            tokenizer,
            [pair.left["input_text"], pair.right["input_text"]],
            maximum=int(base["data"]["max_prompt_tokens"]),
        )
        prompt_tokens += int(batch["attention_mask"].sum().item())
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            hidden = v1._prompt_hidden(model, batch)
            left = heads(hidden[0:1])
            right = heads(hidden[1:2])
            objective = slot_objective(
                left,
                right,
                [json.loads(str(pair.left["target_text"]))],
                [json.loads(str(pair.right["target_text"]))],
                [str(pair.left["environment"])],
                inventory,
                consistency_lambda=0.0,
            )
        if not torch.isfinite(objective.total):
            raise RuntimeError(f"non-finite gateway loss at step {step}")
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
        del batch, hidden, left, right, objective
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    probe_after = _probe_loss(
        v1, base, probe_pairs, tokenizer, model, heads
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
        staging / "slot_heads.safetensors",
    )
    window = 32
    return model, heads, {
        "optimizer_steps": steps,
        "unique_training_pairs": len(pairs),
        "training_epochs": 1,
        "prompt_tokens_seen": prompt_tokens,
        "fixed_probe_pairs": probe_count,
        "fixed_probe_loss_before": probe_before,
        "fixed_probe_loss_after": probe_after,
        "fixed_probe_loss_improvement_fraction": (
            (probe_before - probe_after) / probe_before
        ),
        "online_loss_first_window_mean": sum(losses[:window]) / window,
        "online_loss_last_window_mean": sum(losses[-window:]) / window,
        "online_loss_window_improvement_fraction": (
            (sum(losses[:window]) - sum(losses[-window:]))
            / sum(losses[:window])
        ),
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
        "cuda_device": torch.cuda.get_device_name(0),
    }


def _promote(staging_run: Path, staging_report: Path) -> None:
    final_run = ROOT / RUN_PATH
    final_report = ROOT / RESULT_PATH
    if final_run.exists() or final_report.exists():
        raise FileExistsError("gateway outputs already exist")
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
    if (ROOT / RUN_PATH).exists() or (ROOT / RESULT_PATH).exists():
        raise FileExistsError("gateway outputs already exist")
    gateway = _load_toml(ROOT / GATEWAY_CONFIG_PATH)
    base = _load_toml(ROOT / BASE_CONFIG_PATH)
    records = _load_records(ROOT / base["data"]["joint"])
    pairs, evaluation_records, bindings = _selections(
        gateway, base, records
    )
    v1 = _load_v1_runner()
    tokenizer = v1._tokenizer(base)
    inventory = load_slot_inventory(
        ROOT / base["architecture"]["slot_inventory"]
    )
    baselines = build_training_constant_baselines(pairs, inventory)
    staging_root = ROOT / ".tmp/phase3_diversity_gateway_v3" / uuid.uuid4().hex
    staging_run = staging_root / "run"
    staging_run.mkdir(parents=True)
    model, heads, training = _train(
        gateway, base, pairs, tokenizer, staging_run
    )
    training["output_files"] = _run_file_hashes(staging_run)
    evaluation, rows = v1._evaluate(
        base, evaluation_records, tokenizer, model, heads
    )
    baseline_metrics = score_training_constant_baselines(
        evaluation_records, baselines, inventory
    )
    recalls = normative_recall_by_class(rows)
    evaluation.update(baseline_metrics)
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
    evaluation["resource_status_pass"] = training[
        "peak_allocated_fraction"
    ] <= float(gateway["gate"]["maximum_peak_memory_fraction"])
    v1_result = _load_json(ROOT / V1_RESULT_LOCK_PATH)
    prefix_replay = math.isclose(
        float(training["online_loss_first_window_mean"]),
        float(v1_result["training"]["loss_first_window_mean"]),
        rel_tol=0.0,
        abs_tol=1e-8,
    )
    evaluation["deterministic_prefix_replay"] = prefix_replay
    checks = gateway_v3_checks(evaluation, gateway["gate"])
    status = "PASS" if all(checks.values()) else "BLOCKED"
    del model, heads
    gc.collect()
    torch.cuda.empty_cache()
    input_lock = _load_json(ROOT / GATEWAY_INPUT_LOCK_PATH)
    report = {
        "status": status,
        "run_kind": gateway["run_kind"],
        "scientific_arm_comparison": False,
        "v1_status_preserved": "BLOCKED",
        "v2_status_preserved": "BLOCKED",
        "git_head_before_execution": _git_head(),
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "selection": bindings,
        "training": training,
        "training_constant_baselines": baselines,
        "evaluation": evaluation,
        "gate_checks": checks,
        "thresholds": gateway["gate"],
        "rows": rows,
        "bound_hashes": input_lock["bound_hashes"],
        "formal_arm_comparison_started": False,
        "next_action": (
            "freeze_formal_promotion_certificate_and_three_arm_runner"
            if status == "PASS"
            else "stop_and_record_v3_architecture_blocked"
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
