"""Phase-2 prompt and target construction without changing Phase-1 artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

INPUT_CONDITIONS = ("structured", "natural_language")
OUTPUT_INSTRUCTION = """Return exactly one JSON object with these keys:
physical_delta, event_record, normative_decision, escalation_required, rollout.
Do not add prose. rollout is a list of objects with horizon, physical_delta, and event_record."""


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
        f"{OUTPUT_INSTRUCTION}"
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
        f"{OUTPUT_INSTRUCTION}"
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
