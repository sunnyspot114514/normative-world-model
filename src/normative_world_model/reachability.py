"""Exhaustive uncertainty reachability table generated from live contracts."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from .normative_oracle import load_profiles


def enumerate_reachability(maximum_required: int = 5) -> list[dict[str, Any]]:
    profiles = load_profiles()
    rows: list[dict[str, Any]] = []
    for required in range(1, maximum_required + 1):
        for policy_minimum in range(0, min(2, required) + 1):
            for observed in range(0, required + 1):
                missing = required - observed
                for conflicting in (False, True):
                    uncertainty = min(
                        Fraction(1),
                        Fraction(4, 5) * Fraction(missing, required)
                        + Fraction(1, 5) * int(conflicting),
                    )
                    minimum_present = observed >= policy_minimum
                    escalating = [
                        profile_id
                        for profile_id, profile in profiles.items()
                        if float(uncertainty) >= profile.uncertainty_escalate_at
                    ]
                    rows.append(
                        {
                            "required": required,
                            "observed": observed,
                            "policy_minimum": policy_minimum,
                            "missing": missing,
                            "conflicting": conflicting,
                            "uncertainty_fraction": str(uncertainty),
                            "uncertainty": round(float(uncertainty), 6),
                            "minimum_evidence_present": minimum_present,
                            "hard_violation": not minimum_present,
                            "escalating_profiles": escalating,
                        }
                    )
    return rows


def adjacent_no_conflict_witnesses(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    profiles = sorted(
        load_profiles().values(), key=lambda profile: profile.uncertainty_escalate_at
    )
    witnesses: dict[str, list[dict[str, Any]]] = {}
    for left, right in zip(profiles[:-1], profiles[1:], strict=True):
        key = f"{left.profile_id}|{right.profile_id}"
        witnesses[key] = [
            row
            for row in rows
            if not row["hard_violation"]
            and not row["conflicting"]
            and left.uncertainty_escalate_at
            <= row["uncertainty"]
            < right.uncertainty_escalate_at
        ]
    return witnesses


def render_reachability_markdown(rows: list[dict[str, Any]]) -> str:
    witnesses = adjacent_no_conflict_witnesses(rows)
    lines = [
        "# Uncertainty reachability",
        "",
        "Generated from the frozen uncertainty formula and evaluator profile thresholds.",
        "Only rows satisfying the policy minimum are program-reachable in the discretionary layer.",
        "",
        "## Adjacent-threshold no-conflict witnesses",
        "",
        "| Profile pair | required | observed | policy minimum | uncertainty |",
        "|---|---:|---:|---:|---:|",
    ]
    for pair, candidates in witnesses.items():
        if not candidates:
            lines.append(f"| {pair} | MISSING | MISSING | MISSING | MISSING |")
            continue
        row = candidates[0]
        lines.append(
            f"| {pair} | {row['required']} | {row['observed']} | "
            f"{row['policy_minimum']} | {row['uncertainty']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Full table",
            "",
            "| required | observed | minimum | conflict | uncertainty | hard | escalating profiles |",
            "|---:|---:|---:|:---:|---:|:---:|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['required']} | {row['observed']} | {row['policy_minimum']} | "
            f"{str(row['conflicting']).lower()} | {row['uncertainty']:.6f} | "
            f"{str(row['hard_violation']).lower()} | "
            f"{', '.join(row['escalating_profiles']) or 'none'} |"
        )
    return "\n".join(lines) + "\n"
