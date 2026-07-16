"""Shared typed event record and cross-environment evaluation glue."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .normative_oracle import EvaluatorProfile, NormativeInput, evaluate
from .policy_oracle import PolicyOracleInput, PolicyOracleResult, evaluate_policy

IMPACT_DIMENSIONS = (
    "safety",
    "privacy",
    "autonomy",
    "trust",
    "efficiency",
    "fairness",
    "commitment",
)


def clamp(value: float, minimum: float = -1.0, maximum: float = 1.0) -> float:
    return round(max(minimum, min(maximum, value)), 6)


@dataclass(frozen=True)
class EventRecord:
    authorized: bool
    approval_required: bool
    approval_present: bool
    persistent_change: bool
    reversibility: float
    recovery_cost: float
    stakeholder_count: int
    third_party_impact: bool
    consent_present: bool
    private_information_exposed: bool
    obligation_active: bool
    obligation_breached: bool
    policy_minimum_evidence_count: int
    minimum_evidence_present: bool
    required_evidence_count: int
    observed_evidence_count: int
    conflicting_evidence: bool
    evidence_complete_and_consistent: bool
    uncertainty: float
    impact_vector: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SimulationResult:
    next_state: dict[str, Any]
    physical_delta: dict[str, Any]
    event_record: EventRecord
    policy_result: PolicyOracleResult
    evaluations: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_state": self.next_state,
            "physical_delta": self.physical_delta,
            "event_record": self.event_record.to_dict(),
            "policy_result": asdict(self.policy_result),
            "evaluations": self.evaluations,
        }


def derive_uncertainty(required: int, observed: int, conflicting: bool) -> float:
    if required < 0 or observed < 0:
        raise ValueError("evidence counts must be nonnegative")
    missing = max(required - observed, 0)
    return round(min(1.0, 0.8 * missing / max(required, 1) + 0.2 * conflicting), 6)


def build_event_record(
    *,
    authorized: bool,
    approval_required: bool,
    approval_present: bool,
    persistent_change: bool,
    reversibility: float,
    recovery_cost: float,
    stakeholder_count: int,
    third_party_impact: bool,
    consent_present: bool,
    private_information_exposed: bool,
    obligation_active: bool,
    obligation_breached: bool,
    policy_minimum_evidence_count: int,
    required_evidence_count: int,
    observed_evidence_count: int,
    conflicting_evidence: bool,
    impacts: dict[str, float],
) -> EventRecord:
    if policy_minimum_evidence_count > required_evidence_count:
        raise ValueError("policy minimum evidence cannot exceed complete evidence")
    if set(impacts) != set(IMPACT_DIMENSIONS):
        raise ValueError("event record impact dimensions are incomplete")
    minimum_present = observed_evidence_count >= policy_minimum_evidence_count
    complete = observed_evidence_count >= required_evidence_count and not conflicting_evidence
    return EventRecord(
        authorized=authorized,
        approval_required=approval_required,
        approval_present=approval_present,
        persistent_change=persistent_change,
        reversibility=clamp(reversibility, 0.0, 1.0),
        recovery_cost=clamp(recovery_cost, 0.0, 1.0),
        stakeholder_count=stakeholder_count,
        third_party_impact=third_party_impact,
        consent_present=consent_present,
        private_information_exposed=private_information_exposed,
        obligation_active=obligation_active,
        obligation_breached=obligation_breached,
        policy_minimum_evidence_count=policy_minimum_evidence_count,
        minimum_evidence_present=minimum_present,
        required_evidence_count=required_evidence_count,
        observed_evidence_count=observed_evidence_count,
        conflicting_evidence=conflicting_evidence,
        evidence_complete_and_consistent=complete,
        uncertainty=derive_uncertainty(
            required_evidence_count, observed_evidence_count, conflicting_evidence
        ),
        impact_vector={key: clamp(value) for key, value in impacts.items()},
    )


def run_shared_oracles(
    record: EventRecord,
    policy: dict[str, Any],
    profiles: dict[str, EvaluatorProfile],
) -> tuple[PolicyOracleResult, dict[str, dict[str, Any]]]:
    policy_result = evaluate_policy(
        PolicyOracleInput(
            authorized=record.authorized,
            approval_required=record.approval_required,
            approval_present=record.approval_present,
            persistent_change=record.persistent_change,
            private_information_exposed=record.private_information_exposed,
            prohibited_private_disclosure=bool(policy["prohibited_private_disclosure"]),
            third_party_impact=record.third_party_impact,
            consent_present=record.consent_present,
            safety_impact=record.impact_vector["safety"],
            nonconsensual_harm_threshold=float(policy["nonconsensual_harm_threshold"]),
            policy_minimum_evidence_count=record.policy_minimum_evidence_count,
            observed_evidence_count=record.observed_evidence_count,
            conflicting_evidence=record.conflicting_evidence,
            conflict_blocking=bool(policy["conflict_blocking"]),
        )
    )
    item = NormativeInput(
        impacts=record.impact_vector,
        reversibility=record.reversibility,
        policy_result=policy_result,
        policy_minimum_evidence_count=record.policy_minimum_evidence_count,
        required_evidence_count=record.required_evidence_count,
        observed_evidence_count=record.observed_evidence_count,
        conflicting_evidence=record.conflicting_evidence,
    )
    evaluations: dict[str, dict[str, Any]] = {}
    for profile_id, profile in profiles.items():
        result = evaluate(profile, item)
        evaluations[profile_id] = {
            "decision": result.decision,
            "reason": result.reason,
            "score": result.score,
            "score_margin_to_boundary": result.score_margin_to_boundary,
        }
    return policy_result, evaluations
