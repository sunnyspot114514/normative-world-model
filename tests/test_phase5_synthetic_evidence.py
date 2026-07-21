from __future__ import annotations

import base64
import copy
import hashlib
import json
import unittest
from pathlib import Path

from normative_world_model.phase5_preflight import load_phase5_config
from normative_world_model.phase5_runtime_plan import RUNTIME_PLAN_FORMAT_VERSION
from normative_world_model.phase5_synthetic_client_plan import (
    PUBLIC_TOY_EXPECTED,
    build_phase5_synthetic_client_plan,
)
from normative_world_model.phase5_synthetic_evidence import (
    SYNTHETIC_EVIDENCE_FORMAT_VERSION,
    _canonical_sha256,
    verify_phase5_synthetic_evidence,
)
from normative_world_model.phase5_termination_probe import (
    TERMINATION_PLAN_FORMAT_VERSION,
)


def _runtime_plan() -> dict:
    plan = {
        "format_version": RUNTIME_PLAN_FORMAT_VERSION,
        "status": "LOCAL_RUNTIME_PLAN_V2_PASS_LOCK_A_NOT_BUILT_EXECUTION_NOT_AUTHORIZED",
        "authorization": {
            "model_download": False,
            "server_rental": False,
            "http_execution": False,
            "gpu_execution": False,
            "retained_population_access": False,
            "scientific_execution": False,
        },
        "launch_specs": [
            {"checkpoint": "agentworld", "model_alias": "phase5-agentworld"},
            {"checkpoint": "base", "model_alias": "phase5-base"},
        ],
    }
    plan["runtime_plan_sha256"] = _canonical_sha256(plan)
    return plan


def _termination_plan() -> dict:
    prompt_ids = [101, 102]
    cases = []
    for checkpoint in ("agentworld", "base"):
        alias = f"phase5-{checkpoint}"
        for forced_id in (248044, 248046):
            for repetition in (1, 2):
                body = {
                    "model": alias,
                    "prompt": "<public termination prompt>",
                    "seed": 2026072004,
                    "allowed_token_ids": [forced_id],
                }
                cases.append(
                    {
                        "case_id": f"{checkpoint}-stop-{forced_id}-repeat-{repetition}",
                        "checkpoint": checkpoint,
                        "model_alias": alias,
                        "forced_stop_token_id": forced_id,
                        "request_body": body,
                        "request_body_sha256": _canonical_sha256(body),
                    }
                )
    plan = {
        "format_version": TERMINATION_PLAN_FORMAT_VERSION,
        "status": "CANDIDATE_PLAN_PASS_EXECUTION_NOT_AUTHORIZED",
        "authorization": {
            "http_execution": False,
            "model_download": False,
            "server_rental": False,
            "gpu_execution": False,
            "project_prompt_access": False,
            "scientific_metrics": False,
        },
        "endpoint": "/v1/completions",
        "cases": cases,
        "acceptance": {
            "expected_case_count": 8,
            "http_status": 200,
            "response_object": "text_completion",
            "expected_response_text": "",
        },
        "public_prompt_token_ids": prompt_ids,
        "public_prompt_token_count": len(prompt_ids),
        "literal_bindings": [
            {"literal": "<|endoftext|>", "token_id": 248044},
            {"literal": "<|im_end|>", "token_id": 248046},
        ],
    }
    plan["plan_sha256"] = _canonical_sha256(plan)
    return plan


def _client_plan(termination: dict) -> dict:
    runtime = _runtime_plan()
    return build_phase5_synthetic_client_plan(
        config=load_phase5_config(),
        runtime_plan=runtime,
        runtime_verification={
            "status": "PASS_LOCAL_PLAN_V2_ONLY_EXECUTION_NOT_AUTHORIZED",
            "runtime_plan_sha256": runtime["runtime_plan_sha256"],
            "http_execution": False,
            "gpu_execution": False,
        },
        termination_plan=termination,
        termination_verification={
            "status": "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
            "plan_sha256": termination["plan_sha256"],
            "http_execution": False,
        },
        common_prompt="<public common prompt>",
        base_common_prompt_token_ids=[1, 2, 3],
        agentworld_common_prompt_token_ids=[1, 2, 3],
        implementation_sources={"fixture.py": {"bytes": 1, "sha256": "0" * 64}},
    )


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _b64_record(body: bytes) -> tuple[str, str]:
    return base64.b64encode(body).decode("ascii"), hashlib.sha256(body).hexdigest()


