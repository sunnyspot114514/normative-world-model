"""Strict parser for model-produced Phase-2 structured outputs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .comparators import parse_finite_decimal
from .contracts import Prediction

DECISIONS = {"allow", "reject", "escalate"}
CONTINUOUS_EVENT_FIELDS = {"reversibility", "recovery_cost", "uncertainty"}
TOP_LEVEL_REQUIRED = {
    "physical_delta",
    "event_record",
    "normative_decision",
    "escalation_required",
    "rollout",
}
TOP_LEVEL_OPTIONAL = {"confidence"}
ROLLOUT_KEYS = {"horizon", "physical_delta", "event_record"}
LIST_ELEMENT_EXEMPLARS = {
    ("physical_delta", "durable_objects_added"): "",
    ("physical_delta", "persistent_flags_added"): "",
}
_FENCE = re.compile(
    r"\A\s*```(?:json)?\s*\n(?P<body>.*)\n```\s*\Z",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class RolloutPrediction:
    horizon: int
    physical_delta: dict[str, Any]
    event_record: dict[str, Any]


@dataclass(frozen=True)
class ParsedModelOutput:
    one_step: Prediction
    rollout: dict[int, RolloutPrediction]


@dataclass(frozen=True)
class ParsedFactualOutput:
    physical_delta: dict[str, Any]
    event_record: dict[str, Any]
    rollout: dict[int, RolloutPrediction]


@dataclass(frozen=True)
class ParsedNormativeOutput:
    normative_decision: str
    escalation_required: bool


@dataclass(frozen=True)
class ParseResult:
    ok: bool
    output: ParsedModelOutput | None
    error_code: str | None = None
    error_detail: str | None = None


class OutputValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _unwrap(text: str) -> str:
    match = _FENCE.fullmatch(text)
    return match.group("body") if match else text.strip()


def _is_continuous_event_path(path: tuple[str, ...]) -> bool:
    return bool(path) and (
        path[-1] in CONTINUOUS_EVENT_FIELDS or "impact_vector" in path
    )


def _validate_shape(
    value: Any,
    exemplar: Any,
    *,
    component: str,
    path: tuple[str, ...] = (),
) -> None:
    label = ".".join(path) or component
    if isinstance(exemplar, dict):
        if not isinstance(value, dict):
            raise OutputValidationError("type_error", f"{label} must be an object")
        if set(value) != set(exemplar):
            missing = sorted(set(exemplar) - set(value))
            extra = sorted(set(value) - set(exemplar))
            raise OutputValidationError(
                "schema_keys",
                f"{label} keys differ; missing={missing}, extra={extra}",
            )
        for key in exemplar:
            _validate_shape(
                value[key],
                exemplar[key],
                component=component,
                path=(*path, key),
            )
        return
    if isinstance(exemplar, list):
        if not isinstance(value, list):
            raise OutputValidationError("type_error", f"{label} must be a list")
        element_exemplar = (
            exemplar[0]
            if exemplar
            else LIST_ELEMENT_EXEMPLARS.get((component, *path))
        )
        if value and element_exemplar is None:
            raise OutputValidationError(
                "list_element_schema",
                f"{label} has no declared element schema",
            )
        if element_exemplar is not None:
            for index, item in enumerate(value):
                _validate_shape(
                    item,
                    element_exemplar,
                    component=component,
                    path=(*path, str(index)),
                )
        return
    if component == "event_record" and _is_continuous_event_path(path):
        try:
            parse_finite_decimal(value)
        except ValueError as error:
            raise OutputValidationError(
                "invalid_number",
                f"{label} is not a finite decimal",
            ) from error
        return
    if isinstance(exemplar, bool):
        if not isinstance(value, bool):
            raise OutputValidationError("type_error", f"{label} must be boolean")
        return
    if isinstance(exemplar, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise OutputValidationError("type_error", f"{label} must be integer")
        return
    if isinstance(exemplar, float):
        try:
            parse_finite_decimal(value)
        except ValueError as error:
            raise OutputValidationError(
                "invalid_number",
                f"{label} is not a finite decimal",
            ) from error
        return
    if exemplar is None:
        if value is not None:
            raise OutputValidationError("type_error", f"{label} must be null")
        return
    if not isinstance(value, type(exemplar)):
        raise OutputValidationError(
            "type_error",
            f"{label} must have type {type(exemplar).__name__}",
        )


def _validate_payload(
    payload: Any,
    expected: dict[str, Any],
) -> ParsedModelOutput:
    if not isinstance(payload, dict):
        raise OutputValidationError("top_level_type", "output must be one JSON object")
    allowed = TOP_LEVEL_REQUIRED | TOP_LEVEL_OPTIONAL
    if set(payload) - allowed or not TOP_LEVEL_REQUIRED.issubset(payload):
        missing = sorted(TOP_LEVEL_REQUIRED - set(payload))
        extra = sorted(set(payload) - allowed)
        raise OutputValidationError(
            "top_level_keys",
            f"top-level keys differ; missing={missing}, extra={extra}",
        )
    _validate_shape(
        payload["physical_delta"],
        expected["physical_delta"],
        component="physical_delta",
    )
    _validate_shape(
        payload["event_record"],
        expected["event_record"],
        component="event_record",
    )
    decision = payload["normative_decision"]
    if decision not in DECISIONS:
        raise OutputValidationError(
            "decision_value",
            f"normative_decision must be one of {sorted(DECISIONS)}",
        )
    escalation = payload["escalation_required"]
    if not isinstance(escalation, bool):
        raise OutputValidationError(
            "type_error",
            "escalation_required must be boolean",
        )
    if escalation != (decision == "escalate"):
        raise OutputValidationError(
            "decision_consistency",
            "escalation_required disagrees with normative_decision",
        )
    confidence = payload.get("confidence")
    if confidence is not None:
        try:
            confidence = float(parse_finite_decimal(confidence))
        except ValueError as error:
            raise OutputValidationError(
                "invalid_confidence",
                "confidence must be a finite decimal",
            ) from error
        if not 0.0 <= confidence <= 1.0:
            raise OutputValidationError(
                "invalid_confidence",
                "confidence must lie in [0, 1]",
            )

    expected_rollout = {
        int(item["horizon"]): item
        for item in expected.get("rollout", [])
    }
    rollout_payload = payload["rollout"]
    if not isinstance(rollout_payload, list):
        raise OutputValidationError("type_error", "rollout must be a list")
    if len(rollout_payload) != len(expected_rollout):
        raise OutputValidationError(
            "rollout_horizons",
            "rollout length differs from the requested horizon set",
        )
    parsed_rollout: dict[int, RolloutPrediction] = {}
    for item in rollout_payload:
        if not isinstance(item, dict) or set(item) != ROLLOUT_KEYS:
            raise OutputValidationError(
                "rollout_keys",
                f"each rollout item must have keys {sorted(ROLLOUT_KEYS)}",
            )
        horizon = item["horizon"]
        if isinstance(horizon, bool) or not isinstance(horizon, int):
            raise OutputValidationError("type_error", "rollout horizon must be integer")
        if horizon in parsed_rollout or horizon not in expected_rollout:
            raise OutputValidationError(
                "rollout_horizons",
                f"unexpected or duplicate rollout horizon {horizon}",
            )
        exemplar = expected_rollout[horizon]
        _validate_shape(
            item["physical_delta"],
            exemplar["physical_delta"],
            component="physical_delta",
        )
        _validate_shape(
            item["event_record"],
            exemplar["event_record"],
            component="event_record",
        )
        parsed_rollout[horizon] = RolloutPrediction(
            horizon=horizon,
            physical_delta=item["physical_delta"],
            event_record=item["event_record"],
        )
    if set(parsed_rollout) != set(expected_rollout):
        raise OutputValidationError(
            "rollout_horizons",
            "rollout horizons differ from the requested horizon set",
        )
    return ParsedModelOutput(
        one_step=Prediction(
            physical_delta=payload["physical_delta"],
            event_record=payload["event_record"],
            normative_decision=decision,
            escalation_required=escalation,
            confidence=confidence,
        ),
        rollout=parsed_rollout,
    )


def parse_model_output(
    text: str,
    expected: dict[str, Any],
) -> ParseResult:
    """Parse one strict JSON output; failures remain explicit observations."""

    try:
        payload = json.loads(_unwrap(text))
    except json.JSONDecodeError as error:
        return ParseResult(
            ok=False,
            output=None,
            error_code="invalid_json",
            error_detail=str(error),
        )
    try:
        output = _validate_payload(payload, expected)
    except OutputValidationError as error:
        return ParseResult(
            ok=False,
            output=None,
            error_code=error.code,
            error_detail=error.detail,
        )
    return ParseResult(ok=True, output=output)


def parse_factual_output(
    text: str,
    expected: dict[str, Any],
) -> tuple[ParsedFactualOutput | None, str | None]:
    """Parse the evaluator-blind component of the factorized arm."""

    try:
        payload = json.loads(_unwrap(text))
    except json.JSONDecodeError:
        return None, "invalid_json"
    required = {"physical_delta", "event_record", "rollout"}
    if not isinstance(payload, dict) or set(payload) != required:
        return None, "top_level_keys"
    try:
        _validate_shape(
            payload["physical_delta"],
            expected["physical_delta"],
            component="physical_delta",
        )
        _validate_shape(
            payload["event_record"],
            expected["event_record"],
            component="event_record",
        )
        if payload["rollout"] != [] or expected.get("rollout", []) != []:
            raise OutputValidationError(
                "rollout_horizons",
                "factorized local pilot currently requires an empty rollout",
            )
    except OutputValidationError as error:
        return None, error.code
    return (
        ParsedFactualOutput(
            physical_delta=payload["physical_delta"],
            event_record=payload["event_record"],
            rollout={},
        ),
        None,
    )


def parse_normative_output(
    text: str,
) -> tuple[ParsedNormativeOutput | None, str | None]:
    """Parse the normative-only component of the factorized arm."""

    try:
        payload = json.loads(_unwrap(text))
    except json.JSONDecodeError:
        return None, "invalid_json"
    required = {"normative_decision", "escalation_required"}
    if not isinstance(payload, dict) or set(payload) != required:
        return None, "top_level_keys"
    decision = payload["normative_decision"]
    escalation = payload["escalation_required"]
    if decision not in DECISIONS:
        return None, "decision_value"
    if not isinstance(escalation, bool):
        return None, "type_error"
    if escalation != (decision == "escalate"):
        return None, "decision_consistency"
    return ParsedNormativeOutput(decision, escalation), None


def combine_factorized_output(
    factual: ParsedFactualOutput,
    normative: ParsedNormativeOutput,
) -> ParsedModelOutput:
    return ParsedModelOutput(
        one_step=Prediction(
            physical_delta=factual.physical_delta,
            event_record=factual.event_record,
            normative_decision=normative.normative_decision,
            escalation_required=normative.escalation_required,
        ),
        rollout=factual.rollout,
    )
