"""Run the single-variable Phase-3 anti-collapse smoke redesign."""

from __future__ import annotations

import argparse
import copy
import gc
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import tomllib
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any

import torch

from normative_world_model.phase3_comparison import (
    compact_binding,
    evaluation_binding,
    select_balanced_evaluation_records,
)
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)
from normative_world_model.smoke_result_lock import (
    verify_phase3_anti_collapse_smoke_result,
)

ROOT = Path(__file__).resolve().parents[1]
V2_CONFIG_PATH = Path("configs/phase3_anti_collapse_smoke_v2.toml")
V2_SELECTION_LOCK_PATH = Path(
    "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"
)
V2_INPUT_LOCK_PATH = Path("configs/phase3_anti_collapse_smoke_v2_lock.json")
V2_RESULT_PATH = Path(
    "artifacts/phase3_anti_collapse_smoke_v2/result.json"
)
V2_RUN_PATH = Path("runs/phase3_anti_collapse_smoke_v2")
V1_RESULT_LOCK_PATH = Path(
    "configs/phase3_anti_collapse_smoke_result_lock.json"
)
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


def _load_v2_config() -> dict[str, Any]:
    with (ROOT / V2_CONFIG_PATH).open("rb") as handle:
        return tomllib.load(handle)


def _load_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _load_v1_runner() -> ModuleType:
    path = ROOT / "scripts/run-phase3-anti-collapse-smoke.py"
    spec = importlib.util.spec_from_file_location("_nwm_phase3_smoke_v1", path)
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


