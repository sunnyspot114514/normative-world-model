"""Authorization-gated producer for Phase-5 public-synthetic evidence.

The orchestration core is intentionally adapter-driven: this module contains no
HTTP, socket, subprocess, model-download, GPU, or retained-data implementation.
It owns request ordering, retries, write-once/fsync evidence, and lifecycle
sequencing.  A future reviewed remote adapter may supply the narrow transport
and process operations only after Lock A is accepted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .phase5_public_metadata import _load_inert_json
from .phase5_synthetic_evidence import (
    ATTEMPT_EVENT_ORDER,
    CHECKPOINT_ORDER,
    LIFECYCLE_EVENT_ORDER,
    SYNTHETIC_EVIDENCE_FORMAT_VERSION,
    _canonical_sha256,
    _verify_plan_binding,
    _verify_runtime_bindings,
    verify_phase5_synthetic_evidence,
)

LOCK_A_ACCEPTED_STATUS = "LOCK_A_ACCEPTED_PUBLIC_SYNTHETIC_ONLY"
CASE_ID_PATTERN = re.compile(r"^[a-z0-9_-]+$")
MAX_RAW_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_HEALTH_POLLS = 451


@dataclass(frozen=True)
class SyntheticHTTPResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


@dataclass(frozen=True)
class SyntheticRuntimeSpec:
    checkpoint: str
    snapshot_manifest: Mapping[str, Any]
    effective_environment: Mapping[str, str]
    argv: tuple[str, ...]


@dataclass(frozen=True)
class SyntheticProcess:
    pid: int
    startup_log_capture_path: str
    log_capture_from_process_start: bool


class SyntheticTransportError(RuntimeError):
    """Retryable transport failure raised by a reviewed adapter."""


class SyntheticRuntimeAdapter(Protocol):
    def probe_port_8000(self) -> tuple[bool, bytes]: ...

    def verify_snapshot_and_environment(self, spec: SyntheticRuntimeSpec) -> tuple[bool, bool]: ...

    def launch(self, spec: SyntheticRuntimeSpec) -> SyntheticProcess: ...

    def poll_health(self) -> SyntheticHTTPResponse: ...

    def send_request(
        self,
        *,
        method: str,
        endpoint: str,
        headers: Sequence[tuple[str, str]],
        body: bytes,
    ) -> SyntheticHTTPResponse: ...

    def request_graceful_shutdown(self, process: SyntheticProcess) -> str: ...

    def wait_for_exit(self, process: SyntheticProcess, timeout_seconds: int) -> bool: ...

    def force_terminate(self, process: SyntheticProcess) -> None: ...

    def exit_code(self, process: SyntheticProcess) -> int: ...

    def final_log_bytes(self, process: SyntheticProcess) -> bytes: ...

    def emergency_cleanup(self) -> Mapping[str, Any]: ...


class _MonotonicTrace:
    def __init__(self, clock_ns: Callable[[], int]) -> None:
        self._clock_ns = clock_ns
        self._last = -1

    def next(self) -> int:
        observed = self._clock_ns()
        if not isinstance(observed, int) or isinstance(observed, bool) or observed < 0:
            raise ValueError("monotonic clock returned an invalid value")
        self._last = max(observed, self._last + 1)
        return self._last


def _canonical_request_body(body: Mapping[str, Any] | None) -> bytes:
    if body is None:
        return b""
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _strict_authorization(
    authorization: Mapping[str, Any], *, expected_client_plan_sha256: str
) -> None:
    expected_keys = {
        "status",
        "client_plan_sha256",
        "runtime_bindings_sha256",
        "public_synthetic_only",
        "server_process_execution",
        "http_execution",
        "gpu_execution",
        "retained_population_access",
        "project_prompt_access",
        "scientific_execution",
    }
    if not isinstance(authorization, Mapping) or set(authorization) != expected_keys:
        raise PermissionError("Lock-A authorization schema differs")
    if (
        authorization["status"] != LOCK_A_ACCEPTED_STATUS
        or authorization["client_plan_sha256"] != expected_client_plan_sha256
        or authorization["public_synthetic_only"] is not True
        or authorization["server_process_execution"] is not True
        or authorization["http_execution"] is not True
        or authorization["gpu_execution"] is not True
        or authorization["retained_population_access"] is not False
        or authorization["project_prompt_access"] is not False
        or authorization["scientific_execution"] is not False
    ):
        raise PermissionError("Lock-A authorization is not accepted and synthetic-only")


def _normalize_runtime_specs(
    specs: Mapping[str, SyntheticRuntimeSpec],
) -> dict[str, SyntheticRuntimeSpec]:
    if not isinstance(specs, Mapping) or set(specs) != set(CHECKPOINT_ORDER):
        raise ValueError("runtime spec checkpoint set differs")
    normalized = {}
    for checkpoint in CHECKPOINT_ORDER:
        spec = specs[checkpoint]
        if not isinstance(spec, SyntheticRuntimeSpec) or spec.checkpoint != checkpoint:
            raise ValueError(f"runtime spec is malformed: {checkpoint}")
        snapshot_bytes = json.dumps(
            spec.snapshot_manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        snapshot = _load_inert_json(snapshot_bytes, label=f"runtime snapshot/{checkpoint}")
        environment_bytes = json.dumps(
            spec.effective_environment,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        environment = _load_inert_json(environment_bytes, label=f"runtime environment/{checkpoint}")
        if not isinstance(snapshot, Mapping) or not isinstance(environment, Mapping):
            raise ValueError(f"runtime spec objects are malformed: {checkpoint}")
        normalized[checkpoint] = SyntheticRuntimeSpec(
            checkpoint=checkpoint,
            snapshot_manifest=dict(snapshot),
            effective_environment=dict(environment),
            argv=tuple(spec.argv),
        )
    return normalized


def _clone_runtime_spec(spec: SyntheticRuntimeSpec) -> SyntheticRuntimeSpec:
    return SyntheticRuntimeSpec(
        checkpoint=spec.checkpoint,
        snapshot_manifest=json.loads(json.dumps(spec.snapshot_manifest)),
        effective_environment=json.loads(json.dumps(spec.effective_environment)),
        argv=tuple(spec.argv),
    )


def runtime_bindings_from_specs(
    specs: Mapping[str, SyntheticRuntimeSpec],
) -> dict[str, dict[str, str]]:
    specs = _normalize_runtime_specs(specs)
    result = {}
    for checkpoint in CHECKPOINT_ORDER:
        spec = specs[checkpoint]
        if (
            not isinstance(spec, SyntheticRuntimeSpec)
            or spec.checkpoint != checkpoint
            or not isinstance(spec.snapshot_manifest, Mapping)
            or not isinstance(spec.effective_environment, Mapping)
            or any(
                not isinstance(key, str) or not key or not isinstance(value, str)
                for key, value in spec.effective_environment.items()
            )
            or not spec.argv
            or any(not isinstance(value, str) or not value for value in spec.argv)
        ):
            raise ValueError(f"runtime spec is malformed: {checkpoint}")
        result[checkpoint] = {
            "snapshot_manifest_sha256": _canonical_sha256(spec.snapshot_manifest),
            "effective_environment_sha256": _canonical_sha256(spec.effective_environment),
            "argv_environment_sha256": _canonical_sha256(
                {
                    "argv": list(spec.argv),
                    "environment": spec.effective_environment,
                }
            ),
        }
    return result


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_once_fsync(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite evidence: {path}")
    partial = path.with_name(path.name + ".part")
    if partial.exists() or partial.is_symlink():
        raise FileExistsError(f"partial evidence path already exists: {partial}")
    try:
        with partial.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
        _fsync_directory(path.parent)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _write_json_once(path: Path, value: Mapping[str, Any]) -> None:
    body = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _write_once_fsync(path, body)


def _reject_symlink_ancestors(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError("synthetic evidence root must be absolute")
    for candidate in (path.parent, *path.parents):
        if candidate.exists() and candidate.is_symlink():
            raise ValueError(f"synthetic evidence root has a symlink ancestor: {candidate}")


def _base64_and_sha256(body: bytes) -> tuple[str, str]:
    return base64.b64encode(body).decode("ascii"), hashlib.sha256(body).hexdigest()


def _validated_response(response: Any, *, label: str) -> SyntheticHTTPResponse:
    if not isinstance(response, SyntheticHTTPResponse):
        raise ValueError(f"adapter response type differs: {label}")
    if (
        not isinstance(response.status, int)
        or isinstance(response.status, bool)
        or not 100 <= response.status <= 599
        or not isinstance(response.body, bytes)
        or len(response.body) > MAX_RAW_RESPONSE_BYTES
        or any(
            not isinstance(pair, tuple)
            or len(pair) != 2
            or any(not isinstance(value, str) for value in pair)
            for pair in response.headers
        )
    ):
        raise ValueError(f"adapter response is malformed: {label}")
    return response


def _extract_generated_text(mode: str, parsed: Mapping[str, Any]) -> str | None:
    if mode in {"runtime_identity", "language_only_negative"}:
        return None
    choices = parsed.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        return None
    if mode == "native_package":
        message = choices[0].get("message")
        return message.get("content") if isinstance(message, Mapping) else None
    return choices[0].get("text")


def _attempt_evidence(
    *,
    request: Mapping[str, Any],
    attempt_index: int,
    adapter: SyntheticRuntimeAdapter,
    attempt_root: Path,
    trace: _MonotonicTrace,
) -> dict[str, Any]:
    case_id = request.get("case_id")
    if not isinstance(case_id, str) or CASE_ID_PATTERN.fullmatch(case_id) is None:
        raise ValueError("request case ID is not path-safe")
    body = _canonical_request_body(request["request_body"])
    if hashlib.sha256(body).hexdigest() != request["request_body_utf8_sha256"]:
        raise ValueError(f"planned request-body hash differs: {case_id}")
    request_b64, request_sha = _base64_and_sha256(body)
    events = []

    def event(name: str) -> None:
        events.append({"event": name, "monotonic_ns": trace.next()})

    event(ATTEMPT_EVENT_ORDER[0])
    event(ATTEMPT_EVENT_ORDER[1])
    transport_outcome = "http_response"
    response_headers: list[list[str]] = []
    status: int | None = None
    try:
        response = _validated_response(
            adapter.send_request(
                method=request["method"],
                endpoint=request["endpoint"],
                headers=tuple(request["headers"].items()),
                body=body,
            ),
            label=case_id,
        )
        status = response.status
        response_headers = [list(pair) for pair in response.headers]
        raw = response.body
    except SyntheticTransportError:
        transport_outcome = "transport_error"
        raw = b""
    raw_name = f"attempt-{attempt_index}-raw-response.bin"
    _write_once_fsync(attempt_root / raw_name, raw)
    event(ATTEMPT_EVENT_ORDER[2])
    event(ATTEMPT_EVENT_ORDER[3])
    event(ATTEMPT_EVENT_ORDER[4])
    parsed: Mapping[str, Any] | None = None
    if transport_outcome == "http_response" and not (
        isinstance(status, int) and 500 <= status <= 599
    ):
        try:
            candidate = _load_inert_json(raw, label=f"synthetic response/{case_id}")
            parsed = candidate if isinstance(candidate, Mapping) else None
        except (UnicodeError, ValueError):
            parsed = None
    event(ATTEMPT_EVENT_ORDER[5])
    generated = None if parsed is None else _extract_generated_text(request["mode"], parsed)
    if generated is not None and not isinstance(generated, str):
        generated = None
    event(ATTEMPT_EVENT_ORDER[6])
    if generated is not None:
        generated_body = generated.encode("utf-8")
        _write_once_fsync(
            attempt_root / f"attempt-{attempt_index}-generated-text.txt",
            generated_body,
        )
        generated_sha = hashlib.sha256(generated_body).hexdigest()
    else:
        generated_sha = None
    event(ATTEMPT_EVENT_ORDER[7])
    event(ATTEMPT_EVENT_ORDER[8])
    if generated is not None and request["mode"] in {
        "native_package",
        "common_base_serialization",
    }:
        try:
            _load_inert_json(generated.encode("utf-8"), label=f"synthetic generated/{case_id}")
        except ValueError:
            pass
    event(ATTEMPT_EVENT_ORDER[9])
    event(ATTEMPT_EVENT_ORDER[10])
    raw_b64, raw_sha = _base64_and_sha256(raw)
    result = {
        "case_id": case_id,
        "attempt_index": attempt_index,
        "method": request["method"],
        "endpoint": request["endpoint"],
        "logical_request_id": request["logical_request_id"],
        "headers_ordered_pairs": [list(pair) for pair in request["headers"].items()],
        "request_body_base64": request_b64,
        "request_body_utf8_sha256": request_sha,
        "seed": request["seed"],
        "event_trace": events,
        "transport_outcome": transport_outcome,
        "http_status": status,
        "response_headers_ordered_pairs": response_headers,
        "raw_response_body_base64": raw_b64,
        "raw_response_body_sha256": raw_sha,
        "generated_text": generated,
        "generated_text_utf8_sha256": generated_sha,
    }
    _write_json_once(attempt_root / f"attempt-{attempt_index}-evidence.json", result)
    return result


def _run_request_battery(
    *,
    requests: Sequence[Mapping[str, Any]],
    adapter: SyntheticRuntimeAdapter,
    checkpoint_root: Path,
    trace: _MonotonicTrace,
) -> list[dict[str, Any]]:
    attempts = []
    for request in requests:
        case_id = request["case_id"]
        case_root = checkpoint_root / "requests" / case_id
        first = _attempt_evidence(
            request=request,
            attempt_index=1,
            adapter=adapter,
            attempt_root=case_root,
            trace=trace,
        )
        attempts.append(first)
        retryable = first["transport_outcome"] == "transport_error" or (
            first["transport_outcome"] == "http_response"
            and isinstance(first["http_status"], int)
            and not isinstance(first["http_status"], bool)
            and 500 <= first["http_status"] <= 599
        )
        if retryable:
            second = _attempt_evidence(
                request=request,
                attempt_index=2,
                adapter=adapter,
                attempt_root=case_root,
                trace=trace,
            )
            attempts.append(second)
            second_retryable = second["transport_outcome"] == "transport_error" or (
                second["transport_outcome"] == "http_response"
                and isinstance(second["http_status"], int)
                and not isinstance(second["http_status"], bool)
                and 500 <= second["http_status"] <= 599
            )
            if second_retryable:
                raise RuntimeError(f"retry exhausted: {case_id}")
            final = second
        else:
            final = first
        expected_status = 400 if request["mode"] == "language_only_negative" else 200
        if final["transport_outcome"] != "http_response" or final["http_status"] != expected_status:
            raise RuntimeError(f"nonretryable HTTP result differs: {case_id}")
    return attempts


def _raw_capture(root: Path, name: str, body: bytes) -> tuple[str, str]:
    if not isinstance(body, bytes) or len(body) > MAX_RAW_RESPONSE_BYTES:
        raise ValueError(f"raw capture exceeds its byte contract: {name}")
    _write_once_fsync(root / name, body)
    return _base64_and_sha256(body)


def _run_checkpoint(
    *,
    checkpoint: str,
    spec: SyntheticRuntimeSpec,
    requests: Sequence[Mapping[str, Any]],
    adapter: SyntheticRuntimeAdapter,
    output_root: Path,
    trace: _MonotonicTrace,
    sleep: Callable[[float], None],
    readiness_poll_interval_seconds: int,
    graceful_shutdown_timeout_seconds: int,
    post_force_exit_timeout_seconds: int,
    port_release_timeout_seconds: int,
) -> dict[str, Any]:
    checkpoint_root = output_root / checkpoint
    lifecycle = []

    def lifecycle_event(name: str, evidence: Mapping[str, Any]) -> None:
        row = {"event": name, "monotonic_ns": trace.next(), "evidence": dict(evidence)}
        lifecycle.append(row)
        _write_json_once(checkpoint_root / f"lifecycle-{len(lifecycle):02d}-{name}.json", row)

    free, raw_probe = adapter.probe_port_8000()
    pre_b64, pre_sha = _raw_capture(checkpoint_root, "prelaunch-port-probe.bin", raw_probe)
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[0],
        {
            "port": 8000,
            "free": free,
            "raw_probe_base64": pre_b64,
            "raw_probe_sha256": pre_sha,
        },
    )
    if free is not True:
        raise RuntimeError(f"port 8000 is not free before launch: {checkpoint}")

    snapshot_verified, environment_verified = adapter.verify_snapshot_and_environment(
        _clone_runtime_spec(spec)
    )
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[1],
        {
            "snapshot_verified": snapshot_verified,
            "environment_verified": environment_verified,
            "snapshot_manifest": dict(spec.snapshot_manifest),
            "snapshot_manifest_sha256": _canonical_sha256(spec.snapshot_manifest),
            "effective_environment": dict(spec.effective_environment),
            "effective_environment_sha256": _canonical_sha256(spec.effective_environment),
        },
    )
    if snapshot_verified is not True or environment_verified is not True:
        raise RuntimeError(f"snapshot or environment verification failed: {checkpoint}")

    argv_environment = {
        "argv": list(spec.argv),
        "environment": dict(spec.effective_environment),
    }
    _write_json_once(checkpoint_root / "intended-launch.json", argv_environment)
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[2],
        {
            **argv_environment,
            "argv_environment_sha256": _canonical_sha256(argv_environment),
            "fsynced": True,
        },
    )
    process = adapter.launch(_clone_runtime_spec(spec))
    if (
        not isinstance(process, SyntheticProcess)
        or not isinstance(process.pid, int)
        or isinstance(process.pid, bool)
        or process.pid < 1
        or not isinstance(process.startup_log_capture_path, str)
        or not process.startup_log_capture_path
        or process.log_capture_from_process_start is not True
    ):
        raise RuntimeError(f"adapter returned an invalid process: {checkpoint}")
    process_start = trace.next()
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[3],
        {"pid": process.pid, "process_start_monotonic_ns": process_start},
    )
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[4],
        {
            "pid": process.pid,
            "capture_path": process.startup_log_capture_path,
            "from_process_start": process.log_capture_from_process_start,
        },
    )

    polls = []
    ready = False
    for attempt_index in range(1, MAX_HEALTH_POLLS + 1):
        if attempt_index > 1:
            sleep(float(readiness_poll_interval_seconds))
        try:
            response = _validated_response(
                adapter.poll_health(), label=f"health/{checkpoint}/{attempt_index}"
            )
            body = response.body
            status = response.status
        except SyntheticTransportError:
            body = b""
            status = None
        body_b64, body_sha = _raw_capture(
            checkpoint_root,
            f"health-poll-{attempt_index}.bin",
            body,
        )
        polls.append(
            {
                "attempt_index": attempt_index,
                "http_status": status,
                "raw_response_body_base64": body_b64,
                "raw_response_body_sha256": body_sha,
                "monotonic_ns": trace.next(),
            }
        )
        if status == 200:
            ready = True
            break
    lifecycle_event(LIFECYCLE_EVENT_ORDER[5], {"polls": polls})
    _write_json_once(checkpoint_root / "readiness.json", {"ready": ready})
    lifecycle_event(LIFECYCLE_EVENT_ORDER[6], {"ready": ready, "fsynced": True})
    if not ready:
        raise RuntimeError(f"readiness poll cap exhausted: {checkpoint}")

    attempts = _run_request_battery(
        requests=requests,
        adapter=adapter,
        checkpoint_root=checkpoint_root,
        trace=trace,
    )
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[7],
        {"status": "COMPLETED", "case_ids": [row["case_id"] for row in requests]},
    )
    signal = adapter.request_graceful_shutdown(process)
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[8],
        {"requested": True, "signal": signal, "captured": True},
    )
    exited = adapter.wait_for_exit(process, graceful_shutdown_timeout_seconds)
    if exited:
        forced = {
            "used": False,
            "grace_timeout_elapsed": False,
            "reason": "NOT_NEEDED",
            "captured": True,
        }
    else:
        adapter.force_terminate(process)
        if not adapter.wait_for_exit(process, post_force_exit_timeout_seconds):
            raise RuntimeError(f"process did not exit after force termination: {checkpoint}")
        forced = {
            "used": True,
            "grace_timeout_elapsed": True,
            "reason": "GRACE_TIMEOUT",
            "captured": True,
        }
    lifecycle_event(LIFECYCLE_EVENT_ORDER[9], forced)
    final_log = adapter.final_log_bytes(process)
    if not isinstance(final_log, bytes):
        raise RuntimeError(f"final log capture is not bytes: {checkpoint}")
    log_b64, log_sha = _raw_capture(checkpoint_root, "final-server.log", final_log)
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[10],
        {
            "exit_code": adapter.exit_code(process),
            "final_log_base64": log_b64,
            "final_log_sha256": log_sha,
            "fsynced": True,
        },
    )
    if (
        not isinstance(port_release_timeout_seconds, int)
        or isinstance(port_release_timeout_seconds, bool)
        or port_release_timeout_seconds < 0
    ):
        raise ValueError("port release timeout is invalid")
    released = False
    release_probe = b""
    for release_attempt in range(port_release_timeout_seconds + 1):
        if release_attempt > 0:
            sleep(1.0)
        released, release_probe = adapter.probe_port_8000()
        if released is True:
            break
    release_b64, release_sha = _raw_capture(
        checkpoint_root, "post-exit-port-probe.bin", release_probe
    )
    lifecycle_event(
        LIFECYCLE_EVENT_ORDER[11],
        {
            "port": 8000,
            "released": released,
            "raw_probe_base64": release_b64,
            "raw_probe_sha256": release_sha,
        },
    )
    if released is not True:
        raise RuntimeError(f"port 8000 was not released: {checkpoint}")
    return {
        "checkpoint": checkpoint,
        "lifecycle_events": lifecycle,
        "attempts": attempts,
    }


def run_phase5_public_synthetic_preflight(
    *,
    client_plan: Mapping[str, Any],
    termination_plan: Mapping[str, Any],
    expected_client_plan_sha256: str,
    runtime_specs: Mapping[str, SyntheticRuntimeSpec],
    adapters: Mapping[str, SyntheticRuntimeAdapter],
    authorization: Mapping[str, Any],
    expected_runtime_bindings: Mapping[str, Mapping[str, str]],
    output_root: Path,
    clock_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Produce and independently verify one public-synthetic evidence bundle."""

    _strict_authorization(authorization, expected_client_plan_sha256=expected_client_plan_sha256)
    _verify_plan_binding(
        client_plan,
        termination_plan,
        expected_client_plan_sha256=expected_client_plan_sha256,
    )
    if not isinstance(adapters, Mapping) or set(adapters) != set(CHECKPOINT_ORDER):
        raise ValueError("runtime adapter checkpoint set differs")
    runtime_specs = _normalize_runtime_specs(runtime_specs)
    bindings = runtime_bindings_from_specs(runtime_specs)
    externally_bound = _verify_runtime_bindings(expected_runtime_bindings)
    if bindings != externally_bound:
        raise ValueError("runtime specs differ from the accepted Lock-A bindings")
    if authorization["runtime_bindings_sha256"] != _canonical_sha256(externally_bound):
        raise PermissionError("Lock-A authorization does not bind the runtime specs")
    _reject_symlink_ancestors(output_root)
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(f"refusing to reuse synthetic evidence root: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    _fsync_directory(output_root.parent)
    trace = _MonotonicTrace(clock_ns)
    try:
        requests = client_plan.get("request_sequence")
        if not isinstance(requests, list):
            raise ValueError("client request sequence is malformed")
        lifecycle = client_plan.get("lifecycle_contract", {})
        runs = []
        for checkpoint in CHECKPOINT_ORDER:
            checkpoint_requests = [row for row in requests if row.get("checkpoint") == checkpoint]
            try:
                run = _run_checkpoint(
                    checkpoint=checkpoint,
                    spec=runtime_specs[checkpoint],
                    requests=checkpoint_requests,
                    adapter=adapters[checkpoint],
                    output_root=output_root,
                    trace=trace,
                    sleep=sleep,
                    readiness_poll_interval_seconds=lifecycle["readiness_poll_interval_seconds"],
                    graceful_shutdown_timeout_seconds=lifecycle[
                        "graceful_shutdown_timeout_seconds"
                    ],
                    post_force_exit_timeout_seconds=lifecycle["post_force_exit_timeout_seconds"],
                    port_release_timeout_seconds=lifecycle["port_release_timeout_seconds"],
                )
            except BaseException:
                cleanup = adapters[checkpoint].emergency_cleanup()
                if not isinstance(cleanup, Mapping):
                    cleanup = {
                        "status": "INVALID_EMERGENCY_CLEANUP_EVIDENCE",
                    }
                try:
                    _write_json_once(
                        output_root / checkpoint / "failure-emergency-cleanup.json",
                        dict(cleanup),
                    )
                except (FileExistsError, OSError, TypeError, ValueError):
                    pass
                raise
            runs.append(run)
        bundle = {
            "format_version": SYNTHETIC_EVIDENCE_FORMAT_VERSION,
            "client_plan_sha256": expected_client_plan_sha256,
            "termination_plan_sha256": termination_plan["plan_sha256"],
            "checkpoint_runs": runs,
        }
        bundle["bundle_sha256"] = _canonical_sha256(bundle)
        verification = verify_phase5_synthetic_evidence(
            client_plan,
            termination_plan,
            bundle,
            expected_client_plan_sha256=expected_client_plan_sha256,
            expected_runtime_bindings=bindings,
        )
        _write_json_once(output_root / "evidence-bundle.json", bundle)
        _write_json_once(output_root / "verification.json", verification)
        return verification
    except BaseException as error:
        failure = {
            "status": "PRESERVED_FAILURE",
            "client_plan_sha256": expected_client_plan_sha256,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        try:
            _write_json_once(output_root / "failure.json", failure)
        except (FileExistsError, OSError):
            pass
        raise
