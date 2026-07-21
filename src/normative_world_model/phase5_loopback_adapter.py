"""Narrow Linux loopback/process adapter for the Phase-5 synthetic preflight.

This module is an execution-capable *candidate*, not an entry point.  It can
only connect to 127.0.0.1:8000, launches one absolute executable without a
shell or inherited environment, re-verifies externally bound checkpoint bytes,
and drains server output into a bounded capture.  The authorization gate stays
in :mod:`phase5_synthetic_runner`; importing this module performs no action.
"""

from __future__ import annotations

import errno
import hashlib
import http.client
import os
import socket
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from .phase5_public_metadata import _canonical_sha256
from .phase5_synthetic_runner import (
    MAX_RAW_RESPONSE_BYTES,
    SyntheticHTTPResponse,
    SyntheticProcess,
    SyntheticRuntimeSpec,
    SyntheticTransportError,
)
from .phase5_weight_snapshot import (
    bound_snapshot_stat_fingerprint,
    reverify_bound_snapshot,
)

LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_PORT = 8000
HEALTH_ENDPOINT = "/health"
CONNECT_TIMEOUT_SECONDS = 5
RESPONSE_TIMEOUT_SECONDS = 300
LOG_DRAIN_JOIN_TIMEOUT_SECONDS = 30
IO_CHUNK_BYTES = 64 * 1024
MAX_RESPONSE_HEADER_BYTES = 64 * 1024
_BINDING_KEYS = {
    "snapshot_manifest_sha256",
    "effective_environment_sha256",
    "argv_environment_sha256",
}
_FORBIDDEN_PLANNED_HEADERS = {
    "connection",
    "content-length",
    "host",
    "transfer-encoding",
}


def _lower_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} is not a lowercase SHA-256")
    return value


def _regular_unlinked_path(path: Path, *, label: str, directory: bool) -> Path:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError(f"{label} must be an absolute non-link path")
    for ancestor in path.parents:
        if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
            raise ValueError(f"{label} has a linked ancestor: {ancestor}")
    if directory:
        if not path.is_dir() or getattr(path, "is_junction", lambda: False)():
            raise ValueError(f"{label} must be a regular directory")
    elif not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"{label} must be a single-link regular file")
    return path


def _validated_runtime_binding(binding: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(binding, Mapping) or set(binding) != _BINDING_KEYS:
        raise ValueError("adapter runtime binding schema differs")
    return {
        key: _lower_sha256(value, label=f"adapter runtime binding/{key}")
        for key, value in binding.items()
    }


def _headers_tuple(headers: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    if not isinstance(headers, Sequence) or isinstance(headers, (str, bytes)):
        raise ValueError("HTTP headers must be an ordered sequence")
    result = []
    seen = set()
    for pair in headers:
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(value, str) and value for value in pair)
        ):
            raise ValueError("HTTP header pair is malformed")
        name, value = pair
        lower = name.lower()
        if lower in seen or lower in _FORBIDDEN_PLANNED_HEADERS:
            raise ValueError(f"HTTP header is duplicated or transport-owned: {name}")
        if any(character in name or character in value for character in ("\r", "\n", "\0")):
            raise ValueError("HTTP header contains a control character")
        seen.add(lower)
        result.append((name, value))
    return tuple(result)


def _endpoint(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or value.startswith("//")
        or "\r" in value
        or "\n" in value
        or "\0" in value
        or "://" in value
    ):
        raise ValueError("HTTP endpoint is not a canonical origin-form path")
    return value


@dataclass(frozen=True)
class LoopbackRequestContract:
    method: str
    endpoint: str
    headers: tuple[tuple[str, str], ...]
    body_sha256: str

    def validated(self) -> LoopbackRequestContract:
        if self.method not in {"GET", "POST"}:
            raise ValueError("request contract method is not allowed")
        return LoopbackRequestContract(
            method=self.method,
            endpoint=_endpoint(self.endpoint),
            headers=_headers_tuple(self.headers),
            body_sha256=_lower_sha256(self.body_sha256, label="request-contract body"),
        )


