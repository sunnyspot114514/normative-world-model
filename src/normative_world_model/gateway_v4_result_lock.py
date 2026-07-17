"""Verification for a preserved Phase-3 role-query gateway V4 result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .phase3_gateway_v4 import gateway_v4_checks

RESULT_PATH = Path("artifacts/phase3_representation_gateway_v4/result.json")
INPUT_LOCK_PATH = Path("configs/phase3_representation_gateway_v4_input_lock.json")
RESULT_LOCK_PATH = Path("configs/phase3_representation_gateway_v4_result_lock.json")


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


def verify_phase3_representation_gateway_v4_result(root: Path) -> list[str]:
    failures: list[str] = []
    result_path = root / RESULT_PATH
    input_path = root / INPUT_LOCK_PATH
    lock_path = root / RESULT_LOCK_PATH
    for path, label in (
        (result_path, "V4 gateway result"),
        (input_path, "V4 gateway input lock"),
        (lock_path, "V4 gateway result lock"),
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
        return [f"cannot load V4 result objects: {error}"]
    if _sha256(result_path) != lock.get("result_sha256"):
        failures.append("V4 result hash mismatch")
    if _sha256(input_path) != lock.get("input_lock_sha256"):
        failures.append("V4 input-lock hash mismatch")
    try:
        checks = gateway_v4_checks(
            result.get("evaluation", {}), result.get("thresholds", {})
        )
    except (KeyError, TypeError, ValueError) as error:
        failures.append(f"cannot recompute V4 gateway checks: {error}")
        checks = {}
    if checks != result.get("gate_checks"):
        failures.append("V4 gateway checks do not recompute")
    if checks != lock.get("gate_checks"):
        failures.append("V4 result-lock checks differ")
    expected_status = "PASS" if checks and all(checks.values()) else "BLOCKED"
    if result.get("status") != expected_status or lock.get("status") != expected_status:
        failures.append("V4 status differs from recomputed checks")
    if result.get("bound_hashes") != input_lock.get("bound_hashes"):
        failures.append("V4 result does not preserve input bindings")
    if result.get("git_head_before_execution") != lock.get(
        "git_head_before_execution"
    ):
        failures.append("V4 execution revision mismatch")
    if result.get("formal_arm_comparison_started") is not False:
        failures.append("formal comparison was marked started by V4")
    if result.get("confirmation_status") != "RESERVED_NOT_GENERATED":
        failures.append("confirmation is no longer reserved after V4")
    expected_next = (
        "preserve_candidate_and_freeze_separate_formal_runner"
        if expected_status == "PASS"
        else "terminate_local_qwen3_1_7b_path_as_engineering_null"
    )
    if result.get("next_action") != expected_next:
        failures.append("V4 next action violates the frozen decision rule")
    output_files = result.get("training", {}).get("output_files", {})
    if output_files != lock.get("run_files"):
        failures.append("V4 run-file map differs from result lock")
    for relative, expected in output_files.items():
        path = root / str(relative)
        if not path.is_file():
            failures.append(f"missing V4 run file: {relative}")
        elif _sha256(path) != expected:
            failures.append(f"V4 run-file hash mismatch: {relative}")
    return failures

