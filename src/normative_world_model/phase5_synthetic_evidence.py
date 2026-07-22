"""Fail-closed verifier for a future Phase-5 public-synthetic preflight.

This module is deliberately read-only.  It does not contain an HTTP client,
socket use, subprocess launch, model download, GPU entry point, or retained
data access.  The future client/orchestrator may produce an evidence bundle;
this module independently checks that bundle against an externally supplied
client-plan hash and runtime bindings.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .phase5_public_metadata import _load_inert_json
from .phase5_synthetic_client_plan import verify_implementation_source_records
from .phase5_termination_probe import verify_common_termination_probe_evidence

SYNTHETIC_EVIDENCE_FORMAT_VERSION = "phase5-public-synthetic-evidence-v2"
RAW_BODY_MAX_BYTES = 4 * 1024 * 1024
CHECKPOINT_ORDER = ("agentworld", "base")
ATTEMPT_EVENT_ORDER = (
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
)
LIFECYCLE_EVENT_ORDER = (
    "prelaunch_port_probe_captured",
    "snapshot_and_environment_verification_captured",
    "argv_and_environment_fsynced",
    "process_started_with_pid_and_monotonic_time_captured",
    "startup_log_stream_capture_started",
    "every_health_poll_envelope_captured_raw",
    "readiness_result_fsynced",
    "checkpoint_request_battery_completed_or_blocked",
    "graceful_shutdown_requested_and_captured",
    "forced_termination_if_needed_captured",
    "process_exit_code_and_final_log_fsynced",
    "port_release_probe_captured",
)


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _request_body_bytes(body: Mapping[str, Any] | None) -> bytes:
    if body is None:
        return b""
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _lower_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _strict_keys(value: Any, expected: set[str], *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{label} schema differs")
    return value


def _integer(value: Any, *, label: str, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} is below its minimum")
    return value


def _decode_base64(value: Any, *, label: str, maximum: int = RAW_BODY_MAX_BYTES) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be base64 text")
    try:
        body = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError(f"{label} is not canonical base64") from error
    if len(body) > maximum:
        raise ValueError(f"{label} exceeds its byte cap")
    if base64.b64encode(body).decode("ascii") != value:
        raise ValueError(f"{label} is not canonical base64")
    return body


def _verify_hash_bound_base64(
    value: Any, digest: Any, *, label: str, maximum: int = RAW_BODY_MAX_BYTES
) -> bytes:
    body = _decode_base64(value, label=label, maximum=maximum)
    if hashlib.sha256(body).hexdigest() != _lower_sha256(digest, label=f"{label} digest"):
        raise ValueError(f"{label} digest differs")
    return body


def _verify_plan_binding(
    client_plan: Mapping[str, Any],
    termination_plan: Mapping[str, Any],
    *,
    expected_client_plan_sha256: str,
) -> None:
    verify_implementation_source_records(client_plan)
    expected = _lower_sha256(expected_client_plan_sha256, label="external client-plan binding")
    if client_plan.get("client_plan_sha256") != expected:
        raise ValueError("client plan differs from the external lock binding")
    client_without_hash = {
        key: value for key, value in client_plan.items() if key != "client_plan_sha256"
    }
    if _canonical_sha256(client_without_hash) != expected:
        raise ValueError("client plan self-hash is invalid")
    if (
        client_plan.get("format_version") != "phase5-public-synthetic-client-plan-v9"
        or client_plan.get("status")
        != (
            "LOCAL_PUBLIC_SYNTHETIC_CLIENT_PLAN_V9_ATTESTED_NONCIRCULAR_LOCK_"
            "PASS_EXECUTION_NOT_AUTHORIZED"
        )
        or not isinstance(client_plan.get("authorization"), Mapping)
        or any(value is not False for value in client_plan["authorization"].values())
        or client_plan.get("raw_before_parse_evidence_contract", {}).get("attempt_event_order")
        != list(ATTEMPT_EVENT_ORDER)
        or client_plan.get("lifecycle_contract", {}).get("lifecycle_evidence_event_order")
        != list(LIFECYCLE_EVENT_ORDER)
    ):
        raise ValueError("client plan is not the reviewed closed V9 contract")
    termination_hash = _lower_sha256(
        termination_plan.get("plan_sha256"), label="termination plan hash"
    )
    termination_without_hash = {
        key: value for key, value in termination_plan.items() if key != "plan_sha256"
    }
    if _canonical_sha256(termination_without_hash) != termination_hash:
        raise ValueError("termination plan self-hash is invalid")
    if not isinstance(termination_plan.get("authorization"), Mapping) or any(
        value is not False for value in termination_plan["authorization"].values()
    ):
        raise ValueError("termination plan authorization is open")
    binding = client_plan.get("termination_plan_binding")
    if not isinstance(binding, Mapping) or binding.get("plan_sha256") != termination_hash:
        raise ValueError("client and termination plan bindings differ")


def _verify_runtime_bindings(
    bindings: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    if not isinstance(bindings, Mapping) or set(bindings) != set(CHECKPOINT_ORDER):
        raise ValueError("runtime binding checkpoint set differs")
    result: dict[str, dict[str, str]] = {}
    expected_keys = {
        "snapshot_manifest_sha256",
        "effective_environment_sha256",
        "argv_environment_sha256",
    }
    for checkpoint in CHECKPOINT_ORDER:
        row = _strict_keys(
            bindings[checkpoint], expected_keys, label=f"runtime binding/{checkpoint}"
        )
        result[checkpoint] = {
            key: _lower_sha256(value, label=f"runtime binding/{checkpoint}/{key}")
            for key, value in row.items()
        }
    return result


def _verify_lifecycle(
    run: Mapping[str, Any],
    *,
    checkpoint: str,
    expected_case_ids: Sequence[str],
    expected_binding: Mapping[str, str],
) -> tuple[int, int, int, int]:
    events = run["lifecycle_events"]
    expected_names = list(LIFECYCLE_EVENT_ORDER)
    if not isinstance(events, list) or len(events) != len(expected_names):
        raise ValueError(f"lifecycle event count differs: {checkpoint}")
    normalized = []
    times = []
    for position, row in enumerate(events):
        item = _strict_keys(
            row,
            {"event", "monotonic_ns", "evidence"},
            label=f"lifecycle/{checkpoint}/{position}",
        )
        if item["event"] != expected_names[position]:
            raise ValueError(f"lifecycle order differs: {checkpoint}")
        timestamp = _integer(
            item["monotonic_ns"],
            label=f"lifecycle/{checkpoint}/{position}/monotonic_ns",
            minimum=0,
        )
        if times and timestamp <= times[-1]:
            raise ValueError(f"lifecycle times are not strictly increasing: {checkpoint}")
        times.append(timestamp)
        normalized.append(item["evidence"])

    prelaunch = _strict_keys(
        normalized[0],
        {"port", "free", "raw_probe_base64", "raw_probe_sha256"},
        label=f"lifecycle/{checkpoint}/prelaunch",
    )
    if prelaunch["port"] != 8000 or prelaunch["free"] is not True:
        raise ValueError(f"prelaunch port proof differs: {checkpoint}")
    _verify_hash_bound_base64(
        prelaunch["raw_probe_base64"],
        prelaunch["raw_probe_sha256"],
        label=f"lifecycle/{checkpoint}/prelaunch probe",
    )

    snapshot = _strict_keys(
        normalized[1],
        {
            "snapshot_verified",
            "environment_verified",
            "snapshot_manifest",
            "snapshot_manifest_sha256",
            "effective_environment",
            "effective_environment_sha256",
        },
        label=f"lifecycle/{checkpoint}/snapshot environment",
    )
    if snapshot["snapshot_verified"] is not True or snapshot["environment_verified"] is not True:
        raise ValueError(f"snapshot or environment was not verified: {checkpoint}")
    if not isinstance(snapshot["snapshot_manifest"], Mapping) or not isinstance(
        snapshot["effective_environment"], Mapping
    ):
        raise ValueError(f"snapshot or environment evidence is malformed: {checkpoint}")
    snapshot_hash = _canonical_sha256(snapshot["snapshot_manifest"])
    environment_hash = _canonical_sha256(snapshot["effective_environment"])
    if (
        snapshot["snapshot_manifest_sha256"] != snapshot_hash
        or snapshot_hash != expected_binding["snapshot_manifest_sha256"]
        or snapshot["effective_environment_sha256"] != environment_hash
        or environment_hash != expected_binding["effective_environment_sha256"]
    ):
        raise ValueError(f"snapshot or environment binding differs: {checkpoint}")

    launch = _strict_keys(
        normalized[2],
        {"argv", "environment", "argv_environment_sha256", "fsynced"},
        label=f"lifecycle/{checkpoint}/argv environment",
    )
    if (
        not isinstance(launch["argv"], list)
        or not launch["argv"]
        or any(not isinstance(value, str) or not value for value in launch["argv"])
        or not isinstance(launch["environment"], Mapping)
        or launch["environment"] != snapshot["effective_environment"]
        or launch["fsynced"] is not True
    ):
        raise ValueError(f"argv/environment capture is malformed: {checkpoint}")
    launch_hash = _canonical_sha256({"argv": launch["argv"], "environment": launch["environment"]})
    if (
        launch["argv_environment_sha256"] != launch_hash
        or launch_hash != expected_binding["argv_environment_sha256"]
    ):
        raise ValueError(f"argv/environment binding differs: {checkpoint}")

    started = _strict_keys(
        normalized[3],
        {"pid", "process_start_monotonic_ns"},
        label=f"lifecycle/{checkpoint}/process start",
    )
    pid = _integer(started["pid"], label=f"lifecycle/{checkpoint}/pid", minimum=1)
    start_time = _integer(
        started["process_start_monotonic_ns"],
        label=f"lifecycle/{checkpoint}/process start time",
        minimum=0,
    )
    if start_time < times[2] or start_time > times[3]:
        raise ValueError(f"process start evidence falls outside its lifecycle window: {checkpoint}")

    log_start = _strict_keys(
        normalized[4],
        {"pid", "capture_path", "from_process_start"},
        label=f"lifecycle/{checkpoint}/startup log",
    )
    if (
        log_start["pid"] != pid
        or not isinstance(log_start["capture_path"], str)
        or not log_start["capture_path"]
        or log_start["from_process_start"] is not True
    ):
        raise ValueError(f"startup log capture differs: {checkpoint}")

    health = _strict_keys(normalized[5], {"polls"}, label=f"lifecycle/{checkpoint}/health polls")
    polls = health["polls"]
    if not isinstance(polls, list) or not polls:
        raise ValueError(f"health poll evidence is empty: {checkpoint}")
    previous_poll_time = -1
    for index, poll in enumerate(polls, start=1):
        item = _strict_keys(
            poll,
            {
                "attempt_index",
                "http_status",
                "raw_response_body_base64",
                "raw_response_body_sha256",
                "monotonic_ns",
            },
            label=f"lifecycle/{checkpoint}/health poll/{index}",
        )
        if item["attempt_index"] != index:
            raise ValueError(f"health poll index differs: {checkpoint}")
        poll_time = _integer(
            item["monotonic_ns"], label=f"lifecycle/{checkpoint}/health poll time", minimum=0
        )
        if poll_time <= previous_poll_time:
            raise ValueError(f"health poll times are not increasing: {checkpoint}")
        if poll_time < start_time or poll_time > times[5]:
            raise ValueError(f"health poll falls outside its lifecycle window: {checkpoint}")
        previous_poll_time = poll_time
        _verify_hash_bound_base64(
            item["raw_response_body_base64"],
            item["raw_response_body_sha256"],
            label=f"lifecycle/{checkpoint}/health poll body/{index}",
        )
        if item["http_status"] is not None:
            _integer(item["http_status"], label=f"lifecycle/{checkpoint}/health status")
    if polls[-1]["http_status"] != 200:
        raise ValueError(f"final health poll is not ready: {checkpoint}")

    readiness = _strict_keys(
        normalized[6], {"ready", "fsynced"}, label=f"lifecycle/{checkpoint}/readiness"
    )
    if readiness != {"ready": True, "fsynced": True}:
        raise ValueError(f"readiness evidence differs: {checkpoint}")

    battery = _strict_keys(
        normalized[7], {"status", "case_ids"}, label=f"lifecycle/{checkpoint}/battery"
    )
    if battery["status"] != "COMPLETED" or battery["case_ids"] != list(expected_case_ids):
        raise ValueError(f"request battery evidence differs: {checkpoint}")

    shutdown = _strict_keys(
        normalized[8],
        {"requested", "signal", "captured"},
        label=f"lifecycle/{checkpoint}/shutdown",
    )
    if (
        shutdown["requested"] is not True
        or shutdown["captured"] is not True
        or not isinstance(shutdown["signal"], str)
        or not shutdown["signal"]
    ):
        raise ValueError(f"graceful shutdown evidence differs: {checkpoint}")

    forced = _strict_keys(
        normalized[9],
        {"used", "grace_timeout_elapsed", "reason", "captured"},
        label=f"lifecycle/{checkpoint}/forced termination",
    )
    if forced["captured"] is not True or not isinstance(forced["used"], bool):
        raise ValueError(f"forced termination evidence differs: {checkpoint}")
    if forced["used"]:
        if forced["grace_timeout_elapsed"] is not True or forced["reason"] != "GRACE_TIMEOUT":
            raise ValueError(f"forced termination was not grace-bounded: {checkpoint}")
    elif forced["grace_timeout_elapsed"] is not False or forced["reason"] != "NOT_NEEDED":
        raise ValueError(f"unused forced termination evidence differs: {checkpoint}")

    exit_row = _strict_keys(
        normalized[10],
        {"exit_code", "final_log_base64", "final_log_sha256", "fsynced"},
        label=f"lifecycle/{checkpoint}/exit",
    )
    _integer(exit_row["exit_code"], label=f"lifecycle/{checkpoint}/exit code")
    if exit_row["fsynced"] is not True:
        raise ValueError(f"final log was not fsynced: {checkpoint}")
    _verify_hash_bound_base64(
        exit_row["final_log_base64"],
        exit_row["final_log_sha256"],
        label=f"lifecycle/{checkpoint}/final log",
    )

    release = _strict_keys(
        normalized[11],
        {"port", "released", "raw_probe_base64", "raw_probe_sha256"},
        label=f"lifecycle/{checkpoint}/port release",
    )
    if release["port"] != 8000 or release["released"] is not True:
        raise ValueError(f"port release evidence differs: {checkpoint}")
    _verify_hash_bound_base64(
        release["raw_probe_base64"],
        release["raw_probe_sha256"],
        label=f"lifecycle/{checkpoint}/release probe",
    )
    return times[0], times[6], times[7], times[-1]


def _response_object(raw_body: bytes, *, label: str) -> Mapping[str, Any]:
    value = _load_inert_json(raw_body, label=label)
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _model_aliases(requests: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for request in requests:
        body = request.get("request_body")
        if isinstance(body, Mapping) and isinstance(body.get("model"), str):
            aliases[str(request.get("checkpoint"))].add(body["model"])
    result = {}
    for checkpoint in CHECKPOINT_ORDER:
        if len(aliases[checkpoint]) != 1:
            raise ValueError(f"model alias is not unique: {checkpoint}")
        result[checkpoint] = next(iter(aliases[checkpoint]))
    return result


def _verify_attempt_identity(
    attempt: Mapping[str, Any], request: Mapping[str, Any], *, label: str
) -> tuple[bytes, bytes, int, int]:
    expected_keys = {
        "case_id",
        "attempt_index",
        "method",
        "endpoint",
        "logical_request_id",
        "headers_ordered_pairs",
        "request_body_base64",
        "request_body_utf8_sha256",
        "seed",
        "event_trace",
        "transport_outcome",
        "http_status",
        "response_headers_ordered_pairs",
        "raw_response_body_base64",
        "raw_response_body_sha256",
        "generated_text",
        "generated_text_utf8_sha256",
    }
    row = _strict_keys(attempt, expected_keys, label=label)
    expected_identity = _canonical_sha256(
        {
            "method": request["method"],
            "endpoint": request["endpoint"],
            "logical_request_id": request["logical_request_id"],
            "headers": request["headers"],
            "request_body": request["request_body"],
            "seed": request["seed"],
        }
    )
    if request.get("request_identity_sha256") != expected_identity:
        raise ValueError(f"planned request identity hash differs: {label}")
    if (
        row["case_id"] != request["case_id"]
        or row["method"] != request["method"]
        or row["endpoint"] != request["endpoint"]
        or row["logical_request_id"] != request["logical_request_id"]
        or row["headers_ordered_pairs"] != [list(item) for item in request["headers"].items()]
        or row["seed"] != request["seed"]
    ):
        raise ValueError(f"request identity differs: {label}")
    body = _verify_hash_bound_base64(
        row["request_body_base64"],
        row["request_body_utf8_sha256"],
        label=f"{label}/request body",
    )
    expected_body = _request_body_bytes(request["request_body"])
    if (
        body != expected_body
        or row["request_body_utf8_sha256"] != request["request_body_utf8_sha256"]
    ):
        raise ValueError(f"request bytes differ: {label}")
    trace = row["event_trace"]
    expected_events = list(ATTEMPT_EVENT_ORDER)
    if not isinstance(trace, list) or len(trace) != len(expected_events):
        raise ValueError(f"attempt event trace count differs: {label}")
    trace_times = []
    for index, event in enumerate(trace):
        item = _strict_keys(event, {"event", "monotonic_ns"}, label=f"{label}/event/{index}")
        if item["event"] != expected_events[index]:
            raise ValueError(f"raw-before-parse event order differs: {label}")
        timestamp = _integer(item["monotonic_ns"], label=f"{label}/event time", minimum=0)
        if trace_times and timestamp <= trace_times[-1]:
            raise ValueError(f"attempt event times are not increasing: {label}")
        trace_times.append(timestamp)
    if not isinstance(row["response_headers_ordered_pairs"], list) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(value, str) for value in pair)
        for pair in row["response_headers_ordered_pairs"]
    ):
        raise ValueError(f"response headers are malformed: {label}")
    raw = _verify_hash_bound_base64(
        row["raw_response_body_base64"],
        row["raw_response_body_sha256"],
        label=f"{label}/raw response body",
    )
    return body, raw, trace_times[0], trace_times[-1]


def _toy_generated_text(response: Mapping[str, Any], *, mode: str, alias: str, label: str) -> str:
    if response.get("model") != alias:
        raise ValueError(f"toy response model differs: {label}")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ValueError(f"toy response choices differ: {label}")
    choice = choices[0]
    if mode == "native_package":
        if response.get("object") != "chat.completion":
            raise ValueError(f"native response object differs: {label}")
        message = choice.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise ValueError(f"native final content is missing: {label}")
        return message["content"]
    if mode == "common_base_serialization":
        if response.get("object") != "text_completion" or not isinstance(choice.get("text"), str):
            raise ValueError(f"common final content is missing: {label}")
        return choice["text"]
    raise ValueError(f"unsupported toy mode: {mode}")


def _toy_reasoning(response: Mapping[str, Any], *, mode: str) -> Any:
    if mode != "native_package":
        return None
    choice = response["choices"][0]
    message = choice["message"]
    if "reasoning" in message:
        return message["reasoning"]
    return message.get("reasoning_content")


def _verify_final_response(
    request: Mapping[str, Any],
    attempt: Mapping[str, Any],
    raw: bytes,
    *,
    alias: str,
    toy_expected: Mapping[str, Any],
    termination_rows: list[dict[str, Any]],
) -> tuple[str | None, Any, bytes]:
    label = str(request["case_id"])
    status = attempt["http_status"]
    mode = request["mode"]
    if mode == "runtime_identity":
        if (
            status != 200
            or attempt["generated_text"] is not None
            or attempt["generated_text_utf8_sha256"] is not None
        ):
            raise ValueError(f"models endpoint status or generated-text evidence differs: {label}")
        response = _response_object(raw, label=f"models/{label}")
        data = response.get("data")
        if (
            response.get("object") != "list"
            or not isinstance(data, list)
            or len(data) != 1
            or not isinstance(data[0], Mapping)
            or data[0].get("id") != alias
        ):
            raise ValueError(f"models endpoint alias differs: {label}")
        return None, None, raw
    if mode == "language_only_negative":
        if (
            status != 400
            or attempt["generated_text"] is not None
            or attempt["generated_text_utf8_sha256"] is not None
        ):
            raise ValueError(f"language-only response status differs: {label}")
        response = _response_object(raw, label=f"language-only/{label}")
        error = response.get("error")
        if not isinstance(error, Mapping):
            raise ValueError(f"language-only error object is missing: {label}")
        message = error.get("message")
        if (
            error.get("code") != 400
            or error.get("type") != "BadRequestError"
            or error.get("param") not in {"image", "vision_chunk"}
            or not isinstance(message, str)
            or "At most 0 " not in message
            or "(s) may be provided in one prompt." not in message
        ):
            raise ValueError(f"language-only error semantics differ: {label}")
        return None, None, raw
    if status != 200:
        raise ValueError(f"final HTTP status differs: {label}")
    response = _response_object(raw, label=f"response/{label}")
    if mode == "common_termination":
        choices = response.get("choices")
        generated = (
            choices[0].get("text")
            if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], Mapping)
            else None
        )
        if not isinstance(generated, str):
            raise ValueError(f"termination generated text is missing: {label}")
        termination_rows.append(
            {
                "case_id": label,
                "request_body": request["request_body"],
                "http_status": status,
                "raw_response_text": raw.decode("utf-8"),
            }
        )
    elif mode in {"native_package", "common_base_serialization"}:
        generated = _toy_generated_text(response, mode=mode, alias=alias, label=label)
        reasoning = _toy_reasoning(response, mode=mode)
        parsed = _load_inert_json(generated.encode("utf-8"), label=f"toy final/{label}")
        if (
            not isinstance(parsed, Mapping)
            or set(parsed) != set(toy_expected)
            or parsed != toy_expected
            or not isinstance(parsed["sum"], int)
            or isinstance(parsed["sum"], bool)
            or not isinstance(parsed["difference"], int)
            or isinstance(parsed["difference"], bool)
            or not isinstance(parsed["checksum"], str)
        ):
            raise ValueError(f"toy semantic oracle differs: {label}")
    else:
        raise ValueError(f"unsupported request mode: {mode}")
    if mode == "common_termination":
        reasoning = None
    if attempt["generated_text"] != generated:
        raise ValueError(f"verbatim generated-text capture differs: {label}")
    expected_text_hash = hashlib.sha256(generated.encode("utf-8")).hexdigest()
    if attempt["generated_text_utf8_sha256"] != expected_text_hash:
        raise ValueError(f"generated-text digest differs: {label}")
    return generated, reasoning, raw


def verify_phase5_synthetic_evidence(
    client_plan: Mapping[str, Any],
    termination_plan: Mapping[str, Any],
    evidence_bundle: Mapping[str, Any],
    *,
    expected_client_plan_sha256: str,
    expected_runtime_bindings: Mapping[str, Mapping[str, str]],
    expected_lock_a_acceptance_sha256: str,
) -> dict[str, Any]:
    """Verify one complete, accepted-candidate public-synthetic evidence bundle."""

    _verify_plan_binding(
        client_plan,
        termination_plan,
        expected_client_plan_sha256=expected_client_plan_sha256,
    )
    runtime_bindings = _verify_runtime_bindings(expected_runtime_bindings)
    expected_lock_a = _lower_sha256(
        expected_lock_a_acceptance_sha256,
        label="external Lock-A acceptance binding",
    )
    bundle = _strict_keys(
        evidence_bundle,
        {
            "format_version",
            "client_plan_sha256",
            "lock_a_acceptance_sha256",
            "termination_plan_sha256",
            "checkpoint_runs",
            "bundle_sha256",
        },
        label="synthetic evidence bundle",
    )
    without_hash = {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    if (
        bundle["format_version"] != SYNTHETIC_EVIDENCE_FORMAT_VERSION
        or bundle["client_plan_sha256"] != expected_client_plan_sha256
        or bundle["lock_a_acceptance_sha256"] != expected_lock_a
        or bundle["termination_plan_sha256"] != termination_plan["plan_sha256"]
        or bundle["bundle_sha256"] != _canonical_sha256(without_hash)
    ):
        raise ValueError("synthetic evidence bundle binding differs")

    requests = client_plan.get("request_sequence")
    if (
        not isinstance(requests, list)
        or len(requests) != client_plan.get("request_count")
        or any(not isinstance(row, Mapping) for row in requests)
    ):
        raise ValueError("client request sequence is malformed")
    case_ids = [row.get("case_id") for row in requests]
    if any(not isinstance(case_id, str) for case_id in case_ids) or len(set(case_ids)) != len(
        case_ids
    ):
        raise ValueError("client request case set is malformed")
    aliases = _model_aliases(requests)
    runs = bundle["checkpoint_runs"]
    if not isinstance(runs, list) or [
        row.get("checkpoint") for row in runs if isinstance(row, Mapping)
    ] != list(CHECKPOINT_ORDER):
        raise ValueError("checkpoint run order differs")

    termination_rows: list[dict[str, Any]] = []
    repeat_texts: dict[tuple[str, str], list[str]] = defaultdict(list)
    repeat_reasoning: dict[tuple[str, str], list[Any]] = defaultdict(list)
    repeat_envelopes: dict[tuple[str, str], list[bytes]] = defaultdict(list)
    lifecycle_bounds = []
    total_attempts = 0
    for run in runs:
        run_row = _strict_keys(
            run,
            {"checkpoint", "lifecycle_events", "attempts"},
            label="checkpoint run",
        )
        checkpoint = run_row["checkpoint"]
        planned = [row for row in requests if row["checkpoint"] == checkpoint]
        planned_case_ids = [row["case_id"] for row in planned]
        lifecycle_bounds.append(
            _verify_lifecycle(
                run_row,
                checkpoint=checkpoint,
                expected_case_ids=planned_case_ids,
                expected_binding=runtime_bindings[checkpoint],
            )
        )
        attempts = run_row["attempts"]
        if not isinstance(attempts, list):
            raise ValueError(f"attempt list is malformed: {checkpoint}")
        cursor = 0
        previous_attempt_end = lifecycle_bounds[-1][1]
        for request in planned:
            case_attempts = []
            while (
                cursor < len(attempts)
                and isinstance(attempts[cursor], Mapping)
                and attempts[cursor].get("case_id") == request["case_id"]
            ):
                case_attempts.append(attempts[cursor])
                cursor += 1
            if len(case_attempts) not in {1, 2}:
                raise ValueError(f"attempt count differs: {request['case_id']}")
            first_status = case_attempts[0].get("http_status")
            first_outcome = case_attempts[0].get("transport_outcome")
            retryable = first_outcome == "transport_error" or (
                first_outcome == "http_response"
                and isinstance(first_status, int)
                and not isinstance(first_status, bool)
                and 500 <= first_status <= 599
            )
            if (len(case_attempts) == 2) != retryable:
                raise ValueError(f"retry predicate differs: {request['case_id']}")
            for attempt_index, attempt in enumerate(case_attempts, start=1):
                if (
                    not isinstance(attempt.get("attempt_index"), int)
                    or isinstance(attempt.get("attempt_index"), bool)
                    or attempt["attempt_index"] != attempt_index
                ):
                    raise ValueError(f"attempt index differs: {request['case_id']}")
                _, raw, attempt_start, attempt_end = _verify_attempt_identity(
                    attempt, request, label=f"{request['case_id']}/attempt-{attempt_index}"
                )
                if attempt_start <= previous_attempt_end:
                    raise ValueError(
                        f"attempt sequence times overlap or reorder: {request['case_id']}"
                    )
                previous_attempt_end = attempt_end
                total_attempts += 1
                outcome = attempt["transport_outcome"]
                if outcome == "transport_error":
                    if (
                        attempt["http_status"] is not None
                        or raw
                        or attempt["generated_text"] is not None
                        or attempt["generated_text_utf8_sha256"] is not None
                    ):
                        raise ValueError(
                            f"transport failure retained response content: {request['case_id']}"
                        )
                    if attempt_index != 1 or len(case_attempts) != 2:
                        raise ValueError(
                            f"terminal transport failure is not acceptable: {request['case_id']}"
                        )
                    continue
                if outcome != "http_response":
                    raise ValueError(f"transport outcome differs: {request['case_id']}")
                status = _integer(
                    attempt["http_status"], label=f"HTTP status/{request['case_id']}", minimum=100
                )
                if status > 599:
                    raise ValueError(f"HTTP status is out of range: {request['case_id']}")
                if 500 <= status <= 599:
                    if (
                        attempt["generated_text"] is not None
                        or attempt["generated_text_utf8_sha256"] is not None
                    ):
                        raise ValueError(
                            f"retryable 5xx retained generated text: {request['case_id']}"
                        )
                    if attempt_index != 1 or len(case_attempts) != 2:
                        raise ValueError(f"terminal 5xx is not acceptable: {request['case_id']}")
                    continue
                if attempt_index != len(case_attempts):
                    raise ValueError(f"nonretryable response was retried: {request['case_id']}")
                text, reasoning, envelope = _verify_final_response(
                    request,
                    attempt,
                    raw,
                    alias=aliases[checkpoint],
                    toy_expected=client_plan["semantic_pass_gate"]["toy_oracle_exact"],
                    termination_rows=termination_rows,
                )
                if request["mode"] in {"native_package", "common_base_serialization"}:
                    repeat_texts[(checkpoint, request["mode"])].append(text or "")
                    repeat_reasoning[(checkpoint, request["mode"])].append(reasoning)
                    repeat_envelopes[(checkpoint, request["mode"])].append(envelope)
        if cursor != len(attempts):
            raise ValueError(f"attempt sequence has extra or reordered rows: {checkpoint}")
        if previous_attempt_end >= lifecycle_bounds[-1][2]:
            raise ValueError(f"request battery completion predates request evidence: {checkpoint}")

    if lifecycle_bounds[1][0] <= lifecycle_bounds[0][1]:
        raise ValueError("base launch began before AgentWorld port release proof")
    if set(repeat_texts) != {
        (checkpoint, mode)
        for checkpoint in CHECKPOINT_ORDER
        for mode in ("native_package", "common_base_serialization")
    } or any(len(values) != 2 or values[0] != values[1] for values in repeat_texts.values()):
        raise ValueError("toy repeat final-content semantics differ")

    termination_result = verify_common_termination_probe_evidence(
        termination_plan,
        termination_rows,
        expected_plan_sha256=termination_plan["plan_sha256"],
    )
    repeat_diagnostics = []
    for checkpoint in CHECKPOINT_ORDER:
        for mode in ("native_package", "common_base_serialization"):
            key = (checkpoint, mode)
            repeat_diagnostics.append(
                {
                    "checkpoint": checkpoint,
                    "mode": mode,
                    "final_content_equal": repeat_texts[key][0] == repeat_texts[key][1],
                    "reasoning_equal": repeat_reasoning[key][0] == repeat_reasoning[key][1],
                    "whole_response_bytes_equal": repeat_envelopes[key][0]
                    == repeat_envelopes[key][1],
                }
            )
    return {
        "status": "PASS_PUBLIC_SYNTHETIC_EVIDENCE_V2",
        "client_plan_sha256": expected_client_plan_sha256,
        "lock_a_acceptance_sha256": expected_lock_a,
        "bundle_sha256": bundle["bundle_sha256"],
        "checkpoint_count": len(runs),
        "request_count": len(requests),
        "attempt_count": total_attempts,
        "termination_case_count": termination_result["case_count"],
        "repeat_cells": len(repeat_texts),
        "repeat_diagnostics": repeat_diagnostics,
    }
