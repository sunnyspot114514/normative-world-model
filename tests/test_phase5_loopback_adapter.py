from __future__ import annotations

import errno
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from normative_world_model.phase5_loopback_adapter import (
    LOOPBACK_HOST,
    LOOPBACK_PORT,
    LoopbackRequestContract,
    LoopbackSyntheticRuntimeAdapter,
)
from normative_world_model.phase5_public_metadata import _canonical_sha256
from normative_world_model.phase5_synthetic_runner import (
    MAX_RAW_RESPONSE_BYTES,
    SyntheticRuntimeSpec,
    SyntheticTransportError,
)
from normative_world_model.phase5_weight_snapshot import verify_downloaded_weight_snapshots
from tests.test_phase5_weight_snapshot import _fixture


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _contracts() -> tuple[LoopbackRequestContract, ...]:
    return tuple(
        LoopbackRequestContract(
            method="POST",
            endpoint=f"/v1/test/{index}",
            headers=(("Accept", "application/json"), ("X-Request-ID", f"case-{index}")),
            body_sha256=_sha(f'{{"index":{index}}}'.encode()),
        )
        for index in range(10)
    )


def _runtime_fixture(root: Path) -> tuple[SyntheticRuntimeSpec, dict[str, str]]:
    snapshots_root = root / "snapshots"
    snapshots_root.mkdir()
    weight_plan, metadata, roots = _fixture(snapshots_root)
    snapshots = verify_downloaded_weight_snapshots(
        weight_plan,
        metadata,
        roots,
        expected_weight_plan_sha256=weight_plan["artifact_sha256"],
        expected_metadata_manifest_sha256=metadata["manifest_sha256"],
    )
    manifest = snapshots["snapshots"][0]
    executable = root / "bin" / "vllm"
    executable.parent.mkdir()
    executable.write_bytes(b"#!/bin/sh\n")
    environment = {"FROZEN_ONLY": "1", "TRANSFORMERS_OFFLINE": "1"}
    argv = (
        str(executable),
        "serve",
        manifest["snapshot_root"],
        "--host",
        LOOPBACK_HOST,
        "--port",
        str(LOOPBACK_PORT),
    )
    spec = SyntheticRuntimeSpec(
        checkpoint="agentworld",
        snapshot_manifest=manifest,
        effective_environment=environment,
        argv=argv,
    )
    binding = {
        "snapshot_manifest_sha256": _canonical_sha256(manifest),
        "effective_environment_sha256": _canonical_sha256(environment),
        "argv_environment_sha256": _canonical_sha256(
            {"argv": list(argv), "environment": environment}
        ),
    }
    return spec, binding


def _adapter(root: Path) -> tuple[LoopbackSyntheticRuntimeAdapter, SyntheticRuntimeSpec]:
    spec, binding = _runtime_fixture(root)
    log_root = root / "logs"
    log_root.mkdir()
    return (
        LoopbackSyntheticRuntimeAdapter(
            checkpoint="agentworld",
            expected_runtime_binding=binding,
            request_contracts=_contracts(),
            startup_log_path=log_root / "agentworld.log",
        ),
        spec,
    )


class _FakeProcess:
    def __init__(self, *, stdout: bytes = b"startup\n", timeout_once: bool = False) -> None:
        self.pid = 4321
        self.stdout = io.BytesIO(stdout)
        self.returncode: int | None = None
        self.timeout_once = timeout_once
        self.terminate_count = 0
        self.kill_count = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminate_count += 1
        if not self.timeout_once:
            self.returncode = -15

    def kill(self) -> None:
        self.kill_count += 1
        self.returncode = -9

    def wait(self, timeout: int | None = None) -> int:
        if self.timeout_once and self.returncode is None:
            self.timeout_once = False
            raise subprocess.TimeoutExpired("vllm", timeout)
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class _FakeHTTPResponse:
    def __init__(self, body: bytes, *, status: int = 200) -> None:
        self.status = status
        self.body = body

    def read(self, maximum: int) -> bytes:
        return self.body

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", "application/json")]


def _launch_fake(
    adapter: LoopbackSyntheticRuntimeAdapter,
    spec: SyntheticRuntimeSpec,
    *,
    fake: _FakeProcess | None = None,
) -> tuple[_FakeProcess, object]:
    adapter.verify_snapshot_and_environment(spec)
    fake = fake or _FakeProcess()
    with (
        patch.object(sys, "platform", "linux"),
        patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
        patch(
            "normative_world_model.phase5_loopback_adapter.subprocess.Popen",
            return_value=fake,
        ),
    ):
        process = adapter.launch(spec)
    return fake, process


