"""Fail-closed verifier for a future Phase-5 Lock-A acceptance certificate.

The module does not create or approve a certificate.  It only validates an
already reviewed, externally hash-bound record before any remote side effect.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from .phase5_public_metadata import _canonical_sha256, _load_inert_json

LOCK_A_FORMAT_VERSION = "phase5-lock-a-acceptance-v1"
LOCK_A_ACCEPTED_STATUS = "LOCK_A_ACCEPTED_PUBLIC_SYNTHETIC_ONLY"
# This is intentionally closed in the committed V6 execution source.  A future
# reviewed Lock-A certificate must be registered here by exact digest before the
# runner can consume it; callers cannot supply their own trust root.
REGISTERED_LOCK_A_ACCEPTANCE_SHA256: str | None = None
LOCK_A_AUTHORIZATION = {
    "model_download": True,
    "server_rental": True,
    "no_gpu_preparation": True,
    "server_process_execution": True,
    "http_execution": True,
    "gpu_execution": True,
    "public_synthetic_only": True,
    "retained_population_access": False,
    "project_prompt_access": False,
    "scientific_execution": False,
    "confirmation_generation": False,
}


def registered_lock_a_acceptance_sha256() -> str:
    """Return the source-registered trust root or fail closed."""

    if REGISTERED_LOCK_A_ACCEPTANCE_SHA256 is None:
        raise PermissionError("no Lock-A acceptance digest is registered in the execution source")
    return _lower_sha256(
        REGISTERED_LOCK_A_ACCEPTANCE_SHA256,
        label="source-registered Lock-A acceptance binding",
    )


def _lower_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _positive_integer(value: Any, *, label: str, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} is not a positive integer")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} exceeds its absolute safety bound")
    return value


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


def _strict_mapping(value: Any, keys: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} schema differs")
    return value


def verify_lock_a_acceptance(
    acceptance: Mapping[str, Any],
    *,
    expected_acceptance_sha256: str,
    expected_client_plan_sha256: str,
    expected_runtime_bindings_sha256: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate one externally bound, time-limited synthetic-only acceptance."""

    expected_acceptance = _lower_sha256(
        expected_acceptance_sha256,
        label="external Lock-A acceptance binding",
    )
    expected_client = _lower_sha256(
        expected_client_plan_sha256,
        label="external client-plan binding",
    )
    expected_runtime = _lower_sha256(
        expected_runtime_bindings_sha256,
        label="external runtime-bindings binding",
    )
    body = json.dumps(
        acceptance,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    record = _load_inert_json(body, label="Lock-A acceptance")
    record = _strict_mapping(
        record,
        {
            "format_version",
            "status",
            "source_commit",
            "client_plan_sha256",
            "client_plan_file_sha256",
            "runtime_bindings_sha256",
            "remote_environment_manifest_sha256",
            "weight_download_plan_sha256",
            "provider_quote",
            "limits",
            "authorization",
            "governance",
            "validity",
            "review_record_sha256s",
            "operator_approval_sha256",
            "acceptance_sha256",
        },
        label="Lock-A acceptance",
    )
    without_hash = {key: value for key, value in record.items() if key != "acceptance_sha256"}
    if (
        record["acceptance_sha256"] != expected_acceptance
        or _canonical_sha256(without_hash) != expected_acceptance
    ):
        raise ValueError("Lock-A acceptance differs from its external binding")
    if (
        record["format_version"] != LOCK_A_FORMAT_VERSION
        or record["status"] != LOCK_A_ACCEPTED_STATUS
        or record["client_plan_sha256"] != expected_client
        or record["runtime_bindings_sha256"] != expected_runtime
    ):
        raise PermissionError("Lock-A acceptance identity differs")
    source_commit = record["source_commit"]
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise ValueError("Lock-A source commit is invalid")
    for field in (
        "client_plan_file_sha256",
        "remote_environment_manifest_sha256",
        "weight_download_plan_sha256",
        "operator_approval_sha256",
    ):
        _lower_sha256(record[field], label=f"Lock-A {field}")

    quote = _strict_mapping(
        record["provider_quote"],
        {
            "provider",
            "currency",
            "gpu_model",
            "gpu_count",
            "gpu_memory_bytes",
            "gpu_hourly_price_minor",
            "storage_daily_price_minor",
            "quote_evidence_sha256",
        },
        label="Lock-A provider quote",
    )
    if (
        quote["provider"] != "AutoDL"
        or quote["currency"] != "CNY"
        or not isinstance(quote["gpu_model"], str)
        or not quote["gpu_model"]
        or quote["gpu_count"] != 1
    ):
        raise ValueError("Lock-A provider quote identity differs")
    _positive_integer(
        quote["gpu_memory_bytes"],
        label="Lock-A GPU memory bytes",
    )
    _positive_integer(
        quote["gpu_hourly_price_minor"],
        label="Lock-A GPU hourly price",
    )
    _positive_integer(
        quote["storage_daily_price_minor"],
        label="Lock-A storage daily price",
    )
    _lower_sha256(quote["quote_evidence_sha256"], label="Lock-A quote evidence")

    limits = _strict_mapping(
        record["limits"],
        {
            "currency",
            "maximum_spend_minor",
            "whole_rental_wall_clock_seconds",
            "maximum_download_bytes",
            "minimum_free_data_disk_bytes",
            "minimum_post_download_free_bytes",
        },
        label="Lock-A limits",
    )
    if limits["currency"] != "CNY":
        raise ValueError("Lock-A limit currency differs")
    _positive_integer(
        limits["maximum_spend_minor"],
        label="Lock-A maximum spend",
        maximum=100_000,
    )
    _positive_integer(
        limits["whole_rental_wall_clock_seconds"],
        label="Lock-A wall-clock cap",
        maximum=24 * 60 * 60,
    )
    _positive_integer(
        limits["maximum_download_bytes"],
        label="Lock-A maximum download bytes",
    )
    minimum_free = _positive_integer(
        limits["minimum_free_data_disk_bytes"],
        label="Lock-A minimum free data-disk bytes",
    )
    post_download_free = _positive_integer(
        limits["minimum_post_download_free_bytes"],
        label="Lock-A minimum post-download free bytes",
    )
    if post_download_free < 16 * 1024**3:
        raise ValueError("Lock-A post-download headroom is below 16 GiB")
    if minimum_free < limits["maximum_download_bytes"] + post_download_free:
        raise ValueError("Lock-A free-disk floor does not leave post-download headroom")

    if record["authorization"] != LOCK_A_AUTHORIZATION:
        raise PermissionError("Lock-A authorization is not exact synthetic-only authority")
    governance = _strict_mapping(
        record["governance"],
        {
            "confirmation_status",
            "formal_scientific_execution_started",
            "retained_data_available_to_remote",
            "next_stage_unlocked",
        },
        label="Lock-A governance",
    )
    if governance != {
        "confirmation_status": "RESERVED_NOT_GENERATED",
        "formal_scientific_execution_started": False,
        "retained_data_available_to_remote": False,
        "next_stage_unlocked": "SYNTHETIC_PREFLIGHT_ONLY",
    }:
        raise PermissionError("Lock-A governance boundary differs")

    validity = _strict_mapping(
        record["validity"],
        {"not_before_utc", "expires_utc"},
        label="Lock-A validity",
    )
    not_before = _utc(validity["not_before_utc"], label="Lock-A not-before")
    expires = _utc(validity["expires_utc"], label="Lock-A expiry")
    if expires <= not_before or expires - not_before > timedelta(days=7):
        raise ValueError("Lock-A validity window differs")
    observed_now = now_utc or datetime.now(UTC).replace(microsecond=0)
    if observed_now.tzinfo != UTC or not not_before <= observed_now <= expires:
        raise PermissionError("Lock-A acceptance is not currently valid")

    reviews = record["review_record_sha256s"]
    if not isinstance(reviews, list) or len(reviews) != 2 or len(set(reviews)) != 2:
        raise ValueError("Lock-A must bind exactly two distinct review records")
    for index, review in enumerate(reviews):
        _lower_sha256(review, label=f"Lock-A review record/{index}")
    return {
        "status": "PASS_EXTERNALLY_BOUND_LOCK_A_ACCEPTANCE",
        "acceptance_sha256": expected_acceptance,
        "source_commit": source_commit,
        "client_plan_sha256": expected_client,
        "runtime_bindings_sha256": expected_runtime,
        "maximum_spend_minor": limits["maximum_spend_minor"],
        "whole_rental_wall_clock_seconds": limits["whole_rental_wall_clock_seconds"],
        "expires_utc": validity["expires_utc"],
    }