def _v2_evaluation(
    base: dict[str, Any],
    v2: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selection = base["selection"]
    schema = select_unique_development_records(records)
    schema_scenarios = {str(record["scenario_id"]) for record in schema}
    v1 = select_balanced_evaluation_records(
        records,
        seed=int(selection["smoke_evaluation_seed"]),
        per_bucket=int(selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios,
    )
    v1_scenarios = {str(record["scenario_id"]) for record in v1}
    formal = select_balanced_evaluation_records(
        records,
        seed=int(selection["formal_evaluation_seed"]),
        per_bucket=int(selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios | v1_scenarios,
    )
    formal_scenarios = {str(record["scenario_id"]) for record in formal}
    v2_records = select_balanced_evaluation_records(
        records,
        seed=int(v2["evaluation"]["seed"]),
        per_bucket=int(v2["evaluation"]["records_per_bucket"]),
        excluded_scenarios=(
            schema_scenarios | v1_scenarios | formal_scenarios
        ),
    )
    return v2_records, compact_binding(evaluation_binding(v2_records))


def _verify_path_hashes(values: object, *, label: str) -> list[str]:
    if not isinstance(values, dict) or not values:
        return [f"{label} hash map is missing"]
    failures: list[str] = []
    for relative, expected in values.items():
        path = ROOT / str(relative)
        if not path.is_file():
            failures.append(f"missing {label}: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"{label} hash mismatch: {relative}")
    return failures


def _uncommitted_bound_inputs(lock: dict[str, Any]) -> list[str]:
    paths = [
        *lock.get("bound_hashes", {}),
        V2_INPUT_LOCK_PATH.as_posix(),
    ]
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--", *paths],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify committed v2 inputs"]
    return [line for line in result.stdout.splitlines() if line]


def validate_inputs(*, require_committed: bool) -> list[str]:
    failures = verify_phase3_anti_collapse_smoke_result(ROOT)
    try:
        v2 = _load_v2_config()
        v1 = _load_v1_runner()
        base = v1._load_config()
    except (OSError, RuntimeError, tomllib.TOMLDecodeError) as error:
        return [*failures, f"cannot load v2 contracts: {error}"]
    if v2.get("status") != "frozen_before_phase3_anti_collapse_smoke_v2":
        failures.append("v2 config is not frozen")
    failures.extend(v1.validate_inputs(require_committed=False))
    base_contract = v2.get("base_contract", {})
    for name in (
        "comparison_config",
        "selection_lock",
        "v1_input_lock",
        "v1_result_lock",
        "v1_runner",
    ):
        relative = base_contract.get(name)
        expected = base_contract.get(f"{name}_sha256")
        path = ROOT / str(relative)
        if not isinstance(relative, str) or not path.is_file():
            failures.append(f"missing v2 base contract: {name}")
        elif _sha256(path) != expected:
            failures.append(f"v2 base-contract hash mismatch: {name}")
    change = v2.get("single_change", {})
    if change != {
        "field": "optimization.smoke_optimizer_steps",
        "v1_value": 256,
        "v2_value": 1024,
        "rationale": (
            "match_the_already_frozen_formal_joint_arm_budget_after_v1_"
            "failed_to_separate_training_labels"
        ),
    }:
        failures.append("v2 single-change declaration changed")
    if int(base["optimization"]["smoke_optimizer_steps"]) != 256:
        failures.append("base smoke step count is no longer 256")
    if int(base["optimization"]["joint_optimizer_steps"]) != 1024:
        failures.append("v2 no longer matches the frozen formal joint budget")
    if not (ROOT / V2_SELECTION_LOCK_PATH).is_file():
        failures.append("v2 selection lock is missing")
    else:
        selection_lock = _load_json(ROOT / V2_SELECTION_LOCK_PATH)
        records = _load_records(ROOT / base["data"]["joint"])
        _, binding = _v2_evaluation(base, v2, records)
        if selection_lock.get("status") != "PASS":
            failures.append("v2 selection lock is not PASS")
        if selection_lock.get("v2_config_sha256") != _sha256(
            ROOT / V2_CONFIG_PATH
        ):
            failures.append("v2 selection config hash mismatch")
        if selection_lock.get("v2_evaluation") != binding:
            failures.append("v2 evaluation selection mismatch")
    if not (ROOT / V2_INPUT_LOCK_PATH).is_file():
        failures.append("v2 input lock is missing")
        return failures
    input_lock = _load_json(ROOT / V2_INPUT_LOCK_PATH)
    if input_lock.get("status") != "FROZEN_BEFORE_SMOKE_V2":
        failures.append("v2 input lock status is invalid")
    failures.extend(
        _verify_path_hashes(input_lock.get("bound_hashes"), label="v2 input")
    )
    if (ROOT / FORMAL_RUN_PATH).exists() or (ROOT / FORMAL_RESULT_PATH).exists():
        failures.append("formal comparison already exists before v2")
    if require_committed:
        failures.extend(_uncommitted_bound_inputs(input_lock))
    return failures


def _run_file_hashes(staging: Path) -> dict[str, str]:
    return {
        (V2_RUN_PATH / path.relative_to(staging)).as_posix(): _sha256(path)
        for path in sorted(staging.rglob("*"))
        if path.is_file()
    }


def _promote(staging_run: Path, staging_report: Path) -> None:
    final_run = ROOT / V2_RUN_PATH
    final_report = ROOT / V2_RESULT_PATH
    if final_run.exists() or final_report.exists():
        raise FileExistsError("v2 smoke outputs already exist")
    final_run.parent.mkdir(parents=True, exist_ok=True)
    final_report.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_run, final_run)
    try:
        os.replace(staging_report, final_report)
    except OSError:
        if final_run.exists() and not staging_run.exists():
            os.replace(final_run, staging_run)
        raise


def run_smoke_v2() -> dict[str, Any]:
    failures = validate_inputs(require_committed=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    if (ROOT / V2_RUN_PATH).exists() or (ROOT / V2_RESULT_PATH).exists():
        raise FileExistsError("v2 smoke outputs already exist")
    v2 = _load_v2_config()
    v1 = _load_v1_runner()
    base = v1._load_config()
    records = _load_records(ROOT / base["data"]["joint"])
    pairs, _, selection_state = v1._selection_state(base, records)
    evaluation_records, evaluation_binding_v2 = _v2_evaluation(
        base,
        v2,
        records,
    )
    execution_config = copy.deepcopy(base)
    execution_config["optimization"]["smoke_optimizer_steps"] = int(
        v2["single_change"]["v2_value"]
    )
    tokenizer = v1._tokenizer(execution_config)
    staging_root = ROOT / ".tmp/phase3_anti_collapse_smoke_v2" / uuid.uuid4().hex
    staging_run = staging_root / "run"
    staging_run.mkdir(parents=True)
    model, heads, training = v1._train(
        execution_config,
        pairs,
        tokenizer,
        staging_run,
    )
    training["output_files"] = _run_file_hashes(staging_run)
    evaluation, rows = v1._evaluate(
        execution_config,
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
    ] <= float(base["optimization"]["maximum_peak_memory_fraction"])
    gate = v1.anti_collapse_checks(
        evaluation,
        base["anti_collapse_smoke"],
    )
    v1_result_lock = _load_json(ROOT / V1_RESULT_LOCK_PATH)
    prefix_replay = math.isclose(
        float(training["loss_first_window_mean"]),
        float(v1_result_lock["training"]["loss_first_window_mean"]),
        rel_tol=0.0,
        abs_tol=1e-8,
    )
    gate["deterministic_prefix_replay"] = prefix_replay
    status = "PASS" if all(gate.values()) else "BLOCKED"
    del model, heads
    gc.collect()
    torch.cuda.empty_cache()
    input_lock = _load_json(ROOT / V2_INPUT_LOCK_PATH)
    report = {
        "status": status,
        "run_kind": "phase3_retained_discovery_anti_collapse_smoke_v2",
        "scientific_arm_comparison": False,
        "v1_status_preserved": "BLOCKED",
        "single_change": v2["single_change"],
        "git_head_before_execution": _git_head(),
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "selection": {
            "smoke_training": selection_state["smoke_training"],
            "v2_evaluation": evaluation_binding_v2,
        },
        "training": training,
        "evaluation": evaluation,
        "gate_checks": gate,
        "thresholds": base["anti_collapse_smoke"],
        "rows": rows,
        "bound_hashes": input_lock["bound_hashes"],
        "next_action": (
            "freeze_formal_one_step_arm_comparison_runner"
            if status == "PASS"
            else "stop_before_formal_arm_comparison"
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
        "failures": [name for name, passed in gate.items() if not passed],
        "result_path": V2_RESULT_PATH.as_posix(),
        "v1_status_preserved": "BLOCKED",
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
            result = run_smoke_v2()
        except (FileExistsError, OSError, RuntimeError, ValueError) as error:
            result = {"status": "FAIL", "failures": [str(error)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
