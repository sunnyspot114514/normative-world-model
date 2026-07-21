from __future__ import annotations

import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path

from normative_world_model.phase5_synthetic_evidence import _canonical_sha256
from normative_world_model.phase5_synthetic_runner import (
    LOCK_A_ACCEPTED_STATUS,
    SyntheticHTTPResponse,
    SyntheticProcess,
    SyntheticRuntimeSpec,
    SyntheticTransportError,
    run_phase5_public_synthetic_preflight,
    runtime_bindings_from_specs,
)
from tests.test_phase5_synthetic_evidence import _fixture


class _Clock:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> int:
        self.value += 1_000_000
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += int(seconds * 1_000_000_000)


class _Adapter:
    def __init__(self, responses: dict[str, SyntheticHTTPResponse]) -> None:
        self.responses = responses
        self.port_free = True
        self.port_probe_results: list[bool] = []
        self.launch_count = 0
        self.force_count = 0
        self.cleanup_count = 0
        self.transport_failure_once: set[str] = set()
        self.unexpected_failure_once: set[str] = set()
        self._failed: set[str] = set()

    def probe_port_8000(self) -> tuple[bool, bytes]:
        free = self.port_probe_results.pop(0) if self.port_probe_results else self.port_free
        return free, b"port probe"

    def verify_snapshot_and_environment(self, spec: SyntheticRuntimeSpec) -> tuple[bool, bool]:
        return True, True

    def launch(self, spec: SyntheticRuntimeSpec) -> SyntheticProcess:
        self.launch_count += 1
        pid = 1000 + self.launch_count
        return SyntheticProcess(
            pid=pid,
            startup_log_capture_path=f"logs/{pid}.log",
            log_capture_from_process_start=True,
        )

    def poll_health(self) -> SyntheticHTTPResponse:
        return SyntheticHTTPResponse(
            status=200,
            headers=(("content-type", "text/plain"),),
            body=b"ok",
        )

    def send_request(
        self,
        *,
        method: str,
        endpoint: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes,
    ) -> SyntheticHTTPResponse:
        request_id = dict(headers)["X-Request-ID"]
        if request_id in self.unexpected_failure_once and request_id not in self._failed:
            self._failed.add(request_id)
            raise RuntimeError("fixture unexpected adapter failure")
        if request_id in self.transport_failure_once and request_id not in self._failed:
            self._failed.add(request_id)
            raise SyntheticTransportError("fixture transport failure")
        return self.responses[request_id]

    def request_graceful_shutdown(self, process: SyntheticProcess) -> str:
        return "SIGTERM"

    def wait_for_exit(self, process: SyntheticProcess, timeout_seconds: int) -> bool:
        return True

    def force_terminate(self, process: SyntheticProcess) -> None:
        self.force_count += 1

    def exit_code(self, process: SyntheticProcess) -> int:
        return 0

    def final_log_bytes(self, process: SyntheticProcess) -> bytes:
        return b"fixture final log"

    def emergency_cleanup(self) -> dict:
        self.cleanup_count += 1
        return {"status": "NO_ACTIVE_PROCESS_OR_TERMINATED", "captured": True}


def _inputs() -> tuple[dict, dict, dict, dict, dict[str, _Adapter]]:
    client, termination, reference_bundle, _ = _fixture()
    specs = {}
    adapters = {}
    for run in reference_bundle["checkpoint_runs"]:
        checkpoint = run["checkpoint"]
        snapshot = run["lifecycle_events"][1]["evidence"]
        launch = run["lifecycle_events"][2]["evidence"]
        specs[checkpoint] = SyntheticRuntimeSpec(
            checkpoint=checkpoint,
            snapshot_manifest=snapshot["snapshot_manifest"],
            effective_environment=launch["environment"],
            argv=tuple(launch["argv"]),
        )
        responses = {}
        for request, attempt in zip(
            [row for row in client["request_sequence"] if row["checkpoint"] == checkpoint],
            run["attempts"],
            strict=True,
        ):
            responses[request["logical_request_id"]] = SyntheticHTTPResponse(
                status=attempt["http_status"],
                headers=tuple(tuple(pair) for pair in attempt["response_headers_ordered_pairs"]),
                body=base64.b64decode(attempt["raw_response_body_base64"]),
            )
        adapters[checkpoint] = _Adapter(responses)
    runtime_bindings = runtime_bindings_from_specs(specs)
    authorization = {
        "status": LOCK_A_ACCEPTED_STATUS,
        "client_plan_sha256": client["client_plan_sha256"],
        "runtime_bindings_sha256": _canonical_sha256(runtime_bindings),
        "public_synthetic_only": True,
        "server_process_execution": True,
        "http_execution": True,
        "gpu_execution": True,
        "retained_population_access": False,
        "project_prompt_access": False,
        "scientific_execution": False,
    }
    return client, termination, specs, authorization, adapters


def _run(root: Path, *, inputs=None) -> dict:
    client, termination, specs, authorization, adapters = inputs or _inputs()
    clock = _Clock()
    return run_phase5_public_synthetic_preflight(
        client_plan=client,
        termination_plan=termination,
        expected_client_plan_sha256=client["client_plan_sha256"],
        runtime_specs=specs,
        adapters=adapters,
        authorization=authorization,
        expected_runtime_bindings=runtime_bindings_from_specs(specs),
        output_root=root,
        clock_ns=clock,
        sleep=clock.sleep,
    )