def _finish_fake(adapter: LoopbackSyntheticRuntimeAdapter, process: object) -> None:
    adapter.request_graceful_shutdown(process)
    if not adapter.wait_for_exit(process, 1):
        adapter.force_terminate(process)
        adapter.wait_for_exit(process, 1)
    adapter.final_log_bytes(process)


class Phase5LoopbackAdapterTests(unittest.TestCase):
    def test_port_probe_only_accepts_refusal_as_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter, _ = _adapter(Path(temporary))
            probe = MagicMock()
            probe.connect_ex.return_value = errno.ECONNREFUSED
            with patch(
                "normative_world_model.phase5_loopback_adapter.socket.socket",
                return_value=probe,
            ):
                free, raw = adapter.probe_port_8000()
            self.assertTrue(free)
            self.assertIn(b"host=127.0.0.1;port=8000", raw)
            probe.connect_ex.assert_called_once_with(("127.0.0.1", 8000))
            probe.connect_ex.return_value = errno.ETIMEDOUT
            with (
                patch(
                    "normative_world_model.phase5_loopback_adapter.socket.socket",
                    return_value=probe,
                ),
                self.assertRaisesRegex(RuntimeError, "ambiguous"),
            ):
                adapter.probe_port_8000()

    def test_snapshot_mutation_and_unbound_environment_are_rejected_before_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            weight = Path(spec.snapshot_manifest["snapshot_root"]) / "model.safetensors"
            weight.write_bytes(b"x" * len(weight.read_bytes()))
            with self.assertRaisesRegex(ValueError, "digest differs"):
                adapter.verify_snapshot_and_environment(spec)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            changed = SyntheticRuntimeSpec(
                checkpoint=spec.checkpoint,
                snapshot_manifest=spec.snapshot_manifest,
                effective_environment={**spec.effective_environment, "INJECTED": "1"},
                argv=spec.argv,
            )
            with self.assertRaisesRegex(ValueError, "external binding"):
                adapter.verify_snapshot_and_environment(changed)

    def test_post_verification_stat_change_and_log_inside_snapshot_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            adapter.verify_snapshot_and_environment(spec)
            weight = Path(spec.snapshot_manifest["snapshot_root"]) / "model.safetensors"
            weight.write_bytes(b"z" * len(weight.read_bytes()))
            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch("normative_world_model.phase5_loopback_adapter.subprocess.Popen") as popen,
                self.assertRaisesRegex(RuntimeError, "stat identity changed"),
            ):
                adapter.launch(spec)
            self.assertFalse(popen.called)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec, binding = _runtime_fixture(root)
            adapter = LoopbackSyntheticRuntimeAdapter(
                checkpoint="agentworld",
                expected_runtime_binding=binding,
                request_contracts=_contracts(),
                startup_log_path=Path(spec.snapshot_manifest["snapshot_root"]) / "server.log",
            )
            adapter.verify_snapshot_and_environment(spec)
            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch("normative_world_model.phase5_loopback_adapter.subprocess.Popen") as popen,
                self.assertRaisesRegex(ValueError, "must not be inside"),
            ):
                adapter.launch(spec)
            self.assertFalse(popen.called)

    def test_launch_requires_verification_and_uses_no_shell_or_inherited_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch("normative_world_model.phase5_loopback_adapter.subprocess.Popen") as popen,
                self.assertRaisesRegex(RuntimeError, "not verified"),
            ):
                adapter.launch(spec)
            self.assertFalse(popen.called)

            adapter.verify_snapshot_and_environment(spec)
            fake = _FakeProcess()

            def launch(argv: list[str], **kwargs):
                self.assertTrue((root / "logs" / "agentworld.log").is_file())
                self.assertEqual(argv, list(spec.argv))
                self.assertEqual(kwargs["env"], dict(spec.effective_environment))
                self.assertEqual(kwargs["cwd"], Path(spec.snapshot_manifest["snapshot_root"]))
                self.assertIs(kwargs["shell"], False)
                self.assertIs(kwargs["close_fds"], True)
                self.assertIs(kwargs["start_new_session"], True)
                return fake

            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch(
                    "normative_world_model.phase5_loopback_adapter.subprocess.Popen",
                    side_effect=launch,
                ),
            ):
                process = adapter.launch(spec)
            self.assertEqual(process.pid, 4321)
            self.assertEqual(adapter.request_graceful_shutdown(process), "SIGTERM")
            self.assertTrue(adapter.wait_for_exit(process, 1))
            self.assertEqual(adapter.exit_code(process), -15)
            self.assertEqual(adapter.final_log_bytes(process), b"startup\n")

    def test_second_launch_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            adapter.verify_snapshot_and_environment(spec)
            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch(
                    "normative_world_model.phase5_loopback_adapter.subprocess.Popen",
                    return_value=_FakeProcess(),
                ),
            ):
                process = adapter.launch(spec)
                with self.assertRaisesRegex(RuntimeError, "second or concurrent"):
                    adapter.launch(spec)
            adapter.request_graceful_shutdown(process)
            self.assertTrue(adapter.wait_for_exit(process, 1))
            adapter.final_log_bytes(process)

    def test_http_is_loopback_bounded_and_contract_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter, spec = _adapter(Path(temporary))
            _, process = _launch_fake(adapter, spec)
            connection = MagicMock()
            connection.getresponse.return_value = _FakeHTTPResponse(b'{"ok":true}')
            first = _contracts()[0]
            body = b'{"index":0}'
            with patch(
                "normative_world_model.phase5_loopback_adapter.http.client.HTTPConnection",
                return_value=connection,
            ) as connection_type:
                response = adapter.send_request(
                    method=first.method,
                    endpoint=first.endpoint,
                    headers=first.headers,
                    body=body,
                )
            connection_type.assert_called_once_with(
                "127.0.0.1", 8000, timeout=300
            )
            connection.putrequest.assert_called_once_with(
                "POST", "/v1/test/0", skip_host=True, skip_accept_encoding=True
            )
            connection.putheader.assert_any_call("Host", "127.0.0.1:8000")
            connection.putheader.assert_any_call("Content-Length", str(len(body)))
            self.assertEqual(response.body, b'{"ok":true}')
            with self.assertRaisesRegex(ValueError, "canonical origin-form"):
                adapter.send_request(
                    method=first.method,
                    endpoint="http://example.com/escape",
                    headers=first.headers,
                    body=body,
                )
            _finish_fake(adapter, process)

    def test_oversized_response_and_transport_failure_do_not_become_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter, spec = _adapter(Path(temporary))
            _, process = _launch_fake(adapter, spec)
            first = _contracts()[0]
            connection = MagicMock()
            connection.getresponse.return_value = _FakeHTTPResponse(
                b"x" * (MAX_RAW_RESPONSE_BYTES + 1)
            )
            with (
                patch(
                    "normative_world_model.phase5_loopback_adapter.http.client.HTTPConnection",
                    return_value=connection,
                ),
                self.assertRaisesRegex(ValueError, "response exceeds"),
            ):
                adapter.send_request(
                    method=first.method,
                    endpoint=first.endpoint,
                    headers=first.headers,
                    body=b'{"index":0}',
                )
            connection.getresponse.side_effect = OSError("refused")
            with (
                patch(
                    "normative_world_model.phase5_loopback_adapter.http.client.HTTPConnection",
                    return_value=connection,
                ),
                self.assertRaises(SyntheticTransportError),
            ):
                adapter.send_request(
                    method=first.method,
                    endpoint=first.endpoint,
                    headers=first.headers,
                    body=b'{"index":0}',
                )
            _finish_fake(adapter, process)

    def test_emergency_cleanup_escalates_and_returns_evidence_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter, spec = _adapter(root)
            adapter.verify_snapshot_and_environment(spec)
            fake = _FakeProcess(timeout_once=True)
            with (
                patch.object(sys, "platform", "linux"),
                patch("normative_world_model.phase5_loopback_adapter.os.access", return_value=True),
                patch(
                    "normative_world_model.phase5_loopback_adapter.subprocess.Popen",
                    return_value=fake,
                ),
            ):
                adapter.launch(spec)
            probe = MagicMock()
            probe.connect_ex.return_value = errno.ECONNREFUSED
            with patch(
                "normative_world_model.phase5_loopback_adapter.socket.socket",
                return_value=probe,
            ):
                result = adapter.emergency_cleanup()
            self.assertEqual(result["status"], "EMERGENCY_CLEANUP_COMPLETED")
            self.assertEqual(result["actions"], ["SIGTERM", "SIGKILL"])
            self.assertEqual(result["exit_code"], -9)
            self.assertTrue(result["port_8000_free"])

    def test_module_has_no_entry_point_or_non_loopback_destination(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_loopback_adapter.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('if __name__ == "__main__"', source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.environ", source)
        self.assertEqual(LOOPBACK_HOST, "127.0.0.1")
        self.assertEqual(LOOPBACK_PORT, 8000)


if __name__ == "__main__":
    unittest.main()
