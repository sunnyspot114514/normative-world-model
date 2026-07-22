from __future__ import annotations

import base64
import ast
import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from normative_world_model.phase5_lock_a import (
    LOCK_A_ACCEPTED_STATUS,
    LOCK_A_AUTHORIZATION,
    LOCK_A_FORMAT_VERSION,
)
from normative_world_model.phase5_synthetic_client_plan import IMPLEMENTATION_SOURCE_PATHS
from normative_world_model.phase5_synthetic_evidence import _canonical_sha256
from normative_world_model.phase5_synthetic_runner import (
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


def _lock_a_acceptance(client: dict, runtime_bindings: dict) -> dict:
    now = datetime.now(UTC).replace(microsecond=0)
    acceptance = {
        "format_version": LOCK_A_FORMAT_VERSION,
        "status": LOCK_A_ACCEPTED_STATUS,
        "source_commit": "1" * 40,
        "client_plan_sha256": client["client_plan_sha256"],
        "client_plan_file_sha256": "2" * 64,
        "runtime_bindings_sha256": _canonical_sha256(runtime_bindings),
        "remote_environment_manifest_sha256": "3" * 64,
        "weight_download_plan_sha256": "4" * 64,
        "provider_quote": {
            "provider": "AutoDL",
            "currency": "CNY",
            "gpu_model": "RTX PRO 6000",
            "gpu_count": 1,
            "gpu_memory_bytes": 96 * 1024**3,
            "gpu_hourly_price_minor": 598,
            "storage_daily_price_minor": 158,
            "quote_evidence_sha256": "5" * 64,
        },
        "limits": {
            "currency": "CNY",
            "maximum_spend_minor": 6_000,
            "whole_rental_wall_clock_seconds": 10 * 60 * 60,
            "maximum_download_bytes": 150 * 1024**3,
            "minimum_free_data_disk_bytes": 182 * 1024**3,
            "minimum_post_download_free_bytes": 32 * 1024**3,
        },
        "authorization": dict(LOCK_A_AUTHORIZATION),
        "governance": {
            "confirmation_status": "RESERVED_NOT_GENERATED",
            "formal_scientific_execution_started": False,
            "retained_data_available_to_remote": False,
            "next_stage_unlocked": "SYNTHETIC_PREFLIGHT_ONLY",
        },
        "validity": {
            "not_before_utc": (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_utc": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "review_record_sha256s": ["6" * 64, "7" * 64],
        "operator_approval_sha256": "8" * 64,
    }
    acceptance["acceptance_sha256"] = _canonical_sha256(acceptance)
    return acceptance


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
    acceptance = _lock_a_acceptance(client, runtime_bindings)
    return client, termination, specs, acceptance, adapters


def _run(root: Path, *, inputs=None) -> dict:
    client, termination, specs, acceptance, adapters = inputs or _inputs()
    clock = _Clock()
    with patch(
        "normative_world_model.phase5_synthetic_runner.registered_lock_a_acceptance_sha256",
        return_value=acceptance["acceptance_sha256"],
    ):
        return run_phase5_public_synthetic_preflight(
            client_plan=client,
            termination_plan=termination,
            expected_client_plan_sha256=client["client_plan_sha256"],
            runtime_specs=specs,
            adapters=adapters,
            lock_a_acceptance=acceptance,
            expected_runtime_bindings=runtime_bindings_from_specs(specs),
            output_root=root,
            clock_ns=clock,
            sleep=clock.sleep,
        )


class Phase5SyntheticRunnerTests(unittest.TestCase):
    def test_plan_hashed_sources_cover_the_transitive_local_import_closure(self) -> None:
        project = Path(__file__).resolve().parents[1]
        package = project / "src" / "normative_world_model"
        entrypoint = project / "scripts" / "run-phase5-public-synthetic-preflight.py"
        modules = {"__init__"}
        entry_tree = ast.parse(entrypoint.read_text(encoding="utf-8"))
        for node in ast.walk(entry_tree):
            if (
                isinstance(node, ast.ImportFrom)
                and isinstance(node.module, str)
                and node.module.startswith("normative_world_model.")
            ):
                modules.add(node.module.split(".", 1)[1].split(".", 1)[0])
        queue = list(modules)
        while queue:
            module = queue.pop()
            path = package / ("__init__.py" if module == "__init__" else f"{module}.py")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                    child = node.module.split(".", 1)[0]
                    if (package / f"{child}.py").is_file() and child not in modules:
                        modules.add(child)
                        queue.append(child)
        closure = {
            "src/normative_world_model/__init__.py"
            if module == "__init__"
            else f"src/normative_world_model/{module}.py"
            for module in modules
        }
        closure.remove("src/normative_world_model/phase5_lock_a_registry.py")
        self.assertTrue(closure.issubset(set(IMPLEMENTATION_SOURCE_PATHS)))

    def test_concrete_entrypoint_binds_exact_two_file_deployment_delta(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "run-phase5-public-synthetic-preflight.py"
        )
        spec = importlib.util.spec_from_file_location("phase5_concrete_entrypoint", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.ALLOWED_DEPLOYMENT_DIFF,
            {
                "configs/phase5_lock_a_acceptance_20260722.json",
                "src/normative_world_model/phase5_lock_a_registry.py",
            },
        )
        self.assertEqual(
            module.DEFAULT_CLIENT_PLAN.name,
            "v11-b2887ba90d81-b752a05215d7.json",
        )
        self.assertEqual(
            module.DEFAULT_TERMINATION_PLAN.name,
            "v2-1a8cdbf5f807.json",
        )

        with tempfile.TemporaryDirectory() as temporary:
            client_plan = Path(temporary) / "client-plan.json"
            client_plan.write_bytes(b"exact reviewed client-plan bytes\n")
            acceptance = {
                "client_plan_file_sha256": module._sha256_file(client_plan)
            }
            module._verify_client_plan_file_binding(client_plan, acceptance)
            client_plan.write_bytes(b"drifted client-plan bytes\n")
            with self.assertRaisesRegex(ValueError, "file bytes"):
                module._verify_client_plan_file_binding(client_plan, acceptance)

    def test_deployment_registry_is_separate_from_plan_hashed_verifier(self) -> None:
        from normative_world_model import phase5_lock_a
        from normative_world_model import phase5_lock_a_registry

        registered = phase5_lock_a_registry.REGISTERED_LOCK_A_ACCEPTANCE_SHA256
        self.assertTrue(
            registered is None
            or (
                isinstance(registered, str)
                and len(registered) == 64
                and all(character in "0123456789abcdef" for character in registered)
            )
        )
        self.assertNotIn(
            "REGISTERED_LOCK_A_ACCEPTANCE_SHA256: str | None = None",
            Path(phase5_lock_a.__file__).read_text(encoding="utf-8"),
        )

    def test_unregistered_trust_root_rejects_valid_certificate_before_side_effect(self) -> None:
        client, termination, specs, acceptance, adapters = _inputs()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with patch(
                "normative_world_model.phase5_synthetic_runner."
                "registered_lock_a_acceptance_sha256",
                side_effect=PermissionError(
                    "no Lock-A acceptance digest is registered in the execution source"
                ),
            ):
                with self.assertRaisesRegex(PermissionError, "no Lock-A acceptance digest"):
                    run_phase5_public_synthetic_preflight(
                        client_plan=client,
                        termination_plan=termination,
                        expected_client_plan_sha256=client["client_plan_sha256"],
                        runtime_specs=specs,
                        adapters=adapters,
                        lock_a_acceptance=acceptance,
                        expected_runtime_bindings=runtime_bindings_from_specs(specs),
                        output_root=root,
                    )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))

    def test_fake_end_to_end_run_writes_and_verifies_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            result = _run(root)
            self.assertEqual(
                result["status"],
                "PASS_APPLICATION_NATIVE_GATE_WITH_RAW_COMMON_DIAGNOSTIC_V3",
            )
            self.assertEqual(result["request_count"], 20)
            self.assertTrue((root / "evidence-bundle.json").is_file())
            self.assertTrue((root / "verification.json").is_file())
            self.assertFalse((root / "failure.json").exists())
            raw_files = list(root.glob("*/requests/*/attempt-1-raw-response.bin"))
            self.assertEqual(len(raw_files), 20)

    def test_authorization_fails_before_adapter_or_output_side_effect(self) -> None:
        inputs = _inputs()
        client, termination, specs, acceptance, adapters = inputs
        closed = copy.deepcopy(acceptance)
        closed["authorization"]["http_execution"] = False
        closed["acceptance_sha256"] = _canonical_sha256(
            {key: value for key, value in closed.items() if key != "acceptance_sha256"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(PermissionError, "synthetic-only"):
                _run(
                    root,
                    inputs=(client, termination, specs, closed, adapters),
                )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))

    def test_tampered_plan_and_self_asserted_runtime_binding_fail_before_launch(self) -> None:
        client, termination, specs, acceptance, adapters = _inputs()
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
                    lock_a_acceptance=acceptance,
                    expected_runtime_bindings=runtime_bindings_from_specs(specs),
                    output_root=root,
                )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))
        source_drifted = copy.deepcopy(client)
        first_source = next(iter(source_drifted["implementation_sources"]))
        source_drifted["implementation_sources"][first_source]["sha256"] = "0" * 64
        source_drifted["client_plan_sha256"] = _canonical_sha256(
            {
                key: value
                for key, value in source_drifted.items()
                if key != "client_plan_sha256"
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with self.assertRaisesRegex(ValueError, "implementation source differs"):
                run_phase5_public_synthetic_preflight(
                    client_plan=source_drifted,
                    termination_plan=termination,
                    expected_client_plan_sha256=source_drifted["client_plan_sha256"],
                    runtime_specs=specs,
                    adapters=adapters,
                    lock_a_acceptance=acceptance,
                    expected_runtime_bindings=runtime_bindings_from_specs(specs),
                    output_root=root,
                )
            self.assertFalse(root.exists())
            self.assertTrue(all(adapter.launch_count == 0 for adapter in adapters.values()))
        wrong_bindings = runtime_bindings_from_specs(specs)
        wrong_bindings["agentworld"]["snapshot_manifest_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run"
            with patch(
                (
                    "normative_world_model.phase5_synthetic_runner."
                    "registered_lock_a_acceptance_sha256"
                ),
                return_value=acceptance["acceptance_sha256"],
            ):
                with self.assertRaisesRegex(PermissionError, "acceptance identity differs"):
                    run_phase5_public_synthetic_preflight(
                        client_plan=client,
                        termination_plan=termination,
                        expected_client_plan_sha256=client["client_plan_sha256"],
                        runtime_specs=specs,
                        adapters=adapters,
                        lock_a_acceptance=acceptance,
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
            self.assertEqual(
                result["status"],
                "PASS_APPLICATION_NATIVE_GATE_WITH_RAW_COMMON_DIAGNOSTIC_V3",
            )
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
        bad_content = '{"checksum":"PUBLIC-23-7","difference":16,"sum":99}'
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
