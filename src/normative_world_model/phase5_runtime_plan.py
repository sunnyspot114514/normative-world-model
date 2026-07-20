"""Build a local-only Phase-5 common runtime launch plan.

This module contains no subprocess, HTTP, model-download, GPU, or retained-data
entry point. It only binds already verified public metadata plans to exact
future server argument vectors.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .phase5_preflight import (
    STAGE2_CONFIG_SEMANTIC_SHA256,
    load_phase5_config,
    validate_stage2_contract,
)
from .phase5_public_metadata import _load_inert_json
from .phase5_public_weight_plan import (
    default_public_weight_plan_path,
    verify_public_weight_plan,
)
from .phase5_termination_probe import (
    TERMINATION_CONFIG_SEMANTIC_SHA256,
    load_termination_probe_config,
    validate_termination_probe_config,
    verify_common_termination_probe_plan,
)

RUNTIME_PLAN_FORMAT_VERSION = "phase5-common-runtime-plan-v1"
RUNTIME_PLAN_MAX_BYTES = 2 * 1024 * 1024
IMPLEMENTATION_SOURCE_PATHS = (
    "configs/phase5_scale_inference_draft.toml",
    "configs/phase5_common_termination_probe_candidate.toml",
    "src/normative_world_model/phase5_preflight.py",
    "src/normative_world_model/phase5_public_weight_plan.py",
    "src/normative_world_model/phase5_runtime_plan.py",
    "src/normative_world_model/phase5_termination_probe.py",
)

COMMON_ENVIRONMENT = {
    "CUDA_VISIBLE_DEVICES": "0",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_OFFLINE": "1",
    "OMP_NUM_THREADS": "1",
    "TOKENIZERS_PARALLELISM": "false",
    "TRANSFORMERS_OFFLINE": "1",
    "VLLM_USE_FLASHINFER_SAMPLER": "0",
}


def _canonical_sha256(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((body + "\n").encode("utf-8")).hexdigest()


def _implementation_source_records() -> dict[str, dict[str, Any]]:
    project_root = Path(__file__).resolve().parents[2]
    records = {}
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        body = (project_root / relative).read_bytes()
        records[relative] = {
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    return records


def _checkpoint_weight_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    weight_plan = row.get("weight_plan")
    if not isinstance(weight_plan, Mapping):
        raise ValueError("public weight-plan checkpoint is malformed")
    files = weight_plan.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("public weight-plan checkpoint has no files")
    return {
        "weight_file_count": weight_plan.get("weight_file_count"),
        "publisher_weight_bytes": weight_plan.get("total_weight_bytes"),
        "index_declared_tensor_bytes": weight_plan.get("index_declared_tensor_bytes"),
        "safetensors_container_overhead_bytes": weight_plan.get(
            "safetensors_container_overhead_bytes"
        ),
        "weight_plan_sha256": weight_plan.get("weight_plan_sha256"),
        "unreferenced_weight_files": weight_plan.get("unreferenced_weight_files"),
    }


def _serve_argv(
    *,
    snapshot_relative_path: str,
    model_alias: str,
    runtime: Mapping[str, Any],
    server: Mapping[str, Any],
) -> list[str]:
    return [
        "serve",
        snapshot_relative_path,
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--served-model-name",
        model_alias,
        "--dtype",
        str(runtime["dtype"]),
        "--tensor-parallel-size",
        str(runtime["tensor_parallel_size"]),
        "--max-model-len",
        str(runtime["maximum_model_length"]),
        "--gpu-memory-utilization",
        format(float(runtime["gpu_memory_utilization"]), ".2f"),
        "--max-num-seqs",
        str(runtime["interface_preflight_max_num_seqs"]),
        "--moe-backend",
        str(runtime["moe_backend"]),
        "--generation-config",
        str(server["generation_config"]),
        "--reasoning-parser",
        str(runtime["reasoning_parser"]),
        "--language-model-only",
        "--enforce-eager",
    ]


def build_phase5_runtime_plan(
    *,
    config: Mapping[str, Any],
    termination_config: Mapping[str, Any],
    public_weight_plan: Mapping[str, Any],
    weight_verification: Mapping[str, Any],
    termination_verification: Mapping[str, Any],
    implementation_sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind exact future launch vectors without authorizing execution."""

    failures = validate_stage2_contract(config)
    failures.extend(validate_termination_probe_config(termination_config))
    if failures:
        raise ValueError("; ".join(failures))
    authorization = config["authorization"]
    if any(
        authorization.get(field) is not False
        for field in (
            "model_download",
            "server_rental",
            "synthetic_preflight_lock_accepted",
            "synthetic_preflight_rental",
            "scientific_execution_lock_accepted",
            "scientific_run",
        )
    ):
        raise ValueError("runtime planning requires every execution authorization closed")
    if (
        weight_verification.get("status") != "PASS"
        or weight_verification.get("model_download") is not False
        or weight_verification.get("weight_bytes_present") is not False
        or weight_verification.get("artifact_sha256")
        != public_weight_plan.get("artifact_sha256")
    ):
        raise ValueError("public weight plan is not independently verified")
    if public_weight_plan.get("authorization") != {
        "model_download": False,
        "remote_fetch_performed": False,
        "weight_bytes_present": False,
    }:
        raise ValueError("public weight-plan authorization differs")
    if (
        termination_verification.get("status")
        != "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED"
        or termination_verification.get("http_execution") is not False
        or not isinstance(termination_verification.get("plan_sha256"), str)
    ):
        raise ValueError("termination plan is not independently verified and closed")

    runtime = config["runtime"]
    server = termination_config["server"]
    if (
        runtime.get("engine") != "vllm"
        or runtime.get("agentworld_observed_engine_version") != server.get("version")
        or server.get("version") != "0.25.1"
        or server.get("generation_config") != "vllm"
    ):
        raise ValueError("runtime engine identity differs")
    if (
        runtime.get("language_model_only_agentworld") is not True
        or runtime.get("language_model_only_base_candidate") is not True
        or runtime.get("language_model_only_base_candidate_status")
        != "PROVISIONAL_COMMON_SETTING_BOTH_CONFIGS_DECLARE_VISION"
    ):
        raise ValueError("common language-only candidate differs")
    if (
        runtime.get("same_container_and_hardware_for_both_checkpoints") is not True
        or runtime.get("tensor_parallel_size") != 1
        or runtime.get("dtype") != "bfloat16"
        or runtime.get("quantization") != "none"
        or runtime.get("enforce_eager") is not True
        or runtime.get("moe_backend") != "triton"
        or runtime.get("flashinfer_sampler_enabled") is not False
        or runtime.get("vllm_use_flashinfer_sampler") != "0"
        or runtime.get("omp_num_threads") != 1
    ):
        raise ValueError("common runtime safety settings differ")

    model_config = config["models"]
    aliases = termination_config["model_aliases"]
    checkpoints = public_weight_plan.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != 2:
        raise ValueError("public weight plan must contain exactly two checkpoints")
    by_name = {
        str(row.get("checkpoint")): row
        for row in checkpoints
        if isinstance(row, Mapping)
    }
    if set(by_name) != {"agentworld", "base"}:
        raise ValueError("public weight plan checkpoint set differs")

    launch_specs = []
    for checkpoint in ("agentworld", "base"):
        model = model_config[checkpoint]
        weight_row = by_name[checkpoint]
        revision = model["observed_revision_2026_07_18"]
        if (
            weight_row.get("repo_id") != model["model_id"]
            or weight_row.get("revision") != revision
        ):
            raise ValueError(f"runtime and weight-plan source differ: {checkpoint}")
        relative_snapshot = f"models/phase5/{checkpoint}/{revision}"
        argv = _serve_argv(
            snapshot_relative_path=relative_snapshot,
            model_alias=aliases[checkpoint],
            runtime=runtime,
            server=server,
        )
        if "--trust-remote-code" in argv:
            raise ValueError("unreviewed remote code is forbidden in the common launch plan")
        launch_specs.append(
            {
                "checkpoint": checkpoint,
                "repo_id": model["model_id"],
                "observed_revision": revision,
                "frozen_revision_status": model["frozen_revision_status"],
                "model_alias": aliases[checkpoint],
                "working_directory_policy": "LOCK_A_REMOTE_ROOT",
                "snapshot_relative_path": relative_snapshot,
                "executable": "vllm",
                "argv": argv,
                "environment": dict(COMMON_ENVIRONMENT),
                "weight_plan": _checkpoint_weight_summary(weight_row),
            }
        )
    if (
        sum(row["weight_plan"]["weight_file_count"] for row in launch_specs)
        != weight_verification.get("weight_file_count")
        or sum(row["weight_plan"]["publisher_weight_bytes"] for row in launch_specs)
        != weight_verification.get("publisher_weight_bytes")
        or any(row["weight_plan"]["unreferenced_weight_files"] for row in launch_specs)
    ):
        raise ValueError("runtime weight-plan projection differs from verified totals")

    result = {
        "format_version": RUNTIME_PLAN_FORMAT_VERSION,
        "status": "LOCAL_RUNTIME_PLAN_PASS_LOCK_A_NOT_BUILT_EXECUTION_NOT_AUTHORIZED",
        "authorization": {
            "model_download": False,
            "server_rental": False,
            "http_execution": False,
            "gpu_execution": False,
            "retained_population_access": False,
            "scientific_execution": False,
        },
        "stage2_config_semantic_sha256": STAGE2_CONFIG_SEMANTIC_SHA256,
        "termination_config_semantic_sha256": TERMINATION_CONFIG_SEMANTIC_SHA256,
        "implementation_sources": dict(
            implementation_sources or _implementation_source_records()
        ),
        "public_weight_plan_verification": dict(weight_verification),
        "termination_plan_verification": dict(termination_verification),
        "common_effective_runtime_contract": {
            "engine": "vllm",
            "engine_version": "0.25.1",
            "generation_config": "vllm",
            "host": "127.0.0.1",
            "port": 8000,
            "language_model_only": True,
            "trust_remote_code": False,
            "tensor_parallel_size": 1,
            "dtype": "bfloat16",
            "quantization": "none",
            "maximum_model_length": runtime["maximum_model_length"],
            "interface_preflight_max_num_seqs": runtime[
                "interface_preflight_max_num_seqs"
            ],
            "gpu_memory_utilization": runtime["gpu_memory_utilization"],
            "enforce_eager": True,
            "moe_backend": "triton",
            "reasoning_parser": "qwen3",
            "flashinfer_sampler_enabled": False,
            "omp_num_threads": 1,
        },
        "launch_order": ["agentworld", "base"],
        "serve_sequentially": True,
        "prior_server_must_exit_before_next_launch": True,
        "common_port": 8000,
        "launch_specs": launch_specs,
        "unresolved_before_lock_a": [
            "freeze_checkpoint_revisions",
            "bind_container_digest_and_provider_image",
            "bind_provider_quote_wall_clock_cap_and_preflight_spend",
            "build_synthetic_client_orchestrator_and_raw_capture",
            "build_throughput_smoke_runner_and_verifier",
            "build_source_import_closure_and_cleanliness_attestation",
            "complete_two_round_lock_a_review",
        ],
    }
    result["runtime_plan_sha256"] = _canonical_sha256(result)
    return result


