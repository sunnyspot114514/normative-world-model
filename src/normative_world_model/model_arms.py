"""Deterministic Phase-2 records for joint and factorized model arms."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from .phase2_dataset import (
    PHYSICAL_DELTA_SCHEMAS,
    build_phase2_examples,
    canonical_json,
)
from .policy_oracle import PolicyOracleInput, evaluate_policy
from .transfer_matrix import TARGET_PROFILE_PAIRS

FACTUAL_OUTPUT_INSTRUCTION = """Return exactly one JSON object with these top-level keys:
physical_delta, event_record, rollout.
Do not add prose. rollout is a list of objects with horizon, physical_delta, and event_record.
The physical_delta schema below applies to both the one-step output and every rollout item."""
NORMATIVE_OUTPUT_INSTRUCTION = """Return exactly one JSON object with these keys:
normative_decision, escalation_required.
Do not add prose."""


def model_output_json(value: Any) -> str:
    """Serialize model targets in the declared schema order."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )


def factual_output_instruction(environment: str) -> str:
    try:
        schema = PHYSICAL_DELTA_SCHEMAS[environment]
    except KeyError as error:
        raise ValueError(f"unsupported environment: {environment}") from error
    return (
        f"{FACTUAL_OUTPUT_INSTRUCTION}\n"
        "Value-free target physical_delta schema (field: type):\n"
        f"{canonical_json(schema)}"
    )


def _stable_id(*parts: Any) -> str:
    preimage = "\t".join(str(part) for part in parts)
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:24]


def _joint_target_text(target: dict[str, Any]) -> str:
    return model_output_json(target)


def _joint_target_parts(target: dict[str, Any]) -> tuple[str, str, str]:
    target_text = _joint_target_text(target)
    factual_object = {
        "physical_delta": target["physical_delta"],
        "event_record": target["event_record"],
    }
    factual_prefix = model_output_json(factual_object)[:-1]
    if not target_text.startswith(factual_prefix):
        raise ValueError("joint target does not begin with the factual prefix")
    normative_suffix = target_text[len(factual_prefix) :]
    if not normative_suffix.startswith(","):
        raise ValueError("joint normative suffix must begin with a comma")
    return target_text, factual_prefix, normative_suffix


def build_joint_records(
    families: Iterable[dict[str, Any]],
    *,
    include_rollout: bool = True,
) -> list[dict[str, Any]]:
    records = []
    for example in build_phase2_examples(families):
        target = dict(example.target)
        if not include_rollout:
            target["rollout"] = []
        target_text, factual_prefix, normative_suffix = _joint_target_parts(
            target
        )
        semantic_group = _stable_id(
            "semantic",
            example.scenario_id,
            example.input_condition,
            example.scenario_surface_variant,
            example.profile_surface_variant,
        )
        surface_group = _stable_id(
            "surface",
            example.scenario_id,
            example.input_condition,
            example.scenario_surface_variant,
            example.profile_id,
        )
        memberships = [
            f"{left}|{right}"
            for left, right in TARGET_PROFILE_PAIRS
            if example.profile_id in (left, right)
        ]
        records.append(
            {
                "record_id": example.example_id,
                "scenario_id": example.scenario_id,
                "environment": example.environment,
                "split": example.split,
                "input_condition": example.input_condition,
                "scenario_surface_variant": example.scenario_surface_variant,
                "profile_surface_variant": example.profile_surface_variant,
                "profile_id": example.profile_id,
                "input_text": example.prompt,
                "target_text": target_text,
                "factual_prefix_text": factual_prefix,
                "normative_suffix_text": normative_suffix,
                "semantic_pair_group": semantic_group,
                "surface_sham_group": surface_group,
                "target_pair_memberships": memberships,
                "arm_views": ["joint_naive", "joint_consistency"],
                "horizon_mode": (
                    "stored_rollout" if include_rollout else "one_step"
                ),
                "consistency_loss_applies_to": [
                    "physical_delta",
                    "event_record",
                ],
                "consistency_loss_excludes": [
                    "normative_decision",
                    "escalation_required",
                ],
            }
        )
    return records


def _factual_target(
    family: dict[str, Any],
    *,
    include_rollout: bool,
) -> dict[str, Any]:
    return {
        "physical_delta": family["primary"]["physical_delta"],
        "event_record": family["primary"]["event_record"],
        "rollout": (
            [
                {
                    "horizon": int(item["horizon"]),
                    "physical_delta": item["physical_delta"],
                    "event_record": item["event_record"],
                }
                for item in family["rollout"]
            ]
            if include_rollout
            else []
        ),
    }


def build_factorized_factual_records(
    families: Iterable[dict[str, Any]],
    *,
    include_rollout: bool = True,
) -> list[dict[str, Any]]:
    records = []
    for family in families:
        target_text = model_output_json(
            _factual_target(family, include_rollout=include_rollout)
        )
        structured_input = (
            "Pre-transition source (canonical JSON):\n"
            f"{canonical_json(family['model_input'])}\n"
            f"{factual_output_instruction(family['environment'])}"
        )
        records.append(
            {
                "record_id": _stable_id(
                    family["scenario_id"],
                    "factorized_factual",
                    "structured",
                ),
                "scenario_id": family["scenario_id"],
                "environment": family["environment"],
                "split": family["split"],
                "input_condition": "structured",
                "scenario_surface_variant": None,
                "input_text": structured_input,
                "target_text": target_text,
                "arm": "factorized_factual",
                "evaluator_visible": False,
                "horizon_mode": (
                    "stored_rollout" if include_rollout else "one_step"
                ),
            }
        )
        for scenario_variant, surface in enumerate(family["surface_twins"]):
            records.append(
                {
                    "record_id": _stable_id(
                        family["scenario_id"],
                        "factorized_factual",
                        "natural_language",
                        scenario_variant,
                    ),
                    "scenario_id": family["scenario_id"],
                    "environment": family["environment"],
                    "split": family["split"],
                    "input_condition": "natural_language",
                    "scenario_surface_variant": scenario_variant,
                    "input_text": (
                        f"Scenario:\n{surface['natural_language']}\n"
                        f"{factual_output_instruction(family['environment'])}"
                    ),
                    "target_text": target_text,
                    "arm": "factorized_factual",
                    "evaluator_visible": False,
                    "horizon_mode": (
                        "stored_rollout" if include_rollout else "one_step"
                    ),
                }
            )
    return records


