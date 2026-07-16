"""Validation helpers for the shared cross-environment predicate contract."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def default_predicate_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "normative_predicates.toml"


def load_predicate_contract(path: Path | None = None) -> dict[str, Any]:
    config_path = path or default_predicate_path()
    with config_path.open("rb") as handle:
        return tomllib.load(handle)


def validate_predicate_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    predicate_names = set(contract.get("predicates", {}))
    if not predicate_names:
        return ["predicate contract defines no predicates"]

    dimensions = contract.get("impact_dimensions", {}).get("names", [])
    if not dimensions:
        failures.append("impact dimensions are missing")

    environments = contract.get("environments", {})
    for environment_id in ("game", "organization"):
        environment = environments.get(environment_id)
        if environment is None:
            failures.append(f"missing environment: {environment_id}")
            continue
        mapping_names = set(environment.get("mapping", {}))
        missing = predicate_names - mapping_names
        extra = mapping_names - predicate_names
        if missing:
            failures.append(f"{environment_id} missing mappings: {sorted(missing)}")
        if extra:
            failures.append(f"{environment_id} has unknown mappings: {sorted(extra)}")

    return failures

