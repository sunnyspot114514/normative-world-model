"""Independent verification for locally retained result locks."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _verify_path_map(
    root: Path,
    values: object,
    *,
    label: str,
) -> list[str]:
    failures: list[str] = []
    if not isinstance(values, dict):
        return [f"{label} must be an object"]
    for relative, expected in values.items():
        path = root / str(relative)
        if not path.is_file():
            failures.append(f"missing {label} file: {relative}")
        elif sha256_file(path) != expected:
            failures.append(f"{label} hash mismatch: {relative}")
    return failures


def _git_blob(root: Path, revision: str, relative: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{relative}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def verify_phase3_schema_gate_result(root: Path) -> list[str]:
    """Verify the historical Phase-3 result without importing training code."""

    root = root.resolve()
    result_path = root / (
        "artifacts/phase3_retained_schema_gate/schema_gate_result.json"
    )
    lock_path = root / "configs/phase3_retained_schema_gate_result_lock.json"
    if not result_path.is_file():
        return ["missing Phase-3 schema-gate result"]
    if not lock_path.is_file():
        return ["missing Phase-3 schema-gate result lock"]
    try:
        result = _load_object(result_path)
        lock = _load_object(lock_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [f"invalid Phase-3 result evidence: {error}"]

    failures: list[str] = []
    if lock.get("status") != "PASS" or result.get("status") != "PASS":
        failures.append("Phase-3 result or lock is not PASS")
    if sha256_file(result_path) != lock.get("result_sha256"):
        failures.append("Phase-3 result hash mismatch")
    for field in (
        "run_kind",
        "git_head_before_execution",
        "scope",
        "confirmation_status",
        "scientific_arm_comparison",
    ):
        if result.get(field) != lock.get(field):
            failures.append(f"Phase-3 result-lock field mismatch: {field}")
    if result.get("confirmation_status") != "RESERVED_NOT_GENERATED":
        failures.append("Phase-3 result indicates confirmation use")
    if result.get("scientific_arm_comparison") is not False:
        failures.append("Phase-3 schema gate is mislabeled as an arm comparison")
    gate_checks = result.get("gate_checks")
    if not isinstance(gate_checks, dict) or not gate_checks or not all(
        value is True for value in gate_checks.values()
    ):
        failures.append("Phase-3 gate checks are incomplete or not all true")

    failures.extend(
        _verify_path_map(root, lock.get("input_locks"), label="input lock")
    )
    failures.extend(
        _verify_path_map(root, lock.get("adapter_files"), label="adapter")
    )
    failures.extend(
        _verify_path_map(root, result.get("source_hashes"), label="source")
    )

    adapter_files = result.get("adapter_files")
    lock_adapters = lock.get("adapter_files")
    if isinstance(adapter_files, dict) and isinstance(lock_adapters, dict):
        locked_by_name = {
            Path(relative).name: digest
            for relative, digest in lock_adapters.items()
        }
        if adapter_files != locked_by_name:
            failures.append("Phase-3 adapter maps disagree")
    else:
        failures.append("Phase-3 adapter maps are malformed")

    revision = result.get("git_head_before_execution")
    bound_inputs = result.get("bound_input_hashes")
    if not isinstance(revision, str) or not revision:
        failures.append("Phase-3 execution revision is missing")
    elif not isinstance(bound_inputs, dict) or not bound_inputs:
        failures.append("Phase-3 bound-input map is missing")
    else:
        for relative, expected in bound_inputs.items():
            blob = _git_blob(root, revision, str(relative))
            if blob is None:
                failures.append(
                    f"missing historical bound input: {relative}"
                )
            elif hashlib.sha256(blob).hexdigest() != expected:
                failures.append(
                    f"historical bound-input hash mismatch: {relative}"
                )
    return failures