def request_contracts_from_client_plan(
    client_plan: Mapping[str, Any], *, checkpoint: str
) -> tuple[LoopbackRequestContract, ...]:
    """Extract exact wire-call contracts from an already hash-verified plan."""

    if checkpoint not in {"agentworld", "base"}:
        raise ValueError("adapter checkpoint is invalid")
    rows = client_plan.get("request_sequence")
    if not isinstance(rows, list):
        raise ValueError("client-plan request sequence is malformed")
    contracts = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("client-plan request row is malformed")
        if row.get("checkpoint") != checkpoint:
            continue
        headers = row.get("headers")
        if not isinstance(headers, Mapping):
            raise ValueError("client-plan request headers are malformed")
        contracts.append(
            LoopbackRequestContract(
                method=row.get("method"),
                endpoint=row.get("endpoint"),
                headers=tuple(headers.items()),
                body_sha256=row.get("request_body_utf8_sha256"),
            ).validated()
        )
    if len(contracts) != 10 or len(set(contracts)) != len(contracts):
        raise ValueError("client-plan checkpoint request-contract set differs")
    return tuple(contracts)


class _BoundedLogCapture:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: BinaryIO | None = None
        self._thread: threading.Thread | None = None
        self._overflow = False
        self._error: BaseException | None = None

    def prepare(self) -> None:
        parent = _regular_unlinked_path(
            self.path.parent,
            label="startup-log parent",
            directory=True,
        )
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError(f"refusing to overwrite startup log: {self.path}")
        self._handle = self.path.open("xb")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        if os.name != "nt":
            descriptor = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def start(self, pipe: BinaryIO) -> None:
        if self._handle is None or self._thread is not None:
            raise RuntimeError("startup-log capture was not prepared exactly once")

        def drain() -> None:
            stored = 0
            try:
                while True:
                    chunk = pipe.read(IO_CHUNK_BYTES)
                    if not chunk:
                        break
                    remaining = MAX_RAW_RESPONSE_BYTES - stored
                    if remaining > 0:
                        written = chunk[:remaining]
                        self._handle.write(written)
                        stored += len(written)
                    if len(chunk) > remaining:
                        self._overflow = True
            except BaseException as error:
                self._error = error
            finally:
                try:
                    pipe.close()
                    self._handle.flush()
                    os.fsync(self._handle.fileno())
                    self._handle.close()
                except BaseException as error:
                    self._error = self._error or error

        self._thread = threading.Thread(
            target=drain,
            name="phase5-bounded-server-log",
            daemon=True,
        )
        self._thread.start()

    def abort_before_start(self) -> None:
        if self._handle is not None and not self._handle.closed:
            self._handle.close()

    def finish(self) -> bytes:
        if self._thread is None:
            raise RuntimeError("startup-log capture never started")
        self._thread.join(LOG_DRAIN_JOIN_TIMEOUT_SECONDS)
        if self._thread.is_alive():
            raise RuntimeError("startup-log drain did not finish")
        if self._error is not None:
            raise RuntimeError("startup-log drain failed") from self._error
        if self._overflow:
            raise ValueError("startup log exceeds its byte contract")
        body = self.path.read_bytes()
        if len(body) > MAX_RAW_RESPONSE_BYTES:
            raise ValueError("startup log exceeds its byte contract")
        return body


@dataclass
class _ActiveProcess:
    public: SyntheticProcess
    process: subprocess.Popen[bytes]
    capture: _BoundedLogCapture


