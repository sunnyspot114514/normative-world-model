"""Public-synthetic tokenizer proof over the restricted Phase-5 snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .phase5_public_metadata import (
    default_public_metadata_root,
    verify_public_metadata_bundle,
)
from .phase5_serialization import (
    FORBIDDEN_COMMON_CONTROL_LITERALS,
    inspect_tokenizer_packages,
    prove_common_prompt_token_equality,
    render_common_base_prompt,
)

PROBE_FORMAT_VERSION = "phase5-public-tokenizer-probe-v1"
EXPECTED_CONFIG_DIFFERENCES = {
    "eos_token": {"base": "<|endoftext|>", "agentworld": "<|im_end|>"},
    "model_max_length": {"base": 262144, "agentworld": 131072},
}
EXPECTED_DEFAULT_EQUIVALENCES = ["model.ignore_merges:absent_equals_false"]
PUBLIC_SYNTHETIC_MESSAGE_SETS: tuple[tuple[str, tuple[dict[str, str], ...]], ...] = (
    (
        "ascii-json",
        (
            {"role": "system", "content": "Return one small public synthetic JSON object."},
            {"role": "user", "content": "Alpha beta 123; keys are status and count."},
        ),
    ),
    (
        "unicode",
        (
            {"role": "system", "content": "This is a public tokenizer robustness probe."},
            {
                "role": "user",
                "content": "Café, café, 中文, العربية, emoji 🧪, and tabs\tnewlines\n.",
            },
        ),
    ),
    (
        "punctuation",
        (
            {"role": "system", "content": "Preserve punctuation in a synthetic response."},
            {
                "role": "user",
                "content": "[]{}()<> /\\ :: == != && || 0.001 -42 +7e3; no project content.",
            },
        ),
    ),
    (
        "multi-turn",
        (
            {"role": "system", "content": "Public multi-turn serialization probe."},
            {"role": "user", "content": "Name a synthetic color."},
            {"role": "assistant", "content": "Blue."},
            {"role": "user", "content": "Now return its synthetic index as JSON."},
        ),
    ),
    (
        "long-public",
        (
            {"role": "system", "content": "Public long-context tokenizer probe."},
            {"role": "user", "content": "alpha beta gamma delta 123 " * 1000},
        ),
    ),
)


def _artifact_sha256(value: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest()


def build_public_tokenizer_probe(
    *,
    metadata_verification: Mapping[str, Any],
    package_report: Mapping[str, Any],
    base_tokenizer: Any,
    agentworld_tokenizer: Any,
    runtime_versions: Mapping[str, str],
) -> dict[str, Any]:
    """Build a local proof from already loaded, caller-bound public tokenizers."""

    if metadata_verification.get("status") != "PASS":
        raise ValueError("public metadata bundle verification did not pass")
    if package_report.get("status") != "PASS":
        raise ValueError("tokenizer package inspection did not pass")
    if package_report.get("tokenizer_config_differences") != EXPECTED_CONFIG_DIFFERENCES:
        raise ValueError("tokenizer config differences are not the reviewed exact pair")
    if package_report.get("normalized_default_equivalences") != EXPECTED_DEFAULT_EQUIVALENCES:
        raise ValueError("tokenizer default equivalences are not the reviewed exact set")
    if len(base_tokenizer) != len(agentworld_tokenizer):
        raise ValueError("effective tokenizer lengths differ")

    control_token_ids = {}
    for literal in FORBIDDEN_COMMON_CONTROL_LITERALS:
        base_id = base_tokenizer.convert_tokens_to_ids(literal)
        agentworld_id = agentworld_tokenizer.convert_tokens_to_ids(literal)
        if (
            not isinstance(base_id, int)
            or isinstance(base_id, bool)
            or base_id != agentworld_id
            or base_tokenizer.encode(literal, add_special_tokens=False) != [base_id]
            or agentworld_tokenizer.encode(literal, add_special_tokens=False) != [agentworld_id]
        ):
            raise ValueError(f"effective control-token binding differs: {literal}")
        control_token_ids[literal] = base_id

    rendered = []
    for prompt_id, messages in PUBLIC_SYNTHETIC_MESSAGE_SETS:
        rendered.append((prompt_id, render_common_base_prompt(base_tokenizer, messages)))
    proof = prove_common_prompt_token_equality(
        rendered,
        base_tokenizer=base_tokenizer,
        agentworld_tokenizer=agentworld_tokenizer,
        tokenizer_package_report=package_report,
    )
    if max(row["token_count"] for row in proof["rows"]) > 8192:
        raise ValueError("public synthetic tokenizer probe exceeds the frozen context cap")
    if not any(row["token_count"] >= 3072 for row in proof["rows"]):
        raise ValueError("public synthetic tokenizer probe lacks a long-context witness")
    loaded_config_differences = {
        "eos_token": {
            "base": base_tokenizer.eos_token,
            "agentworld": agentworld_tokenizer.eos_token,
        },
        "model_max_length": {
            "base": base_tokenizer.model_max_length,
            "agentworld": agentworld_tokenizer.model_max_length,
        },
    }
    if loaded_config_differences != EXPECTED_CONFIG_DIFFERENCES:
        raise ValueError(
            "loaded tokenizer diagnostics differ from their bound package declarations"
        )
    result = {
        "format_version": PROBE_FORMAT_VERSION,
        "status": "PASS_WITH_LOCK_A_EOS_ACTION",
        "input_tokenization_status": "PASS",
        "metadata_verification": dict(metadata_verification),
        "runtime_versions": dict(runtime_versions),
        "effective_tokenizer_length": len(base_tokenizer),
        "effective_control_token_ids": control_token_ids,
        "package_report": dict(package_report),
        "common_prompt_proof": proof,
        "runtime_diagnostics": {
            "base_eos_token": base_tokenizer.eos_token,
            "base_eos_token_id": base_tokenizer.eos_token_id,
            "agentworld_eos_token": agentworld_tokenizer.eos_token,
            "agentworld_eos_token_id": agentworld_tokenizer.eos_token_id,
            "base_model_max_length": base_tokenizer.model_max_length,
            "agentworld_model_max_length": agentworld_tokenizer.model_max_length,
        },
        "lock_a_required_actions": [
            "freeze_one_common_mode_eos_termination_policy_after_synthetic_serving_probe"
        ],
    }
    result["probe_sha256"] = _artifact_sha256(result)
    return result


def default_public_tokenizer_probe_path() -> Path:
    root = default_public_metadata_root()
    return root.parents[1] / "phase5_public_tokenizer_probe" / f"{root.name}.json"


def _write_probe_once(path: Path, result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite public tokenizer probe: {path}")
    partial = path.with_name(path.name + ".part")
    data = (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    try:
        with partial.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def run_public_tokenizer_probe(
    loader: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Verify, load locally without remote code, and prove public prompt token IDs."""

    if loader is None:
        try:
            import tokenizers
            import transformers
            from transformers import AutoTokenizer
        except ImportError as error:
            raise RuntimeError(
                "the public tokenizer probe requires transformers/tokenizers"
            ) from error
        loader = AutoTokenizer.from_pretrained
        runtime_versions = {
            "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__,
        }
    else:
        runtime_versions = {"transformers": "injected", "tokenizers": "injected"}
    root = default_public_metadata_root()
    metadata_verification = verify_public_metadata_bundle(root)
    base_root = root / "base" / "files"
    agentworld_root = root / "agentworld" / "files"
    package_report = inspect_tokenizer_packages(base_root, agentworld_root)
    load_kwargs = {
        "local_files_only": True,
        "trust_remote_code": False,
        "use_fast": True,
    }
    base_tokenizer = loader(base_root, **load_kwargs)
    agentworld_tokenizer = loader(agentworld_root, **load_kwargs)
    if not getattr(base_tokenizer, "is_fast", False) or not getattr(
        agentworld_tokenizer, "is_fast", False
    ):
        raise ValueError("both public tokenizer snapshots must load as fast tokenizers")
    result = build_public_tokenizer_probe(
        metadata_verification=metadata_verification,
        package_report=package_report,
        base_tokenizer=base_tokenizer,
        agentworld_tokenizer=agentworld_tokenizer,
        runtime_versions=runtime_versions,
    )
    _write_probe_once(default_public_tokenizer_probe_path(), result)
    return result
