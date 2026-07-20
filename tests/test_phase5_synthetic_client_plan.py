from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from normative_world_model.phase5_preflight import load_phase5_config
from normative_world_model.phase5_runtime_plan import RUNTIME_PLAN_FORMAT_VERSION
from normative_world_model.phase5_synthetic_client_plan import (
    PUBLIC_REQUEST_SEED,
    PUBLIC_TOY_EXPECTED,
    _canonical_sha256,
    build_phase5_synthetic_client_plan,
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
            {
                "checkpoint": "agentworld",
                "model_alias": "phase5-agentworld",
            },
            {"checkpoint": "base", "model_alias": "phase5-base"},
        ],
    }
    plan["runtime_plan_sha256"] = _canonical_sha256(plan)
    return plan


def _termination_plan() -> dict:
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
                        "case_id": (
                            f"{checkpoint}-stop-{forced_id}-repeat-{repetition}"
                        ),
                        "checkpoint": checkpoint,
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
    }
    plan["plan_sha256"] = _canonical_sha256(plan)
    return plan


def _build(**overrides) -> dict:
    runtime = overrides.pop("runtime_plan", _runtime_plan())
    termination = overrides.pop("termination_plan", _termination_plan())
    return build_phase5_synthetic_client_plan(
        config=overrides.pop("config", load_phase5_config()),
        runtime_plan=runtime,
        runtime_verification=overrides.pop(
            "runtime_verification",
            {
                "status": "PASS_LOCAL_PLAN_V2_ONLY_EXECUTION_NOT_AUTHORIZED",
                "runtime_plan_sha256": runtime["runtime_plan_sha256"],
                "http_execution": False,
                "gpu_execution": False,
            },
        ),
        termination_plan=termination,
        termination_verification=overrides.pop(
            "termination_verification",
            {
                "status": "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
                "plan_sha256": termination["plan_sha256"],
                "http_execution": False,
            },
        ),
        common_prompt=overrides.pop(
            "common_prompt", "<public common prompt><|im_start|>assistant\n"
        ),
        base_common_prompt_token_ids=overrides.pop(
            "base_common_prompt_token_ids", [11, 12, 13]
        ),
        agentworld_common_prompt_token_ids=overrides.pop(
            "agentworld_common_prompt_token_ids", [11, 12, 13]
        ),
        implementation_sources=overrides.pop(
            "implementation_sources",
            {"fixture.py": {"bytes": 1, "sha256": "a" * 64}},
        ),
        **overrides,
    )


