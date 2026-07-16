"""Single comparison contract for one-step, paired, and rollout metrics."""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

COMPARATOR_VERSION = "2.1-candidate"
CONTINUOUS_ABS_TOLERANCE = Decimal("0.005")
_DECIMAL_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_EVENT_CONTINUOUS_FIELDS = {"reversibility", "recovery_cost", "uncertainty"}


def parse_finite_decimal(value: Any) -> Decimal:
    """Normalize model numeric spellings such as 0.1, 0.10, and .1."""

    if isinstance(value, bool):
        raise ValueError("booleans are not continuous numeric predictions")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite numeric prediction")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        result = Decimal(str(value))
    elif isinstance(value, str) and _DECIMAL_PATTERN.fullmatch(value.strip()):
        try:
            result = Decimal(value.strip())
        except InvalidOperation as error:
            raise ValueError("invalid decimal prediction") from error
    else:
        raise ValueError("continuous prediction must be a finite decimal")
    if not result.is_finite():
        raise ValueError("non-finite numeric prediction")
    return result


def continuous_equal(left: Any, right: Any) -> bool:
    """Inclusive boundary: an absolute distance of exactly 0.005 is equal."""

    try:
        return abs(parse_finite_decimal(left) - parse_finite_decimal(right)) <= CONTINUOUS_ABS_TOLERANCE
    except ValueError:
        return False


def _event_values_equal(left: Any, right: Any, path: tuple[str, ...]) -> bool:
    if (
        path
        and not isinstance(left, (dict, list))
        and (path[-1] in _EVENT_CONTINUOUS_FIELDS or "impact_vector" in path)
    ):
        return continuous_equal(left, right)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _event_values_equal(left[key], right[key], (*path, key)) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _event_values_equal(a, b, (*path, str(index)))
            for index, (a, b) in enumerate(zip(left, right, strict=True))
        )
    return left == right


def event_records_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Comparator used by correctness, invariance, and every rollout horizon."""

    return _event_values_equal(left, right, ())


def physical_deltas_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Physical state deltas are discrete and therefore remain exact."""

    return left == right