def build_factorized_normative_records(
    families: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for family in families:
        factual_context = {
            "event_record": family["primary"]["event_record"],
            "policy_result": family["primary"]["policy_result"],
        }
        for profile_id, evaluator in family["evaluator_twins"].items():
            decision = evaluator["target"]["decision"]
            target_text = model_output_json(
                {
                    "normative_decision": decision,
                    "escalation_required": decision == "escalate",
                }
            )
            for profile_variant in (0, 1):
                records.append(
                    {
                        "record_id": _stable_id(
                            family["scenario_id"],
                            "factorized_normative",
                            "structured",
                            profile_id,
                            profile_variant,
                        ),
                        "scenario_id": family["scenario_id"],
                        "environment": family["environment"],
                        "split": family["split"],
                        "input_condition": "structured",
                        "profile_id": profile_id,
                        "profile_surface_variant": profile_variant,
                        "input_text": factorized_normative_input_text(
                            factual_context,
                            evaluator,
                            condition="structured",
                            profile_variant=profile_variant,
                        ),
                        "target_text": target_text,
                        "arm": "factorized_normative",
                        "training_factual_context_origin": "gold_event_record",
                        "evaluation_factual_context_origin": (
                            "factorized_factual_prediction_plus_"
                            "recomputed_policy_oracle"
                        ),
                    }
                )
                records.append(
                    {
                        "record_id": _stable_id(
                            family["scenario_id"],
                            "factorized_normative",
                            "natural_language",
                            profile_id,
                            profile_variant,
                        ),
                        "scenario_id": family["scenario_id"],
                        "environment": family["environment"],
                        "split": family["split"],
                        "input_condition": "natural_language",
                        "profile_id": profile_id,
                        "profile_surface_variant": profile_variant,
                        "input_text": factorized_normative_input_text(
                            factual_context,
                            evaluator,
                            condition="natural_language",
                            profile_variant=profile_variant,
                        ),
                        "target_text": target_text,
                        "arm": "factorized_normative",
                        "training_factual_context_origin": "gold_event_record",
                        "evaluation_factual_context_origin": (
                            "factorized_factual_prediction_plus_"
                            "recomputed_policy_oracle"
                        ),
                    }
                )
    return records


def factorized_normative_input_text(
    factual_context: dict[str, Any],
    evaluator: dict[str, Any],
    *,
    condition: str,
    profile_variant: int,
) -> str:
    if condition == "structured":
        heading = "Evaluator profile:"
        profile = evaluator["structured_profile_shams"][profile_variant]
    elif condition == "natural_language":
        heading = "Evaluator contract:"
        profile = evaluator["natural_language_profile_shams"][profile_variant]
    else:
        raise ValueError(f"unsupported input condition: {condition}")
    return (
        "Predicted factual context (canonical JSON):\n"
        f"{canonical_json(factual_context)}\n"
        f"{heading}\n"
        f"{profile}\n"
        f"{NORMATIVE_OUTPUT_INSTRUCTION}"
    )


def recompute_factorized_policy_result(
    model_input: dict[str, Any],
    predicted_event_record: dict[str, Any],
) -> dict[str, Any]:
    """Recompute hard-policy output from source policy and predicted consequences."""

    policy = model_input["policy"]
    result = evaluate_policy(
        PolicyOracleInput(
            authorized=bool(predicted_event_record["authorized"]),
            approval_required=bool(
                predicted_event_record["approval_required"]
            ),
            approval_present=bool(
                predicted_event_record["approval_present"]
            ),
            persistent_change=bool(
                predicted_event_record["persistent_change"]
            ),
            private_information_exposed=bool(
                predicted_event_record["private_information_exposed"]
            ),
            prohibited_private_disclosure=bool(
                policy["prohibited_private_disclosure"]
            ),
            third_party_impact=bool(
                predicted_event_record["third_party_impact"]
            ),
            consent_present=bool(
                predicted_event_record["consent_present"]
            ),
            safety_impact=float(
                predicted_event_record["impact_vector"]["safety"]
            ),
            nonconsensual_harm_threshold=float(
                policy["nonconsensual_harm_threshold"]
            ),
            policy_minimum_evidence_count=int(
                policy["policy_minimum_evidence_count"]
            ),
            observed_evidence_count=int(
                predicted_event_record["observed_evidence_count"]
            ),
            conflicting_evidence=bool(
                predicted_event_record["conflicting_evidence"]
            ),
            conflict_blocking=bool(policy["conflict_blocking"]),
        )
    )
    return asdict(result)


def evaluator_visibility_failures(
    factual_records: Iterable[dict[str, Any]],
) -> list[str]:
    forbidden = (
        "Evaluator profile",
        "Evaluator contract",
        "dimension weights",
        "dimension vetoes",
        "uncertainty threshold",
        "irreversible-harm threshold",
        '"veto_floor"',
        '"weights"',
        '"profile_id"',
    )
    return [
        record["record_id"]
        for record in factual_records
        if record.get("evaluator_visible") is not False
        or any(token in record["input_text"] for token in forbidden)
    ]