class Phase5SyntheticClientPlanTests(unittest.TestCase):
    def test_plan_binds_public_requests_and_keeps_every_execution_closed(self) -> None:
        plan = _build()
        self.assertEqual(
            plan["status"],
            "LOCAL_PUBLIC_SYNTHETIC_CLIENT_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
        )
        self.assertEqual(plan["request_count"], 20)
        self.assertFalse(any(plan["authorization"].values()))
        self.assertEqual(plan["implementation_state"]["client"], "NOT_BUILT")
        self.assertFalse(plan["implementation_state"]["network_calls_performed"])
        self.assertEqual(
            plan["client_plan_sha256"],
            _canonical_sha256(
                {
                    key: value
                    for key, value in plan.items()
                    if key != "client_plan_sha256"
                }
            ),
        )

        cases = plan["request_sequence"]
        self.assertEqual(
            [row["checkpoint"] for row in cases[:10]], ["agentworld"] * 10
        )
        self.assertEqual([row["checkpoint"] for row in cases[10:]], ["base"] * 10)
        self.assertEqual(
            sum(row["mode"] == "common_termination" for row in cases), 8
        )
        self.assertEqual(
            sum(row["mode"] in {"native_package", "common_base_serialization"} for row in cases),
            8,
        )

    def test_toy_cases_bind_guided_schema_semantic_oracle_and_final_only_replay(self) -> None:
        plan = _build()
        toy = [
            row
            for row in plan["request_sequence"]
            if row["mode"] in {"native_package", "common_base_serialization"}
        ]
        self.assertEqual(len(toy), 8)
        for row in toy:
            body = row["request_body"]
            self.assertEqual(body["seed"], PUBLIC_REQUEST_SEED)
            self.assertEqual(body["request_id"], row["logical_request_id"])
            self.assertEqual(body["response_format"]["type"], "json_schema")
            self.assertFalse(
                body["response_format"]["json_schema"]["schema"][
                    "additionalProperties"
                ]
            )
            self.assertEqual(row["headers"]["X-Request-ID"], row["logical_request_id"])
        gate = plan["semantic_pass_gate"]
        self.assertEqual(gate["toy_oracle_exact"], PUBLIC_TOY_EXPECTED)
        self.assertTrue(gate["toy_oracle_must_pass_for_every_toy_case"])
        self.assertEqual(
            gate["repeat_comparison"],
            "FINAL_CONTENT_EXACT_STRING_EQUALITY_WITHIN_CHECKPOINT_AND_MODE",
        )
        self.assertIn("SEPARATELY", gate["reasoning_comparison"])

    def test_retry_identity_and_raw_before_parse_are_machine_readable(self) -> None:
        plan = _build()
        retry = plan["retry_contract"]
        self.assertEqual(retry["maximum_retries"], 1)
        self.assertEqual(retry["retryable_outcomes"], ["transport_error", "http_5xx"])
        self.assertTrue(retry["same_request_body_required"])
        self.assertTrue(retry["same_request_body_utf8_bytes_required"])
        self.assertTrue(retry["same_method_and_endpoint_required"])
        self.assertTrue(retry["same_headers_required"])
        self.assertTrue(retry["same_logical_request_id_required"])
        self.assertTrue(retry["same_seed_required"])
        self.assertTrue(retry["both_attempts_retained"])

        evidence = plan["raw_before_parse_evidence_contract"]
        order = evidence["attempt_event_order"]
        self.assertLess(
            order.index("raw_capture_fsynced"),
            order.index("response_envelope_parse_started"),
        )
        self.assertLess(
            order.index("generated_text_capture_fsynced"),
            order.index("generated_text_json_parse_started"),
        )
        self.assertIn("raw_response_body_base64", evidence["raw_envelope_fields"])
        self.assertTrue(
            evidence[
                "generated_text_must_be_fsynced_verbatim_before_generated_text_json_parse"
            ]
        )

        for row in plan["request_sequence"]:
            expected = _canonical_sha256(
                {
                    "method": row["method"],
                    "endpoint": row["endpoint"],
                    "logical_request_id": row["logical_request_id"],
                    "headers": row["headers"],
                    "request_body": row["request_body"],
                    "seed": row["seed"],
                }
            )
            self.assertEqual(row["request_identity_sha256"], expected)
            expected_body = row["request_body"]
            if expected_body is None:
                rendered = b""
            else:
                rendered = json.dumps(
                    expected_body,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            self.assertEqual(
                row["request_body_utf8_sha256"], hashlib.sha256(rendered).hexdigest()
            )

    def test_language_only_probe_is_public_valid_and_rejection_is_required(self) -> None:
        plan = _build()
        probes = [
            row
            for row in plan["request_sequence"]
            if row["mode"] == "language_only_negative"
        ]
        self.assertEqual(len(probes), 2)
        for row in probes:
            parts = row["request_body"]["messages"][0]["content"]
            image = next(part for part in parts if part["type"] == "image_url")
            self.assertTrue(image["image_url"]["url"].startswith("data:image/png;base64,"))
        gate = plan["semantic_pass_gate"]["language_only_probe"]
        self.assertEqual(gate["required_status_class"], "4xx")
        self.assertEqual(gate["http_2xx_result"], "FAIL_LANGUAGE_ONLY_CONTRACT")
        self.assertEqual(gate["exact_error_body_semantics_status"], "PENDING_RUNTIME_EVIDENCE")

    def test_drift_in_bindings_token_ids_or_authorization_fails_closed(self) -> None:
        runtime = _runtime_plan()
        runtime["launch_specs"][0]["model_alias"] = "changed"
        with self.assertRaisesRegex(ValueError, "runtime plan"):
            _build(runtime_plan=runtime)

        termination = _termination_plan()
        termination["cases"][0]["request_body"]["seed"] = 1
        with self.assertRaisesRegex(ValueError, "termination plan"):
            _build(termination_plan=termination)

        with self.assertRaisesRegex(ValueError, "token proof"):
            _build(agentworld_common_prompt_token_ids=[11, 12, 14])

        opened = load_phase5_config()
        opened["authorization"]["server_rental"] = True
        with self.assertRaises(ValueError):
            _build(config=opened)

    def test_module_has_no_execution_network_or_retained_data_client_surface(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "normative_world_model"
            / "phase5_synthetic_client_plan.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "import subprocess",
            "import socket",
            "import urllib",
            "import requests",
            "import httpx",
            "data/generated",
            "joint_examples",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
