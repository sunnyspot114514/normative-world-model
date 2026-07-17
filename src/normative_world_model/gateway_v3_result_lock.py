"""Verification for the preserved Phase-3 diversity gateway v3 result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .phase3_gateway import gateway_v3_checks

RESULT_PATH = Path("artifacts/phase3_diversity_gateway_v3/result.json")
INPUT_LOCK_PATH = Path(
    "configs/phase3_diversity_gateway_v3_input_lock.json"
)
RESULT_LOCK_PATH = Path(
    "configs/phase3_diversity_gateway_v3_result_lock.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one object")
    return value


def verify_phase3_diversity_gateway_v3_result(root: Path) -> list[str]:
    failures: list[str] = []
    result_path = root / RESULT_PATH
    input_path = root / INPUT_LOCK_PATH
    lock_path = root / RESULT_LOCK_PATH
    for path, label in (
        (result_path, "gateway result"),
        (input_path, "gateway input lock"),
        (lock_path, "gateway result lock"),
    ):
        if not path.is_file():
            failures.append(f"missing {label}")
    if failures:
        return failures
    try:
        result = _load(result_path)
        input_lock = _load(input_path)
        lock = _load(lock_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"cannot load gateway result objects: {error}"]
    if _sha256(result_path) != lock.get("result_sha256"):
        failures.append("gateway result hash mismatch")
    if _sha256(input_path) != lock.get("input_lock_sha256"):
        failures.append("gateway input-lock hash mismatch")
    if result.get("status") != "BLOCKED" or lock.get("status") != "BLOCKED":
        failures.append("gateway result is not preserved as BLOCKED")
    try:
        checks = gateway_v3_checks(
            result.get("evaluation", {}), result.get("thresholds", {})
        )
    except (KeyError, TypeError, ValueError) as error:
        failures.append(f"cannot recompute gateway checks: {error}")
        checks = {}
    if checks != result.get("gate_checks"):
        failures.append("gateway checks do not recompute")
    if checks != lock.get("gate_checks"):
        failures.append("gateway result-lock checks differ")
    expected_status = "PASS" if checks and all(checks.values()) else "BLOCKED"
    if result.get("status") != expected_status:
        failures.append("gateway status differs from recomputed checks")
    if result.get("bound_hashes") != input_lock.get("bound_hashes"):
        failures.append("gateway result does not preserve input bindings")
    if result.get("git_head_before_execution") != lock.get(
        "git_head_before_execution"
    ):
        failures.append("gateway execution revision mismatch")
    if result.get("formal_arm_comparison_started") is not False:
        failures.append("formal comparison was marked started")
    if result.get("confirmation_status") != "RESERVED_NOT_GENERATED":
        failures.append("confirmation is no longer reserved")
    if result.get("next_action") != "stop_and_record_v3_architecture_blocked":
        failures.append("gateway next action violates the frozen stop rule")
    output_files = result.get("training", {}).get("output_files", {})
    if output_files != lock.get("run_files"):
        failures.append("gateway run-file map differs from result lock")
    for relative, expected in output_files.items():
        path = root / str(relative)
        if not path.is_file():
            failures.append(f"missing gateway run file: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"gateway run-file hash mismatch: {relative}")
    return failures