def _response_for(request: dict, termination: dict) -> tuple[dict, str | None]:
    checkpoint = request["checkpoint"]
    alias = f"phase5-{checkpoint}"
    mode = request["mode"]
    if mode == "runtime_identity":
        return {"object": "list", "data": [{"id": alias, "object": "model"}]}, None
    if mode == "language_only_negative":
        return {
            "error": {
                "code": 400,
                "type": "BadRequestError",
                "param": "image",
                "message": "At most 0 image(s) may be provided in one prompt.",
            }
        }, None
    if mode == "common_termination":
        forced_id = request["request_body"]["allowed_token_ids"][0]
        return {
            "model": alias,
            "object": "text_completion",
            "choices": [
                {
                    "index": 0,
                    "text": "",
                    "finish_reason": "stop",
                    "stop_reason": forced_id,
                    "token_ids": [forced_id],
                    "prompt_token_ids": termination["public_prompt_token_ids"],
                }
            ],
            "usage": {
                "prompt_tokens": termination["public_prompt_token_count"],
                "completion_tokens": 1,
                "total_tokens": termination["public_prompt_token_count"] + 1,
            },
        }, ""
    content = json.dumps(PUBLIC_TOY_EXPECTED, sort_keys=True, separators=(",", ":"))
    if mode == "native_package":
        return {
            "model": alias,
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"content": content, "reasoning": "public"}}],
        }, content
    return {
        "model": alias,
        "object": "text_completion",
        "choices": [{"index": 0, "text": content}],
    }, content


