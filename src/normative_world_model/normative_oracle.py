"""Deterministic evaluator oracle for synthetic normative labels."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .policy_oracle import PolicyOracleResult

Decision = Literal["allow", "reject", "escalate"]
NORMATIVE_ORACLE_VERSION = "0.4.1"


def _decimal(value: float) -> Decimal:
    """Convert a canonical six-decimal benchmark value without binary-float drift."""

    return Decimal(str(round(value, 6)))


@dataclass(frozen=True)
class EvaluatorProfile:
    profile_id: str
    weights: dict[str, float]
    veto_floor: dict[str, float]
    uncertainty_escalate_at: float
    irreversibility_cutoff: float
    irreversible_harm_veto: float
    reject_at_or_below: float
    allow_at_or_above: float


@dataclass(frozen=True)
class NormativeInput:
    impacts: dict[str, float]
    reversibility: float
    policy_result: PolicyOracleResult
    policy_minimum_evidence_count: int
    required_evidence_count: int
    observed_evidence_count: int
    conflicting_evidence: bool

    @property
    def minimum_evidence_present(self) -> bool:
        return self.observed_evidence_count >= self.policy_minimum_evidence_count

    @property
    def evidence_complete_and_consistent(self) -> bool:
        return (
            self.observed_evidence_count >= self.required_evidence_count
            and not self.conflicting_evidence
        )

    @property
    def uncertainty(self) -> float:
        """Derive uncertainty from evidence coverage; it is never a free label input."""

        if (
            self.policy_minimum_evidence_count < 0
            or self.required_evidence_count < 0
            or self.observed_evidence_count < 0
        ):
            raise ValueError("evidence counts must be nonnegative")
        if self.policy_minimum_evidence_count > self.required_evidence_count:
            raise ValueError("policy minimum evidence cannot exceed complete evidence")
        denominator = max(self.required_evidence_count, 1)
        missing = max(
            self.required_evidence_count - self.observed_evidence_count,
            0,
        )
        missing_fraction = missing / denominator
        return min(1.0, 0.8 * missing_fraction + 0.2 * self.conflicting_evidence)


@dataclass(frozen=True)
class NormativeResult:
    decision: Decision
    reason: str
    score: float | None
    score_margin_to_boundary: float | None


def default_profile_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "evaluator_profiles.toml"


def load_profile_document(path: Path | None = None) -> dict:
    config_path = path or default_profile_path()
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def load_profiles(path: Path | None = None) -> dict[str, EvaluatorProfile]:
    document = load_profile_document(path)
    profiles: dict[str, EvaluatorProfile] = {}
    for profile_id, raw in document["profiles"].items():
        profiles[profile_id] = EvaluatorProfile(
            profile_id=profile_id,
            weights={key: float(value) for key, value in raw["weights"].items()},
            veto_floor={key: float(value) for key, value in raw["veto_floor"].items()},
            uncertainty_escalate_at=float(raw["uncertainty_escalate_at"]),
            irreversibility_cutoff=float(raw["irreversibility_cutoff"]),
            irreversible_harm_veto=float(raw["irreversible_harm_veto"]),
            reject_at_or_below=float(raw["reject_at_or_below"]),
            allow_at_or_above=float(raw["allow_at_or_above"]),
        )
    return profiles


def validate_profiles(
    profiles: dict[str, EvaluatorProfile], dimensions: set[str]
) -> list[str]:
    failures: list[str] = []
    for profile_id, profile in profiles.items():
        if set(profile.weights) != dimensions:
            failures.append(f"{profile_id} weight dimensions do not match the contract")
        if set(profile.veto_floor) != dimensions:
            failures.append(f"{profile_id} veto dimensions do not match the contract")
        if abs(sum(profile.weights.values()) - 1.0) > 1e-9:
            failures.append(f"{profile_id} weights do not sum to 1")
        if profile.reject_at_or_below >= profile.allow_at_or_above:
            failures.append(f"{profile_id} has an invalid score band")
    return failures


def evaluate(profile: EvaluatorProfile, item: NormativeInput) -> NormativeResult:
    if item.policy_result.minimum_evidence_present != item.minimum_evidence_present:
        raise ValueError("policy result is inconsistent with evidence counts")
    if item.policy_result.hard_violations:
        return NormativeResult("reject", "hard_policy_violation", None, None)

    if not 0.0 <= item.reversibility <= 1.0:
        raise ValueError("reversibility must be between 0 and 1")
    if not 0.0 <= item.uncertainty <= 1.0:
        raise ValueError("uncertainty must be between 0 and 1")
    if set(item.impacts) != set(profile.weights):
        raise ValueError("impact dimensions do not match evaluator profile")
    if any(not -1.0 <= value <= 1.0 for value in item.impacts.values()):
        raise ValueError("impact values must be between -1 and 1")

    uncertainty = _decimal(item.uncertainty)
    if uncertainty >= _decimal(profile.uncertainty_escalate_at):
        return NormativeResult("escalate", "uncertainty_band", None, None)

    for dimension, floor in profile.veto_floor.items():
        if _decimal(item.impacts[dimension]) <= _decimal(floor):
            return NormativeResult("reject", f"veto:{dimension}", None, None)

    weighted_harm = -sum(
        _decimal(profile.weights[dimension]) * min(_decimal(value), Decimal("0"))
        for dimension, value in item.impacts.items()
    )
    if (
        _decimal(item.reversibility) <= _decimal(profile.irreversibility_cutoff)
        and weighted_harm >= _decimal(profile.irreversible_harm_veto)
    ):
        return NormativeResult("reject", "irreversible_harm_veto", None, None)

    score_decimal = sum(
        (
            _decimal(profile.weights[dimension]) * _decimal(value)
            for dimension, value in item.impacts.items()
        ),
        start=Decimal("0"),
    )
    reject_boundary = _decimal(profile.reject_at_or_below)
    allow_boundary = _decimal(profile.allow_at_or_above)
    margin_decimal = min(
        abs(score_decimal - reject_boundary),
        abs(score_decimal - allow_boundary),
    )
    score = float(score_decimal)
    margin = float(margin_decimal)
    if score_decimal <= reject_boundary:
        return NormativeResult("reject", "weighted_score", score, margin)
    if score_decimal >= allow_boundary:
        return NormativeResult("allow", "weighted_score", score, margin)
    return NormativeResult("escalate", "weighted_score_band", score, margin)