def default_phase5_runtime_plan_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return (
        project_root
        / ".cache"
        / "phase5_runtime_plan"
        / (
            f"v1-{STAGE2_CONFIG_SEMANTIC_SHA256[:12]}-"
            f"{TERMINATION_CONFIG_SEMANTIC_SHA256[:12]}.json"
        )
    )


def _write_once(path: Path, plan: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite runtime plan: {path}")
    data = (json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if len(data) > RUNTIME_PLAN_MAX_BYTES:
        raise ValueError("runtime plan exceeds its byte cap")
    partial = path.with_name(path.name + ".part")
    try:
        with partial.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _read_weight_plan() -> dict[str, Any]:
    path = default_public_weight_plan_path()
    value = _load_inert_json(path.read_bytes(), label="public weight plan")
    if not isinstance(value, dict):
        raise ValueError("public weight plan must be an object")
    return value


def _live_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    weight_verification = verify_public_weight_plan()
    termination_verification = verify_common_termination_probe_plan()
    return _read_weight_plan(), weight_verification, termination_verification


def run_phase5_runtime_plan() -> dict[str, Any]:
    public_weight_plan, weight_verification, termination_verification = _live_inputs()
    plan = build_phase5_runtime_plan(
        config=load_phase5_config(),
        termination_config=load_termination_probe_config(),
        public_weight_plan=public_weight_plan,
        weight_verification=weight_verification,
        termination_verification=termination_verification,
    )
    _write_once(default_phase5_runtime_plan_path(), plan)
    return plan


def _read_runtime_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("runtime plan is not a regular file")
    stat = path.stat()
    if stat.st_nlink != 1 or stat.st_size <= 0 or stat.st_size > RUNTIME_PLAN_MAX_BYTES:
        raise ValueError("runtime plan violates its file contract")
    value = _load_inert_json(path.read_bytes(), label="runtime plan")
    if not isinstance(value, dict):
        raise ValueError("runtime plan must be an object")
    return value


def verify_phase5_runtime_plan() -> dict[str, Any]:
    stored = _read_runtime_plan(default_phase5_runtime_plan_path())
    without_hash = {
        key: value for key, value in stored.items() if key != "runtime_plan_sha256"
    }
    if stored.get("runtime_plan_sha256") != _canonical_sha256(without_hash):
        raise ValueError("runtime plan self-hash is invalid")
    public_weight_plan, weight_verification, termination_verification = _live_inputs()
    rebuilt = build_phase5_runtime_plan(
        config=load_phase5_config(),
        termination_config=load_termination_probe_config(),
        public_weight_plan=public_weight_plan,
        weight_verification=weight_verification,
        termination_verification=termination_verification,
    )
    if stored != rebuilt:
        raise ValueError("runtime plan differs from independent rebuild")
    return {
        "status": "PASS_LOCAL_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
        "runtime_plan_sha256": stored["runtime_plan_sha256"],
        "checkpoint_count": len(stored["launch_specs"]),
        "model_download": stored["authorization"]["model_download"],
        "server_rental": stored["authorization"]["server_rental"],
        "http_execution": stored["authorization"]["http_execution"],
        "gpu_execution": stored["authorization"]["gpu_execution"],
    }
