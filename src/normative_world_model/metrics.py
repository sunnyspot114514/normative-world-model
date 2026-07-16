"""Primary paired metrics for the leakage-controlled experiment."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import Prediction
from .comparators import event_records_equal, physical_deltas_equal


@dataclass(frozen=True)
class PairMetrics:
    physical_exact_a: bool
    physical_exact_b: bool
    physical_invariant: bool
    physical_consistent_and_correct: bool
    event_record_exact_a: bool
    event_record_exact_b: bool
    event_record_invariant: bool
    event_record_consistent_and_correct: bool
    normative_correct_a: bool
    normative_correct_b: bool
    normative_pair_correct: bool
    normative_flip_required: bool
    normative_flip_observed: bool
    joint_pair_success: bool


def score_counterfactual_pair(
    prediction_a: Prediction,
    prediction_b: Prediction,
    target_a: Prediction,
    target_b: Prediction,
) -> PairMetrics:
    """Score paired evaluator interventions without rewarding constant outputs."""

    physical_exact_a = physical_deltas_equal(prediction_a.physical_delta, target_a.physical_delta)
    physical_exact_b = physical_deltas_equal(prediction_b.physical_delta, target_b.physical_delta)
    physical_invariant = physical_deltas_equal(prediction_a.physical_delta, prediction_b.physical_delta)
    target_physical_invariant = physical_deltas_equal(target_a.physical_delta, target_b.physical_delta)
    physical_consistent_and_correct = (
        target_physical_invariant
        and physical_exact_a
        and physical_exact_b
        and physical_invariant
    )

    event_record_exact_a = event_records_equal(prediction_a.event_record, target_a.event_record)
    event_record_exact_b = event_records_equal(prediction_b.event_record, target_b.event_record)
    event_record_invariant = event_records_equal(prediction_a.event_record, prediction_b.event_record)
    target_event_record_invariant = event_records_equal(target_a.event_record, target_b.event_record)
    event_record_consistent_and_correct = (
        target_event_record_invariant
        and event_record_exact_a
        and event_record_exact_b
        and event_record_invariant
    )

    normative_correct_a = prediction_a.normative_decision == target_a.normative_decision
    normative_correct_b = prediction_b.normative_decision == target_b.normative_decision
    normative_pair_correct = normative_correct_a and normative_correct_b
    normative_flip_required = target_a.normative_decision != target_b.normative_decision
    normative_flip_observed = (
        prediction_a.normative_decision != prediction_b.normative_decision
    )
    joint_pair_success = (
        physical_consistent_and_correct
        and event_record_consistent_and_correct
        and normative_pair_correct
    )

    return PairMetrics(
        physical_exact_a=physical_exact_a,
        physical_exact_b=physical_exact_b,
        physical_invariant=physical_invariant,
        physical_consistent_and_correct=physical_consistent_and_correct,
        event_record_exact_a=event_record_exact_a,
        event_record_exact_b=event_record_exact_b,
        event_record_invariant=event_record_invariant,
        event_record_consistent_and_correct=event_record_consistent_and_correct,
        normative_correct_a=normative_correct_a,
        normative_correct_b=normative_correct_b,
        normative_pair_correct=normative_pair_correct,
        normative_flip_required=normative_flip_required,
        normative_flip_observed=normative_flip_observed,
        joint_pair_success=joint_pair_success,
    )
