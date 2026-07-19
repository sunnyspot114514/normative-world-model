"""Local-only plan and evidence verifier for the Phase-5 termination probe.

There is deliberately no HTTP client or server launcher in this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .phase5_public_metadata import _load_inert_json
from .phase5_serialization import render_common_base_prompt
from .phase5_tokenizer_probe import (
    _load_bound_tokenizers,
    _resolve_loader,
    verify_public_tokenizer_probe,
)

TERMINATION_CONFIG_SEMANTIC_SHA256 = (
    "832c06e718b9436f708fa0db9d4ed78e09936b2d0253a692e13958a6986d69f7"
)
TERMINATION_PLAN_FORMAT_VERSION = "phase5-common-termination-plan-v1"
TERMINATION_PLAN_MAX_BYTES = 2 * 1024 * 1024
RAW_RESPONSE_MAX_BYTES = 2 * 1024 * 1024
IMPLEMENTATION_SOURCE_PATHS = (
    "configs/phase5_common_termination_probe_candidate.toml",
    "src/normative_world_model/phase5_public_metadata.py",
    "src/normative_world_model/phase5_serialization.py",
    "src/normative_world_model/phase5_termination_probe.py",
    "src/normative_world_model/phase5_tokenizer_probe.py",
)


def default_termination_probe_config_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "configs"
        / "phase5_common_termination_probe_candidate.toml"
    )


def load_termination_probe_config(path: Path | None = None) -> dict[str, Any]:
    with (path or default_termination_probe_config_path()).open("rb") as handle:
        return tomllib.load(handle)


def _canonical_sha256(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((body + "\n").encode("utf-8")).hexdigest()


def termination_config_semantic_sha256(config: Mapping[str, Any]) -> str:
    body = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def validate_termination_probe_config(config: Mapping[str, Any]) -> list[str]:
    failures = []
    if termination_config_semantic_sha256(config) != TERMINATION_CONFIG_SEMANTIC_SHA256:
        failures.append("termination probe config differs from its reviewed semantic binding")
    if config.get("status") != "CANDIDATE_LOCAL_PLAN_ONLY":
        failures.append("termination probe must remain a local-only candidate")
    authorization = config.get("authorization", {})
    for field in (
        "http_execution",
        "model_download",
        "server_rental",
        "gpu_execution",
        "project_prompt_access",
        "scientific_metrics",
    ):
        if authorization.get(field) is not False:
            failures.append(f"authorization.{field} must remain false")
    server = config.get("server", {})
    if (
        server.get("engine") != "vllm"
        or server.get("version") != "0.25.1"
        or server.get("generation_config") != "vllm"
        or server.get("generation_config_cli") != "--generation-config vllm"
    ):
        failures.append("server generation-config closure differs")
    aliases = config.get("model_aliases", {})
    if aliases != {"agentworld": "phase5-agentworld", "base": "phase5-base"}:
        failures.append("served model aliases differ")
    if config.get("checkpoint_default_eos") != {
        "agentworld": {"literal": "<|im_end|>", "token_id": 248046},
        "base": {"literal": "<|endoftext|>", "token_id": 248044},
    }:
        failures.append("checkpoint default EOS bindings differ")
    request = config.get("request", {})
    expected_request = {
        "endpoint": "/v1/completions",
        "stream": False,
        "temperature": 0.0,
        "top_p": 1.0,
        "n": 1,
        "seed": 2026072004,
        "max_tokens": 4,
        "min_tokens": 0,
        "add_special_tokens": False,
        "truncate_prompt_tokens": "NONE",
        "stop_strings": [],
        "stop_token_ids": [248044, 248046],
        "stop_token_literals": ["<|endoftext|>", "<|im_end|>"],
        "forced_stop_token_ids": [248044, 248046],
        "ignore_eos": True,
        "include_stop_str_in_output": False,
        "skip_special_tokens": False,
        "return_token_ids": True,
        "repetitions_per_checkpoint_stop_token": 2,
    }
    if request != expected_request:
        failures.append("termination request contract differs")
    acceptance = config.get("acceptance", {})
    expected_acceptance = {
        "expected_case_count": 8,
        "http_status": 200,
        "choice_count": 1,
        "finish_reason": "stop",
        "completion_tokens": 1,
        "require_stop_reason_exact_token_id": True,
        "require_generated_token_ids_exact_forced_token": True,
        "require_prompt_token_ids_exact": True,
        "require_response_model_alias_exact": True,
        "require_repeat_semantics_exact": True,
        "failure_policy": "TECHNICALLY_BLOCKED",
    }
    if acceptance != expected_acceptance:
        failures.append("termination acceptance contract differs")
    messages = config.get("public_messages")
    if not isinstance(messages, list) or not all(
        isinstance(row, dict) and isinstance(row.get("content"), str) and row["content"]
        for row in messages
    ):
        failures.append("public termination messages are malformed")
    elif [row.get("role") for row in messages] != ["system", "user"]:
        failures.append("public termination messages differ")
    return failures


def _implementation_source_records() -> dict[str, dict[str, Any]]:
    project_root = Path(__file__).resolve().parents[2]
    result = {}
    for relative in IMPLEMENTATION_SOURCE_PATHS:
        body = (project_root / relative).read_bytes()
        result[relative] = {
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    return result


def _effective_token_id(tokenizer: Any, literal: str) -> int:
    token_id = tokenizer.convert_tokens_to_ids(literal)
    if (
        not isinstance(token_id, int)
        or isinstance(token_id, bool)
        or tokenizer.encode(literal, add_special_tokens=False) != [token_id]
    ):
        raise ValueError(f"termination literal is not one exact token: {literal}")
    return token_id


def build_common_termination_probe_plan(
    *,
    config: Mapping[str, Any],
    base_tokenizer: Any,
    agentworld_tokenizer: Any,
    tokenizer_probe_verification: Mapping[str, Any],
) -> dict[str, Any]:
    failures = validate_termination_probe_config(config)
    if failures:
        raise ValueError("; ".join(failures))
    if (
        tokenizer_probe_verification.get("status") != "PASS"
        or not isinstance(tokenizer_probe_verification.get("probe_sha256"), str)
        or len(tokenizer_probe_verification["probe_sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in tokenizer_probe_verification["probe_sha256"]
        )
    ):
        raise ValueError("public tokenizer proof is not verified")

    for checkpoint, tokenizer in (
        ("agentworld", agentworld_tokenizer),
        ("base", base_tokenizer),
    ):
        expected = config["checkpoint_default_eos"][checkpoint]
        if (
            getattr(tokenizer, "eos_token", None) != expected["literal"]
            or getattr(tokenizer, "eos_token_id", None) != expected["token_id"]
        ):
            raise ValueError(f"checkpoint default EOS binding differs: {checkpoint}")

    request_config = config["request"]
    literal_bindings = []
    for literal, expected_id in zip(
        request_config["stop_token_literals"],
        request_config["stop_token_ids"],
        strict=True,
    ):
        base_id = _effective_token_id(base_tokenizer, literal)
        agentworld_id = _effective_token_id(agentworld_tokenizer, literal)
        if base_id != expected_id or agentworld_id != expected_id:
            raise ValueError(f"termination token ID differs from candidate contract: {literal}")
        literal_bindings.append({"literal": literal, "token_id": expected_id})

    rendered_prompt = render_common_base_prompt(base_tokenizer, config["public_messages"])
    base_ids = base_tokenizer.encode(rendered_prompt, add_special_tokens=False)
    agentworld_ids = agentworld_tokenizer.encode(rendered_prompt, add_special_tokens=False)
    if base_ids != agentworld_ids:
        raise ValueError("termination prompt token IDs differ across checkpoints")
    if not base_ids or len(base_ids) + request_config["max_tokens"] > 8192:
        raise ValueError("termination prompt violates the common context contract")

    cases = []
    for checkpoint in ("agentworld", "base"):
        model_alias = config["model_aliases"][checkpoint]
        for forced_id in request_config["forced_stop_token_ids"]:
            for repetition in range(
                request_config["repetitions_per_checkpoint_stop_token"]
            ):
                body = {
                    "model": model_alias,
                    "prompt": rendered_prompt,
                    "stream": request_config["stream"],
                    "temperature": request_config["temperature"],
                    "top_p": request_config["top_p"],
                    "n": request_config["n"],
                    "seed": request_config["seed"],
                    "max_tokens": request_config["max_tokens"],
                    "min_tokens": request_config["min_tokens"],
                    "add_special_tokens": request_config["add_special_tokens"],
                    "truncate_prompt_tokens": None,
                    "stop": request_config["stop_strings"],
                    "stop_token_ids": request_config["stop_token_ids"],
                    "allowed_token_ids": [forced_id],
                    "ignore_eos": request_config["ignore_eos"],
                    "include_stop_str_in_output": request_config[
                        "include_stop_str_in_output"
                    ],
                    "skip_special_tokens": request_config["skip_special_tokens"],
                    "return_token_ids": request_config["return_token_ids"],
                    "echo": False,
                }
                cases.append(
                    {
                        "case_id": (
                            f"{checkpoint}-stop-{forced_id}-repeat-{repetition + 1}"
                        ),
                        "checkpoint": checkpoint,
                        "model_alias": model_alias,
                        "forced_stop_token_id": forced_id,
                        "repetition": repetition + 1,
                        "request_body": body,
                        "request_body_sha256": _canonical_sha256(body),
                    }
                )
    if len(cases) != config["acceptance"]["expected_case_count"]:
        raise ValueError("termination plan case count differs")
    result = {
        "format_version": TERMINATION_PLAN_FORMAT_VERSION,
        "status": "CANDIDATE_PLAN_PASS_EXECUTION_NOT_AUTHORIZED",
        "authorization": dict(config["authorization"]),
        "termination_config_semantic_sha256": TERMINATION_CONFIG_SEMANTIC_SHA256,
        "implementation_sources": _implementation_source_records(),
        "server_contract": dict(config["server"]),
        "tokenizer_probe_verification": dict(tokenizer_probe_verification),
        "literal_bindings": literal_bindings,
        "public_prompt": rendered_prompt,
        "public_prompt_token_ids": base_ids,
        "public_prompt_token_count": len(base_ids),
        "endpoint": request_config["endpoint"],
        "cases": cases,
        "acceptance": dict(config["acceptance"]),
    }
    result["plan_sha256"] = _canonical_sha256(result)
    return result


def default_common_termination_probe_plan_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return (
        project_root
        / ".cache"
        / "phase5_common_termination_probe_plan"
        / f"v1-{TERMINATION_CONFIG_SEMANTIC_SHA256[:12]}.json"
    )


def _write_plan_once(path: Path, plan: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite termination probe plan: {path}")
    data = (json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if len(data) > TERMINATION_PLAN_MAX_BYTES:
        raise ValueError("termination probe plan exceeds its byte cap")
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


def _load_live_probe_inputs() -> tuple[Any, Any, dict[str, Any]]:
    verification = verify_public_tokenizer_probe()
    loader, _ = _resolve_loader()
    _, _, base_tokenizer, agentworld_tokenizer = _load_bound_tokenizers(loader)
    return base_tokenizer, agentworld_tokenizer, verification


def run_common_termination_probe_plan() -> dict[str, Any]:
    base_tokenizer, agentworld_tokenizer, verification = _load_live_probe_inputs()
    plan = build_common_termination_probe_plan(
        config=load_termination_probe_config(),
        base_tokenizer=base_tokenizer,
        agentworld_tokenizer=agentworld_tokenizer,
        tokenizer_probe_verification=verification,
    )
    _write_plan_once(default_common_termination_probe_plan_path(), plan)
    return plan


def _read_plan(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("termination probe plan is not a regular file")
    stat = path.stat()
    if stat.st_nlink != 1:
        raise ValueError("termination probe plan has multiple hard links")
    if stat.st_size <= 0 or stat.st_size > TERMINATION_PLAN_MAX_BYTES:
        raise ValueError("termination probe plan violates its byte cap")
    value = _load_inert_json(path.read_bytes(), label="termination probe plan")
    if not isinstance(value, dict):
        raise ValueError("termination probe plan must be an object")
    return value


def _verify_plan_documents(
    stored: Mapping[str, Any],
    rebuilt: Mapping[str, Any],
) -> dict[str, Any]:
    without_hash = {key: value for key, value in stored.items() if key != "plan_sha256"}
    if stored.get("plan_sha256") != _canonical_sha256(without_hash):
        raise ValueError("termination probe plan hash is invalid")
    if stored != rebuilt:
        raise ValueError("termination probe plan differs from independent rebuild")
    return {
        "status": "PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED",
        "plan_sha256": stored["plan_sha256"],
        "case_count": len(stored["cases"]),
        "public_prompt_token_count": stored["public_prompt_token_count"],
        "http_execution": stored["authorization"]["http_execution"],
    }


def verify_common_termination_probe_plan() -> dict[str, Any]:
    stored = _read_plan(default_common_termination_probe_plan_path())
    base_tokenizer, agentworld_tokenizer, verification = _load_live_probe_inputs()
    rebuilt = build_common_termination_probe_plan(
        config=load_termination_probe_config(),
        base_tokenizer=base_tokenizer,
        agentworld_tokenizer=agentworld_tokenizer,
        tokenizer_probe_verification=verification,
    )
    return _verify_plan_documents(stored, rebuilt)


def verify_common_termination_probe_evidence(
    plan: Mapping[str, Any],
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    expected_plan_sha256: str,
) -> dict[str, Any]:
    """Verify raw-before-parse response rows for a future authorized probe."""

    if (
        not isinstance(expected_plan_sha256, str)
        or len(expected_plan_sha256) != 64
        or any(character not in "0123456789abcdef" for character in expected_plan_sha256)
        or plan.get("plan_sha256") != expected_plan_sha256
    ):
        raise ValueError("termination probe plan differs from the external lock binding")
    without_hash = {key: value for key, value in plan.items() if key != "plan_sha256"}
    if plan.get("plan_sha256") != _canonical_sha256(without_hash):
        raise ValueError("termination probe plan hash is invalid")
    plan_rows = plan.get("cases", [])
    if not isinstance(plan_rows, list) or not all(isinstance(row, dict) for row in plan_rows):
        raise ValueError("termination probe plan case list is malformed")
    for case in plan_rows:
        if case.get("request_body_sha256") != _canonical_sha256(case.get("request_body")):
            raise ValueError("termination probe request-body hash is invalid")
    planned = {row["case_id"]: row for row in plan_rows}
    if len(planned) != plan.get("acceptance", {}).get("expected_case_count"):
        raise ValueError("termination probe plan case set is malformed")
    observed = {}
    signatures: dict[tuple[str, int], list[tuple[Any, ...]]] = defaultdict(list)
    required_keys = {"case_id", "request_body", "http_status", "raw_response_text"}
    for row in evidence_rows:
        if not isinstance(row, Mapping) or set(row) != required_keys:
            raise ValueError("termination evidence row schema differs")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or case_id in observed:
            raise ValueError("termination evidence has a duplicate or invalid case ID")
        observed[case_id] = row
        if case_id not in planned:
            continue
        expected = planned[case_id]
        if row["request_body"] != expected["request_body"]:
            raise ValueError(f"termination request body differs: {case_id}")
        if row["http_status"] != plan["acceptance"]["http_status"]:
            raise ValueError(f"termination HTTP status differs: {case_id}")
        raw = row["raw_response_text"]
        if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > RAW_RESPONSE_MAX_BYTES:
            raise ValueError(f"termination raw response is invalid: {case_id}")
        response = _load_inert_json(raw.encode("utf-8"), label=f"termination/{case_id}")
        if not isinstance(response, dict) or response.get("model") != expected["model_alias"]:
            raise ValueError(f"termination response model differs: {case_id}")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError(f"termination response choices differ: {case_id}")
        choice = choices[0]
        forced_id = expected["forced_stop_token_id"]
        stop_reason = choice.get("stop_reason")
        if (
            not isinstance(choice.get("index"), int)
            or isinstance(choice.get("index"), bool)
            or choice["index"] != 0
            or not isinstance(choice.get("text"), str)
            or choice.get("finish_reason") != "stop"
            or not isinstance(stop_reason, int)
            or isinstance(stop_reason, bool)
            or stop_reason != forced_id
            or choice.get("token_ids") != [forced_id]
            or choice.get("prompt_token_ids") != plan["public_prompt_token_ids"]
        ):
            raise ValueError(f"termination stop semantics differ: {case_id}")
        usage = response.get("usage")
        if (
            not isinstance(usage, dict)
            or not isinstance(usage.get("completion_tokens"), int)
            or isinstance(usage.get("completion_tokens"), bool)
            or usage["completion_tokens"] != 1
            or not isinstance(usage.get("prompt_tokens"), int)
            or isinstance(usage.get("prompt_tokens"), bool)
            or usage["prompt_tokens"] != plan["public_prompt_token_count"]
        ):
            raise ValueError(f"termination usage differs: {case_id}")
        signature = (
            choice.get("text"),
            tuple(choice["token_ids"]),
            choice["finish_reason"],
            choice["stop_reason"],
            usage["prompt_tokens"],
            usage["completion_tokens"],
        )
        signatures[(expected["checkpoint"], forced_id)].append(signature)
    if set(observed) != set(planned):
        raise ValueError("termination evidence exact case set differs")
    for key, rows in signatures.items():
        if len(rows) != 2 or rows[0] != rows[1]:
            raise ValueError(f"termination repeat semantics differ: {key}")
    return {
        "status": "PASS",
        "case_count": len(observed),
        "checkpoint_stop_cells": len(signatures),
        "explicit_stop_token_ids": plan["literal_bindings"],
    }
