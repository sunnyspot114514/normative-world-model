"""Build or verify the hash-bound V4 execution input lock."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from normative_world_model.gateway_v3_result_lock import (
    verify_phase3_diversity_gateway_v3_result,
)

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "configs/phase3_representation_gateway_v4_input_lock.json"
BOUND_PATHS = (
    "artifacts/phase3_diversity_gateway_v3/result.json",
    "artifacts/phase3_internal/model_snapshot_manifest.json",
    "configs/phase3_diversity_gateway_v3.toml",
    "configs/phase3_diversity_gateway_v3_input_lock.json",
    "configs/phase3_diversity_gateway_v3_result_lock.json",
    "configs/phase3_diversity_gateway_v3_selection_lock.json",
    "configs/phase3_representation_gateway_v4.toml",
    "configs/phase3_representation_gateway_v4_selection_lock.json",
    "configs/phase3_retained_arm_comparison.toml",
    "configs/phase3_retained_arm_selection_lock.json",
    "configs/phase3_slot_inventory.json",
    "data/generated/phase1_discovery_v3/confirmation_reservation.json",
    "data/generated/phase3_retained_schema_gate/arms/joint_one_step.jsonl.gz",
    "requirements-model.txt",
    "scripts/build-phase3-representation-gateway-v4-selection-lock.py",
    "scripts/run-phase3-anti-collapse-smoke.py",
    "scripts/run-phase3-representation-gateway-v4.py",
    "src/normative_world_model/gateway_v3_result_lock.py",
    "src/normative_world_model/model_arms.py",
    "src/normative_world_model/model_output.py",
    "src/normative_world_model/phase2_metrics.py",
    "src/normative_world_model/phase3_comparison.py",
    "src/normative_world_model/phase3_gateway.py",
    "src/normative_world_model/phase3_gateway_v4.py",
    "src/normative_world_model/phase3_schema_gate.py",
    "src/normative_world_model/slot_objective.py",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_script(relative: str, name: str) -> ModuleType:
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one object")
    return value


def build_lock() -> dict[str, Any]:
    failures = verify_phase3_diversity_gateway_v3_result(ROOT)
    if failures:
        raise RuntimeError("V3 result does not verify: " + "; ".join(failures))
    for relative in BOUND_PATHS:
        if not (ROOT / relative).is_file():
            raise FileNotFoundError(f"missing V4 bound input: {relative}")
    runner = _load_script(
        "scripts/run-phase3-representation-gateway-v4.py", "_nwm_v4_lock_runner"
    )
    selection = _load_script(
        "scripts/build-phase3-representation-gateway-v4-selection-lock.py",
        "_nwm_v4_lock_selection",
    )
    config = runner._load_toml(ROOT / runner.CONFIG_PATH)
    base = runner._load_toml(ROOT / runner.BASE_CONFIG_PATH)
    pairs, evaluation = selection.select_v4_populations()
    tokenizer = runner._v1_runner()._tokenizer(base)
    marker_audit = runner._marker_audit(
        config, tokenizer, pairs, evaluation
    )
    selection_lock = _load_json(
        ROOT / "configs/phase3_representation_gateway_v4_selection_lock.json"
    )
    return {
        "version": "4.0-role-query-execution-input-lock",
        "status": "FROZEN_BEFORE_V4_EXECUTION",
        "bound_hashes": {
            relative: _sha256(ROOT / relative) for relative in BOUND_PATHS
        },
        "selection_lock_sha256": _sha256(
            ROOT / "configs/phase3_representation_gateway_v4_selection_lock.json"
        ),
        "training_order_sha256": selection_lock["formal_training"]["order_sha256"],
        "evaluation_order_sha256": selection_lock["v4_evaluation"]["order_sha256"],
        "continuous_statistics_sha256": selection_lock[
            "continuous_statistics_sha256"
        ],
        "normative_class_weights_sha256": selection_lock[
            "normative_class_weights_sha256"
        ],
        "marker_audit": marker_audit,
        "training": {
            "unique_pairs": int(config["training"]["unique_pairs"]),
            "optimizer_steps": int(config["training"]["optimizer_steps"]),
            "consistency_lambda": float(config["training"]["consistency_lambda"]),
            "fixed_probe_pairs": int(config["gate"]["fixed_training_probe_pairs"]),
        },
        "governance": {
            "v3_status_remains": "BLOCKED",
            "formal_evaluation_may_not_be_opened_by_v4": True,
            "confirmation_generation_authorized": False,
            "no_fifth_diagnostic_population": True,
            "pass_requires_a_separate_formal_runner_freeze": True,
        },
        "locally_regenerated_or_ignored_paths": [
            "artifacts/phase3_diversity_gateway_v3/result.json",
            "artifacts/phase3_internal/model_snapshot_manifest.json",
            "data/generated/phase1_discovery_v3/confirmation_reservation.json",
            "data/generated/phase3_retained_schema_gate/arms/joint_one_step.jsonl.gz",
        ],
        "formal_arm_comparison_started": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("inspect", "verify"), default="inspect")
    args = parser.parse_args()
    actual = build_lock()
    failures: list[str] = []
    if args.mode == "verify":
        if not LOCK_PATH.is_file():
            failures.append("V4 input lock is missing")
        elif _load_json(LOCK_PATH) != actual:
            failures.append("V4 input lock differs from deterministic rebuild")
    print(
        json.dumps(
            {
                "status": "PASS" if not failures else "FAIL",
                "failures": failures,
                "lock": actual,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
