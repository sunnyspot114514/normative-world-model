"""Deterministic paired-family generator for the Phase-1 discovery corpus."""

from __future__ import annotations

import copy
import hashlib
import json
import random
import secrets
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .audits import (
    audit_density,
    audit_natural_language,
    audit_nontriviality,
    audit_model_input_integrity,
    audit_split_integrity,
    audit_state_machine_integrity,
    audit_surface_leakage_by_environment,
)
from .calibration import run_calibration_cases
from .environments.game import (
    ACTION_FAMILIES as GAME_ACTIONS,
    TACTICS as GAME_TACTICS,
    generate_game_source,
    noncausal_game_surface,
    render_game,
    simulate_game,
)
from .environments.organization import (
    ACTION_FAMILIES as ORGANIZATION_ACTIONS,
    TACTICS as ORGANIZATION_TACTICS,
    generate_organization_source,
    noncausal_organization_surface,
    render_organization,
    simulate_organization,
)
from .normative_oracle import load_profiles
from .normative_oracle import NORMATIVE_ORACLE_VERSION
from .reachability import enumerate_reachability, render_reachability_markdown

SCHEMA_VERSION = "0.4"
GENERATOR_REVISION = 2
ARCHETYPE_CYCLE = (
    "safety_efficiency",
    "safety_efficiency_weighted",
    "privacy_autonomy",
    "privacy_autonomy_weighted_reject_band",
    "commitment_safety",
    "commitment_safety_weighted",
    "uncertainty",
    "efficiency_negative_privacy",
    "safety_efficiency_weighted",
    "privacy_autonomy_weighted_reject_allow",
    "commitment_safety_weighted",
    "safety_efficiency",
    "privacy_autonomy",
    "commitment_safety",
    "uncertainty",
    "mixed",
    "safety_efficiency_weighted",
    "privacy_autonomy_weighted",
    "commitment_safety_weighted",
    "efficiency_negative_autonomy",
    "safety_efficiency",
    "privacy_autonomy",
    "commitment_safety",
    "negative",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reverse_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _reverse_mapping(value[key]) for key in reversed(value)}
    if isinstance(value, list):
        return [_reverse_mapping(item) for item in value]
    return value


