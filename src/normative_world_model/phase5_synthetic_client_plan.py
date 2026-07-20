"""Build a local-only Phase-5 public-synthetic client/orchestrator plan.

The module deliberately contains no HTTP, socket, subprocess, model-download,
GPU, or retained-data execution surface.  It binds the exact future public
requests, evidence ordering, retry identity, semantic gate, and server
lifecycle sequence for later Lock-A review.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .phase5_preflight import (
    STAGE2_CONFIG_SEMANTIC_SHA256,
    load_phase5_config,
    validate_stage2_contract,
)
from .phase5_public_metadata import _load_inert_json
from .phase5_runtime_plan import (
    RUNTIME_PLAN_FORMAT_VERSION,
    _read_runtime_plan,
    default_phase5_runtime_plan_path,
    verify_phase5_runtime_plan,
)
from .phase5_serialization import render_common_base_prompt
from .phase5_termination_probe import (
    TERMINATION_CONFIG_SEMANTIC_SHA256,
    TERMINATION_PLAN_FORMAT_VERSION,
    _load_live_probe_inputs,
    _read_plan,
    default_common_termination_probe_plan_path,
    verify_common_termination_probe_plan,
)

SYNTHETIC_CLIENT_PLAN_FORMAT_VERSION = "phase5-public-synthetic-client-plan-v1"
SYNTHETIC_CLIENT_PLAN_MAX_BYTES = 4 * 1024 * 1024
PUBLIC_REQUEST_SEED = 2026071803
PUBLIC_IMAGE_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A"
    "AgEBAScY42YAAAAASUVORK5CYII="
)
PUBLIC_TOY_MESSAGES = (
    {
        "role": "system",
        "content": (
            "This is a public synthetic interface probe. Return only the JSON "
            "object required by the supplied schema."
        ),
    },
    {
        "role": "user",
        "content": (
            "For the public integers 17 and 5, return their sum, the first minus "
            "the second, and the checksum literal PUBLIC-17-5."
        ),
    },
)
PUBLIC_TOY_SCHEMA = {
    "type": "object",
    "properties": {
        "sum": {"type": "integer"},
        "difference": {"type": "integer"},
        "checksum": {"type": "string", "enum": ["PUBLIC-17-5"]},
    },
    "required": ["sum", "difference", "checksum"],
    "additionalProperties": False,
}
PUBLIC_TOY_EXPECTED = {
    "sum": 22,
    "difference": 12,
    "checksum": "PUBLIC-17-5",
}
IMPLEMENTATION_SOURCE_PATHS = (
    "configs/phase5_scale_inference_draft.toml",
    "configs/phase5_common_termination_probe_candidate.toml",
    "src/normative_world_model/phase5_preflight.py",
    "src/normative_world_model/phase5_runtime_plan.py",
    "src/normative_world_model/phase5_serialization.py",
    "src/normative_world_model/phase5_synthetic_client_plan.py",
    "src/normative_world_model/phase5_termination_probe.py",
)


def _canonical_sha256(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((body + "\n").encode("utf-8")).hexdigest()


def _request_body_bytes(body: Mapping[str, Any] | None) -> bytes:
    if body is None:
        return b""
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


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


def _assert_lower_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "phase5_public_arithmetic",
            "description": "Public synthetic arithmetic interface check.",
            "schema": dict(PUBLIC_TOY_SCHEMA),
            "strict": True,
        },
    }


def _request_record(
    *,
    case_id: str,
    checkpoint: str,
    mode: str,
    method: str,
    endpoint: str,
    body: Mapping[str, Any] | None,
    seed: int | None,
) -> dict[str, Any]:
    logical_request_id = f"phase5-public-{case_id}"
    headers = {
        "Accept": "application/json",
        "X-Request-ID": logical_request_id,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    result = {
        "case_id": case_id,
        "checkpoint": checkpoint,
        "mode": mode,
        "method": method,
        "endpoint": endpoint,
        "logical_request_id": logical_request_id,
        "headers": headers,
        "request_body": None if body is None else dict(body),
        "request_body_utf8_sha256": hashlib.sha256(
            _request_body_bytes(body)
        ).hexdigest(),
        "seed": seed,
    }
    result["request_identity_sha256"] = _canonical_sha256(
        {
            "method": method,
            "endpoint": endpoint,
            "logical_request_id": logical_request_id,
            "headers": headers,
            "request_body": result["request_body"],
            "seed": seed,
        }
    )
    return result


def _toy_request_body(
    *,
    checkpoint: str,
    model_alias: str,
    mode: str,
    repetition: int,
    common_prompt: str,
) -> dict[str, Any]:
    request_id = f"phase5-public-{checkpoint}-{mode}-toy-repeat-{repetition}"
    common = {
        "model": model_alias,
        "stream": False,
        "temperature": 0.0,
        "top_p": 1.0,
        "n": 1,
        "seed": PUBLIC_REQUEST_SEED,
        "response_format": _response_format(),
        "request_id": request_id,
        "return_token_ids": True,
    }
    if mode == "native_package":
        return {
            **common,
            "messages": [dict(message) for message in PUBLIC_TOY_MESSAGES],
            "max_completion_tokens": 2048,
            "include_reasoning": True,
        }
    if mode == "common_base_serialization":
        return {
            **common,
            "prompt": common_prompt,
            "max_tokens": 2048,
            "min_tokens": 0,
            "add_special_tokens": False,
            "truncate_prompt_tokens": None,
            "stop": [],
            "stop_token_ids": [248044, 248046],
            "ignore_eos": True,
            "include_stop_str_in_output": False,
            "skip_special_tokens": True,
        }
    raise ValueError(f"unsupported public toy mode: {mode}")


def _language_only_request_body(*, checkpoint: str, model_alias: str) -> dict[str, Any]:
    case_id = f"{checkpoint}-language-only-multimodal-negative"
    return {
        "model": model_alias,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "This is a public synthetic one-pixel PNG. State its "
                            "dimensions in one short sentence."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": PUBLIC_IMAGE_DATA_URI},
                    },
                ],
            }
        ],
        "stream": False,
        "temperature": 0.0,
        "top_p": 1.0,
        "n": 1,
        "seed": PUBLIC_REQUEST_SEED,
        "max_completion_tokens": 16,
        "request_id": f"phase5-public-{case_id}",
    }


def build_phase5_synthetic_client_plan(
    *,
    config: Mapping[str, Any],
    runtime_plan: Mapping[str, Any],
    runtime_verification: Mapping[str, Any],
    termination_plan: Mapping[str, Any],
    termination_verification: Mapping[str, Any],
    common_prompt: str,
    base_common_prompt_token_ids: Sequence[int],
    agentworld_common_prompt_token_ids: Sequence[int],
    implementation_sources: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind a future public-only client without authorizing its execution."""

    failures = validate_stage2_contract(config)
    if failures:
        raise ValueError("; ".join(failures))
    authorization = config["authorization"]
    for field in (
        "model_download",
        "server_rental",
        "synthetic_preflight_lock_accepted",
        "synthetic_preflight_rental",
        "scientific_execution_lock_accepted",
        "scientific_run",
    ):
        if authorization.get(field) is not False:
            raise ValueError("synthetic client planning requires closed authorization")

    runtime_hash = _assert_lower_sha256(
        runtime_plan.get("runtime_plan_sha256"), label="runtime plan hash"
    )
    runtime_without_hash = {
        key: value
        for key, value in runtime_plan.items()
        if key != "runtime_plan_sha256"
    }
    if (
        runtime_plan.get("format_version") != RUNTIME_PLAN_FORMAT_VERSION
        or runtime_plan.get("status")
        != "LOCAL_RUNTIME_PLAN_V2_PASS_LOCK_A_NOT_BUILT_EXECUTION_NOT_AUTHORIZED"
        or runtime_hash != _canonical_sha256(runtime_without_hash)
        or runtime_verification.get("status")
        != "PASS_LOCAL_PLAN_V2_ONLY_EXECUTION_NOT_AUTHORIZED"
        or runtime_verification.get("runtime_plan_sha256") != runtime_hash
        or runtime_verification.get("http_execution") is not False
        or runtime_verification.get("gpu_execution") is not False
    ):
        raise ValueError("runtime plan is not independently verified and closed")
    if any(runtime_plan.get("authorization", {}).values()):
        raise ValueError("runtime plan authorization is open")

    termination_hash = _assert_lower_sha256(
        termination_plan.get("plan_sha256"), label="termination plan hash"
    )
    termination_without_hash = {
        key: value for key, value in termination_plan.items() if key != "plan_sha256"
    }
    if (
        termination_plan.get("format_version") != TERMINATION_PLAN_FORMAT_VERSION
        or termination_plan.get("status")
        != "CANDIDATE_PLAN_PASS_EXECUTION_NOT_AUTHORIZED"
        or termination_hash != _canonical_sha256(termination_without_hash)
        or termination_verification.get("status")
        != "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED"
        or termination_verification.get("plan_sha256") != termination_hash
        or termination_verification.get("http_execution") is not False
    ):
        raise ValueError("termination plan is not independently verified and closed")
    if any(termination_plan.get("authorization", {}).values()):
        raise ValueError("termination plan authorization is open")

    if not isinstance(common_prompt, str) or not common_prompt:
        raise ValueError("common public prompt is empty")
    base_ids = list(base_common_prompt_token_ids)
    agentworld_ids = list(agentworld_common_prompt_token_ids)
    if (
        base_ids != agentworld_ids
        or not base_ids
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in base_ids
        )
        or len(base_ids) + 2048 > 8192
    ):
        raise ValueError("common public prompt token proof differs or exceeds context")

    launches = runtime_plan.get("launch_specs")
    if (
        not isinstance(launches, list)
        or len(launches) != 2
        or [row.get("checkpoint") for row in launches] != ["agentworld", "base"]
    ):
        raise ValueError("runtime launch order differs")
    aliases = {row["checkpoint"]: row["model_alias"] for row in launches}

    termination_cases = termination_plan.get("cases")
    if not isinstance(termination_cases, list) or len(termination_cases) != 8:
        raise ValueError("termination case set differs")
    termination_references = []
    for case in termination_cases:
        body = case.get("request_body")
        if case.get("request_body_sha256") != _canonical_sha256(body):
            raise ValueError("termination request-body hash differs")
        termination_references.append(
            {
                "case_id": case["case_id"],
                "checkpoint": case["checkpoint"],
                "endpoint": termination_plan["endpoint"],
                "logical_request_id": f"phase5-public-termination-{case['case_id']}",
                "headers": {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Request-ID": f"phase5-public-termination-{case['case_id']}",
                },
                "request_body": body,
                "request_body_sha256": case["request_body_sha256"],
                "request_body_utf8_sha256": hashlib.sha256(
                    _request_body_bytes(body)
                ).hexdigest(),
                "seed": body.get("seed"),
            }
        )

    requests = []
    for checkpoint in ("agentworld", "base"):
        alias = aliases[checkpoint]
        requests.append(
            _request_record(
                case_id=f"{checkpoint}-models",
                checkpoint=checkpoint,
                mode="runtime_identity",
                method="GET",
                endpoint="/v1/models",
                body=None,
                seed=None,
            )
        )
        language_case = f"{checkpoint}-language-only-multimodal-negative"
        requests.append(
            _request_record(
                case_id=language_case,
                checkpoint=checkpoint,
                mode="language_only_negative",
                method="POST",
                endpoint="/v1/chat/completions",
                body=_language_only_request_body(
                    checkpoint=checkpoint, model_alias=alias
                ),
                seed=PUBLIC_REQUEST_SEED,
            )
        )
        for reference in termination_references:
            if reference["checkpoint"] != checkpoint:
                continue
            requests.append(
                {
                    **reference,
                    "mode": "common_termination",
                    "method": "POST",
                    "request_identity_sha256": _canonical_sha256(
                        {
                            "method": "POST",
                            "endpoint": reference["endpoint"],
                            "logical_request_id": reference["logical_request_id"],
                            "headers": reference["headers"],
                            "request_body": reference["request_body"],
                            "seed": reference["seed"],
                        }
                    ),
                }
            )
        for mode, endpoint in (
            ("native_package", config["runtime"]["native_endpoint"]),
            (
                "common_base_serialization",
                config["runtime"]["common_serialization_endpoint"],
            ),
        ):
            for repetition in (1, 2):
                case_id = f"{checkpoint}-{mode}-toy-repeat-{repetition}"
                requests.append(
                    _request_record(
                        case_id=case_id,
                        checkpoint=checkpoint,
                        mode=mode,
                        method="POST",
                        endpoint=endpoint,
                        body=_toy_request_body(
                            checkpoint=checkpoint,
                            model_alias=alias,
                            mode=mode,
                            repetition=repetition,
                            common_prompt=common_prompt,
                        ),
                        seed=PUBLIC_REQUEST_SEED,
                    )
                )

    event_order = [
        "request_prepared_and_identity_verified",
        "transport_attempt_started",
        "response_envelope_and_body_captured_raw",
        "raw_capture_fsynced",
        "response_envelope_parse_started",
        "response_envelope_parse_completed_or_failed",
        "generated_text_extracted_verbatim",
        "generated_text_capture_fsynced",
        "generated_text_json_parse_started",
        "generated_text_json_parse_completed_or_failed",
        "semantic_checks_completed",
    ]
    result = {
        "format_version": SYNTHETIC_CLIENT_PLAN_FORMAT_VERSION,
        "status": "LOCAL_PUBLIC_SYNTHETIC_CLIENT_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
        "authorization": {
            "model_download": False,
            "server_rental": False,
            "server_process_execution": False,
            "http_execution": False,
            "gpu_execution": False,
            "retained_population_access": False,
            "project_prompt_access": False,
            "scientific_execution": False,
        },
        "stage2_config_semantic_sha256": STAGE2_CONFIG_SEMANTIC_SHA256,
        "termination_config_semantic_sha256": TERMINATION_CONFIG_SEMANTIC_SHA256,
        "runtime_plan_binding": {
            "format_version": runtime_plan["format_version"],
            "runtime_plan_sha256": runtime_hash,
            "verification_status": runtime_verification["status"],
        },
        "termination_plan_binding": {
            "format_version": termination_plan["format_version"],
            "plan_sha256": termination_hash,
            "verification_status": termination_verification["status"],
            "case_count": len(termination_references),
        },
        "implementation_sources": dict(
            implementation_sources or _implementation_source_records()
        ),
        "public_content_contract": {
            "content_class": "PUBLIC_SYNTHETIC_ONLY",
            "toy_messages": [dict(message) for message in PUBLIC_TOY_MESSAGES],
            "toy_schema": dict(PUBLIC_TOY_SCHEMA),
            "toy_expected": dict(PUBLIC_TOY_EXPECTED),
            "language_only_probe_image_data_uri": PUBLIC_IMAGE_DATA_URI,
            "project_scenario_files_allowed": False,
            "selected_prompt_text_allowed": False,
            "scientific_request_bodies_allowed": False,
            "prompt_derived_artifacts_allowed": False,
        },
        "common_prompt_proof": {
            "rendered_prompt": common_prompt,
            "token_ids": base_ids,
            "token_count": len(base_ids),
            "base_equals_agentworld": True,
            "generation_headroom": 8192 - len(base_ids),
        },
        "request_sequence": requests,
        "request_count": len(requests),
        "retry_contract": {
            "maximum_retries": 1,
            "retryable_outcomes": ["transport_error", "http_5xx"],
            "nonretryable_outcomes": ["http_2xx", "http_4xx"],
            "same_logical_request_id_required": True,
            "same_method_and_endpoint_required": True,
            "same_headers_required": True,
            "same_request_body_required": True,
            "same_request_body_utf8_bytes_required": True,
            "same_seed_required": True,
            "both_attempts_retained": True,
            "second_failure_result": "TECHNICALLY_BLOCKED",
        },
        "raw_before_parse_evidence_contract": {
            "status": "SCHEMA_FROZEN_CLIENT_AND_VERIFIER_NOT_IMPLEMENTED",
            "attempt_event_order": event_order,
            "raw_capture_must_be_fsynced_before_parse": True,
            "request_body_serialization": (
                "UTF8_JSON_SORT_KEYS_NO_ASCII_ESCAPE_COMPACT_SEPARATORS_NO_TRAILING_NEWLINE"
            ),
            "raw_envelope_fields": [
                "logical_request_id",
                "attempt_index",
                "transport_outcome",
                "http_status",
                "response_headers_ordered_pairs",
                "raw_response_body_base64",
                "raw_response_body_sha256",
                "capture_monotonic_ns",
            ],
            "response_envelope_must_be_retained_before_envelope_parse": True,
            "generated_text_must_be_fsynced_verbatim_before_generated_text_json_parse": True,
            "invalid_utf8_policy": "RETAIN_RAW_BYTES_AND_FAIL_TEXT_PARSE",
        },
        "semantic_pass_gate": {
            "status": "FROZEN_CANDIDATE_VERIFIER_NOT_IMPLEMENTED",
            "all_required": True,
            "models_endpoint_alias_exact": True,
            "language_only_probe": {
                "request_is_valid_public_multimodal": True,
                "required_status_class": "4xx",
                "http_2xx_result": "FAIL_LANGUAGE_ONLY_CONTRACT",
                "http_5xx_result": "TECHNICALLY_BLOCKED_AFTER_FROZEN_RETRY",
                "exact_error_body_semantics_status": "PENDING_RUNTIME_EVIDENCE",
            },
            "termination_evidence_verifier_must_pass": True,
            "toy_schema_must_pass": True,
            "toy_oracle_exact": dict(PUBLIC_TOY_EXPECTED),
            "toy_oracle_must_pass_for_every_toy_case": True,
            "repeat_comparison": "FINAL_CONTENT_EXACT_STRING_EQUALITY_WITHIN_CHECKPOINT_AND_MODE",
            "reasoning_comparison": "REPORTED_SEPARATELY_NOT_A_PASS_PREDICATE",
            "whole_envelope_comparison": "REPORTED_SEPARATELY_NOT_A_PASS_PREDICATE",
            "missing_raw_generated_text_result": "FAIL",
        },
        "lifecycle_contract": {
            "status": "FROZEN_CANDIDATE_ORCHESTRATOR_NOT_IMPLEMENTED",
            "checkpoint_order": ["agentworld", "base"],
            "per_checkpoint_order": [
                "verify_port_8000_free_before_launch",
                "verify_snapshot_and_effective_environment",
                "capture_exact_argv_environment_and_startup_log",
                "launch_one_server",
                "poll_get_health_until_ready_or_timeout",
                "execute_request_sequence_for_checkpoint",
                "request_graceful_shutdown",
                "force_terminate_only_after_grace_timeout",
                "capture_process_exit_and_final_log",
                "verify_port_8000_released",
            ],
            "readiness_timeout_seconds": 900,
            "readiness_poll_interval_seconds": 2,
            "graceful_shutdown_timeout_seconds": 120,
            "post_force_exit_timeout_seconds": 30,
            "port_release_timeout_seconds": 30,
            "next_checkpoint_launch_forbidden_before_port_release": True,
            "simultaneous_checkpoint_servers_forbidden": True,
        },
        "implementation_state": {
            "client": "NOT_BUILT",
            "orchestrator": "NOT_BUILT",
            "independent_evidence_verifier": "NOT_BUILT",
            "network_calls_performed": False,
            "processes_started": False,
        },
        "unresolved_before_lock_a": [
            "implement_client_raw_capture_and_exact_retry_state_machine",
            "implement_independent_semantic_and_lifecycle_evidence_verifier",
            "verify_exact_language_only_error_semantics_on_both_checkpoints",
            "bind_effective_environment_allowlist_and_post_download_weight_verifier",
            "bind_container_provider_quote_and_whole_rental_cap",
            "complete_two_round_review_of_runtime_v2_and_client_plan",
        ],
    }
    result["client_plan_sha256"] = _canonical_sha256(result)
    return result


