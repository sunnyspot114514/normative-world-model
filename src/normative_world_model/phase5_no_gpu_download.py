"""Fail-closed verifier for the Phase-5 no-GPU weight-preparation grant.

This module is read-only.  It authorizes copying and downloading the frozen
public checkpoints only; it cannot authorize a GPU, a model server, retained
data access, or scientific execution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .phase5_public_metadata import _canonical_sha256, _load_inert_json

FORMAT_VERSION = "phase5-no-gpu-download-acceptance-v1"
ACCEPTED_STATUS = "LOCK_A_NO_GPU_DOWNLOAD_ACCEPTED"
REGISTERED_ACCEPTANCE_SHA256 = (
    "23df26336b5206784dd6e39f15fcf5c1a4b8b9f386d097f2958379b20d204096"
)
AUTHORIZATION = {
    "server_rental": True,
    "no_gpu_preparation": True,
    "model_download": True,
    "weight_preparation_process_execution": True,
    "gpu_execution": False,
    "model_server_process_execution": False,
    "http_model_execution": False,
    "retained_population_access": False,
    "project_prompt_access": False,
    "scientific_execution": False,
    "confirmation_generation": False,
}
EXPECTED_GOVERNANCE = {
    "confirmation_status": "RESERVED_NOT_GENERATED",
    "formal_scientific_execution_started": False,
    "retained_data_available_to_remote": False,
    "remote_payload_class": "PUBLIC_MODEL_WEIGHTS_AND_PUBLIC_METADATA_ONLY",
    "next_stage_unlocked": "NO_GPU_WEIGHT_PREPARATION_ONLY",
}


def _strict_mapping(value: Any, keys: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} schema differs")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} is not canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{label} is not a valid UTC timestamp") from error
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise ValueError(f"{label} must use whole-second UTC precision")
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(f"{label} is not canonical UTC text")
    return parsed


def verify_no_gpu_download_acceptance(
    acceptance_path: Path,
    *,
    repository_root: Path,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Verify the exact source-registered no-GPU preparation grant."""

    record = _load_inert_json(acceptance_path.read_bytes(), label="no-GPU acceptance")
    record = _strict_mapping(
        record,
        {
            "format_version",
            "status",
            "source_commit",
            "validity",
            "operator_approval",
            "authorization",
            "provider_quote",
            "limits",
            "weight_plan",
            "checkpoints",
            "remote_environment",
            "preparation_implementation",
            "internal_reviews",
            "governance",
            "acceptance_sha256",
        },
        label="no-GPU acceptance",
    )
    without_hash = {key: value for key, value in record.items() if key != "acceptance_sha256"}
    if (
        record["acceptance_sha256"] != REGISTERED_ACCEPTANCE_SHA256
        or _canonical_sha256(without_hash) != REGISTERED_ACCEPTANCE_SHA256
    ):
        raise ValueError("no-GPU acceptance differs from its source binding")
    if record["format_version"] != FORMAT_VERSION or record["status"] != ACCEPTED_STATUS:
        raise PermissionError("no-GPU acceptance identity differs")
    source_commit = record["source_commit"]
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ValueError("no-GPU preparation source commit is invalid")
    if record["authorization"] != AUTHORIZATION:
        raise PermissionError("no-GPU authorization boundary differs")
    if record["governance"] != EXPECTED_GOVERNANCE:
        raise PermissionError("no-GPU governance boundary differs")

    approval = _strict_mapping(
        record["operator_approval"],
        {
            "approved_scope",
            "request_text",
            "no_gpu_transaction_confirmation_text",
            "gpu_start_requires_action_time_confirmation",
        },
        label="no-GPU operator approval",
    )
    if (
        approval["approved_scope"]
        != "NO_GPU_WEIGHT_PREPARATION_THEN_SEPARATELY_CONFIRMED_GPU_PREFLIGHT"
        or approval["request_text"] != "可以，用无卡模式下载，然后有卡去跑吧"
        or approval["no_gpu_transaction_confirmation_text"] != "确认"
        or approval["gpu_start_requires_action_time_confirmation"] is not True
    ):
        raise PermissionError("no-GPU operator approval differs")

    quote = _strict_mapping(
        record["provider_quote"],
        {
            "provider",
            "currency",
            "instance_id",
            "zone_host",
            "gpu_model",
            "gpu_count",
            "gpu_memory_bytes",
            "no_gpu_hourly_price_minor",
            "gpu_hourly_price_minor",
            "storage_daily_price_minor",
        },
        label="no-GPU provider quote",
    )
    if quote != {
        "provider": "AutoDL",
        "currency": "CNY",
        "instance_id": "y4c4dlvw4m-87db1829",
        "zone_host": "northwest-b/d44",
        "gpu_model": "RTX PRO 6000",
        "gpu_count": 1,
        "gpu_memory_bytes": 103079215104,
        "no_gpu_hourly_price_minor": 10,
        "gpu_hourly_price_minor": 598,
        "storage_daily_price_minor": 158,
    }:
        raise ValueError("no-GPU provider quote differs")

    validity = _strict_mapping(
        record["validity"], {"not_before_utc", "expires_utc"}, label="no-GPU validity"
    )
    not_before = _utc(validity["not_before_utc"], label="no-GPU not-before")
    expires = _utc(validity["expires_utc"], label="no-GPU expiry")
    if expires <= not_before or expires - not_before > timedelta(days=2):
        raise ValueError("no-GPU validity window differs")
    observed_now = now_utc or datetime.now(UTC).replace(microsecond=0)
    if observed_now.tzinfo != UTC or not not_before <= observed_now <= expires:
        raise PermissionError("no-GPU acceptance is not currently valid")

    limits = _strict_mapping(
        record["limits"],
        {
            "currency",
            "maximum_spend_minor",
            "whole_rental_wall_clock_seconds",
            "maximum_network_download_bytes",
            "maximum_additional_data_disk_bytes",
            "observed_free_data_disk_bytes",
            "minimum_post_preparation_free_bytes",
        },
        label="no-GPU limits",
    )
    if (
        limits["currency"] != "CNY"
        or limits["maximum_spend_minor"] != 6000
        or limits["whole_rental_wall_clock_seconds"] != 36000
        or limits["minimum_post_preparation_free_bytes"] < 32 * 1024**3
        or limits["observed_free_data_disk_bytes"]
        < limits["maximum_additional_data_disk_bytes"]
        + limits["minimum_post_preparation_free_bytes"]
    ):
        raise ValueError("no-GPU resource limits differ or lack disk headroom")

    weight = _strict_mapping(
        record["weight_plan"],
        {
            "path",
            "artifact_sha256",
            "file_sha256",
            "publisher_weight_bytes",
            "agentworld_copy_bytes",
            "base_network_download_bytes",
            "weight_file_count",
        },
        label="no-GPU weight plan binding",
    )
    weight_path = (repository_root / weight["path"]).resolve()
    if not weight_path.is_relative_to(repository_root.resolve()):
        raise ValueError("no-GPU weight plan escapes repository root")
    if _sha256_file(weight_path) != weight["file_sha256"]:
        raise ValueError("no-GPU weight-plan file hash differs")
    plan = _load_inert_json(weight_path.read_bytes(), label="public weight plan")
    plan_without_hash = {key: value for key, value in plan.items() if key != "artifact_sha256"}
    if (
        plan.get("artifact_sha256") != weight["artifact_sha256"]
        or _canonical_sha256(plan_without_hash) != weight["artifact_sha256"]
        or plan.get("totals", {}).get("publisher_weight_bytes")
        != weight["publisher_weight_bytes"]
        or plan.get("totals", {}).get("weight_file_count") != weight["weight_file_count"]
    ):
        raise ValueError("no-GPU weight-plan identity or totals differ")
    checkpoints = plan.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != 2:
        raise ValueError("no-GPU weight plan must contain exactly two checkpoints")
    projected = [
        {
            "checkpoint": row.get("checkpoint"),
            "repo_id": row.get("repo_id"),
            "revision": row.get("revision"),
            "weight_plan_sha256": row.get("weight_plan", {}).get("weight_plan_sha256"),
        }
        for row in checkpoints
    ]
    if projected != record["checkpoints"]:
        raise ValueError("no-GPU checkpoint identities differ")
    checkpoint_bytes = {
        row["checkpoint"]: row["weight_plan"]["total_weight_bytes"] for row in checkpoints
    }
    if (
        checkpoint_bytes != {
            "agentworld": weight["agentworld_copy_bytes"],
            "base": weight["base_network_download_bytes"],
        }
        or limits["maximum_network_download_bytes"] != weight["base_network_download_bytes"]
        or limits["maximum_additional_data_disk_bytes"] != weight["publisher_weight_bytes"]
    ):
        raise ValueError("no-GPU download or disk budget differs from the weight plan")

    implementation = _strict_mapping(
        record["preparation_implementation"],
        {
            "path",
            "sha256",
            "manifest_row_count",
            "primary_resolver",
            "fallback_resolver",
            "fallback_after_failed_attempts",
            "resumable_base_download",
            "agentworld_source_rehash_before_copy",
            "destination_rehash_before_atomic_rename",
            "fail_closed_existing_file_policy",
        },
        label="no-GPU preparation implementation",
    )
    implementation_path = (repository_root / implementation["path"]).resolve()
    if (
        not implementation_path.is_relative_to(repository_root.resolve())
        or _sha256_file(implementation_path) != implementation["sha256"]
        or implementation["manifest_row_count"] != weight["weight_file_count"]
        or implementation["primary_resolver"] != "https://huggingface.co"
        or implementation["fallback_resolver"] != "https://hf-mirror.com"
        or implementation["fallback_after_failed_attempts"] != 2
        or any(
            implementation[field] is not True
            for field in (
                "resumable_base_download",
                "agentworld_source_rehash_before_copy",
                "destination_rehash_before_atomic_rename",
                "fail_closed_existing_file_policy",
            )
        )
    ):
        raise ValueError("no-GPU preparation implementation differs")

    environment = _strict_mapping(
        record["remote_environment"],
        {
            "manifest_sha256",
            "format_version",
            "observed_mode",
            "kernel",
            "python_version",
            "python_executable_sha256",
            "vllm_version",
            "torch_version",
            "transformers_version",
        },
        label="no-GPU remote environment",
    )
    if (
        environment["manifest_sha256"]
        != "a7fbd35254b8616dca42494869b888f9a2755122d2012f4749ed5e99b96274b5"
        or environment["observed_mode"] != "NO_GPU"
    ):
        raise ValueError("no-GPU remote environment differs")
    reviews = record["internal_reviews"]
    if (
        not isinstance(reviews, list)
        or [review.get("round") for review in reviews if isinstance(review, Mapping)] != [1, 2]
        or [review.get("result") for review in reviews if isinstance(review, Mapping)]
        != ["PASS_AFTER_FIXES", "PASS"]
    ):
        raise ValueError("no-GPU internal review record differs")
    return {
        "status": "PASS_SOURCE_BOUND_NO_GPU_WEIGHT_PREPARATION",
        "acceptance_sha256": REGISTERED_ACCEPTANCE_SHA256,
        "source_commit": source_commit,
        "expires_utc": validity["expires_utc"],
        "maximum_network_download_bytes": limits["maximum_network_download_bytes"],
        "maximum_additional_data_disk_bytes": limits["maximum_additional_data_disk_bytes"],
    }
