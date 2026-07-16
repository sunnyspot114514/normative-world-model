"""Run the frozen retained-discovery strict-schema convergence gate."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import tomllib
import uuid
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import torch

from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_metrics import score_one_step
from normative_world_model.phase3_schema_gate import (
    canonical_digest,
    development_selection_binding,
    select_unique_development_records,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path("configs/phase3_retained_schema_gate.toml")
DATASET_LOCK_PATH = Path(
    "configs/phase3_retained_schema_gate_dataset_lock.json"
)
RESULT_PATH = Path(
    "artifacts/phase3_retained_schema_gate/schema_gate_result.json"
)
RUN_PATH = Path("runs/phase3_retained_schema_gate")
DATA_PATH = Path("data/generated/phase3_retained_schema_gate/arms")

SOURCE_PATHS = {
    "phase1_game_jsonl": Path(
        "data/generated/phase1_discovery_v3/game.jsonl"
    ),
    "phase1_organization_jsonl": Path(
        "data/generated/phase1_discovery_v3/organization.jsonl"
    ),
    "phase1_provenance": Path(
        "artifacts/phase1_v3/provenance_manifest.json"
    ),
    "phase2_result_lock": Path(
        "configs/phase2_retained_result_lock.json"
    ),
    "phase2_provenance": Path(
        "artifacts/phase2_retained_v2/provenance_manifest.json"
    ),
    "model_snapshot_manifest": Path(
        "artifacts/phase3_internal/model_snapshot_manifest.json"
    ),
    "model_requirements": Path("requirements-model.txt"),
    "confirmation_reservation": Path(
        "data/generated/phase1_discovery_v3/confirmation_reservation.json"
    ),
}

BOUND_INPUTS = (
    CONFIG_PATH,
    DATASET_LOCK_PATH,
    Path("docs/PHASE3_RETAINED_SCHEMA_GATE.md"),
    Path("scripts/run-phase3-retained-schema-gate.py"),
    Path("scripts/run-local-multirecord-pilot.py"),
    Path("scripts/export-local-pilot-data.py"),
    Path("scripts/audit-phase2-token-lengths.py"),
    Path("src/normative_world_model/__init__.py"),
    Path("src/normative_world_model/phase3_schema_gate.py"),
    Path("src/normative_world_model/local_pilot.py"),
    Path("src/normative_world_model/metrics.py"),
    Path("src/normative_world_model/model_arms.py"),
    Path("src/normative_world_model/model_output.py"),
    Path("src/normative_world_model/phase2_dataset.py"),
    Path("src/normative_world_model/phase2_metrics.py"),
    Path("src/normative_world_model/policy_oracle.py"),
    Path("src/normative_world_model/transfer_matrix.py"),
    Path("src/normative_world_model/comparators.py"),
    Path("src/normative_world_model/contracts.py"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _load_config() -> dict[str, Any]:
    with (ROOT / CONFIG_PATH).open("rb") as handle:
        return tomllib.load(handle)


def _load_pilot_module() -> ModuleType:
    path = ROOT / "scripts/run-local-multirecord-pilot.py"
    spec = importlib.util.spec_from_file_location("_nwm_local_pilot", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the frozen local-pilot implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _uncommitted_bound_inputs() -> list[str]:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--",
            *(path.as_posix() for path in BOUND_INPUTS),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["cannot verify committed Phase-3 bound inputs"]
    return [line for line in result.stdout.splitlines() if line]


def _training_selection_binding(
    pairs: list[Any],
) -> dict[str, Any]:
    pair_rows = [
        {
            "pair_type": pair.pair_type,
            "left": pair.left["record_id"],
            "right": pair.right["record_id"],
        }
        for pair, _, _ in pairs
    ]
    return {
        "training_pair_count": len(pairs),
        "training_pair_order_sha256": canonical_digest(pair_rows),
        "training_pair_type_counts": dict(
            sorted(Counter(row["pair_type"] for row in pair_rows).items())
        ),
        "unique_training_scenario_count": len(
            {str(pair.left["scenario_id"]) for pair, _, _ in pairs}
        ),
        "training_prompt_tokens_once": sum(
            left.prompt_tokens + right.prompt_tokens
            for _, left, right in pairs
        ),
        "training_target_tokens_once": sum(
            left.target_tokens + right.target_tokens
            for _, left, right in pairs
        ),
    }


def _verify_model_snapshot(
    config: dict[str, Any],
    snapshot: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    model_dir = ROOT / config["model"]["local_dir"]
    if snapshot.get("status") != "PASS":
        failures.append("model snapshot manifest is not PASS")
    if snapshot.get("resolved_revision") != config["model"]["revision"]:
        failures.append("model snapshot revision does not match the gate")
    for relative, metadata in snapshot.get("files", {}).items():
        path = model_dir / relative
        if not path.is_file():
            failures.append(f"missing model snapshot file: {relative}")
        elif _sha256(path) != metadata.get("sha256"):
            failures.append(f"model snapshot hash mismatch: {relative}")
    for package, expected in snapshot.get("packages", {}).items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"missing locked model package: {package}")
            continue
        if actual != expected:
            failures.append(
                f"model package {package} is {actual}, expected {expected}"
            )
    return failures


def validate_inputs(*, require_committed: bool) -> list[str]:
    failures: list[str] = []
    try:
        config = _load_config()
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"invalid Phase-3 schema-gate config: {error}"]
    exact = {
        "version": "0.1-retained-schema-gate",
        "status": "frozen_before_retained_schema_gate",
        "run_kind": "phase3_retained_discovery_schema_gate",
    }
    for field, expected in exact.items():
        if config.get(field) != expected:
            failures.append(f"Phase-3 config {field} changed")
    expected_model = {
        "model_id": "Qwen/Qwen3-1.7B-Base",
        "revision": "ea980cb0a6c2ae4b936e82123acc929f1cec04c1",
        "license": "Apache-2.0",
        "trust_remote_code": False,
        "local_dir": "models/qwen3-1.7b-base-ea980cb0",
    }
    if config.get("model") != expected_model:
        failures.append("Phase-3 schema-gate model contract changed")
    expected_runtime = {
        "device": "cuda",
        "dtype": "float16",
        "attention_implementation": "sdpa",
        "seed": 20260717,
        "max_sequence_tokens": 3072,
        "gradient_checkpointing": True,
        "max_peak_memory_fraction": 0.95,
    }
    if config.get("runtime") != expected_runtime:
        failures.append("Phase-3 schema-gate runtime contract changed")
    expected_data = {
        "source_phase1_dir": "data/generated/phase1_discovery_v3",
        "output_dir": "data/generated/phase3_retained_schema_gate/arms",
        "horizon_mode": "one_step",
        "arm_manifest": (
            "artifacts/phase3_retained_schema_gate/arm_data_manifest.json"
        ),
        "token_audit": (
            "artifacts/phase3_retained_schema_gate/token_length_audit.json"
        ),
        "dataset_lock": (
            "configs/phase3_retained_schema_gate_dataset_lock.json"
        ),
    }
    if config.get("data") != expected_data:
        failures.append("Phase-3 schema-gate data contract changed")
    expected_pilot = {
        "optimizer_steps": 64,
        "max_train_items": 64,
        "learning_rate": 0.0001,
        "consistency_proxy_lambda": 0.0,
        "generation_records": 16,
        "generation_max_new_tokens": 768,
        "teacher_forced_eval_items": 16,
        "output_dir": "runs/phase3_retained_schema_gate",
        "report": (
            "artifacts/phase3_retained_schema_gate/schema_gate_result.json"
        ),
    }
    if config.get("pilot") != expected_pilot:
        failures.append("Phase-3 schema-gate training contract changed")
    expected_lora = {
        "r": 8,
        "alpha": 16,
        "dropout": 0.0,
        "target_modules": [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    }
    if config.get("lora") != expected_lora:
        failures.append("Phase-3 schema-gate LoRA contract changed")
    expected_gate = {
        "arm": "joint_naive",
        "minimum_generation_attempts": 16,
        "minimum_strict_parse_rate": 0.25,
        "require_finite_training_loss": True,
        "require_resource_status_pass": True,
        "failure_action": "stop_before_retained_arm_comparison",
    }
    if config.get("gate") != expected_gate:
        failures.append("Phase-3 schema-gate thresholds changed")
    governance = config.get("governance", {})
    expected_governance = {
        "scope": "retained_discovery_schema_convergence_only",
        "authorizes_retained_schema_gate_training": True,
        "authorizes_retained_arm_comparison": False,
        "authorizes_confirmation": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "consistency_objective_status": "NOT_APPLICABLE_JOINT_NAIVE_ONLY",
        "h5_rollout_status": "UNIDENTIFIED",
        "server_rental_authorized": False,
    }
    if governance != expected_governance:
        failures.append("Phase-3 schema-gate governance changed")
    source_hashes = config.get("source_hashes", {})
    if set(source_hashes) != set(SOURCE_PATHS):
        failures.append("Phase-3 source hash keys are incomplete")
    for key, relative in SOURCE_PATHS.items():
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing Phase-3 source: {relative.as_posix()}")
        elif source_hashes.get(key) != _sha256(path):
            failures.append(f"Phase-3 source hash mismatch: {key}")
    reservation_path = ROOT / SOURCE_PATHS["confirmation_reservation"]
    if reservation_path.is_file():
        reservation = _load_json(reservation_path)
        if reservation.get("status") != "RESERVED_NOT_GENERATED":
            failures.append("confirmation is no longer reserved")

    lock_path = ROOT / DATASET_LOCK_PATH
    if not lock_path.is_file():
        failures.append("Phase-3 dataset lock is missing")
    else:
        lock = _load_json(lock_path)
        if lock.get("status") != "PASS":
            failures.append("Phase-3 dataset lock is not PASS")
        if lock.get("family_count") != 2000:
            failures.append("Phase-3 dataset lock family count is not 2,000")
        if lock.get("maximum_observed_total_tokens", 10**9) > 3072:
            failures.append("Phase-3 dataset lock exceeds the sequence cap")
        if lock.get("confirmation_status") != "RESERVED_NOT_GENERATED":
            failures.append("Phase-3 dataset lock indicates confirmation use")
        for relative, expected in lock.get("hashes", {}).items():
            path = ROOT / relative
            if not path.is_file() or _sha256(path) != expected:
                failures.append(f"Phase-3 dataset hash mismatch: {relative}")
        manifest_path = ROOT / config["data"]["arm_manifest"]
        audit_path = ROOT / config["data"]["token_audit"]
        if manifest_path.is_file():
            manifest = _load_json(manifest_path)
            if manifest.get("status") != "PASS":
                failures.append("Phase-3 arm manifest is not PASS")
            if manifest.get("family_count") != 2000:
                failures.append("Phase-3 arm manifest family count is not 2,000")
            if (
                manifest.get(
                    "factorized_factual_evaluator_visibility_failure_count"
                )
                != 0
            ):
                failures.append("Phase-3 factual evaluator isolation failed")
        if audit_path.is_file() and _load_json(audit_path).get("status") != "PASS":
            failures.append("Phase-3 token audit is not PASS")
    snapshot_path = ROOT / SOURCE_PATHS["model_snapshot_manifest"]
    if snapshot_path.is_file():
        failures.extend(
            _verify_model_snapshot(config, _load_json(snapshot_path))
        )
    if require_committed:
        failures.extend(_uncommitted_bound_inputs())
    return failures


def _promote(
    staging_run: Path,
    staging_report: Path,
    final_run: Path,
    final_report: Path,
) -> None:
    if final_run.exists() or final_report.exists():
        raise FileExistsError("Phase-3 schema-gate outputs already exist")
    final_run.parent.mkdir(parents=True, exist_ok=True)
    final_report.parent.mkdir(parents=True, exist_ok=True)
    run_promoted = False
    try:
        os.replace(staging_run, final_run)
        run_promoted = True
        os.replace(staging_report, final_report)
    except OSError:
        if run_promoted and final_run.exists() and not staging_run.exists():
            os.replace(final_run, staging_run)
        raise


def _generation_check(
    pilot: ModuleType,
    config: dict[str, Any],
    tokenizer: Any,
    records: list[dict[str, Any]],
    adapter_dir: Path,
) -> dict[str, Any]:
    selected = select_unique_development_records(records)
    model = pilot._load_adapter_model(config, adapter_dir)
    rows = []
    for record in selected:
        expected = json.loads(record["target_text"])
        text = pilot._generate(
            model,
            tokenizer,
            record["input_text"],
            max_new_tokens=min(
                int(config["pilot"]["generation_max_new_tokens"]),
                pilot._encoding(tokenizer, record, config).target_tokens + 32,
            ),
        )
        parsed = parse_model_output(text, expected)
        score = score_one_step(
            parsed.output if parsed.ok else None,
            expected,
        )
        rows.append(
            {
                "record_id": record["record_id"],
                "scenario_id": record["scenario_id"],
                "environment": record["environment"],
                "profile_id": record["profile_id"],
                "parse_ok": parsed.ok,
                "parse_error": parsed.error_code,
                "physical_field_f1": score.physical.f1,
                "event_field_f1": score.event_record.f1,
                "normative_correct": score.normative_correct,
                "generated_text": text,
            }
        )
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "attempt_count": len(rows),
        "unique_scenario_count": len(
            {row["scenario_id"] for row in rows}
        ),
        "parse_rate": (
            sum(row["parse_ok"] for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "rows": rows,
    }


def run_gate() -> dict[str, Any]:
    failures = validate_inputs(require_committed=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    if (ROOT / RESULT_PATH).exists() or (ROOT / RUN_PATH).exists():
        raise FileExistsError("Phase-3 schema-gate outputs already exist")
    config = _load_config()
    lock = _load_json(ROOT / DATASET_LOCK_PATH)
    pilot = _load_pilot_module()
    tokenizer = pilot._tokenizer(config)
    records = _load_records(ROOT / DATA_PATH / "joint_one_step.jsonl.gz")
    pairs = pilot._balanced_shortest_pairs(
        records,
        tokenizer,
        config,
        int(config["pilot"]["max_train_items"]),
    )
    actual_selection = {
        **_training_selection_binding(pairs),
        **development_selection_binding(records),
    }
    if actual_selection != lock.get("selection"):
        raise RuntimeError("Phase-3 frozen record selection changed")

    staging_root = (
        ROOT / ".tmp" / "phase3_retained_schema_gate" / uuid.uuid4().hex
    )
    staging_run = staging_root / "run"
    staging_adapter = staging_run / "joint_naive"
    training = pilot._train_arm(
        "joint_naive",
        records,
        tokenizer,
        config,
        optimizer_steps=int(config["pilot"]["optimizer_steps"]),
        maximum_records=int(config["pilot"]["max_train_items"]),
        consistency_lambda=0.0,
        adapter_dir=staging_adapter,
    )
    generation = _generation_check(
        pilot,
        config,
        tokenizer,
        records,
        staging_adapter,
    )
    gate = config["gate"]
    gate_checks = {
        "resource_status_pass": training["status"] == "PASS",
        "finite_training_loss": all(
            isinstance(training[field], (int, float))
            and float("-inf") < float(training[field]) < float("inf")
            for field in ("loss_first", "loss_last", "loss_minimum")
        ),
        "generation_attempts": (
            generation["attempt_count"]
            == int(gate["minimum_generation_attempts"])
        ),
        "unique_generation_scenarios": (
            generation["unique_scenario_count"]
            == int(gate["minimum_generation_attempts"])
        ),
        "strict_parse_rate": (
            generation["parse_rate"]
            >= float(gate["minimum_strict_parse_rate"])
        ),
    }
    status = "PASS" if all(gate_checks.values()) else "BLOCKED"
    logical_adapter = (RUN_PATH / "joint_naive").as_posix()
    training["adapter_dir"] = logical_adapter
    adapter_hashes = {
        path.relative_to(staging_adapter).as_posix(): _sha256(path)
        for path in sorted(staging_adapter.rglob("*"))
        if path.is_file()
    }
    report = {
        "status": status,
        "run_kind": config["run_kind"],
        "scope": config["governance"]["scope"],
        "retained_discovery_result": True,
        "scientific_arm_comparison": False,
        "confirmation_result": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "git_head_before_execution": _git_head(),
        "gate_checks": gate_checks,
        "thresholds": gate,
        "selection": actual_selection,
        "training": training,
        "generation": generation,
        "adapter_files": adapter_hashes,
        "source_hashes": {
            relative.as_posix(): _sha256(ROOT / relative)
            for relative in SOURCE_PATHS.values()
        },
        "dataset_lock_sha256": _sha256(ROOT / DATASET_LOCK_PATH),
        "bound_input_hashes": {
            relative.as_posix(): _sha256(ROOT / relative)
            for relative in BOUND_INPUTS
        },
        "next_action": (
            "implement_and_freeze_slot_level_consistency"
            if status == "PASS"
            else str(gate["failure_action"])
        ),
    }
    staging_report = staging_root / "result.json"
    staging_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    final_run = ROOT / RUN_PATH
    final_report = ROOT / RESULT_PATH
    _promote(
        staging_run,
        staging_report,
        final_run,
        final_report,
    )
    try:
        staging_root.rmdir()
        staging_root.parent.rmdir()
    except OSError:
        pass
    return {
        "status": status,
        "failures": [
            name for name, passed in gate_checks.items() if not passed
        ],
        "strict_parse_rate": generation["parse_rate"],
        "generation_attempts": generation["attempt_count"],
        "unique_generation_scenarios": generation[
            "unique_scenario_count"
        ],
        "result_path": RESULT_PATH.as_posix(),
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("validate", "run"),
        default="validate",
    )
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
            result = run_gate()
        except (FileExistsError, RuntimeError) as error:
            result = {"status": "FAIL", "failures": [str(error)]}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
