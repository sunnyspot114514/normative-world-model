"""Preregistration-v3 smoke generation with renderer-only corrections."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import secrets
import tomllib
from pathlib import Path
from typing import Any

from .audits import (
    _profile_equivalence_markers,
    _scenario_equivalence_markers,
    _tokens,
    audit_density,
    audit_model_input_integrity,
    audit_nontriviality,
    audit_split_integrity,
    audit_state_machine_integrity,
    audit_surface_leakage_by_environment,
)
from .calibration import run_calibration_cases
from .generator import (
    _digest_families,
    _load_density_gates,
    _write_dataset_card,
    _write_json,
    _write_jsonl,
    generate_environment_families,
    project_root,
)
from .normative_oracle import NORMATIVE_ORACLE_VERSION
from .reachability import enumerate_reachability, render_reachability_markdown

PREREGISTRATION_VERSION = 3
GENERATOR_REVISION = 1
SCHEMA_VERSION = "0.4"
RUN_KIND = "v3_internal_smoke"

_GAME_ACTIONS = r"(?:disclose|intervene|promise|allocate resource)"
_ORGANIZATION_ACTIONS = (
    r"(?:read or write file|spend budget|send external message|deploy or delete)"
)
_MALFORMED_ACTION_PATTERNS = (
    re.compile(rf"\bplan to {_GAME_ACTIONS} for the\b", re.IGNORECASE),
    re.compile(
        rf"\bproposes the \w+ {_GAME_ACTIONS} concerning the\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bproposes to {_ORGANIZATION_ACTIONS} across the\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bsuggests the \w+ {_ORGANIZATION_ACTIONS} for the\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpermitted acts are\b", re.IGNORECASE),
    re.compile(
        r"\bthe role permits (?:read or write file|spend budget|"
        r"send external message|deploy or delete)\b",
        re.IGNORECASE,
    ),
)


def _repair_count_grammar(text: str, environment: str) -> str:
    if environment == "game":
        text = re.sub(r"\bone clues\b", "one clue", text)
        text = re.sub(r"\bone stakeholders\b", "one stakeholder", text)
    else:
        text = re.sub(r"\bone records\b", "one record", text)
        text = re.sub(
            r"\bExactly one stakeholders are\b",
            "Exactly one stakeholder is",
            text,
        )
    return text


def _repair_action_phrase_grammar(text: str, environment: str) -> str:
    if environment == "game":
        text = re.sub(
            rf"\bThey plan to (?P<action>{_GAME_ACTIONS}) for the "
            r"(?P<target>[^.;]+?) using the (?P<tactic>[a-z]+) approach at "
            r"(?P<intensity>low|moderate|high) intensity;",
            r'They plan the "\g<action>" action for the \g<target> using the '
            r"\g<tactic> approach at \g<intensity> intensity;",
            text,
        )
        text = re.sub(
            rf"\b(?P<actor>[A-Z][a-z]+) proposes the (?P<tactic>[a-z]+) "
            rf"(?P<action>{_GAME_ACTIONS}) concerning the "
            r"(?P<target>[^,.;]+), with "
            r"(?P<intensity>low|moderate|high) force;",
            r'\g<actor> proposes the "\g<action>" action concerning the '
            r"\g<target>, using the \g<tactic> approach with "
            r"\g<intensity> force;",
            text,
        )
        return text.replace(
            "and permitted acts are ",
            "and permitted action types are ",
        )

    text = re.sub(
        rf"\bThe (?P<role>[a-z]+) proposes to "
        rf"(?P<action>{_ORGANIZATION_ACTIONS}) across the "
        r"(?P<scope>[^.;]+?) using the (?P<tactic>[a-z]+) approach at "
        r"(?P<intensity>low|moderate|high) intensity;",
        r'The \g<role> proposes the "\g<action>" action for the '
        r"\g<scope>, using the \g<tactic> approach at "
        r"\g<intensity> intensity;",
        text,
    )
    text = re.sub(
        rf"\bThe (?P<role>[a-z]+) suggests the (?P<tactic>[a-z]+) "
        rf"(?P<action>{_ORGANIZATION_ACTIONS}) for the "
        r"(?P<scope>[^,.;]+), with "
        r"(?P<intensity>low|moderate|high) force;",
        r'The \g<role> suggests the "\g<action>" action for the '
        r"\g<scope>, using the \g<tactic> approach with "
        r"\g<intensity> force;",
        text,
    )
    return text.replace(
        "and the role permits ",
        "and the permitted action types are ",
    )


def repair_family_language_v3(family: dict[str, Any]) -> dict[str, Any]:
    """Apply the frozen v3 renderer-only grammar normalization."""

    value = copy.deepcopy(family)
    value["preregistration_version"] = PREREGISTRATION_VERSION
    value["generator_revision"] = GENERATOR_REVISION
    for surface in value["surface_twins"]:
        surface["natural_language"] = _repair_action_phrase_grammar(
            _repair_count_grammar(
                surface["natural_language"],
                value["environment"],
            ),
            value["environment"],
        )
    for evaluator in value["evaluator_twins"].values():
        evaluator["natural_language_profile_shams"] = [
            re.sub(
                r"(For the [^,]+ evaluator,\s+)The uncertainty threshold",
                r"\1the uncertainty threshold",
                sham,
            )
            for sham in evaluator["natural_language_profile_shams"]
        ]
    return value


def generate_v3_environment_families(
    environment: str,
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    return [
        repair_family_language_v3(family)
        for family in generate_environment_families(environment, count, seed)
    ]


def _singularize_marker(marker: str) -> str:
    marker = re.sub(r"\bone clues\b", "one clue", marker)
    marker = re.sub(r"\bone records\b", "one record", marker)
    marker = re.sub(r"\bone stakeholders\b", "one stakeholder", marker)
    return marker


def audit_natural_language_v3(
    families: list[dict[str, Any]],
) -> dict[str, Any]:
    """Audit real v3 strings, including the grammar classes missed in v2."""

    scenario_texts = [
        surface["natural_language"]
        for family in families
        for surface in family["surface_twins"]
    ]
    texts = [
        f"{surface['natural_language']} Evaluator contract: {profile_sham}"
        for family in families
        for surface in family["surface_twins"]
        for evaluator in family["evaluator_twins"].values()
        for profile_sham in evaluator["natural_language_profile_shams"]
    ]
    decimal_count = sum(
        len(re.findall(r"\b\d+\.\d+\b", text)) for text in texts
    )
    assignment_count = sum(
        len(re.findall(r"\b[a-z_]+\s*=", text, re.IGNORECASE))
        for text in texts
    )
    token_counts = [
        len(re.findall(r"[a-z]+", text.lower())) for text in texts
    ]
    vocabulary = (
        set().union(*(_tokens(text, "word") for text in texts))
        if texts
        else set()
    )
    noncausal = {
        surface["noncausal_surface_text"]
        for family in families
        for surface in family["surface_twins"]
    }

    missing_scenario_markers = 0
    missing_profile_markers = 0
    variable_article_errors = 0
    count_agreement_errors = 0
    subject_verb_agreement_errors = 0
    profile_sentence_case_errors = 0
    action_phrase_errors = 0
    for family in families:
        scenario_markers = [
            _singularize_marker(marker)
            for marker in _scenario_equivalence_markers(family)
        ]
        state = family["model_input"]["state"]
        action = family["model_input"]["action"]
        observed = int(state["observed_evidence_count"])
        stakeholders = int(state["stakeholder_count"])
        variable_terms = [action["tactic"]]
        if family["environment"] == "game":
            variable_terms.extend(
                [state["surface_context"]["witness"], state.get("actor", "")]
            )
            evidence_pattern = (
                r"\bone clue\b" if observed == 1 else r"\bone clues\b"
            )
        else:
            variable_terms.extend(
                [state["surface_context"]["observer"], state.get("role", "")]
            )
            evidence_pattern = (
                r"\bone record\b" if observed == 1 else r"\bone records\b"
            )

        for surface in family["surface_twins"]:
            lowered = surface["natural_language"].lower()
            missing_scenario_markers += sum(
                marker not in lowered for marker in scenario_markers
            )
            variable_article_errors += sum(
                bool(
                    re.search(
                        rf"\b(?:a|an)\s+{re.escape(str(term).lower())}\b",
                        lowered,
                    )
                )
                for term in variable_terms
                if term
            )
            if observed == 1 and not re.search(evidence_pattern, lowered):
                count_agreement_errors += 1
            if stakeholders == 1 and not re.search(
                r"\bone stakeholder\b",
                lowered,
            ):
                count_agreement_errors += 1
            if (
                family["environment"] == "organization"
                and stakeholders == 1
                and "exactly one stakeholder is in scope" not in lowered
            ):
                subject_verb_agreement_errors += 1
            action_phrase_errors += sum(
                bool(pattern.search(surface["natural_language"]))
                for pattern in _MALFORMED_ACTION_PATTERNS
            )

        for evaluator in family["evaluator_twins"].values():
            profile_markers = _profile_equivalence_markers(evaluator)
            for sham in evaluator["natural_language_profile_shams"]:
                lowered = sham.lower()
                missing_profile_markers += sum(
                    marker not in lowered for marker in profile_markers
                )
                profile_sentence_case_errors += bool(
                    re.search(r",\s+The\s+", sham)
                )

    # The typed ordinal mappings are unchanged from schema 0.4. Probe them
    # through the native audit and retain only the mapping/cardinality section.
    from .audits import audit_natural_language

    compatibility_rows = copy.deepcopy(families)
    for family in compatibility_rows:
        for surface in family["surface_twins"]:
            text = surface["natural_language"]
            state = family["model_input"]["state"]
            if int(state["observed_evidence_count"]) == 1:
                if family["environment"] == "game":
                    text = re.sub(r"\bone clue\b", "one clues", text)
                else:
                    text = re.sub(r"\bone record\b", "one records", text)
            if int(state["stakeholder_count"]) == 1:
                if family["environment"] == "organization":
                    text = re.sub(
                        r"\bExactly one stakeholder is\b",
                        "Exactly one stakeholders are",
                        text,
                    )
                else:
                    text = re.sub(
                        r"\bone stakeholder\b",
                        "one stakeholders",
                        text,
                    )
            surface["natural_language"] = text
    ordinal_metrics = audit_natural_language(compatibility_rows)["metrics"]

    metrics = {
        "decimal_literal_count": decimal_count,
        "key_value_assignment_count": assignment_count,
        "mean_word_count": sum(token_counts) / max(len(token_counts), 1),
        "minimum_word_count": min(token_counts, default=0),
        "vocabulary_size": len(vocabulary),
        "unique_noncausal_surface_count": len(noncausal),
        "scenario_render_count": len(scenario_texts),
        "composed_prompt_count": len(texts),
        "audited_prompt_scope": (
            "scenario, action, policy, actor values, and evaluator profile"
        ),
        "missing_scenario_equivalence_markers": missing_scenario_markers,
        "missing_profile_equivalence_markers": missing_profile_markers,
        "variable_article_error_count": variable_article_errors,
        "count_agreement_error_count": count_agreement_errors,
        "subject_verb_agreement_error_count": subject_verb_agreement_errors,
        "profile_sentence_case_error_count": profile_sentence_case_errors,
        "action_phrase_error_count": action_phrase_errors,
        "ordinal_renderer_cardinality": ordinal_metrics[
            "ordinal_renderer_cardinality"
        ],
        "ordinal_renderer_cardinality_failure_count": ordinal_metrics[
            "ordinal_renderer_cardinality_failure_count"
        ],
    }
    failures = []
    if decimal_count:
        failures.append("decimal literals appear in natural-language inputs")
    if assignment_count:
        failures.append("key=value serialization appears in natural-language inputs")
    if metrics["mean_word_count"] < 75:
        failures.append("natural-language inputs are too short")
    if len(vocabulary) < 100:
        failures.append("natural-language vocabulary is too small")
    if len(noncausal) < 100:
        failures.append("noncausal prose is not scenario-dependent")
    if missing_scenario_markers:
        failures.append("natural-language scenario omits structured source facts")
    if missing_profile_markers:
        failures.append("natural-language evaluator profile omits typed values")
    if variable_article_errors:
        failures.append("variable-template article grammar error")
    if count_agreement_errors:
        failures.append("count-noun agreement error")
    if subject_verb_agreement_errors:
        failures.append("subject-verb agreement error")
    if profile_sentence_case_errors:
        failures.append("profile paraphrase sentence-case error")
    if action_phrase_errors:
        failures.append("malformed controlled-language action phrase")
    if metrics["ordinal_renderer_cardinality_failure_count"]:
        failures.append("ordinal renderer is not an injective state encoding")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "metrics": metrics,
    }


def _phase1_v3_input_paths(root: Path) -> list[Path]:
    return [
        root / "configs" / "normative_predicates.toml",
        root / "configs" / "evaluator_profiles.toml",
        root / "configs" / "calibration_cases.json",
        root / "configs" / "preregistration_v3.toml",
        root / "PREREGISTRATION_V3.md",
        root / "docs" / "NORMATIVE_PREDICATE_CONTRACT.md",
        root / "docs" / "EVALUATOR_PROFILES.md",
        root / "docs" / "EXTERNAL_SMOKE_ACCEPTANCE_V3.md",
        root / "docs" / "LEAKAGE_AUDIT_SPEC.md",
        root / "docs" / "METRIC_COMPARATOR_V2_1.md",
        root / "docs" / "INTERNAL_REVIEW_PROTOCOL.md",
        root / "docs" / "PHASE1_V2_INTERNAL_REVIEW.md",
        root / "docs" / "PHASE1_V3_REVISION0_INTERNAL_REVIEW.md",
        root / "scripts" / "independent-smoke-audit.py",
        root / "scripts" / "run-phase1-v3-smoke.py",
        root / "scripts" / "check-phase1-v3-smoke.ps1",
        root / "src" / "normative_world_model" / "__init__.py",
        root / "src" / "normative_world_model" / "audits.py",
        root / "src" / "normative_world_model" / "calibration.py",
        root / "src" / "normative_world_model" / "generator.py",
        root / "src" / "normative_world_model" / "normative_oracle.py",
        root / "src" / "normative_world_model" / "ontology.py",
        root / "src" / "normative_world_model" / "phase1_v3.py",
        root / "src" / "normative_world_model" / "policy_oracle.py",
        root / "src" / "normative_world_model" / "reachability.py",
        root / "src" / "normative_world_model" / "simulation.py",
        root / "src" / "normative_world_model" / "environments" / "__init__.py",
        root / "src" / "normative_world_model" / "environments" / "game.py",
        root
        / "src"
        / "normative_world_model"
        / "environments"
        / "organization.py",
    ]


def run_phase1_v3_smoke(
    families_per_environment: int = 300,
    seed: int = 20260716,
) -> dict[str, Any]:
    root = project_root()
    data_dir = root / "data" / "generated" / "phase1_v3_smoke"
    artifact_dir = root / "artifacts" / "phase1_v3_smoke"
    gates = _load_density_gates()
    all_families: list[dict[str, Any]] = []
    environment_reports: dict[str, Any] = {}
    file_hashes: dict[str, str] = {}

    for offset, environment in enumerate(("game", "organization")):
        environment_seed = seed + offset * 100_003
        families = generate_v3_environment_families(
            environment,
            families_per_environment,
            environment_seed,
        )
        replay = generate_v3_environment_families(
            environment,
            families_per_environment,
            environment_seed,
        )
        replay_match = _digest_families(families) == _digest_families(replay)
        path = data_dir / f"{environment}.jsonl"
        file_hashes[str(path.relative_to(root))] = _write_jsonl(path, families)
        environment_reports[environment] = {
            "seed": environment_seed,
            "replay_digest_matches": replay_match,
            "density": audit_density(families, gates),
            "split_integrity": audit_split_integrity(families),
            "state_machine_integrity": audit_state_machine_integrity(families),
            "natural_language": audit_natural_language_v3(families),
            "nontriviality": audit_nontriviality(families),
            "model_input_integrity": audit_model_input_integrity(families),
        }
        all_families.extend(families)

    leakage = audit_surface_leakage_by_environment(all_families, seed + 700_001)
    calibration = run_calibration_cases()
    reachability_path = artifact_dir / "uncertainty_reachability.md"
    reachability_path.parent.mkdir(parents=True, exist_ok=True)
    reachability_path.write_text(
        render_reachability_markdown(enumerate_reachability(5)),
        encoding="utf-8",
    )
    file_hashes[str(reachability_path.relative_to(root))] = hashlib.sha256(
        reachability_path.read_bytes()
    ).hexdigest()

    secret_path = root / ".tmp" / "confirmation_v3_secret.json"
    if secret_path.exists():
        secret = json.loads(secret_path.read_text(encoding="utf-8"))["nonce"]
    else:
        secret = secrets.token_hex(32)
        _write_json(secret_path, {"nonce": secret})

    input_paths = _phase1_v3_input_paths(root)
    input_entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(input_paths, key=lambda item: item.relative_to(root).as_posix())
    ]
    input_preimage = "".join(
        f"{entry['path']}\t{entry['sha256']}\n" for entry in input_entries
    ).encode()
    input_commitment = hashlib.sha256(input_preimage).hexdigest()
    with (root / "configs" / "preregistration_v3.toml").open("rb") as handle:
        preregistration = tomllib.load(handle)
    confirmation_seed = int(preregistration["seeds"]["confirmation"])
    confirmation_reservation = {
        "status": "RESERVED_NOT_GENERATED",
        "preregistration_version": PREREGISTRATION_VERSION,
        "families_per_environment_input_cell": 250,
        "unique_scenario_families_per_environment": 250,
        "presentation_design": (
            "paired_same_family_across_structured_and_natural_language"
        ),
        "total_unique_scenario_families": 500,
        "total_presentations": 1000,
        "effective_statistical_unit": "scenario_family",
        "environments": ["game", "organization"],
        "input_conditions": ["structured", "natural_language"],
        "seed_commitment": hashlib.sha256(
            (
                f"confirmation-v3:{confirmation_seed}:"
                f"{input_commitment}:{secret}"
            ).encode()
        ).hexdigest(),
        "commitment_inputs_sha256": input_commitment,
        "commitment_input_manifest": input_entries,
        "commitment_input_manifest_preimage": (
            "UTF-8 lines sorted by path: <path>\\t<sha256>\\n"
        ),
        "commitment_scheme": (
            "sha256('confirmation-v3:' + confirmation_seed + ':' + "
            "commitment_inputs_sha256 + ':' + secret_256_bit_nonce)"
        ),
        "note": "No confirmation scenarios or targets were generated.",
    }
    confirmation_path = data_dir / "confirmation_reservation.json"
    _write_json(confirmation_path, confirmation_reservation)
    file_hashes[str(confirmation_path.relative_to(root))] = hashlib.sha256(
        confirmation_path.read_bytes()
    ).hexdigest()

    status_failures: list[str] = []
    for environment, environment_report in environment_reports.items():
        if not environment_report["replay_digest_matches"]:
            status_failures.append(f"{environment}: deterministic replay")
        for audit_name in (
            "density",
            "split_integrity",
            "state_machine_integrity",
            "natural_language",
            "nontriviality",
            "model_input_integrity",
        ):
            audit = environment_report[audit_name]
            if audit["status"] != "PASS":
                status_failures.extend(
                    f"{environment}: {failure}" for failure in audit["failures"]
                )
    if leakage["status"] != "PASS":
        status_failures.extend(
            f"leakage: {failure}" for failure in leakage["failures"]
        )
    if calibration["status"] != "PASS":
        status_failures.extend(
            f"calibration: {failure}" for failure in calibration["failures"]
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": RUN_KIND,
        "status": "PASS" if not status_failures else "FAIL",
        "generator_schema_revisions_used": GENERATOR_REVISION,
        "generator_schema_revision_limit": int(
            preregistration["stopping"]["maximum_generator_schema_revisions"]
        ),
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
        "internal_review": {
            "status": "NATIVE_PATH_PASS"
            if not status_failures
            else "NATIVE_PATH_FAIL",
            "authorizes_retained_generation": False,
            "external_acceptance_required": True,
        },
        "file_hashes": file_hashes,
    }
    report_path = artifact_dir / "phase1_exit_report.json"
    _write_json(report_path, report)
    dataset_card_path = artifact_dir / "DATASET_CARD.md"
    _write_dataset_card(dataset_card_path, report)
    manifest = {
        "generator_schema_version": SCHEMA_VERSION,
        "preregistration_version": PREREGISTRATION_VERSION,
        "generator_revision": GENERATOR_REVISION,
        "normative_oracle_version": NORMATIVE_ORACLE_VERSION,
        "run_kind": RUN_KIND,
        "seed": seed,
        "family_count": len(all_families),
        "family_count_scope": "combined across environments",
        "families_per_environment": {
            environment: families_per_environment
            for environment in environment_reports
        },
        "files": {
            **file_hashes,
            str(report_path.relative_to(root)): hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest(),
            str(dataset_card_path.relative_to(root)): hashlib.sha256(
                dataset_card_path.read_bytes()
            ).hexdigest(),
        },
        "inputs": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
        "governance": {
            "internal_review_only": True,
            "authorizes_retained_generation": False,
            "external_acceptance_required": True,
        },
    }
    _write_json(artifact_dir / "provenance_manifest.json", manifest)
    return report
