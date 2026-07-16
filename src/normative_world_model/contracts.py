"""Dependency-free structured contracts used by the first experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

NormativeDecision = Literal["allow", "reject", "escalate"]


@dataclass(frozen=True)
class WorldState:
    """Causal world state. Actor values belong here because they may affect dynamics."""

    scenario_id: str
    observable_facts: dict[str, Any]
    actor_values: dict[str, float] = field(default_factory=dict)
    permissions: frozenset[str] = field(default_factory=frozenset)
    irreversible_flags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ProposedAction:
    """An uncommitted action whose counterfactual effects are to be predicted."""

    action_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluatorContext:
    """A non-causal lens absent from physical and event-record predictors."""

    profile_id: str
    evaluator_values: dict[str, float]
    policy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Prediction:
    """Structured targets produced after seeing only pre-transition inputs.

    ``physical_delta`` is the simulated world transition. ``event_record`` is a
    synthetic institutional interpretation of that transition; it is not
    presented to either predictor as an input.
    """

    physical_delta: dict[str, Any]
    event_record: dict[str, Any]
    normative_decision: NormativeDecision
    escalation_required: bool = False
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
