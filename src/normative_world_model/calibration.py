"""End-to-end calibration cases with asserted, never injected, expectations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .environments.game import simulate_game
from .environments.organization import simulate_organization
from .normative_oracle import NormativeInput, evaluate, load_profiles
from .policy_oracle import PolicyOracleInput, evaluate_policy


def default_calibration_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "calibration_cases.json"


def load_calibration_document(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or default_calibration_path()).read_text(encoding="utf-8"))


def run_calibration_cases(path: Path | None = None) -> dict[str, Any]:
    document = load_calibration_document(path)
    profiles = load_profiles()
    failures: list[str] = []
    results: dict[str, Any] = {}
    for case in document["cases"]:
        simulate = simulate_game if case["environment"] == "game" else simulate_organization
        result = simulate(case["source"], profiles)
        expected = case["expected"]
        actual_violations = list(result.policy_result.hard_violations)
        if actual_violations != expected["hard_violations"]:
            failures.append(f"{case['case_id']}: hard violations")
        if abs(result.event_record.uncertainty - expected["uncertainty"]) > 1e-6:
            failures.append(f"{case['case_id']}: uncertainty")
        actual_decisions = {
            profile_id: evaluation["decision"]
            for profile_id, evaluation in result.evaluations.items()
        }
        if actual_decisions != expected["decisions"]:
            failures.append(f"{case['case_id']}: decisions")
        expected_reasons = expected.get("reasons")
        actual_reasons = {
            profile_id: evaluation["reason"]
            for profile_id, evaluation in result.evaluations.items()
        }
        if expected_reasons is not None and actual_reasons != expected_reasons:
            failures.append(f"{case['case_id']}: reasons")
        results[case["case_id"]] = {
            "hard_violations": actual_violations,
            "uncertainty": result.event_record.uncertainty,
            "decisions": actual_decisions,
            "reasons": actual_reasons,
        }
    boundary_policy = evaluate_policy(
        PolicyOracleInput(
            authorized=True,
            approval_required=False,
            approval_present=True,
            persistent_change=False,
            private_information_exposed=False,
            prohibited_private_disclosure=False,
            third_party_impact=False,
            consent_present=True,
            safety_impact=0.0,
            nonconsensual_harm_threshold=-0.45,
            policy_minimum_evidence_count=0,
            observed_evidence_count=1,
            conflicting_evidence=False,
        )
    )
    for case in document.get("oracle_boundary_cases", []):
        profile = profiles[case["profile_id"]]
        result = evaluate(
            profile,
            NormativeInput(
                impacts={
                    dimension: float(case["uniform_impact"])
                    for dimension in profile.weights
                },
                reversibility=1.0,
                policy_result=boundary_policy,
                policy_minimum_evidence_count=0,
                required_evidence_count=1,
                observed_evidence_count=1,
                conflicting_evidence=False,
            ),
        )
        if result.decision != case["expected_decision"]:
            failures.append(f"{case['case_id']}: boundary decision")
        if result.score != float(case["expected_score"]) or result.score_margin_to_boundary != 0.0:
            failures.append(f"{case['case_id']}: boundary score")
        results[case["case_id"]] = {
            "decision": result.decision,
            "reason": result.reason,
            "score": result.score,
            "score_margin_to_boundary": result.score_margin_to_boundary,
        }
    if document["temporary_fixture_allowlist"]:
        failures.append("temporary calibration fixture allowlist is not empty")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "temporary_fixture_allowlist": document["temporary_fixture_allowlist"],
        "results": results,
    }