def _words_int(value: int) -> str:
    ones = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
    tens = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
    if value < 20:
        return ones[value]
    if value < 100:
        return tens[value // 10] + (f"-{ones[value % 10]}" if value % 10 else "")
    if value == 100:
        return "one hundred"
    raise ValueError("spoken decimal helper supports hundredths only")


def _spoken_hundredths(value: float) -> str:
    scaled = int(round(abs(value) * 100))
    prefix = "negative " if value < 0 else ""
    return f"{prefix}{_words_int(scaled)} hundredths"


def _scenario_id(environment: str, seed: int, index: int) -> str:
    digest = hashlib.sha256(f"{environment}:{seed}:{index}".encode()).hexdigest()[:16]
    return f"{environment}-{digest}"


def _model_input(source: dict[str, Any]) -> dict[str, Any]:
    """Return the exact bytes-visible model input, excluding oracle bookkeeping IDs."""

    value = copy.deepcopy(source)
    value["state"].pop("turn", None)
    value["state"].pop("ticket", None)
    return value


def _composition_signature(source: dict[str, Any]) -> str:
    state = source["state"]
    stakeholder_count = int(state["stakeholder_count"])
    bucket = "one" if stakeholder_count == 1 else "few" if stakeholder_count <= 3 else "many"
    return f"{source['action']['family']}|{bucket}|{bool(state['obligation_active'])}"


def _split_for(scenario_id: str, composition_signature: str) -> tuple[str, bool]:
    composition_holdout = (
        int(hashlib.sha256(composition_signature.encode()).hexdigest()[:8], 16) % 11
        == 0
    )
    if composition_holdout:
        return "development", True
    value = int(hashlib.sha256(scenario_id.encode()).hexdigest()[:8], 16) % 5
    return ("development" if value == 0 else "train"), False


def _find_changed_twin(
    source: dict[str, Any],
    simulate: Callable[[dict[str, Any], dict[str, Any]], Any],
    profiles: dict[str, Any],
    primary_delta: dict[str, Any],
    group: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Find a one-field causal intervention that changes the physical transition."""

    excluded = {
        "turn", "ticket", "role", "actor", "surface_context", "authorized_actions",
        "approval_present", "consent_present", "observed_evidence_count",
        "conflicting_evidence", "stakeholder_count", "third_party_present",
        "external_party_affected", "obligation_active", "persistent_flags", "durable_objects",
    }
    candidates = source["state"][group] if group == "actor_values" else source["state"]
    for key in sorted(candidates):
        if key in excluded or not isinstance(candidates[key], int) or isinstance(candidates[key], bool):
            continue
        for replacement in (0, 4, 2):
            if replacement == candidates[key]:
                continue
            twin = copy.deepcopy(source)
            destination = twin["state"][group] if group == "actor_values" else twin["state"]
            destination[key] = replacement
            result = simulate(twin, profiles)
            if result.physical_delta != primary_delta:
                return twin, result.to_dict()
    if group == "actor_values":
        twin = copy.deepcopy(source)
        key = sorted(twin["state"][group])[0]
        current = int(twin["state"][group][key])
        twin["state"][group][key] = 0 if current != 0 else 4
        return twin, simulate(twin, profiles).to_dict()
    raise AssertionError(f"no causal {group} intervention changed the transition")


def _mutate_policy_source(source: dict[str, Any]) -> dict[str, Any]:
    twin = copy.deepcopy(source)
    observed = int(twin["state"]["observed_evidence_count"])
    required = int(twin["policy"]["required_evidence_count"])
    current = int(twin["policy"]["policy_minimum_evidence_count"])
    if observed < required:
        twin["policy"]["policy_minimum_evidence_count"] = (
            min(required, observed + 1) if current <= observed else max(0, observed)
        )
    else:
        twin["policy"]["approval_required"] = not bool(
            twin["policy"]["approval_required"]
        )
    return twin


def _surface_twins(
    source: dict[str, Any],
    render: Callable[[dict[str, Any], int], str],
    noncausal: Callable[[dict[str, Any], int], str],
) -> list[dict[str, Any]]:
    return [
        {
            "surface_id": f"surface-{index}",
            "natural_language": render(source, index),
            "noncausal_surface_text": noncausal(source, index),
        }
        for index in range(2)
    ]


def _build_rollout(
    source: dict[str, Any],
    simulate: Callable[[dict[str, Any], dict[str, Any]], Any],
    profiles: dict[str, Any],
    actions: tuple[str, ...],
    tactics: tuple[str, ...],
) -> list[dict[str, Any]]:
    current = copy.deepcopy(source)
    rows: list[dict[str, Any]] = []
    for horizon in range(1, 4):
        result = simulate(current, profiles)
        rows.append({
            "horizon": horizon,
            "pre_state": copy.deepcopy(current["state"]),
            "action": copy.deepcopy(current["action"]),
            "next_state": result.next_state,
            "physical_delta": result.physical_delta,
            "event_record": result.event_record.to_dict(),
        })
        next_source = copy.deepcopy(current)
        next_source["state"] = copy.deepcopy(result.next_state)
        next_source["action"]["family"] = actions[(actions.index(current["action"]["family"]) + 1) % len(actions)]
        next_source["action"]["tactic"] = tactics[(tactics.index(current["action"]["tactic"]) + 3) % len(tactics)]
        next_source["action"]["persistent"] = next_source["action"]["family"] in {"disclose", "promise", "send_external_message", "deploy_or_delete"}
        current = next_source
    return rows


def _evaluator_twins(profiles: dict[str, Any], evaluations: dict[str, Any]) -> dict[str, Any]:
    twins = {}
    for profile_id, profile in profiles.items():
        payload = asdict(profile)
        weights = ", ".join(
            f"{key} carries {_spoken_hundredths(value)}" for key, value in profile.weights.items()
        )
        vetoes = ", ".join(
            f"{key} has a floor of {_spoken_hundredths(value)}" for key, value in profile.veto_floor.items()
        )
        spoken_id = profile_id.replace("_", " ")
        thresholds = (
            f"The uncertainty threshold is {_spoken_hundredths(profile.uncertainty_escalate_at)}, "
            f"the irreversibility cutoff is {_spoken_hundredths(profile.irreversibility_cutoff)}, "
            f"the irreversible-harm threshold is {_spoken_hundredths(profile.irreversible_harm_veto)}, "
            f"the lower decision band is {_spoken_hundredths(profile.reject_at_or_below)}, "
            f"and the upper decision band is {_spoken_hundredths(profile.allow_at_or_above)}."
        )
        twins[profile_id] = {
            "profile_input": payload,
            "natural_language_profile_shams": [
                (
                    f"The {spoken_id} evaluator uses these dimension weights: {weights}. "
                    f"Its dimension vetoes are: {vetoes}. {thresholds}"
                ),
                (
                    f"For the {spoken_id} evaluator, {thresholds} The weighting contract says {weights}. "
                    f"The dimension-specific floors say {vetoes}."
                ),
            ],
            "structured_profile_shams": [
                _canonical_json(payload),
                json.dumps(_reverse_mapping(payload), ensure_ascii=False, indent=2),
            ],
            "target": evaluations[profile_id],
        }
    return twins


def generate_environment_families(
    environment: str,
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    profiles = load_profiles()
    if environment == "game":
        source_factory = generate_game_source
        simulate = simulate_game
        render = render_game
        noncausal = noncausal_game_surface
        actions, tactics = GAME_ACTIONS, GAME_TACTICS
    elif environment == "organization":
        source_factory = generate_organization_source
        simulate = simulate_organization
        render = render_organization
        noncausal = noncausal_organization_surface
        actions, tactics = ORGANIZATION_ACTIONS, ORGANIZATION_TACTICS
    else:
        raise ValueError(f"unknown environment: {environment}")

    rng = random.Random(seed)
    families: list[dict[str, Any]] = []
    for index in range(count):
        archetype = ARCHETYPE_CYCLE[index % len(ARCHETYPE_CYCLE)]
        source = source_factory(rng, index, archetype)
        primary = simulate(source, profiles)
        factual_source, factual_dict = _find_changed_twin(
            source, simulate, profiles, primary.physical_delta, "state"
        )
        factual_result = simulate(factual_source, profiles)
        actor_source, actor_dict = _find_changed_twin(
            source, simulate, profiles, primary.physical_delta, "actor_values"
        )
        policy_source = _mutate_policy_source(source)
        policy_result = simulate(policy_source, profiles)
        if primary.physical_delta == factual_result.physical_delta:
            raise AssertionError("factual twin failed to change the physical transition")
        if primary.physical_delta != policy_result.physical_delta:
            raise AssertionError("policy twin changed the physical transition")

        scenario_id = _scenario_id(environment, seed, index)
        composition_signature = _composition_signature(source)
        split, composition_holdout = _split_for(scenario_id, composition_signature)
        families.append(
            {
                "schema_version": SCHEMA_VERSION,
                "generator_revision": GENERATOR_REVISION,
                "scenario_id": scenario_id,
                "environment": environment,
                "split": split,
                "archetype": archetype,
                "composition_signature": composition_signature,
                "composition_holdout": composition_holdout,
                "source": source,
                "model_input": _model_input(source),
                "model_input_sha256": hashlib.sha256(
                    _canonical_json(_model_input(source)).encode()
                ).hexdigest(),
                "primary": primary.to_dict(),
                "evaluator_twins": _evaluator_twins(profiles, primary.evaluations),
                "factual_twin": {
                    "source": factual_source,
                    "model_input": _model_input(factual_source),
                    "result": factual_dict,
                },
                "actor_value_twin": {
                    "source": actor_source,
                    "model_input": _model_input(actor_source),
                    "result": actor_dict,
                },
                "policy_twin": {
                    "source": policy_source,
                    "model_input": _model_input(policy_source),
                    "result": policy_result.to_dict(),
                },
                "surface_twins": _surface_twins(source, render, noncausal),
                "rollout": _build_rollout(source, simulate, profiles, actions, tactics),
                "temporary_fixture_fields": [],
            }
        )
    random.Random(seed ^ 0x5A17C0DE).shuffle(families)
    return families


def _digest_families(families: list[dict[str, Any]]) -> str:
    payload = "\n".join(_canonical_json(family) for family in families) + "\n"
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(_canonical_json(row) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_density_gates() -> dict[str, Any]:
    path = project_root() / "configs" / "normative_predicates.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)["density_gates"]


def _phase1_input_paths(root: Path) -> list[Path]:
    config_paths = [
        root / "configs" / "normative_predicates.toml",
        root / "configs" / "evaluator_profiles.toml",
        root / "configs" / "calibration_cases.json",
        root / "configs" / "preregistration.toml",
    ]
    contract_paths = [
        root / "PREREGISTRATION.md",
        root / "docs" / "NORMATIVE_PREDICATE_CONTRACT.md",
        root / "docs" / "EVALUATOR_PROFILES.md",
        root / "docs" / "LEAKAGE_AUDIT_SPEC.md",
        root / "docs" / "METRIC_COMPARATOR_V2_1.md",
        root / "docs" / "EXTERNAL_SMOKE_ACCEPTANCE.md",
        root / "docs" / "EXTERNAL_AUDIT_ADJUDICATION.md",
        root / "scripts" / "build-smoke-audit-bundle.py",
        root / "scripts" / "check-phase1-smoke.ps1",
    ]
    source_paths = sorted(
        (root / "src" / "normative_world_model").rglob("*.py"),
        key=lambda path: str(path.relative_to(root)).replace("\\", "/"),
    )
    return [*config_paths, *contract_paths, *source_paths]


def external_smoke_acceptance_failures(root: Path | None = None) -> list[str]:
    """Require explicit external acceptance of the exact smoke manifest before retention."""

    root = root or project_root()
    artifact_dir = root / "artifacts" / "phase1_revision2_smoke"
    acceptance_path = artifact_dir / "EXTERNAL_AUDIT_ACCEPTED.json"
    manifest_path = artifact_dir / "provenance_manifest.json"
    report_path = artifact_dir / "phase1_exit_report.json"
    if not acceptance_path.exists():
        return ["external revision-2 smoke acceptance record is missing"]
    if not manifest_path.exists() or not report_path.exists():
        return ["revision-2 smoke manifest or report is missing"]
    try:
        acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError) as error:
        return [f"invalid external smoke acceptance record: {error}"]
    failures = []
    if acceptance.get("status") != "ACCEPTED":
        failures.append("external smoke status is not ACCEPTED")
    if acceptance.get("unconditional") is not True:
        failures.append("external smoke acceptance is not explicitly unconditional")
    if acceptance.get("conditions", []) != []:
        failures.append("external smoke acceptance still contains unresolved conditions")
    actual_manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if acceptance.get("smoke_provenance_manifest_sha256") != actual_manifest_hash:
        failures.append("external acceptance does not bind the current smoke manifest")
    accepted_files = acceptance.get("smoke_corpus_sha256", {})
    expected_files = {
        key.replace("\\", "/"): value
        for key, value in manifest.get("files", {}).items()
        if key.endswith("game.jsonl") or key.endswith("organization.jsonl")
    }
    if accepted_files != expected_files:
        failures.append("external acceptance does not bind both smoke corpus hashes")
    if report.get("status") != "PASS" or report.get("run_kind") != "revision2_smoke":
        failures.append("bound smoke report is not a revision-2 PASS")
    if not acceptance.get("auditor") or not acceptance.get("accepted_at"):
        failures.append("external acceptance lacks auditor or accepted_at provenance")
    return failures


def run_phase1(
    families_per_environment: int = 1000,
    seed: int = 20260715,
    *,
    run_kind: str = "retained",
) -> dict[str, Any]:
    root = project_root()
    if run_kind == "retained":
        acceptance_failures = external_smoke_acceptance_failures(root)
        if acceptance_failures:
            raise RuntimeError(
                "retained generation is blocked: " + "; ".join(acceptance_failures)
            )
        data_dir = root / "data" / "generated" / "phase1_discovery_v2"
        artifact_dir = root / "artifacts" / "phase1_v2"
    elif run_kind == "revision2_smoke":
        data_dir = root / "data" / "generated" / "phase1_revision2_smoke"
        artifact_dir = root / "artifacts" / "phase1_revision2_smoke"
    else:
        raise ValueError(f"unknown Phase-1 run kind: {run_kind}")
    gates = _load_density_gates()
    all_families: list[dict[str, Any]] = []
    environment_reports: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}

    for offset, environment in enumerate(("game", "organization")):
        environment_seed = seed + offset * 100_003
        families = generate_environment_families(
            environment, families_per_environment, environment_seed
        )
        replay = generate_environment_families(
            environment, families_per_environment, environment_seed
        )
        replay_match = _digest_families(families) == _digest_families(replay)
        path = data_dir / f"{environment}.jsonl"
        file_hashes[str(path.relative_to(root))] = _write_jsonl(path, families)
        density = audit_density(families, gates)
        split = audit_split_integrity(families)
        state_machine = audit_state_machine_integrity(families)
        language = audit_natural_language(families)
        nontriviality = audit_nontriviality(families)
        model_input_integrity = audit_model_input_integrity(families)
        environment_reports[environment] = {
            "seed": environment_seed,
            "replay_digest_matches": replay_match,
            "density": density,
            "split_integrity": split,
            "state_machine_integrity": state_machine,
            "natural_language": language,
            "nontriviality": nontriviality,
            "model_input_integrity": model_input_integrity,
        }
        all_families.extend(families)

    leakage = audit_surface_leakage_by_environment(all_families, seed + 700_001)
    calibration = run_calibration_cases()
    reachability_rows = enumerate_reachability(5)
    reachability_path = artifact_dir / "uncertainty_reachability.md"
    reachability_path.parent.mkdir(parents=True, exist_ok=True)
    reachability_path.write_text(
        render_reachability_markdown(reachability_rows), encoding="utf-8"
    )
    file_hashes[str(reachability_path.relative_to(root))] = hashlib.sha256(
        reachability_path.read_bytes()
    ).hexdigest()

    secret_path = root / ".tmp" / "confirmation_v2_secret.json"
    if secret_path.exists():
        secret = json.loads(secret_path.read_text(encoding="utf-8"))["nonce"]
    else:
        secret = secrets.token_hex(32)
        _write_json(secret_path, {"nonce": secret})
    input_paths = _phase1_input_paths(root)
    input_entries = [
        {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(input_paths, key=lambda item: str(item.relative_to(root)).replace("\\", "/"))
    ]
    input_preimage = "".join(
        f"{entry['path']}\t{entry['sha256']}\n" for entry in input_entries
    ).encode()
    input_commitment = hashlib.sha256(input_preimage).hexdigest()
    with (root / "configs" / "preregistration.toml").open("rb") as handle:
        confirmation_seed = int(tomllib.load(handle)["seeds"]["confirmation"])
    confirmation_reservation = {
        "status": "RESERVED_NOT_GENERATED",
        "families_per_environment_input_cell": 250,
        "unique_scenario_families_per_environment": 250,
        "presentation_design": "paired_same_family_across_structured_and_natural_language",
        "total_unique_scenario_families": 500,
        "total_presentations": 1000,
        "effective_statistical_unit": "scenario_family",
        "environments": ["game", "organization"],
        "input_conditions": ["structured", "natural_language"],
        "seed_commitment": hashlib.sha256(
            f"confirmation-v2:{confirmation_seed}:{input_commitment}:{secret}".encode()
        ).hexdigest(),
        "commitment_inputs_sha256": input_commitment,
        "commitment_input_manifest": input_entries,
        "commitment_input_manifest_preimage": "UTF-8 lines sorted by path: <path>\\t<sha256>\\n",
        "commitment_scheme": "sha256('confirmation-v2:' + confirmation_seed + ':' + commitment_inputs_sha256 + ':' + secret_256_bit_nonce)",
        "note": "No confirmation scenarios or targets were generated in Phase 1 discovery.",
    }
    confirmation_path = data_dir / "confirmation_reservation.json"
    _write_json(confirmation_path, confirmation_reservation)
    file_hashes[str(confirmation_path.relative_to(root))] = hashlib.sha256(
        confirmation_path.read_bytes()
    ).hexdigest()

    status_failures = []
    for environment, report in environment_reports.items():
        if not report["replay_digest_matches"]:
            status_failures.append(f"{environment}: deterministic replay")
        if report["density"]["status"] != "PASS":
            status_failures.extend(
                f"{environment}: {failure}" for failure in report["density"]["failures"]
            )
        if report["split_integrity"]["status"] != "PASS":
            status_failures.extend(
                f"{environment}: {failure}"
                for failure in report["split_integrity"]["failures"]
            )
        for audit_name in (
            "state_machine_integrity", "natural_language", "nontriviality",
            "model_input_integrity",
        ):
            if report[audit_name]["status"] != "PASS":
                status_failures.extend(
                    f"{environment}: {failure}" for failure in report[audit_name]["failures"]
                )
    if leakage["status"] != "PASS":
        status_failures.extend(f"leakage: {failure}" for failure in leakage["failures"])
    if calibration["status"] != "PASS":
        status_failures.extend(
            f"calibration: {failure}" for failure in calibration["failures"]
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": run_kind,
        "status": "PASS" if not status_failures else "FAIL",
        "generator_schema_revisions_used": GENERATOR_REVISION,
        "generator_schema_revision_limit": 2,
        "failures": status_failures,
        "families_per_environment": families_per_environment,
        "total_discovery_families": len(all_families),
        "temporary_fixture_family_count": sum(
            bool(family["temporary_fixture_fields"]) for family in all_families
        ),
        "environments": environment_reports,
        "surface_leakage": leakage,
        "calibration": calibration,
        "confirmation": confirmation_reservation,
        "file_hashes": file_hashes,
    }
    report_path = artifact_dir / "phase1_exit_report.json"
    _write_json(report_path, report)

    _write_dataset_card(artifact_dir / "DATASET_CARD.md", report)
    dataset_card_path = artifact_dir / "DATASET_CARD.md"
    manifest = {
        "generator_schema_version": SCHEMA_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": run_kind,
        "seed": seed,
        "family_count": len(all_families),
        "family_count_scope": "combined across environments",
        "families_per_environment": {
            environment: families_per_environment
            for environment in environment_reports
        },
        "files": {
            **file_hashes,
            str(report_path.relative_to(root)): hashlib.sha256(report_path.read_bytes()).hexdigest(),
            str(dataset_card_path.relative_to(root)): hashlib.sha256(
                dataset_card_path.read_bytes()
            ).hexdigest(),
        },
        "inputs": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
    }
    _write_json(artifact_dir / "provenance_manifest.json", manifest)
    return report


def _write_dataset_card(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Phase-1 discovery dataset card",
        "",
        f"Status: **{report['status']}**",
        "",
        f"The corpus contains {report['total_discovery_families']} deterministic scenario families, "
        "split between independent narrative-game and organizational-agent state machines.",
        "Every family contains evaluator, factual, policy, and surface twins. No confirmation "
        "scenario was generated.",
        "",
        "## Exit summary",
        "",
        "| Environment | Families | No-hard | Evaluator-divergent | Uncertainty-divergent | Replay |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for environment, environment_report in report["environments"].items():
        metrics = environment_report["density"]["metrics"]
        lines.append(
            f"| {environment} | {metrics['family_count']} | "
            f"{metrics['no_hard_violation_fraction']:.3f} | "
            f"{metrics['evaluator_divergent_fraction']:.3f} | "
            f"{metrics['uncertainty_divergent_family_fraction']:.3f} | "
            f"{environment_report['replay_digest_matches']} |"
        )
    lines.extend(
        [
            "",
            "## Per-environment Gate C",
            "",
            "| Environment | Max macro AUC | Cluster upper bound | Status |",
            "|---|---:|---:|:---:|",
        ]
    )
    for environment, leakage_report in report["surface_leakage"]["environments"].items():
        maximum_auc = max(
            view["macro_auc"] for view in leakage_report["grouped_tfidf"].values()
        )
        lines.append(
            f"| {environment} | {maximum_auc:.3f} | "
            f"{leakage_report['bootstrap_upper_bound']:.3f} | "
            f"{leakage_report['status']} |"
        )
    lines.extend(
        [
            "",
            "The impact vector is a synthetic institutional event-record coordinate, not physical "
            "or universal moral ground truth. Splits are by scenario family before surface rendering. "
            "Generated artifacts are local and excluded from Git by project policy.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def verify_phase1_artifacts() -> list[str]:
    root = project_root()
    artifact_dir = root / "artifacts" / "phase1_v2"
    manifest_path = artifact_dir / "provenance_manifest.json"
    report_path = artifact_dir / "phase1_exit_report.json"
    failures: list[str] = []
    if not manifest_path.exists() or not report_path.exists():
        return ["Phase-1 manifest or exit report is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for section in ("files", "inputs"):
        for relative, expected_hash in manifest[section].items():
            path = root / relative
            if not path.exists():
                failures.append(f"missing {section} path: {relative}")
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                failures.append(f"hash mismatch: {relative}")
    if report["status"] != "PASS":
        failures.append("Phase-1 exit report is not PASS")
    if report["total_discovery_families"] != 2000:
        failures.append("Phase-1 retained corpus does not contain 2,000 families")
    if report["temporary_fixture_family_count"] != 0:
        failures.append("Phase-1 retained corpus still contains temporary fixtures")
    if report["confirmation"]["status"] != "RESERVED_NOT_GENERATED":
        failures.append("confirmation population was unexpectedly generated")
    return failures
