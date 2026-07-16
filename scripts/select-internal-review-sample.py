"""Select a deterministic, coverage-augmented sample for human smoke review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


KNOWN_GRAMMAR_PATTERNS = {
    "count_agreement": re.compile(r"\bone (?:clues|records|stakeholders)\b", re.IGNORECASE),
    "subject_verb_agreement": re.compile(r"\bone stakeholders are\b", re.IGNORECASE),
    "profile_sentence_case": re.compile(
        r"\bFor the [^,]+ evaluator,\s+The\b"
    ),
    "malformed_action_phrase": re.compile(
        r"\b(?:plan to (?:disclose|intervene|promise|allocate resource) for the|"
        r"proposes the \w+ (?:disclose|intervene|promise|allocate resource) "
        r"concerning the|proposes to (?:read or write file|spend budget|"
        r"send external message|deploy or delete) across the|"
        r"suggests the \w+ (?:read or write file|spend budget|"
        r"send external message|deploy or delete) for the|permitted acts are|"
        r"the role permits (?:read or write file|spend budget|"
        r"send external message|deploy or delete))\b",
        re.IGNORECASE,
    ),
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _rank(scenario_id: str) -> str:
    return hashlib.sha256(scenario_id.encode("utf-8")).hexdigest()


def _select_lowest(
    buckets: dict[str, list[dict[str, Any]]],
    selected: dict[str, set[str]],
) -> None:
    for reason, rows in sorted(buckets.items()):
        row = min(rows, key=lambda item: (_rank(item["scenario_id"]), item["scenario_id"]))
        selected[row["scenario_id"]].add(reason)


def _grammar_findings(row: dict[str, Any]) -> list[str]:
    texts = [
        surface["natural_language"]
        for surface in row["surface_twins"]
    ]
    for twin in row["evaluator_twins"].values():
        texts.extend(twin["natural_language_profile_shams"])
    return sorted(
        name
        for name, pattern in KNOWN_GRAMMAR_PATTERNS.items()
        if any(pattern.search(text) for text in texts)
    )


def _summary(row: dict[str, Any], reasons: set[str]) -> dict[str, Any]:
    evaluations = row["primary"]["evaluations"]
    return {
        "scenario_id": row["scenario_id"],
        "selection_rank_sha256": _rank(row["scenario_id"]),
        "selection_reasons": sorted(reasons),
        "environment": row["environment"],
        "split": row["split"],
        "action_family": row["source"]["action"]["family"],
        "hard_violations": row["primary"]["policy_result"]["hard_violations"],
        "evaluator_decisions": {
            profile: result["decision"]
            for profile, result in evaluations.items()
        },
        "evaluator_reasons": {
            profile: result["reason"]
            for profile, result in evaluations.items()
        },
        "score_margins": {
            profile: result["score_margin_to_boundary"]
            for profile, result in evaluations.items()
        },
        "actor_twin_changes_physical_result": (
            row["actor_value_twin"]["result"]["physical_delta"]
            != row["primary"]["physical_delta"]
        ),
        "grammar_findings": _grammar_findings(row),
        "natural_language_surfaces": [
            surface["natural_language"]
            for surface in row["surface_twins"]
        ],
        "profile_shams": {
            profile: twin["natural_language_profile_shams"]
            for profile, twin in row["evaluator_twins"].items()
        },
    }


def select_review_sample(
    data_dir: Path,
    *,
    base_per_environment: int,
) -> dict[str, Any]:
    rows = []
    for environment in ("game", "organization"):
        rows.extend(_load_jsonl(data_dir / f"{environment}.jsonl"))

    selected: dict[str, set[str]] = defaultdict(set)
    rows_by_id = {row["scenario_id"]: row for row in rows}

    for environment in ("game", "organization"):
        environment_rows = [
            row for row in rows if row["environment"] == environment
        ]
        for row in sorted(
            environment_rows,
            key=lambda item: (_rank(item["scenario_id"]), item["scenario_id"]),
        )[:base_per_environment]:
            selected[row["scenario_id"]].add(f"hash_sample:{environment}")

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_boundary_count = 0
    unchanged_actor_twin_count = 0
    grammar_warning_count = 0
    for row in rows:
        environment = row["environment"]
        buckets[f"coverage:environment={environment}"].append(row)
        buckets[f"coverage:{environment}:split={row['split']}"].append(row)
        buckets[
            f"coverage:{environment}:action={row['source']['action']['family']}"
        ].append(row)

        hard_violations = row["primary"]["policy_result"]["hard_violations"]
        if not hard_violations:
            buckets[f"coverage:{environment}:hard_policy=none"].append(row)
        for violation in hard_violations:
            buckets[f"coverage:{environment}:hard_policy={violation}"].append(row)

        decisions = {
            result["decision"]
            for result in row["primary"]["evaluations"].values()
        }
        uncertainty_reason_present = False
        for profile, result in row["primary"]["evaluations"].items():
            buckets[
                f"coverage:{environment}:evaluator_reason={result['reason']}"
            ].append(row)
            if result["reason"] == "uncertainty_band":
                uncertainty_reason_present = True
            if result["score_margin_to_boundary"] == 0.0:
                selected[row["scenario_id"]].add(
                    f"exact_boundary:{profile}"
                )
                exact_boundary_count += 1
        if uncertainty_reason_present and len(decisions) > 1:
            buckets[f"coverage:{environment}:uncertainty_disagreement"].append(row)

        if (
            row["actor_value_twin"]["result"]["physical_delta"]
            == row["primary"]["physical_delta"]
        ):
            selected[row["scenario_id"]].add("actor_twin_physical_unchanged")
            unchanged_actor_twin_count += 1

        findings = _grammar_findings(row)
        if findings:
            grammar_warning_count += 1
            for finding in findings:
                selected[row["scenario_id"]].add(f"grammar_warning:{finding}")

    _select_lowest(buckets, selected)
    sample = [
        _summary(rows_by_id[scenario_id], reasons)
        for scenario_id, reasons in sorted(
            selected.items(),
            key=lambda item: (_rank(item[0]), item[0]),
        )
    ]
    return {
        "status": "READY_FOR_HUMAN_REVIEW",
        "data_scope": data_dir.as_posix(),
        "selection_rule": (
            "lowest sha256(scenario_id) base sample plus deterministic coverage "
            "buckets and all boundary/unchanged-actor/grammar exceptions"
        ),
        "base_per_environment": base_per_environment,
        "total_corpus_rows": len(rows),
        "selected_row_count": len(sample),
        "exact_boundary_assertion_count": exact_boundary_count,
        "actor_twin_physical_unchanged_count": unchanged_actor_twin_count,
        "grammar_warning_row_count": grammar_warning_count,
        "rows": sample,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/phase1_v3_smoke"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/phase1_v3_smoke/deterministic_review_sample.json"
        ),
    )
    parser.add_argument("--base-per-environment", type=int, default=8)
    args = parser.parse_args()
    if args.base_per_environment <= 0:
        parser.error("--base-per-environment must be positive")
    report = select_review_sample(
        args.data_dir,
        base_per_environment=args.base_per_environment,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