class Phase5SyntheticRunnerTests(unittest.TestCase):
    def test_fake_end_to_end_run_writes_and_verifies_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            result = _run(root)
            self.assertEqual(result["status"], "PASS_PUBLIC_SYNTHETIC_EVIDENCE_V1")
            self.assertEqual(result["request_count"], 20)
            self.assertTrue((root / "evidence-bundle.json").is_file())
            self.assertTrue((root / "verification.json").is_file())
            self.assertFalse((root / "failure.json").exists())
            raw_files = list(root.glob("*/requests/*/attempt-1-raw-response.bin"))
            self.assertEqual(len(raw_files), 20)

    def test_authorization_fails_before_adapter_or_output_side_effect(self) -> None:
        inputs = _inputs()
        client, termination, specs, authorization, adapters = inputs
        closed = copy.deepcopy(authorization)
        closed["http_execution"] = False
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(PermissionError, "not accepted"):
                _run(
                    root,
                    inputs=(client, termination, specs, closed, adapters),
                )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))

    def test_tampered_plan_and_self_asserted_runtime_binding_fail_before_launch(self) -> None:
        client, termination, specs, authorization, adapters = _inputs()
        tampered = copy.deepcopy(client)
        tampered["request_sequence"][0]["endpoint"] = "/wrong"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(ValueError, "self-hash"):
                run_phase5_public_synthetic_preflight(
                    client_plan=tampered,
                    termination_plan=termination,
                    expected_client_plan_sha256=client["client_plan_sha256"],
                    runtime_specs=specs,
                    adapters=adapters,
                    authorization=authorization,
                    expected_runtime_bindings=runtime_bindings_from_specs(specs),
                    output_root=root,
                )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))
        wrong_bindings = runtime_bindings_from_specs(specs)
        wrong_bindings["agentworld"]["snapshot_manifest_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(ValueError, "runtime specs differ"):
                run_phase5_public_synthetic_preflight(
                    client_plan=client,
                    termination_plan=termination,
                    expected_client_plan_sha256=client["client_plan_sha256"],
                    runtime_specs=specs,
                    adapters=adapters,
                    authorization=authorization,
                    expected_runtime_bindings=wrong_bindings,
                    output_root=root,
                )
            self.assertFalse(root.exists())

    def test_one_transport_retry_preserves_both_attempts(self) -> None:
        inputs = _inputs()
        client, _, _, _, adapters = inputs
        first = client["request_sequence"][0]
        adapters["agentworld"].transport_failure_once.add(first["logical_request_id"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            result = _run(root, inputs=inputs)
            self.assertEqual(result["attempt_count"], 21)
            case_root = root / "agentworld" / "requests" / first["case_id"]
            self.assertTrue((case_root / "attempt-1-evidence.json").is_file())
            self.assertTrue((case_root / "attempt-2-evidence.json").is_file())
            self.assertEqual((case_root / "attempt-1-raw-response.bin").read_bytes(), b"")

    def test_port_release_uses_the_frozen_timeout_instead_of_one_shot_probe(self) -> None:
        inputs = _inputs()
        adapters = inputs[-1]
        adapters["agentworld"].port_probe_results = [True, False, True]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            result = _run(root, inputs=inputs)
            self.assertEqual(result["status"], "PASS_PUBLIC_SYNTHETIC_EVIDENCE_V1")
            release = (
                root
                / "agentworld"
                / "lifecycle-12-port_release_probe_captured.json"
            )
            self.assertTrue(release.is_file())

    def test_semantic_failure_preserves_raw_evidence_and_failure_record(self) -> None:
        inputs = _inputs()
        client, _, _, _, adapters = inputs
        toy = next(
            row
            for row in client["request_sequence"]
            if row["case_id"] == "agentworld-native_package-toy-repeat-1"
        )
        bad_content = '{"checksum":"PUBLIC-17-5","difference":12,"sum":99}'
        bad_response = {
            "model": "phase5-agentworld",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"content": bad_content}}],
        }
        adapters["agentworld"].responses[toy["logical_request_id"]] = SyntheticHTTPResponse(
            status=200,
            headers=(("content-type", "application/json"),),
            body=json.dumps(bad_response, separators=(",", ":")).encode(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(ValueError, "toy semantic oracle"):
                _run(root, inputs=inputs)
            self.assertTrue((root / "failure.json").is_file())
            case_root = root / "agentworld" / "requests" / toy["case_id"]
            self.assertTrue((case_root / "attempt-1-raw-response.bin").is_file())
            self.assertFalse((root / "evidence-bundle.json").exists())

    def test_busy_port_stops_before_launch_and_preserves_failure(self) -> None:
        inputs = _inputs()
        adapters = inputs[-1]
        adapters["agentworld"].port_free = False
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(RuntimeError, "not free"):
                _run(root, inputs=inputs)
            self.assertEqual(adapters["agentworld"].launch_count, 0)
            self.assertTrue((root / "agentworld" / "prelaunch-port-probe.bin").is_file())
            self.assertTrue((root / "failure.json").is_file())
            self.assertEqual(adapters["agentworld"].cleanup_count, 1)

    def test_unexpected_live_failure_invokes_emergency_cleanup(self) -> None:
        inputs = _inputs()
        client, _, _, _, adapters = inputs
        first = client["request_sequence"][0]
        adapters["agentworld"].unexpected_failure_once.add(first["logical_request_id"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(RuntimeError, "unexpected adapter failure"):
                _run(root, inputs=inputs)
            self.assertEqual(adapters["agentworld"].cleanup_count, 1)
            self.assertTrue((root / "agentworld" / "failure-emergency-cleanup.json").is_file())
            self.assertTrue((root / "failure.json").is_file())

    def test_existing_output_root_is_never_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            root.mkdir()
            marker = root / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "refusing to reuse"):
                _run(root)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_core_has_no_concrete_network_process_or_retained_data_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_synthetic_runner.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess",
            "import socket",
            "import requests",
            "import httpx",
            "urllib.request",
            "torch.cuda",
            "data/phase1",
            "data/phase2",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
