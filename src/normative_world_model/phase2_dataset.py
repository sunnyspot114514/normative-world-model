"""Phase-2 prompt and target construction without changing Phase-1 artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

INPUT_CONDITIONS = ("structured", "natural_language")
PHYSICAL_DELTA_SCHEMAS = {
    "game": {
        "choice_access_delta": "integer",
        "fairness_balance_delta": "integer",
        "health_level_delta": "integer",
        "panic_level_delta": "integer",
        "persistent_flags_added": "array[string]",
        "progress_level_delta": "integer",
        "promise_debt_delta": "integer",
        "resource_stock_delta": "integer",
        "secrecy_level_delta": "integer",
        "trust_level_delta": "integer",
    },
    "organization": {
        "allocation_balance_delta": "integer",
        "budget_remaining_delta": "integer",
        "durable_objects_added": "array[string]",
        "exposure_level_delta": "integer",
        "incident_pressure_delta": "integer",
        "process_debt_delta": "integer",
        "service_health_delta": "integer",
        "stakeholder_trust_delta": "integer",
        "user_control_delta": "integer",
        "work_remaining_delta": "integer",
    },
}
OUTPUT_INSTRUCTION = """Return exactly one JSON object with these top-level keys:
physical_delta, event_record, normative_decision, escalation_required, rollout.
Do not add prose. rollout is a list of objects with horizon, physical_delta, and event_record.
The physical_delta schema below applies to both the one-step output and every rollout item."""


@dataclass(frozen=True)
class Phase2Example:
    example_id: str
    scenario_id: str
    environment: str
    split: str
    input_condition: str
    scenario_surface_variant: int | None
    profile_surface_variant: int
    profile_id: str
    prompt: str
    target: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def physical_delta_schema_instruction(environment: str) -> str:
    try:
        schema = PHYSICAL_DELTA_SCHEMAS[environment]
    except KeyError as error:
        raise ValueError(f"unsupported environment: {environment}") from error
    return (
        f"{OUTPUT_INSTRUCTION}\n"
        "Value-free target physical_delta schema (field: type):\n"
        f"{canonical_json(schema)}"
    )


def neutral_physical_delta(environment: str) -> dict[str, Any]:
    """Return a schema-valid, value-neutral physical delta for diagnostics."""

    try:
        schema = PHYSICAL_DELTA_SCHEMAS[environment]
    except KeyError as error:
        raise ValueError(f"unsupported environment: {environment}") from error
    return {
        field: [] if field_type == "array[string]" else 0
        for field, field_type in schema.items()
    }


def validate_physical_delta_schema(
    environment: str,
    physical_delta: dict[str, Any],
) -> None:
    try:
        schema = PHYSICAL_DELTA_SCHEMAS[environment]
    except KeyError as error:
        raise ValueError(f"unsupported environment: {environment}") from error
    if set(physical_delta) != set(schema):
        raise ValueError(
            f"{environment} physical_delta fields do not match the public schema"
        )
    for field, field_type in schema.items():
        value = physical_delta[field]
        if field_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{environment} {field} must be an integer")
        elif field_type == "array[string]":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(
                    f"{environment} {field} must be an array of strings"
                )
        else:
            raise ValueError(f"unsupported physical schema type: {field_type}")


def target_output(
    result: dict[str, Any],
    profile_id: str,
    *,
    rollout: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    decision = result["evaluations"][profile_id]["decision"]
    return {
        "physical_delta": result["physical_delta"],
        "event_record": result["event_record"],
        "normative_decision": decision,
        "escalation_required": decision == "escalate",
        "rollout": [
            {
                "horizon": int(item["horizon"]),
                "physical_delta": item["physical_delta"],
                "event_record": item["event_record"],
            }
            for item in rollout
        ],
    }


def _structured_prompt(
    family: dict[str, Any],
    profile_id: str,
    profile_variant: int,
) -> str:
    profile = family["evaluator_twins"][profile_id]["structured_profile_shams"][
        profile_variant
    ]
    return (
        "Pre-transition source (canonical JSON):\n"
        f"{canonical_json(family['model_input'])}\n"
        "Evaluator profile (JSON; formatting is not semantic):\n"
        f"{profile}\n"
        f"{physical_delta_schema_instruction(family['environment'])}"
    )


def _natural_language_prompt(
    family: dict[str, Any],
    profile_id: str,
    scenario_variant: int,
    profile_variant: int,
) -> str:
    scenario = family["surface_twins"][scenario_variant]["natural_language"]
    profile = family["evaluator_twins"][profile_id][
        "natural_language_profile_shams"
    ][profile_variant]
    return (
        f"Scenario:\n{scenario}\n"
        f"Evaluator contract:\n{profile}\n"
        f"{physical_delta_schema_instruction(family['environment'])}"
    )


def _example_id(
    scenario_id: str,
    condition: str,
    scenario_variant: int | None,
    profile_variant: int,
    profile_id: str,
) -> str:
    preimage = (
        f"{scenario_id}\t{condition}\t{scenario_variant}\t"
        f"{profile_variant}\t{profile_id}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:24]


def build_phase2_examples(
    families: Iterable[dict[str, Any]],
) -> list[Phase2Example]:
    """Create paired structured/NL presentations from stored Phase-1 rows."""

    examples: list[Phase2Example] = []
    for family in families:
        validate_physical_delta_schema(
            family["environment"],
            family["primary"]["physical_delta"],
        )
        for rollout_item in family["rollout"]:
            validate_physical_delta_schema(
                family["environment"],
                rollout_item["physical_delta"],
            )
        for profile_id in family["evaluator_twins"]:
            target = target_output(
                family["primary"],
                profile_id,
                rollout=family["rollout"],
            )
            for profile_variant in (0, 1):
                examples.append(
                    Phase2Example(
                        example_id=_example_id(
                            family["scenario_id"],
                            "structured",
                            None,
                            profile_variant,
                            profile_id,
                        ),
                        scenario_id=family["scenario_id"],
                        environment=family["environment"],
                        split=family["split"],
                        input_condition="structured",
                        scenario_surface_variant=None,
                        profile_surface_variant=profile_variant,
                        profile_id=profile_id,
                        prompt=_structured_prompt(
                            family,
                            profile_id,
                            profile_variant,
                        ),
                        target=target,
                    )
                )
            for scenario_variant in (0, 1):
                for profile_variant in (0, 1):
                    examples.append(
                        Phase2Example(
                            example_id=_example_id(
                                family["scenario_id"],
                                "natural_language",
                                scenario_variant,
                                profile_variant,
                                profile_id,
                            ),
                            scenario_id=family["scenario_id"],
                            environment=family["environment"],
                            split=family["split"],
                            input_condition="natural_language",
                            scenario_surface_variant=scenario_variant,
                            profile_surface_variant=profile_variant,
                            profile_id=profile_id,
                            prompt=_natural_language_prompt(
                                family,
                                profile_id,
                                scenario_variant,
                                profile_variant,
                            ),
                            target=target,
                        )
                    )
    return examples
