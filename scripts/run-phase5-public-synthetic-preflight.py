from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from normative_world_model.phase5_loopback_adapter import (
    LoopbackSyntheticRuntimeAdapter,
    request_contracts_from_client_plan,
)
from normative_world_model.phase5_public_metadata import _canonical_sha256, _load_inert_json
from normative_world_model.phase5_synthetic_client_plan import _read_client_plan
from normative_world_model.phase5_synthetic_runner import (
    SyntheticRuntimeSpec,
    run_phase5_public_synthetic_preflight,
    runtime_bindings_from_specs,
)
from normative_world_model.phase5_termination_probe import _read_plan


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT_PLAN = (
    PROJECT_ROOT
    / ".cache"
    / "phase5_synthetic_client_plan"
    / "v11-b2887ba90d81-b752a05215d7.json"
)
DEFAULT_TERMINATION_PLAN = (
    PROJECT_ROOT
    / ".cache"
    / "phase5_common_termination_probe_plan"
    / "v2-1a8cdbf5f807.json"
)
DEFAULT_RUNTIME_BUNDLE = PROJECT_ROOT / "configs" / "phase5_lock_a_runtime_bundle_20260722.json"
DEFAULT_ACCEPTANCE = PROJECT_ROOT / "configs" / "phase5_lock_a_acceptance_20260722.json"
DEFAULT_REMOTE_ENVIRONMENT = (
    PROJECT_ROOT / "configs" / "phase5_lock_a_remote_environment_20260722.json"
)
ALLOWED_DEPLOYMENT_DIFF = {
    "configs/phase5_lock_a_acceptance_20260722.json",
    "src/normative_world_model/phase5_lock_a_registry.py",
}
REMOTE_OUTPUT_PARENT = Path("/root/autodl-tmp/phase5-lock-a-runs")


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"{label} is not a single-link regular file")
    value = _load_inert_json(path.read_bytes(), label=label)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(PROJECT_ROOT), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"attested runtime file is not a single-link regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_client_plan_file_binding(
    path: Path, acceptance: Mapping[str, Any]
) -> None:
    expected = acceptance.get("client_plan_file_sha256")
    if not isinstance(expected, str) or _sha256_file(path) != expected:
        raise ValueError("client-plan file bytes differ from the accepted binding")