class LoopbackSyntheticRuntimeAdapter:
    """Execution-capable adapter restricted to one frozen checkpoint server."""

    def __init__(
        self,
        *,
        checkpoint: str,
        expected_runtime_binding: Mapping[str, str],
        request_contracts: Sequence[LoopbackRequestContract],
        startup_log_path: Path,
    ) -> None:
        if checkpoint not in {"agentworld", "base"}:
            raise ValueError("adapter checkpoint is invalid")
        if not startup_log_path.is_absolute():
            raise ValueError("startup log path must be absolute")
        contracts = tuple(contract.validated() for contract in request_contracts)
        if len(contracts) != 10 or len(set(contracts)) != len(contracts):
            raise ValueError("adapter request-contract set differs")
        self.checkpoint = checkpoint
        self.expected_runtime_binding = _validated_runtime_binding(expected_runtime_binding)
        self.request_contracts = frozenset(contracts)
        self.startup_log_path = startup_log_path
        self._verified_spec_sha256: str | None = None
        self._verified_stat_fingerprint_sha256: str | None = None
        self._active: _ActiveProcess | None = None

    def probe_port_8000(self) -> tuple[bool, bytes]:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.settimeout(CONNECT_TIMEOUT_SECONDS)
            code = probe.connect_ex((LOOPBACK_HOST, LOOPBACK_PORT))
        except OSError as error:
            raise RuntimeError("loopback port probe was ambiguous") from error
        finally:
            probe.close()
        raw = f"connect_ex={code};host={LOOPBACK_HOST};port={LOOPBACK_PORT}".encode("ascii")
        refused_codes = {errno.ECONNREFUSED, getattr(errno, "WSAECONNREFUSED", 10061)}
        if code == 0:
            return False, raw
        if code in refused_codes:
            return True, raw
        raise RuntimeError(f"loopback port probe was ambiguous: connect_ex={code}")

    def _validate_spec(self, spec: SyntheticRuntimeSpec) -> tuple[Path, str]:
        if not isinstance(spec, SyntheticRuntimeSpec) or spec.checkpoint != self.checkpoint:
            raise ValueError("runtime spec checkpoint differs")
        snapshot_hash = _canonical_sha256(spec.snapshot_manifest)
        environment_hash = _canonical_sha256(spec.effective_environment)
        argv_environment_hash = _canonical_sha256(
            {"argv": list(spec.argv), "environment": spec.effective_environment}
        )
        observed = {
            "snapshot_manifest_sha256": snapshot_hash,
            "effective_environment_sha256": environment_hash,
            "argv_environment_sha256": argv_environment_hash,
        }
        if observed != self.expected_runtime_binding:
            raise ValueError("runtime spec differs from the adapter's external binding")
        if not spec.argv or any(
            not isinstance(value, str) or not value or "\0" in value for value in spec.argv
        ):
            raise ValueError("runtime argv is malformed")
        executable = _regular_unlinked_path(
            Path(spec.argv[0]), label="runtime executable", directory=False
        )
        if sys.platform.startswith("linux") and not os.access(executable, os.X_OK):
            raise ValueError("runtime executable is not executable")
        environment = spec.effective_environment
        if not isinstance(environment, Mapping) or not environment:
            raise ValueError("effective environment is malformed")
        for key, value in environment.items():
            if (
                not isinstance(key, str)
                or not key
                or "=" in key
                or "\0" in key
                or not isinstance(value, str)
                or "\0" in value
            ):
                raise ValueError("effective environment contains an invalid entry")
        snapshot_root_value = spec.snapshot_manifest.get("snapshot_root")
        if not isinstance(snapshot_root_value, str):
            raise ValueError("runtime snapshot root is malformed")
        snapshot_root = Path(snapshot_root_value)
        if tuple(spec.argv).count(snapshot_root_value) != 1:
            raise ValueError("runtime argv does not contain exactly one bound snapshot root")
        required_pairs = {"--host": LOOPBACK_HOST, "--port": str(LOOPBACK_PORT)}
        for flag, expected in required_pairs.items():
            positions = [index for index, value in enumerate(spec.argv) if value == flag]
            if len(positions) != 1 or positions[0] + 1 >= len(spec.argv):
                raise ValueError(f"runtime argv {flag} contract differs")
            if spec.argv[positions[0] + 1] != expected:
                raise ValueError(f"runtime argv {flag} value differs")
        spec_hash = _canonical_sha256(
            {
                "checkpoint": spec.checkpoint,
                "snapshot_manifest": spec.snapshot_manifest,
                "effective_environment": spec.effective_environment,
                "argv": list(spec.argv),
            }
        )
        return snapshot_root, spec_hash

    def verify_snapshot_and_environment(self, spec: SyntheticRuntimeSpec) -> tuple[bool, bool]:
        snapshot_root, spec_hash = self._validate_spec(spec)
        _regular_unlinked_path(snapshot_root, label="runtime snapshot root", directory=True)
        manifest_hash = spec.snapshot_manifest.get("snapshot_manifest_sha256")
        verification = reverify_bound_snapshot(
            spec.snapshot_manifest,
            expected_snapshot_manifest_sha256=manifest_hash,
        )
        if (
            verification["checkpoint"] != self.checkpoint
            or verification["status"] != "PASS_BOUND_SNAPSHOT_REVERIFIED_PRELAUNCH"
        ):
            raise ValueError("prelaunch snapshot verification differs")
        self._verified_spec_sha256 = spec_hash
        self._verified_stat_fingerprint_sha256 = verification["stat_fingerprint_sha256"]
        return True, True

    def launch(self, spec: SyntheticRuntimeSpec) -> SyntheticProcess:
        if not sys.platform.startswith("linux"):
            raise RuntimeError("concrete Phase-5 adapter only supports Linux")
        if self._active is not None:
            raise RuntimeError("adapter refuses a second or concurrent server launch")
        snapshot_root, spec_hash = self._validate_spec(spec)
        if self._verified_spec_sha256 != spec_hash:
            raise RuntimeError("runtime spec was not verified immediately before launch")
        if (
            self._verified_stat_fingerprint_sha256 is None
            or bound_snapshot_stat_fingerprint(spec.snapshot_manifest)
            != self._verified_stat_fingerprint_sha256
        ):
            raise RuntimeError("runtime snapshot stat identity changed before launch")
        resolved_snapshot_root = snapshot_root.resolve(strict=True)
        resolved_log_path = self.startup_log_path.resolve(strict=False)
        try:
            resolved_log_path.relative_to(resolved_snapshot_root)
        except ValueError:
            pass
        else:
            raise ValueError("startup log must not be inside the bound snapshot root")
        capture = _BoundedLogCapture(self.startup_log_path)
        capture.prepare()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                list(spec.argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=snapshot_root,
                env=dict(spec.effective_environment),
                shell=False,
                close_fds=True,
                start_new_session=True,
            )
            if process.stdout is None:
                raise RuntimeError("server process did not expose its startup-log pipe")
            capture.start(process.stdout)
        except BaseException:
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                finally:
                    try:
                        process.wait(timeout=10)
                    except BaseException:
                        pass
            capture.abort_before_start()
            raise
        public = SyntheticProcess(
            pid=process.pid,
            startup_log_capture_path=str(self.startup_log_path),
            log_capture_from_process_start=True,
        )
        self._active = _ActiveProcess(public=public, process=process, capture=capture)
        return public

    def _http(
        self,
        *,
        method: str,
        endpoint: str,
        headers: Sequence[tuple[str, str]],
        body: bytes,
    ) -> SyntheticHTTPResponse:
        if self._active is None or self._active.process.poll() is not None:
            raise RuntimeError("loopback HTTP requires this adapter's live server process")
        endpoint = _endpoint(endpoint)
        headers = _headers_tuple(headers)
        if not isinstance(body, bytes) or len(body) > MAX_RAW_RESPONSE_BYTES:
            raise ValueError("HTTP request body exceeds its byte contract")
        connection = http.client.HTTPConnection(
            LOOPBACK_HOST,
            LOOPBACK_PORT,
            timeout=RESPONSE_TIMEOUT_SECONDS,
        )
        try:
            connection.putrequest(method, endpoint, skip_host=True, skip_accept_encoding=True)
            connection.putheader("Host", f"{LOOPBACK_HOST}:{LOOPBACK_PORT}")
            connection.putheader("Content-Length", str(len(body)))
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders(body)
            response = connection.getresponse()
            raw = response.read(MAX_RAW_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RAW_RESPONSE_BYTES:
                raise ValueError("HTTP response exceeds its byte contract")
            response_headers = tuple(response.getheaders())
            if (
                sum(
                    len(name.encode("utf-8")) + len(value.encode("utf-8")) + 4
                    for name, value in response_headers
                )
                > MAX_RESPONSE_HEADER_BYTES
            ):
                raise ValueError("HTTP response headers exceed their byte contract")
            return SyntheticHTTPResponse(
                status=response.status,
                headers=response_headers,
                body=raw,
            )
        except ValueError:
            raise
        except (OSError, http.client.HTTPException) as error:
            raise SyntheticTransportError("loopback HTTP transport failed") from error
        finally:
            connection.close()

    def poll_health(self) -> SyntheticHTTPResponse:
        return self._http(
            method="GET",
            endpoint=HEALTH_ENDPOINT,
            headers=(("Accept", "application/json"),),
            body=b"",
        )

    def send_request(
        self,
        *,
        method: str,
        endpoint: str,
        headers: Sequence[tuple[str, str]],
        body: bytes,
    ) -> SyntheticHTTPResponse:
        contract = LoopbackRequestContract(
            method=method,
            endpoint=endpoint,
            headers=tuple(headers),
            body_sha256=hashlib.sha256(body).hexdigest(),
        ).validated()
        if contract not in self.request_contracts:
            raise ValueError("HTTP request differs from every frozen checkpoint contract")
        return self._http(method=method, endpoint=endpoint, headers=headers, body=body)

    def _require_process(self, process: SyntheticProcess) -> _ActiveProcess:
        if (
            self._active is None
            or not isinstance(process, SyntheticProcess)
            or process != self._active.public
        ):
            raise ValueError("process handle does not belong to this adapter")
        return self._active

    def request_graceful_shutdown(self, process: SyntheticProcess) -> str:
        active = self._require_process(process)
        if active.process.poll() is None:
            active.process.terminate()
            return "SIGTERM"
        return "ALREADY_EXITED"

    def wait_for_exit(self, process: SyntheticProcess, timeout_seconds: int) -> bool:
        active = self._require_process(process)
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or timeout_seconds < 0
        ):
            raise ValueError("process wait timeout is invalid")
        try:
            active.process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            return False
        return True

    def force_terminate(self, process: SyntheticProcess) -> None:
        active = self._require_process(process)
        if active.process.poll() is None:
            active.process.kill()

    def exit_code(self, process: SyntheticProcess) -> int:
        active = self._require_process(process)
        code = active.process.poll()
        if not isinstance(code, int) or isinstance(code, bool):
            raise RuntimeError("server process has not exited")
        return code

    def final_log_bytes(self, process: SyntheticProcess) -> bytes:
        active = self._require_process(process)
        if active.process.poll() is None:
            raise RuntimeError("cannot finalize server log before process exit")
        return active.capture.finish()

    def emergency_cleanup(self) -> Mapping[str, Any]:
        active = self._active
        if active is None:
            return {
                "status": "NO_ACTIVE_PROCESS",
                "captured": True,
            }
        actions = []
        errors = []
        if active.process.poll() is None:
            try:
                active.process.terminate()
                actions.append("SIGTERM")
            except BaseException as error:
                errors.append(type(error).__name__)
            if active.process.poll() is None:
                try:
                    active.process.wait(timeout=10)
                except BaseException as error:
                    if not isinstance(error, subprocess.TimeoutExpired):
                        errors.append(type(error).__name__)
            if active.process.poll() is None:
                try:
                    active.process.kill()
                    actions.append("SIGKILL")
                except BaseException as error:
                    errors.append(type(error).__name__)
                try:
                    active.process.wait(timeout=10)
                except BaseException as error:
                    errors.append(type(error).__name__)
        code = active.process.poll()
        try:
            active.capture.finish()
        except BaseException as error:
            errors.append(type(error).__name__)
        try:
            port_free, raw = self.probe_port_8000()
            port_probe = raw.decode("ascii", errors="replace")
        except BaseException as error:
            port_free = False
            port_probe = f"ERROR:{type(error).__name__}"
        return {
            "status": "EMERGENCY_CLEANUP_COMPLETED" if not errors else "EMERGENCY_CLEANUP_ERROR",
            "captured": True,
            "pid": active.public.pid,
            "actions": actions,
            "exit_code": code,
            "port_8000_free": port_free,
            "port_probe": port_probe,
            "errors": errors,
        }
