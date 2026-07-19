from __future__ import annotations

import json
import unittest
from copy import deepcopy

from normative_world_model.phase5_termination_probe import (
    build_common_termination_probe_plan,
    load_termination_probe_config,
    validate_termination_probe_config,
    verify_common_termination_probe_evidence,
)


class _TerminationTokenizer:
    def __init__(self, checkpoint: str) -> None:
        self._ids = {"<|endoftext|>": 248044, "<|im_end|>": 248046}
        if checkpoint == "base":
            self.eos_token = "<|endoftext|>"
            self.eos_token_id = 248044
        else:
            self.eos_token = "<|im_end|>"
            self.eos_token_id = 248046

    def convert_tokens_to_ids(self, literal: str) -> int:
        return self._ids[literal]

    def apply_chat_template(self, messages, **kwargs):
        if kwargs["add_generation_prompt"] is not False:
            raise AssertionError("common renderer must receive history-only mode")
        return "<history>" + "|".join(row["content"] for row in messages)

    def encode(self, value: str, *, add_special_tokens: bool) -> list[int]:
        if add_special_tokens:
            raise AssertionError("special tokens must not be added implicitly")
        if value in self._ids:
            return [self._ids[value]]
        return [11, 12, 13, 14]


def _plan() -> dict:
    return build_common_termination_probe_plan(
        config=load_termination_probe_config(),
        base_tokenizer=_TerminationTokenizer("base"),
        agentworld_tokenizer=_TerminationTokenizer("agentworld"),
        tokenizer_probe_verification={"status": "PASS", "probe_sha256": "a" * 64},
    )


def _evidence(plan: dict) -> list[dict]:
    rows = []
    for case in plan["cases"]:
        forced_id = case["forced_stop_token_id"]
        response = {
            "id": f"synthetic-{case['case_id']}",
            "model": case["model_alias"],
            "choices": [
                {
                    "index": 0,
                    "text": next(
                        row["literal"]
                        for row in plan["literal_bindings"]
                        if row["token_id"] == forced_id
                    ),
                    "finish_reason": "stop",
                    "stop_reason": forced_id,
                    "token_ids": [forced_id],
                    "prompt_token_ids": plan["public_prompt_token_ids"],
                }
            ],
            "usage": {
                "prompt_tokens": plan["public_prompt_token_count"],
                "completion_tokens": 1,
                "total_tokens": plan["public_prompt_token_count"] + 1,
            },
        }
        rows.append(
            {
                "case_id": case["case_id"],
                "request_body": case["request_body"],
                "http_status": 200,
                "raw_response_text": json.dumps(response, sort_keys=True),
            }
        )
    return rows


class Phase5TerminationProbeTests(unittest.TestCase):
    def test_candidate_is_closed_and_builds_eight_symmetric_cases(self) -> None:
        config = load_termination_probe_config()
        self.assertEqual(validate_termination_probe_config(config), [])
        plan = _plan()
        self.assertEqual(plan["status"], "CANDIDATE_PLAN_PASS_EXECUTION_NOT_AUTHORIZED")
        self.assertFalse(plan["authorization"]["http_execution"])
        self.assertEqual(len(plan["cases"]), 8)
        self.assertEqual(
            {(row["checkpoint"], row["forced_stop_token_id"]) for row in plan["cases"]},
            {
                ("agentworld", 248044),
                ("agentworld", 248046),
                ("base", 248044),
                ("base", 248046),
            },
        )
        for case in plan["cases"]:
            body = case["request_body"]
            self.assertTrue(body["ignore_eos"])
            self.assertEqual(body["stop_token_ids"], [248044, 248046])
            self.assertEqual(body["allowed_token_ids"], [case["forced_stop_token_id"]])
            self.assertFalse(body["skip_special_tokens"])
            self.assertTrue(body["return_token_ids"])

    def test_config_drift_fails_closed(self) -> None:
        config = load_termination_probe_config()
        config["request"]["ignore_eos"] = False
        self.assertTrue(validate_termination_probe_config(config))

    def test_loaded_default_eos_drift_stops_plan(self) -> None:
        base = _TerminationTokenizer("base")
        base.eos_token_id = 248046
        with self.assertRaisesRegex(ValueError, "default EOS binding differs: base"):
            build_common_termination_probe_plan(
                config=load_termination_probe_config(),
                base_tokenizer=base,
                agentworld_tokenizer=_TerminationTokenizer("agentworld"),
                tokenizer_probe_verification={
                    "status": "PASS",
                    "probe_sha256": "a" * 64,
                },
            )

    def test_evidence_requires_explicit_stop_reason_and_exact_repeats(self) -> None:
        plan = _plan()
        rows = _evidence(plan)
        self.assertEqual(
            verify_common_termination_probe_evidence(
                plan, rows, expected_plan_sha256=plan["plan_sha256"]
            )["status"],
            "PASS",
        )
        broken = deepcopy(rows)
        response = json.loads(broken[0]["raw_response_text"])
        response["choices"][0]["stop_reason"] = None
        broken[0]["raw_response_text"] = json.dumps(response)
        with self.assertRaisesRegex(ValueError, "stop semantics"):
            verify_common_termination_probe_evidence(
                plan, broken, expected_plan_sha256=plan["plan_sha256"]
            )

        with self.assertRaisesRegex(ValueError, "exact case set"):
            verify_common_termination_probe_evidence(
                plan, rows[:-1], expected_plan_sha256=plan["plan_sha256"]
            )

        with self.assertRaisesRegex(ValueError, "external lock binding"):
            verify_common_termination_probe_evidence(
                plan, rows, expected_plan_sha256="b" * 64
            )

        bool_usage = deepcopy(rows)
        response = json.loads(bool_usage[0]["raw_response_text"])
        response["usage"]["completion_tokens"] = True
        bool_usage[0]["raw_response_text"] = json.dumps(response)
        with self.assertRaisesRegex(ValueError, "usage differs"):
            verify_common_termination_probe_evidence(
                plan, bool_usage, expected_plan_sha256=plan["plan_sha256"]
            )

    def test_evidence_rejects_duplicate_json_keys_before_semantics(self) -> None:
        plan = _plan()
        rows = _evidence(plan)
        rows[0]["raw_response_text"] = '{"model":"x","model":"y"}'
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            verify_common_termination_probe_evidence(
                plan, rows, expected_plan_sha256=plan["plan_sha256"]
            )


if __name__ == "__main__":
    unittest.main()
