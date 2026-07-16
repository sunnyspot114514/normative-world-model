"""Core contracts and diagnostics for normative world-model experiments."""

from .contracts import EvaluatorContext, Prediction, ProposedAction, WorldState
from .metrics import PairMetrics, score_counterfactual_pair

__all__ = [
    "EvaluatorContext",
    "PairMetrics",
    "Prediction",
    "ProposedAction",
    "WorldState",
    "score_counterfactual_pair",
]