def _verify_remote_environment(
    manifest: Mapping[str, Any], acceptance: Mapping[str, Any]
) -> dict[str, Any]:
    without_hash = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if (
        manifest.get("format_version") != "phase5-remote-environment-manifest-v2"
        or manifest.get("manifest_sha256") != _canonical_sha256(without_hash)
        or manifest.get("manifest_sha256")
        != acceptance.get("remote_environment_manifest_sha256")
    ):
        raise ValueError("remote environment manifest differs from its accepted binding")
    python_path = Path(manifest["python_executable"])
    runtime_path = Path(manifest["runtime_executable"])
    if (
        Path(sys.executable).resolve(strict=True) != python_path
        or _sha256_file(python_path) != manifest.get("python_executable_sha256")
        or _sha256_file(runtime_path) != manifest.get("runtime_executable_sha256")
        or socket.gethostname() != manifest.get("hostname")
        or os.uname().release != manifest.get("kernel")
    ):
        raise ValueError("live runtime identity differs from the accepted environment")
    gpu = subprocess.run(
        [
            "/usr/bin/nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    ).stdout.strip()
    disk = shutil.disk_usage("/root/autodl-tmp")
    minimum_free = acceptance.get("limits", {}).get("minimum_free_data_disk_bytes")
    if (
        gpu != manifest.get("gpu_query_noheader_nounits")
        or disk.total != manifest.get("data_disk_total_bytes")
        or not isinstance(minimum_free, int)
        or isinstance(minimum_free, bool)
        or disk.free < minimum_free
    ):
        raise ValueError("live GPU or data-disk envelope differs from Lock A")
    return {
        "manifest_sha256": manifest["manifest_sha256"],
        "current_free_data_disk_bytes": disk.free,
        "gpu_query_noheader_nounits": gpu,
    }


def _verify_two_commit_deployment(acceptance: Mapping[str, Any]) -> dict[str, str]:
    if os.name == "nt":
        raise RuntimeError("the concrete Phase-5 preflight entry point is Linux-only")
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise PermissionError("tracked deployment worktree is not clean")
    source_commit = acceptance.get("source_commit")
    parent_commit = _git("rev-parse", "HEAD^")
    deployment_commit = _git("rev-parse", "HEAD")
    if parent_commit != source_commit:
        raise PermissionError("deployment parent does not equal the accepted source commit")
    changed = {
        line
        for line in _git("diff", "--name-only", "--diff-filter=ACMRT", parent_commit, deployment_commit).splitlines()
        if line
    }
    if changed != ALLOWED_DEPLOYMENT_DIFF:
        raise PermissionError("deployment commit contains files outside the two-file trust-root delta")
    return {"source_commit": parent_commit, "deployment_commit": deployment_commit}


def _runtime_specs(bundle: Mapping[str, Any]) -> dict[str, SyntheticRuntimeSpec]:
    rows = bundle.get("runtime_specs")
    if not isinstance(rows, Mapping) or set(rows) != {"agentworld", "base"}:
        raise ValueError("runtime-bundle checkpoint set differs")
    result = {}
    for checkpoint in ("agentworld", "base"):
        row = rows[checkpoint]
        if not isinstance(row, Mapping) or set(row) != {
            "snapshot_manifest",
            "effective_environment",
            "argv",
        }:
            raise ValueError(f"runtime-bundle row differs: {checkpoint}")
        environment = row["effective_environment"]
        argv = row["argv"]
        if not isinstance(environment, Mapping) or not isinstance(argv, list):
            raise ValueError(f"runtime-bundle row is malformed: {checkpoint}")
        result[checkpoint] = SyntheticRuntimeSpec(
            checkpoint=checkpoint,
            snapshot_manifest=row["snapshot_manifest"],
            effective_environment=dict(environment),
            argv=tuple(argv),
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-plan", type=Path, default=DEFAULT_CLIENT_PLAN)
    parser.add_argument("--termination-plan", type=Path, default=DEFAULT_TERMINATION_PLAN)
    parser.add_argument("--runtime-bundle", type=Path, default=DEFAULT_RUNTIME_BUNDLE)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument(
        "--remote-environment", type=Path, default=DEFAULT_REMOTE_ENVIRONMENT
    )
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    client_plan_path = args.client_plan.resolve(strict=True)
    termination_plan = _read_plan(args.termination_plan.resolve(strict=True))
    runtime_bundle = _load_json(args.runtime_bundle.resolve(strict=True), label="runtime bundle")
    acceptance = _load_json(args.acceptance.resolve(strict=True), label="Lock-A acceptance")
    _verify_client_plan_file_binding(client_plan_path, acceptance)
    client_plan = _read_client_plan(client_plan_path)
    remote_environment = _load_json(
        args.remote_environment.resolve(strict=True), label="remote environment manifest"
    )
    _verify_two_commit_deployment(acceptance)
    _verify_remote_environment(remote_environment, acceptance)

    bundle_without_hash = {
        key: value for key, value in runtime_bundle.items() if key != "bundle_sha256"
    }
    if (
        runtime_bundle.get("format_version") != "phase5-lock-a-runtime-bundle-v1"
        or runtime_bundle.get("bundle_sha256") != _canonical_sha256(bundle_without_hash)
        or runtime_bundle.get("client_plan_sha256") != client_plan.get("client_plan_sha256")
        or runtime_bundle.get("termination_plan_sha256") != termination_plan.get("plan_sha256")
        or runtime_bundle.get("remote_environment_manifest_sha256")
        != acceptance.get("remote_environment_manifest_sha256")
        or runtime_bundle.get("weight_download_plan_sha256")
        != acceptance.get("weight_download_plan_sha256")
    ):
        raise ValueError("runtime bundle differs from its accepted bindings")

    specs = _runtime_specs(runtime_bundle)
    bindings = runtime_bindings_from_specs(specs)
    if (
        _canonical_sha256(bindings) != runtime_bundle.get("runtime_bindings_sha256")
        or runtime_bundle.get("runtime_bindings_sha256")
        != acceptance.get("runtime_bindings_sha256")
    ):
        raise ValueError("runtime specs differ from the accepted runtime binding")

    output_root = args.output_root.resolve(strict=False)
    output_root.relative_to(REMOTE_OUTPUT_PARENT)
    if output_root == REMOTE_OUTPUT_PARENT:
        raise ValueError("output root must be a fresh child of the Phase-5 run root")

    adapters = {
        checkpoint: LoopbackSyntheticRuntimeAdapter(
            checkpoint=checkpoint,
            expected_runtime_binding=bindings[checkpoint],
            request_contracts=request_contracts_from_client_plan(
                client_plan, checkpoint=checkpoint
            ),
            startup_log_path=output_root / checkpoint / "vllm-startup.log",
        )
        for checkpoint in ("agentworld", "base")
    }
    result = run_phase5_public_synthetic_preflight(
        client_plan=client_plan,
        termination_plan=termination_plan,
        expected_client_plan_sha256=client_plan["client_plan_sha256"],
        runtime_specs=specs,
        adapters=adapters,
        lock_a_acceptance=acceptance,
        expected_runtime_bindings=bindings,
        output_root=output_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
