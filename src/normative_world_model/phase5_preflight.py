"""Local-only Phase-5 contract, selector, and remote-payload primitives.

This module deliberately contains no model-download, network, GPU, or server
execution path.  The real retained-discovery selector is separately gated; the
functions here can be exercised against synthetic fixtures before that gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .model_arms import recompute_factorized_policy_result
from .transfer_matrix import TARGET_PROFILE_PAIRS

ALLOWED_REMOTE_CONTENT_CLASSES = frozenset(
    {"declared_runtime_source_files", "public_synthetic_inputs"}
)
PROFILE_IDS = tuple(sorted({item for pair in TARGET_PROFILE_PAIRS for item in pair}))
STAGE2_CONFIG_SEMANTIC_SHA256 = (
    "d46462f4f4c26765090a771972db30c62fa0a7a85e711d0c544f724bee55e481"
)


def default_phase5_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "phase5_scale_inference_draft.toml"


def load_phase5_config(path: Path | None = None) -> dict[str, Any]:
    with (path or default_phase5_config_path()).open("rb") as handle:
        return tomllib.load(handle)


def phase5_config_semantic_sha256(config: Mapping[str, Any]) -> str:
    """Hash the complete parsed TOML semantics, independent of formatting."""

    canonical = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_stage2_contract(config: Mapping[str, Any]) -> list[str]:
    """Return fail-closed Stage-2 contract violations without changing state."""

    failures: list[str] = []
    if phase5_config_semantic_sha256(config) != STAGE2_CONFIG_SEMANTIC_SHA256:
        failures.append("complete Stage-2 config semantics differ from the reviewed binding")
    authorization = config.get("authorization", {})
    if authorization.get("protocol_drafting") is not True:
        failures.append("protocol_drafting must remain true during Stage 2")
    if authorization.get("public_metadata_download") is not True:
        failures.append("public metadata download must remain the only bounded network action")
    for name in (
        "population_selection",
        "model_download",
        "server_rental",
        "synthetic_preflight_lock_accepted",
        "synthetic_preflight_rental",
        "scientific_execution_lock_accepted",
        "scientific_run",
        "performance_inference",
        "training",
        "formal_evaluation",
        "confirmation_generation",
    ):
        if authorization.get(name) is not False:
            failures.append(f"authorization.{name} must remain false")
    if authorization.get("population_selection_authorization_status") != (
        "PENDING_SEPARATE_LOCAL_DERIVATION_GATE"
    ):
        failures.append("population selection is not waiting on its separate local gate")
    for name in ("synthetic_preflight_maximum_spend_usd", "scientific_run_maximum_spend_usd"):
        if authorization.get(name) != 0:
            failures.append(f"authorization.{name} must remain zero")

    source = config.get("source", {})
    if source.get("confirmation_status") != "RESERVED_NOT_GENERATED":
        failures.append("confirmation must remain RESERVED_NOT_GENERATED")
    if source.get("formal_population_opened") is not False:
        failures.append("formal population must remain unopened")

    claims = config.get("claim_boundary", {})
    for name in (
        "independent_confirmation",
        "causal_training_stage_attribution",
        "v4_rerun",
        "local_qwen3_1_7b_path_reopened",
        "base_serving_preflight_passed",
        "common_serialization_full_population_proved",
        "scientific_comparison_authorized",
    ):
        if claims.get(name) is not False:
            failures.append(f"claim_boundary.{name} must remain false")

    serialization = config.get("serialization_proof", {})
    if serialization.get("served_snapshot_reproof_location") != (
        "LOCAL_AFTER_HASH_VERIFIED_RETURN_TRANSFER"
    ):
        failures.append("served-snapshot proof must be local after verified return transfer")
    if (
        serialization.get(
            "selected_project_prompt_content_or_derivatives_sent_to_preflight"
        )
        is not False
    ):
        failures.append("project prompt content or derivatives may not enter preflight")

    remote = config.get("synthetic_preflight_remote_payload", {})
    for name in (
        "project_scenario_files_allowed",
        "selected_prompt_text_allowed",
        "scientific_request_bodies_allowed",
        "project_prompt_derived_artifacts_allowed",
        "selected_prompt_token_id_sequences_allowed",
        "rendered_prompt_caches_allowed",
        "prompt_embeddings_allowed",
        "reversible_prompt_encodings_allowed",
    ):
        if remote.get(name) is not False:
            failures.append(f"synthetic_preflight_remote_payload.{name} must be false")
    if remote.get("allowlist_required") is not True:
        failures.append("remote allowlist must be required")
    if remote.get("undeclared_file_policy") != "FAIL_CLOSED":
        failures.append("undeclared remote files must fail closed")
    if set(remote.get("allowed_content_classes", ())) != ALLOWED_REMOTE_CONTENT_CLASSES:
        failures.append("remote content classes differ from the frozen two-class allowlist")

    selection = config.get("selection", {})
    if selection.get("status") != "NOT_BUILT":
        failures.append("selection status must remain NOT_BUILT during local Stage 2")
    if selection.get("population_derivation_status") != "NOT_STARTED":
        failures.append("population derivation must remain NOT_STARTED")
    if selection.get("scenario_families") != (
        selection.get("discretionary_flip_families", 0)
        + selection.get("hard_policy_invariant_families", 0)
    ):
        failures.append("selection family counts do not add up")
    if selection.get("requests_per_checkpoint") != (
        selection.get("scenario_families", 0)
        * selection.get("presentations_per_family", 0)
        * len(selection.get("serialization_modes", ()))
    ):
        failures.append("requests_per_checkpoint does not match the population factors")
    if selection.get("target_profile_pairs") != ["|".join(pair) for pair in TARGET_PROFILE_PAIRS]:
        failures.append("selection target profile pairs differ from the frozen code order")
    if selection.get("scenario_ranking_rule") != (
        "minimum_sha256(seed_tab_environment_tab_stratum_tab_scenario_id)"
    ):
        failures.append("scenario ranking rule is not frozen")
    if selection.get("profile_pair_selection_rule") != (
        "minimum_sha256(seed_tab_profile_pair_tab_scenario_id_tab_left_tab_right)"
        "_among_eligible_pairs"
    ):
        failures.append("profile-pair selection rule is not frozen")
    if selection.get("structured_scenario_surface_variant") != "NONE":
        failures.append("structured scenario surface variant must be NONE")
    if selection.get("natural_language_scenario_surface_variant") != 0:
        failures.append("natural-language selection must use scenario surface variant zero")
    if selection.get("profile_surface_variants") != [0, 1]:
        failures.append("profile surface variants must be canonical zero and sham one")

    runtime = config.get("runtime", {})
    smoke = config.get("throughput_smoke", {})
    if smoke.get("status") != "NOT_BUILT":
        failures.append("throughput smoke must remain NOT_BUILT during local Stage 2")
    input_targets = smoke.get("input_token_targets")
    generated_cap = runtime.get("maximum_generated_tokens")
    model_length = runtime.get("maximum_model_length")
    if (
        not isinstance(input_targets, list)
        or not input_targets
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value <= 0
            for value in input_targets
        )
    ):
        failures.append("throughput input-token targets must be a nonempty positive-integer list")
    elif (
        not isinstance(generated_cap, int)
        or isinstance(generated_cap, bool)
        or generated_cap <= 0
        or not isinstance(model_length, int)
        or isinstance(model_length, bool)
        or model_length <= 0
    ):
        failures.append("runtime generation and model-length caps must be positive integers")
    elif max(input_targets) + generated_cap > model_length:
        failures.append("largest prompt plus generation cap exceeds model length")
    if smoke.get("concurrency_candidates") != runtime.get("throughput_concurrency_candidates"):
        failures.append("runtime and smoke concurrency grids differ")
    if smoke.get("stability_requests_per_candidate_per_condition") != 8:
        failures.append("stability request count must be eight per candidate-condition")
    if smoke.get("stability_minimum_generated_tokens_per_cell") != 8192:
        failures.append("stability cells must require at least 8192 generated tokens")
    for name in (
        "stability_requires_all_final_http_2xx_after_retry",
        "stability_requires_all_synthetic_schema_valid",
        "stability_requires_no_context_truncation",
        "warmup_excluded_from_throughput_statistics",
        "whole_rental_wall_clock_cap_required_at_lock_a",
    ):
        if smoke.get(name) is not True:
            failures.append(f"throughput_smoke.{name} must be true")
    if smoke.get("latency_is_stability_pass_predicate") is not False:
        failures.append("latency must remain diagnostic rather than a stability pass predicate")
    if smoke.get("measurement_cap_scope") != "post_warmup_decode_measurement_windows_only":
        failures.append("measurement-cap scope is not frozen")
    if smoke.get("cap_exhaustion_before_evidence_policy") != "INSUFFICIENT_FOR_LOCK_B":
        failures.append("cap exhaustion must be insufficient for Lock B")

    lock_a = config.get("locks", {}).get("synthetic_preflight", {})
    lock_b = config.get("locks", {}).get("scientific_execution", {})
    if lock_a.get("status") != "NOT_BUILT" or lock_b.get("status") != "NOT_BUILT":
        failures.append("both Phase-5 locks must remain NOT_BUILT")
    if lock_a.get("scientific_runner_status") != "CANDIDATE_ONLY":
        failures.append("science runner must remain CANDIDATE_ONLY before Lock B")
    return failures


def _digest(seed: int, *parts: object) -> str:
    preimage = "\t".join((str(seed), *(str(part) for part in parts)))
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def _target(record: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(record["target_text"]))
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("record has invalid target_text") from error
    if not isinstance(value, dict):
        raise ValueError("record target_text must decode to an object")
    return value


def _structured_model_input(record: Mapping[str, Any]) -> dict[str, Any]:
    marker = "Pre-transition source (canonical JSON):\n"
    text = str(record.get("input_text", ""))
    if not text.startswith(marker):
        raise ValueError("canonical structured record lacks the source marker")
    try:
        value, _ = json.JSONDecoder().raw_decode(text[len(marker) :])
    except json.JSONDecodeError as error:
        raise ValueError("canonical structured source JSON is invalid") from error
    if not isinstance(value, dict):
        raise ValueError("structured model input must decode to an object")
    return value


def _record_key(record: Mapping[str, Any]) -> tuple[str, str, int, int | None]:
    condition = str(record.get("input_condition"))
    profile = str(record.get("profile_id"))
    profile_variant = int(record.get("profile_surface_variant", -1))
    scenario_variant_raw = record.get("scenario_surface_variant")
    scenario_variant = None if scenario_variant_raw is None else int(scenario_variant_raw)
    return condition, profile, profile_variant, scenario_variant


@dataclass(frozen=True)
class SelectedPhase5Family:
    scenario_id: str
    environment: str
    stratum: str
    profile_pair: tuple[str, str]
    presentation_record_ids: tuple[str, ...]


def _inspect_family(
    records: list[dict[str, Any]],
    *,
    seed: int,
) -> tuple[str, tuple[str, str], tuple[str, ...]] | None:
    scenario_ids = {str(record.get("scenario_id")) for record in records}
    environments = {str(record.get("environment")) for record in records}
    if len(scenario_ids) != 1 or len(environments) != 1:
        raise ValueError("family mixes scenario IDs or environments")
    by_key: dict[tuple[str, str, int, int | None], dict[str, Any]] = {}
    for record in records:
        key = _record_key(record)
        if key in by_key:
            raise ValueError(f"family contains duplicate presentation key: {key}")
        by_key[key] = record

    canonical = {}
    for profile in PROFILE_IDS:
        key = ("structured", profile, 0, None)
        if key not in by_key:
            raise ValueError(f"family lacks canonical structured profile: {profile}")
        canonical[profile] = by_key[key]
    targets = {profile: _target(record) for profile, record in canonical.items()}
    model_inputs = {
        profile: _structured_model_input(record)
        for profile, record in canonical.items()
    }
    canonical_model_inputs = {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in model_inputs.values()
    }
    if len(canonical_model_inputs) != 1:
        raise ValueError("evaluator profiles do not share one pre-transition model input")
    factual_digests = {
        hashlib.sha256(
            json.dumps(
                {
                    "physical_delta": target.get("physical_delta"),
                    "event_record": target.get("event_record"),
                    "rollout": target.get("rollout"),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for target in targets.values()
    }
    if len(factual_digests) != 1:
        raise ValueError("evaluator profiles do not share one factual target")

    first_profile = PROFILE_IDS[0]
    event_record = targets[first_profile].get("event_record")
    if not isinstance(event_record, dict):
        raise ValueError("target event_record is missing")
    model_input = model_inputs[first_profile]
    policy_result = recompute_factorized_policy_result(model_input, event_record)
    hard_violations = policy_result.get("hard_violations", [])
    decisions = {
        profile: str(target.get("normative_decision"))
        for profile, target in targets.items()
    }
    scenario_id = next(iter(scenario_ids))
    flipping = [pair for pair in TARGET_PROFILE_PAIRS if decisions[pair[0]] != decisions[pair[1]]]
    if hard_violations:
        if set(decisions.values()) != {"reject"}:
            raise ValueError("hard-policy family is not reject-invariant across profiles")
        stratum = "hard_policy_invariant"
        eligible_pairs = list(TARGET_PROFILE_PAIRS)
    elif flipping:
        stratum = "discretionary_flip"
        eligible_pairs = flipping
    else:
        return None
    pair = min(
        eligible_pairs,
        key=lambda item: _digest(seed, "profile_pair", scenario_id, item[0], item[1]),
    )

    presentation_ids = []
    for condition in ("structured", "natural_language"):
        scenario_variant = None if condition == "structured" else 0
        for profile in pair:
            for profile_variant in (0, 1):
                key = (condition, profile, profile_variant, scenario_variant)
                try:
                    record = by_key[key]
                except KeyError as error:
                    raise ValueError(f"family lacks required presentation: {key}") from error
                if _target(record) != targets[profile]:
                    raise ValueError("surface variant changes the target")
                if (
                    condition == "structured"
                    and _structured_model_input(record) != model_inputs[profile]
                ):
                    raise ValueError("structured surface variant changes the model input")
                presentation_ids.append(str(record["record_id"]))
    if len(presentation_ids) != 8 or len(set(presentation_ids)) != 8:
        raise ValueError("selected family does not contain eight unique presentations")
    return stratum, pair, tuple(presentation_ids)


def select_phase5_fixture_population(
    records: Iterable[dict[str, Any]],
    *,
    excluded_scenario_ids: Iterable[str],
    seed: int,
    discretionary_per_environment: int = 36,
    hard_policy_per_environment: int = 12,
) -> list[SelectedPhase5Family]:
    """Select a balanced population from synthetic fixtures only.

    The future real-source entry point must be a separate function that checks a
    committed population-selection authorization before it opens any export.
    """

    excluded = set(excluded_scenario_ids)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("split") == "development" and str(record.get("scenario_id")) not in excluded:
            grouped[str(record["scenario_id"])].append(record)
    buckets: dict[tuple[str, str], list[SelectedPhase5Family]] = defaultdict(list)
    for scenario_id, family_records in grouped.items():
        inspected = _inspect_family(family_records, seed=seed)
        if inspected is None:
            continue
        stratum, pair, presentations = inspected
        environment = str(family_records[0]["environment"])
        if environment not in ("game", "organization"):
            raise ValueError(f"unsupported environment: {environment}")
        buckets[(environment, stratum)].append(
            SelectedPhase5Family(
                scenario_id=scenario_id,
                environment=environment,
                stratum=stratum,
                profile_pair=pair,
                presentation_record_ids=presentations,
            )
        )

    required = {
        (environment, stratum): count
        for environment in ("game", "organization")
        for stratum, count in (
            ("discretionary_flip", discretionary_per_environment),
            ("hard_policy_invariant", hard_policy_per_environment),
        )
    }
    selected = []
    for bucket_name in sorted(required):
        bucket = sorted(
            buckets.get(bucket_name, ()),
            key=lambda item: _digest(seed, *bucket_name, item.scenario_id),
        )
        count = required[bucket_name]
        if len(bucket) < count:
            raise ValueError(
                f"insufficient eligible families in {bucket_name}: {len(bucket)} < {count}"
            )
        selected.extend(bucket[:count])
    if len({item.scenario_id for item in selected}) != len(selected):
        raise ValueError("selection reused a scenario family")
    presentation_ids = [
        record_id
        for item in selected
        for record_id in item.presentation_record_ids
    ]
    if len(set(presentation_ids)) != len(presentation_ids):
        raise ValueError("selection reused a presentation record ID")
    return selected


def phase5_selection_binding(selection: Iterable[SelectedPhase5Family]) -> dict[str, Any]:
    rows = [asdict(item) for item in selection]
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "family_count": len(rows),
        "presentation_count": sum(len(row["presentation_record_ids"]) for row in rows),
        "unique_scenario_count": len({row["scenario_id"] for row in rows}),
        "ordered_selection_sha256": hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest(),
    }


def _normalized_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != value
    ):
        raise ValueError(f"payload path is not a normalized relative path: {value!r}")
    return path


def verify_remote_payload(
    root: Path,
    declared_files: Mapping[str, str],
) -> dict[str, Any]:
    """Verify an exact, symlink-free synthetic payload and return its manifest."""

    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("payload root must be a directory")
    if not declared_files:
        raise ValueError("payload declaration must contain at least one file")
    declared: dict[str, str] = {}
    for raw_path, content_class in declared_files.items():
        relative = _normalized_relative_path(raw_path).as_posix()
        if relative in declared:
            raise ValueError(f"duplicate normalized payload path: {relative}")
        if content_class not in ALLOWED_REMOTE_CONTENT_CLASSES:
            raise ValueError(f"forbidden payload content class: {content_class}")
        declared[relative] = content_class

    actual_files: set[str] = set()
    symlinks: list[str] = []
    empty_directories: list[str] = []
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        if base != root and not directory_names and not file_names:
            empty_directories.append(base.relative_to(root).as_posix())
        for name in list(directory_names):
            item = base / name
            if item.is_symlink():
                symlinks.append(item.relative_to(root).as_posix())
        for name in file_names:
            item = base / name
            relative = item.relative_to(root).as_posix()
            if item.is_symlink():
                symlinks.append(relative)
            else:
                actual_files.add(relative)
    if symlinks:
        raise ValueError(f"payload contains symlinks: {sorted(symlinks)}")
    if empty_directories:
        raise ValueError(f"payload contains undeclared empty directories: {empty_directories}")
    if actual_files != set(declared):
        undeclared = sorted(actual_files - set(declared))
        missing = sorted(set(declared) - actual_files)
        raise ValueError(f"payload exact-set mismatch: undeclared={undeclared}, missing={missing}")

    entries = []
    for relative in sorted(declared):
        path = root / PurePosixPath(relative)
        resolved = path.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"payload file escapes root: {relative}") from error
        stat = resolved.stat()
        if stat.st_nlink != 1:
            raise ValueError(f"payload file must have exactly one hard link: {relative}")
        data = resolved.read_bytes()
        entries.append(
            {
                "path": relative,
                "content_class": declared[relative],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return {
        "status": "PASS",
        "file_count": len(entries),
        "files": entries,
        "manifest_sha256": hashlib.sha256((canonical + "\n").encode("utf-8")).hexdigest(),
    }