def default_phase5_synthetic_client_plan_path(
    *, runtime_plan_sha256: str | None = None, termination_plan_sha256: str | None = None
) -> Path:
    if runtime_plan_sha256 is None:
        runtime_plan_sha256 = _read_runtime_plan(
            default_phase5_runtime_plan_path()
        )["runtime_plan_sha256"]
    if termination_plan_sha256 is None:
        termination_plan_sha256 = _read_plan(
            default_common_termination_probe_plan_path()
        )["plan_sha256"]
    _assert_lower_sha256(runtime_plan_sha256, label="runtime plan hash")
    _assert_lower_sha256(termination_plan_sha256, label="termination plan hash")
    project_root = Path(__file__).resolve().parents[2]
    return (
        project_root
        / ".cache"
        / "phase5_synthetic_client_plan"
        / f"v1-{runtime_plan_sha256[:12]}-{termination_plan_sha256[:12]}.json"
    )


def _write_once(path: Path, plan: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite synthetic client plan: {path}")
    data = (json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if len(data) > SYNTHETIC_CLIENT_PLAN_MAX_BYTES:
        raise ValueError("synthetic client plan exceeds its byte cap")
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


def _live_inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    str,
    list[int],
    list[int],
]:
    runtime_plan = _read_runtime_plan(default_phase5_runtime_plan_path())
    runtime_verification = verify_phase5_runtime_plan()
    termination_plan = _read_plan(default_common_termination_probe_plan_path())
    termination_verification = verify_common_termination_probe_plan()
    base_tokenizer, agentworld_tokenizer, _ = _load_live_probe_inputs()
    common_prompt = render_common_base_prompt(base_tokenizer, PUBLIC_TOY_MESSAGES)
    base_ids = base_tokenizer.encode(common_prompt, add_special_tokens=False)
    agentworld_ids = agentworld_tokenizer.encode(common_prompt, add_special_tokens=False)
    return (
        runtime_plan,
        runtime_verification,
        termination_plan,
        termination_verification,
        common_prompt,
        list(base_ids),
        list(agentworld_ids),
    )


def run_phase5_synthetic_client_plan() -> dict[str, Any]:
    inputs = _live_inputs()
    plan = build_phase5_synthetic_client_plan(
        config=load_phase5_config(),
        runtime_plan=inputs[0],
        runtime_verification=inputs[1],
        termination_plan=inputs[2],
        termination_verification=inputs[3],
        common_prompt=inputs[4],
        base_common_prompt_token_ids=inputs[5],
        agentworld_common_prompt_token_ids=inputs[6],
    )
    _write_once(
        default_phase5_synthetic_client_plan_path(
            runtime_plan_sha256=inputs[0]["runtime_plan_sha256"],
            termination_plan_sha256=inputs[2]["plan_sha256"],
        ),
        plan,
    )
    return plan


def _read_client_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("synthetic client plan is not a regular file")
    stat = path.stat()
    if (
        stat.st_nlink != 1
        or stat.st_size <= 0
        or stat.st_size > SYNTHETIC_CLIENT_PLAN_MAX_BYTES
    ):
        raise ValueError("synthetic client plan violates its file contract")
    value = _load_inert_json(path.read_bytes(), label="synthetic client plan")
    if not isinstance(value, dict):
        raise ValueError("synthetic client plan must be an object")
    return value


def verify_phase5_synthetic_client_plan() -> dict[str, Any]:
    inputs = _live_inputs()
    path = default_phase5_synthetic_client_plan_path(
        runtime_plan_sha256=inputs[0]["runtime_plan_sha256"],
        termination_plan_sha256=inputs[2]["plan_sha256"],
    )
    stored = _read_client_plan(path)
    without_hash = {
        key: value for key, value in stored.items() if key != "client_plan_sha256"
    }
    if stored.get("client_plan_sha256") != _canonical_sha256(without_hash):
        raise ValueError("synthetic client plan self-hash is invalid")
    rebuilt = build_phase5_synthetic_client_plan(
        config=load_phase5_config(),
        runtime_plan=inputs[0],
        runtime_verification=inputs[1],
        termination_plan=inputs[2],
        termination_verification=inputs[3],
        common_prompt=inputs[4],
        base_common_prompt_token_ids=inputs[5],
        agentworld_common_prompt_token_ids=inputs[6],
    )
    if stored != rebuilt:
        raise ValueError("synthetic client plan differs from independent rebuild")
    return {
        "status": "PASS_LOCAL_CLIENT_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
        "client_plan_sha256": stored["client_plan_sha256"],
        "request_count": stored["request_count"],
        "http_execution": stored["authorization"]["http_execution"],
        "server_process_execution": stored["authorization"][
            "server_process_execution"
        ],
        "scientific_execution": stored["authorization"]["scientific_execution"],
    }