def _attempt(request: dict, termination: dict, *, clock: int) -> dict:
    response, generated = _response_for(request, termination)
    raw = _json_bytes(response)
    raw_b64, raw_sha = _b64_record(raw)
    request_body = (
        b""
        if request["request_body"] is None
        else json.dumps(
            request["request_body"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )
    request_b64, request_sha = _b64_record(request_body)
    status = 400 if request["mode"] == "language_only_negative" else 200
    event_names = [
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
    return {
        "case_id": request["case_id"],
        "attempt_index": 1,
        "method": request["method"],
        "endpoint": request["endpoint"],
        "logical_request_id": request["logical_request_id"],
        "headers_ordered_pairs": [list(item) for item in request["headers"].items()],
        "request_body_base64": request_b64,
        "request_body_utf8_sha256": request_sha,
        "seed": request["seed"],
        "event_trace": [
            {"event": name, "monotonic_ns": clock + index} for index, name in enumerate(event_names)
        ],
        "transport_outcome": "http_response",
        "http_status": status,
        "response_headers_ordered_pairs": [["content-type", "application/json"]],
        "raw_response_body_base64": raw_b64,
        "raw_response_body_sha256": raw_sha,
        "generated_text": generated,
        "generated_text_utf8_sha256": (
            None if generated is None else hashlib.sha256(generated.encode("utf-8")).hexdigest()
        ),
    }


def _lifecycle(checkpoint: str, case_ids: list[str], *, clock: int) -> tuple[list[dict], dict]:
    snapshot = {"checkpoint": checkpoint, "revision": "fixture-revision"}
    environment = {"VLLM_SERVER_DEV_MODE": "0", "CUDA_VISIBLE_DEVICES": "0"}
    argv = ["python", "-m", "vllm.entrypoints.openai.api_server", "--port", "8000"]
    launch = {"argv": argv, "environment": environment}
    probe_b64, probe_sha = _b64_record(b"port-8000-free")
    health_b64, health_sha = _b64_record(b"ok")
    log_b64, log_sha = _b64_record(b"fixture final log")
    evidences = [
        {"port": 8000, "free": True, "raw_probe_base64": probe_b64, "raw_probe_sha256": probe_sha},
        {
            "snapshot_verified": True,
            "environment_verified": True,
            "snapshot_manifest": snapshot,
            "snapshot_manifest_sha256": _canonical_sha256(snapshot),
            "effective_environment": environment,
            "effective_environment_sha256": _canonical_sha256(environment),
        },
        {
            "argv": argv,
            "environment": environment,
            "argv_environment_sha256": _canonical_sha256(launch),
            "fsynced": True,
        },
        {"pid": 1234, "process_start_monotonic_ns": clock + 300},
        {"pid": 1234, "capture_path": f"logs/{checkpoint}.log", "from_process_start": True},
        {
            "polls": [
                {
                    "attempt_index": 1,
                    "http_status": 200,
                    "raw_response_body_base64": health_b64,
                    "raw_response_body_sha256": health_sha,
                    "monotonic_ns": clock + 450,
                }
            ]
        },
        {"ready": True, "fsynced": True},
        {"status": "COMPLETED", "case_ids": case_ids},
        {"requested": True, "signal": "SIGTERM", "captured": True},
        {"used": False, "grace_timeout_elapsed": False, "reason": "NOT_NEEDED", "captured": True},
        {"exit_code": 0, "final_log_base64": log_b64, "final_log_sha256": log_sha, "fsynced": True},
        {
            "port": 8000,
            "released": True,
            "raw_probe_base64": probe_b64,
            "raw_probe_sha256": probe_sha,
        },
    ]
    names = [
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
    ]
    event_times = [
        clock,
        clock + 100,
        clock + 200,
        clock + 300,
        clock + 400,
        clock + 500,
        clock + 600,
        clock + 100_000,
        clock + 100_100,
        clock + 100_200,
        clock + 100_300,
        clock + 100_400,
    ]
    events = [
        {"event": name, "monotonic_ns": timestamp, "evidence": evidence}
        for name, timestamp, evidence in zip(names, event_times, evidences, strict=True)
    ]
    bindings = {
        "snapshot_manifest_sha256": _canonical_sha256(snapshot),
        "effective_environment_sha256": _canonical_sha256(environment),
        "argv_environment_sha256": _canonical_sha256(launch),
    }
    return events, bindings


def _fixture() -> tuple[dict, dict, dict, dict]:
    termination = _termination_plan()
    client = _client_plan(termination)
    runs = []
    bindings = {}
    for checkpoint, clock in (("agentworld", 1_000), ("base", 1_000_000)):
        requests = [row for row in client["request_sequence"] if row["checkpoint"] == checkpoint]
        events, binding = _lifecycle(checkpoint, [row["case_id"] for row in requests], clock=clock)
        bindings[checkpoint] = binding
        runs.append(
            {
                "checkpoint": checkpoint,
                "lifecycle_events": events,
                "attempts": [
                    _attempt(row, termination, clock=clock + 10_000 + index * 100)
                    for index, row in enumerate(requests)
                ],
            }
        )
    bundle = {
        "format_version": SYNTHETIC_EVIDENCE_FORMAT_VERSION,
        "client_plan_sha256": client["client_plan_sha256"],
        "termination_plan_sha256": termination["plan_sha256"],
        "checkpoint_runs": runs,
    }
    bundle["bundle_sha256"] = _canonical_sha256(bundle)
    return client, termination, bundle, bindings


def _rehash(bundle: dict) -> None:
    bundle["bundle_sha256"] = _canonical_sha256(
        {key: value for key, value in bundle.items() if key != "bundle_sha256"}
    )


class Phase5SyntheticEvidenceTests(unittest.TestCase):
    def test_complete_fixture_passes_and_is_plan_bound(self) -> None:
        client, termination, bundle, bindings = _fixture()
        result = verify_phase5_synthetic_evidence(
            client,
            termination,
            bundle,
            expected_client_plan_sha256=client["client_plan_sha256"],
            expected_runtime_bindings=bindings,
        )
        self.assertEqual(result["status"], "PASS_PUBLIC_SYNTHETIC_EVIDENCE_V1")
        self.assertEqual(result["request_count"], 20)
        self.assertEqual(result["termination_case_count"], 8)
        self.assertEqual(result["repeat_cells"], 4)
        self.assertEqual(len(result["repeat_diagnostics"]), 4)
        self.assertTrue(all(row["final_content_equal"] for row in result["repeat_diagnostics"]))

    def test_raw_before_parse_order_and_cross_checkpoint_lifecycle_are_enforced(self) -> None:
        client, termination, bundle, bindings = _fixture()
        broken = copy.deepcopy(bundle)
        trace = broken["checkpoint_runs"][0]["attempts"][0]["event_trace"]
        trace[2], trace[3] = trace[3], trace[2]
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "raw-before-parse event order"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )
        broken = copy.deepcopy(bundle)
        broken["checkpoint_runs"][1]["lifecycle_events"][0]["monotonic_ns"] = 1_500
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "base launch began"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )

    def test_unrelated_400_and_wrong_toy_oracle_fail(self) -> None:
        client, termination, bundle, bindings = _fixture()
        broken = copy.deepcopy(bundle)
        language = broken["checkpoint_runs"][0]["attempts"][1]
        raw = _json_bytes(
            {"error": {"code": 404, "type": "NotFoundError", "param": None, "message": "missing"}}
        )
        language["raw_response_body_base64"], language["raw_response_body_sha256"] = _b64_record(
            raw
        )
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "language-only error semantics"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )
        broken = copy.deepcopy(bundle)
        toy = next(
            row
            for row in broken["checkpoint_runs"][0]["attempts"]
            if row["case_id"].endswith("native_package-toy-repeat-1")
        )
        bad_content = '{"checksum":"PUBLIC-17-5","difference":12,"sum":23}'
        bad_response = {
            "model": "phase5-agentworld",
            "object": "chat.completion",
            "choices": [{"index": 0, "message": {"content": bad_content}}],
        }
        toy["raw_response_body_base64"], toy["raw_response_body_sha256"] = _b64_record(
            _json_bytes(bad_response)
        )
        toy["generated_text"] = bad_content
        toy["generated_text_utf8_sha256"] = hashlib.sha256(bad_content.encode()).hexdigest()
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "toy semantic oracle"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )

    def test_nonretryable_success_cannot_be_retried(self) -> None:
        client, termination, bundle, bindings = _fixture()
        broken = copy.deepcopy(bundle)
        duplicate = copy.deepcopy(broken["checkpoint_runs"][0]["attempts"][0])
        duplicate["attempt_index"] = 2
        broken["checkpoint_runs"][0]["attempts"].insert(1, duplicate)
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "retry predicate differs"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )

    def test_one_identical_retry_is_allowed_only_after_transport_failure(self) -> None:
        client, termination, bundle, bindings = _fixture()
        retried = copy.deepcopy(bundle)
        attempts = retried["checkpoint_runs"][0]["attempts"]
        successful = copy.deepcopy(attempts[0])
        failed = copy.deepcopy(successful)
        failed["transport_outcome"] = "transport_error"
        failed["http_status"] = None
        failed["response_headers_ordered_pairs"] = []
        failed["raw_response_body_base64"] = ""
        failed["raw_response_body_sha256"] = hashlib.sha256(b"").hexdigest()
        failed["generated_text"] = None
        failed["generated_text_utf8_sha256"] = None
        successful["attempt_index"] = 2
        shift = (
            failed["event_trace"][-1]["monotonic_ns"]
            + 1
            - successful["event_trace"][0]["monotonic_ns"]
        )
        for event in successful["event_trace"]:
            event["monotonic_ns"] += shift
        attempts[0:1] = [failed, successful]
        _rehash(retried)
        result = verify_phase5_synthetic_evidence(
            client,
            termination,
            retried,
            expected_client_plan_sha256=client["client_plan_sha256"],
            expected_runtime_bindings=bindings,
        )
        self.assertEqual(result["attempt_count"], 21)

    def test_reasoning_and_whole_envelope_drift_are_diagnostics_not_pass_predicates(self) -> None:
        client, termination, bundle, bindings = _fixture()
        changed = copy.deepcopy(bundle)
        second = next(
            row
            for row in changed["checkpoint_runs"][0]["attempts"]
            if row["case_id"].endswith("native_package-toy-repeat-2")
        )
        response = json.loads(base64.b64decode(second["raw_response_body_base64"]))
        response["choices"][0]["message"]["reasoning"] = "different public reasoning"
        response["diagnostic_nonce"] = 2
        second["raw_response_body_base64"], second["raw_response_body_sha256"] = _b64_record(
            _json_bytes(response)
        )
        _rehash(changed)
        result = verify_phase5_synthetic_evidence(
            client,
            termination,
            changed,
            expected_client_plan_sha256=client["client_plan_sha256"],
            expected_runtime_bindings=bindings,
        )
        diagnostic = next(
            row
            for row in result["repeat_diagnostics"]
            if row["checkpoint"] == "agentworld" and row["mode"] == "native_package"
        )
        self.assertTrue(diagnostic["final_content_equal"])
        self.assertFalse(diagnostic["reasoning_equal"])
        self.assertFalse(diagnostic["whole_response_bytes_equal"])

    def test_runtime_binding_and_request_bytes_are_external_not_self_asserted(self) -> None:
        client, termination, bundle, bindings = _fixture()
        wrong_bindings = copy.deepcopy(bindings)
        wrong_bindings["agentworld"]["effective_environment_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "snapshot or environment binding"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                bundle,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=wrong_bindings,
            )
        broken = copy.deepcopy(bundle)
        broken["checkpoint_runs"][0]["attempts"][0]["request_body_base64"] = base64.b64encode(
            b"x"
        ).decode()
        broken["checkpoint_runs"][0]["attempts"][0]["request_body_utf8_sha256"] = hashlib.sha256(
            b"x"
        ).hexdigest()
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "request bytes differ"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )

    def test_duplicate_generated_json_keys_are_rejected(self) -> None:
        client, termination, bundle, bindings = _fixture()
        broken = copy.deepcopy(bundle)
        toy = next(
            row
            for row in broken["checkpoint_runs"][0]["attempts"]
            if row["case_id"].endswith("common_base_serialization-toy-repeat-1")
        )
        content = '{"sum":22,"sum":22,"difference":12,"checksum":"PUBLIC-17-5"}'
        response = {
            "model": "phase5-agentworld",
            "object": "text_completion",
            "choices": [{"index": 0, "text": content}],
        }
        toy["raw_response_body_base64"], toy["raw_response_body_sha256"] = _b64_record(
            _json_bytes(response)
        )
        toy["generated_text"] = content
        toy["generated_text_utf8_sha256"] = hashlib.sha256(content.encode()).hexdigest()
        _rehash(broken)
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            verify_phase5_synthetic_evidence(
                client,
                termination,
                broken,
                expected_client_plan_sha256=client["client_plan_sha256"],
                expected_runtime_bindings=bindings,
            )

    def test_verifier_has_no_execution_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_synthetic_evidence.py"
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
