"""Independent verification of the Phase-3 anti-collapse smoke v2 result."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .result_lock import sha256_file
from .smoke_result_lock import verify_phase3_anti_collapse_smoke_result


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _git_blob(root: Path, revision: str, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def _summary_failures(
    expected: object,
    actual: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        return [f"v2 {label} summary is malformed"]
    return [
        f"v2 {label} summary mismatch: {name}"
        for name, value in expected.items()
        if actual.get(name) != value
    ]


def verify_phase3_anti_collapse_smoke_v2_result(root: Path) -> list[str]:
    """Verify v2 and confirm that both engineering gates remain BLOCKED."""

    root = root.resolve()
    result_path = root / (
        "artifacts/phase3_anti_collapse_smoke_v2/result.json"
    )
    result_lock_path = root / (
        "configs/phase3_anti_collapse_smoke_v2_result_lock.json"
    )
    input_lock_path = root / (
        "configs/phase3_anti_collapse_smoke_v2_lock.json"
    )
    if not result_path.is_file():
        return ["missing Phase-3 anti-collapse smoke v2 result"]
    if not result_lock_path.is_file():
        return ["missing Phase-3 anti-collapse smoke v2 result lock"]
    if not input_lock_path.is_file():
        return ["missing Phase-3 anti-collapse smoke v2 input lock"]
    try:
        result = _load_object(result_path)
        result_lock = _load_object(result_lock_path)
        input_lock = _load_object(input_lock_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"invalid anti-collapse v2 evidence: {error}"]

    failures = verify_phase3_anti_collapse_smoke_result(root)
    if result.get("status") != "BLOCKED":
        failures.append("anti-collapse v2 result is no longer BLOCKED")
    if result_lock.get("status") != "BLOCKED":
        failures.append("anti-collapse v2 result lock is not BLOCKED")
    if result.get("v1_status_preserved") != "BLOCKED":
        failures.append("anti-collapse v2 no longer preserves v1 BLOCKED")
    if sha256_file(result_path) != result_lock.get("result_sha256"):
        failures.append("anti-collapse v2 result hash mismatch")
    if sha256_file(input_lock_path) != result_lock.get(
        "input_lock_sha256"
    ):
        failures.append("anti-collapse v2 input-lock hash mismatch")
    for field in (
        "run_kind",
        "scientific_arm_comparison",
        "v1_status_preserved",
        "git_head_before_execution",
        "confirmation_status",
        "single_change",
    ):
        if result.get(field) != result_lock.get(field):
            failures.append(f"anti-collapse v2 result-lock mismatch: {field}")
    if result.get("scientific_arm_comparison") is not False:
        failures.append("anti-collapse v2 is mislabeled as scientific")
    if result.get("confirmation_status") != "RESERVED_NOT_GENERATED":
        failures.append("anti-collapse v2 indicates confirmation use")
    if result.get("next_action") != "stop_before_formal_arm_comparison":
        failures.append("anti-collapse v2 stop action changed")

    gate = result.get("gate_checks")
    if gate != result_lock.get("gate_checks"):
        failures.append("anti-collapse v2 gate checks differ from lock")
    if not isinstance(gate, dict) or not gate:
        failures.append("anti-collapse v2 gate checks are malformed")
    elif all(value is True for value in gate.values()):
        failures.append("BLOCKED anti-collapse v2 has no failed gate")
    elif gate.get("deterministic_prefix_replay") is not True:
        failures.append("anti-collapse v2 did not replay the v1 prefix")

    failures.extend(
        _summary_failures(
            result_lock.get("training"),
            result.get("training"),
            label="training",
        )
    )
    locked_evaluation = result_lock.get("evaluation")
    actual_evaluation = result.get("evaluation")
    if isinstance(locked_evaluation, dict) and isinstance(
        actual_evaluation, dict
    ):
        normalized = dict(actual_evaluation)
        normalized["records"] = actual_evaluation.get("evaluation_records")
        failures.extend(
            _summary_failures(
                locked_evaluation,
                normalized,
                label="evaluation",
            )
        )
    else:
        failures.append("v2 evaluation summary is malformed")

    run_files = result_lock.get("run_files")
    report_files = (
        result.get("training", {}).get("output_files")
        if isinstance(result.get("training"), dict)
        else None
    )
    if run_files != report_files:
        failures.append("anti-collapse v2 run-file maps disagree")
    if isinstance(run_files, dict):
        for relative, expected in run_files.items():
            path = root / str(relative)
            if not path.is_file():
                failures.append(f"missing anti-collapse v2 run file: {relative}")
            elif sha256_file(path) != expected:
                failures.append(f"v2 run-file hash mismatch: {relative}")
    else:
        failures.append("anti-collapse v2 run-file lock is malformed")

    bound_hashes = result.get("bound_hashes")
    if bound_hashes != input_lock.get("bound_hashes"):
        failures.append("v2 report and input-lock bindings disagree")
    revision = result.get("git_head_before_execution")
    if not isinstance(revision, str) or not revision:
        failures.append("anti-collapse v2 execution revision is missing")
    elif isinstance(bound_hashes, dict):
        for relative, expected in bound_hashes.items():
            blob = _git_blob(root, revision, str(relative))
            if blob is not None:
                actual = hashlib.sha256(blob).hexdigest()
            else:
                path = root / str(relative)
                actual = sha256_file(path) if path.is_file() else None
            if actual is None:
                failures.append(f"missing anti-collapse v2 input: {relative}")
            elif actual != expected:
                failures.append(f"v2 bound-input hash mismatch: {relative}")
    else:
        failures.append("anti-collapse v2 bound-input map is malformed")

    confirmation = root / (
        "data/generated/phase1_discovery_v3/confirmation_reservation.json"
    )
    if not confirmation.is_file():
        failures.append("confirmation reservation is missing after v2")
    else:
        try:
            if _load_object(confirmation).get("status") != (
                "RESERVED_NOT_GENERATED"
            ):
                failures.append("confirmation is no longer reserved after v2")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            failures.append(f"invalid confirmation reservation after v2: {error}")
    return failures
