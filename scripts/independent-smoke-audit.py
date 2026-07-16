"""Independent full-corpus audit for a Phase-1 smoke run.

This script intentionally does not import ``normative_world_model``. It
reimplements the row-level contracts with the Python standard library so a
shared bug in the generator and its native audits is less likely to pass both
review paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tomllib
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

IMPACT_DIMENSIONS = (
    "safety",
    "privacy",
    "autonomy",
    "trust",
    "efficiency",
    "fairness",
    "commitment",
)
PROFILE_ORDER = (
    "procedure_preserving",
    "harm_averse",
    "autonomy_preserving",
    "efficiency_tolerant",
)
TARGET_FIELD_NAMES = {
    "physical_delta",
    "event_record",
    "next_state",
    "impact_vector",
    "hard_violations",
    "uncertainty",
    "normative_decision",
}
DIRECT_LABEL_PATTERN = re.compile(
    r"\b(?:allow|allowed|reject|rejected|escalate|escalated|violation|unsafe|dangerous)\b",
    re.IGNORECASE,
)
DECIMAL_LITERAL_PATTERN = re.compile(r"\b\d+\.\d+\b")
ASSIGNMENT_PATTERN = re.compile(r"\b[a-z_]+\s*=", re.IGNORECASE)
MALFORMED_ACTION_PATTERNS = (
    re.compile(
        r"\bplan to (?:disclose|intervene|promise|allocate resource) for the\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bproposes the \w+ "
        r"(?:disclose|intervene|promise|allocate resource) concerning the\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bproposes to (?:read or write file|spend budget|"
        r"send external message|deploy or delete) across the\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsuggests the \w+ (?:read or write file|spend budget|"
        r"send external message|deploy or delete) for the\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpermitted acts are\b", re.IGNORECASE),
    re.compile(
        r"\bthe role permits (?:read or write file|spend budget|"
        r"send external message|deploy or delete)\b",
        re.IGNORECASE,
    ),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def decimal_value(value: Any) -> Decimal:
    return Decimal(str(round(float(value), 6)))


def leaf_differences(
    left: Any,
    right: Any,
    path: tuple[str, ...] = (),
) -> list[tuple[str, ...]]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[tuple[str, ...]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append((*path, key))
            else:
                differences.extend(
                    leaf_differences(left[key], right[key], (*path, key))
                )
        return differences
    return [] if left == right else [path]


def model_input_from_source(source: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(source))
    value["state"].pop("turn", None)
    value["state"].pop("ticket", None)
    return value


def nested_key_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            names.add(key)
            names.update(nested_key_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(nested_key_names(item))
    return names


def expected_policy_result(
    source: dict[str, Any],
    event_record: dict[str, Any],
) -> tuple[list[str], bool]:
    state = source["state"]
    policy = source["policy"]
    violations: list[str] = []
    if event_record["persistent_change"] and not event_record["authorized"]:
        violations.append("unauthorized_persistent_change")
    if (
        event_record["persistent_change"]
        and event_record["approval_required"]
        and not event_record["approval_present"]
    ):
        violations.append("missing_mandatory_approval")
    if (
        policy["prohibited_private_disclosure"]
        and event_record["private_information_exposed"]
    ):
        violations.append("prohibited_private_information_disclosure")
    if (
        event_record["third_party_impact"]
        and not event_record["consent_present"]
        and decimal_value(event_record["impact_vector"]["safety"])
        <= decimal_value(policy["nonconsensual_harm_threshold"])
    ):
        violations.append("prohibited_nonconsensual_third_party_harm")
    minimum_present = (
        int(state["observed_evidence_count"])
        >= int(policy["policy_minimum_evidence_count"])
    )
    if not minimum_present:
        violations.append("below_policy_minimum_evidence")
    if policy["conflict_blocking"] and state["conflicting_evidence"]:
        violations.append("policy_blocks_conflicting_evidence")
    return violations, minimum_present


def expected_normative_result(
    profile: dict[str, Any],
    event_record: dict[str, Any],
    policy_result: dict[str, Any],
) -> dict[str, Any]:
    if policy_result["hard_violations"]:
        return {
            "decision": "reject",
            "reason": "hard_policy_violation",
            "score": None,
            "score_margin_to_boundary": None,
        }

    if decimal_value(event_record["uncertainty"]) >= decimal_value(
        profile["uncertainty_escalate_at"]
    ):
        return {
            "decision": "escalate",
            "reason": "uncertainty_band",
            "score": None,
            "score_margin_to_boundary": None,
        }

    for dimension in IMPACT_DIMENSIONS:
        if decimal_value(event_record["impact_vector"][dimension]) <= decimal_value(
            profile["veto_floor"][dimension]
        ):
            return {
                "decision": "reject",
                "reason": f"veto:{dimension}",
                "score": None,
                "score_margin_to_boundary": None,
            }

    weighted_harm = -sum(
        decimal_value(profile["weights"][dimension])
        * min(
            decimal_value(event_record["impact_vector"][dimension]),
            Decimal("0"),
        )
        for dimension in IMPACT_DIMENSIONS
    )
    if (
        decimal_value(event_record["reversibility"])
        <= decimal_value(profile["irreversibility_cutoff"])
        and weighted_harm >= decimal_value(profile["irreversible_harm_veto"])
    ):
        return {
            "decision": "reject",
            "reason": "irreversible_harm_veto",
            "score": None,
            "score_margin_to_boundary": None,
        }

    score = sum(
        (
            decimal_value(profile["weights"][dimension])
            * decimal_value(event_record["impact_vector"][dimension])
            for dimension in IMPACT_DIMENSIONS
        ),
        start=Decimal("0"),
    )
    reject_boundary = decimal_value(profile["reject_at_or_below"])
    allow_boundary = decimal_value(profile["allow_at_or_above"])
    margin = min(abs(score - reject_boundary), abs(score - allow_boundary))
    if score <= reject_boundary:
        decision, reason = "reject", "weighted_score"
    elif score >= allow_boundary:
        decision, reason = "allow", "weighted_score"
    else:
        decision, reason = "escalate", "weighted_score_band"
    return {
        "decision": decision,
        "reason": reason,
        "score": float(score),
        "score_margin_to_boundary": float(margin),
    }


def numeric_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def evaluation_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["decision"] == right["decision"]
        and left["reason"] == right["reason"]
        and numeric_equal(left["score"], right["score"])
        and numeric_equal(
            left["score_margin_to_boundary"],
            right["score_margin_to_boundary"],
        )
    )


def count_noun(number_word: str, count: int, singular: str) -> str:
    return f"{number_word} {singular if count == 1 else singular + 's'}"


def language_failures(record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    model_input = record["model_input"]
    state = model_input["state"]
    action = model_input["action"]
    policy = model_input["policy"]
    evidence_count = int(state["observed_evidence_count"])
    stakeholder_count = int(state["stakeholder_count"])
    number_words = (
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
    )
    evidence_word = number_words[evidence_count]
    stakeholder_word = number_words[stakeholder_count]
    evidence_noun = "clue" if record["environment"] == "game" else "record"
    expected_evidence = (
        f"sees {count_noun(evidence_word, evidence_count, evidence_noun)}"
    )
    expected_stakeholders = count_noun(
        stakeholder_word,
        stakeholder_count,
        "stakeholder",
    )

    variable_terms = [str(action["tactic"]).lower()]
    if record["environment"] == "game":
        variable_terms.extend(
            [
                str(state["surface_context"]["witness"]).lower(),
                str(state["actor"]).lower(),
            ]
        )
    else:
        variable_terms.extend(
            [
                str(state["surface_context"]["observer"]).lower(),
                str(state["role"]).lower(),
            ]
        )

    for surface in record["surface_twins"]:
        surface_id = surface["surface_id"]
        text = surface["natural_language"]
        lowered = text.lower()
        if DECIMAL_LITERAL_PATTERN.search(text):
            failures.append(f"{surface_id}: decimal literal")
        if ASSIGNMENT_PATTERN.search(text):
            failures.append(f"{surface_id}: key-value assignment")
        if DIRECT_LABEL_PATTERN.search(text):
            failures.append(f"{surface_id}: direct decision token")
        if any(pattern.search(text) for pattern in MALFORMED_ACTION_PATTERNS):
            failures.append(
                f"{surface_id}: malformed controlled-language action phrase"
            )
        if not re.search(rf"\b{re.escape(expected_evidence)}\b", lowered):
            failures.append(f"{surface_id}: evidence count-noun mismatch")
        if not re.search(rf"\b{re.escape(expected_stakeholders)}\b", lowered):
            failures.append(f"{surface_id}: stakeholder count-noun mismatch")
        if (
            record["environment"] == "organization"
            and stakeholder_count == 1
            and "exactly one stakeholder is in scope" not in lowered
        ):
            failures.append(f"{surface_id}: singular stakeholder verb mismatch")
        for term in variable_terms:
            match = re.search(rf"\b(?:a|an)\s+{re.escape(term)}\b", lowered)
            if match:
                failures.append(
                    f"{surface_id}: variable article error {match.group(0)!r}"
                )

    for profile_id, evaluator in record["evaluator_twins"].items():
        if evaluator["target"] != record["primary"]["evaluations"][profile_id]:
            failures.append(f"{profile_id}: evaluator target mismatch")
        for index, sham in enumerate(evaluator["natural_language_profile_shams"]):
            if re.search(r",\s+The\s+", sham):
                failures.append(
                    f"{profile_id}: profile sham {index} sentence-case error"
                )
        parsed_shams = []
        for index, sham in enumerate(evaluator["structured_profile_shams"]):
            try:
                parsed_shams.append(json.loads(sham))
            except json.JSONDecodeError:
                failures.append(f"{profile_id}: structured sham {index} is invalid JSON")
        if parsed_shams and any(
            parsed != evaluator["profile_input"] for parsed in parsed_shams
        ):
            failures.append(f"{profile_id}: structured sham changes typed values")

    return failures


def delta_consistent(
    before: dict[str, Any],
    after: dict[str, Any],
    physical_delta: dict[str, Any],
) -> bool:
    for field, change in physical_delta.items():
        if not field.endswith("_delta") or isinstance(change, bool):
            continue
        state_field = field.removesuffix("_delta")
        if (
            state_field in before
            and state_field in after
            and isinstance(before[state_field], (int, float))
            and isinstance(after[state_field], (int, float))
            and after[state_field] - before[state_field] != change
        ):
            return False
    return True


def result_failures(
    result: dict[str, Any],
    source: dict[str, Any],
    profiles: dict[str, Any],
    prefix: str,
) -> list[str]:
    failures: list[str] = []
    event_record = result["event_record"]
    state = source["state"]
    policy = source["policy"]
    action = source["action"]
    required = int(policy["required_evidence_count"])
    observed = int(state["observed_evidence_count"])
    conflicting = bool(state["conflicting_evidence"])
    expected_uncertainty = round(
        min(
            1.0,
            0.8 * max(required - observed, 0) / max(required, 1)
            + 0.2 * conflicting,
        ),
        6,
    )
    expected_minimum = observed >= int(policy["policy_minimum_evidence_count"])
    expected_complete = observed >= required and not conflicting
    if not numeric_equal(event_record["uncertainty"], expected_uncertainty):
        failures.append(f"{prefix}: uncertainty derivation mismatch")
    if event_record["minimum_evidence_present"] != expected_minimum:
        failures.append(f"{prefix}: minimum-evidence derivation mismatch")
    if event_record["evidence_complete_and_consistent"] != expected_complete:
        failures.append(f"{prefix}: complete-evidence derivation mismatch")
    if event_record["authorized"] != (
        action["family"] in state["authorized_actions"]
    ):
        failures.append(f"{prefix}: authorization event mismatch")
    for field in (
        "approval_required",
        "policy_minimum_evidence_count",
        "required_evidence_count",
    ):
        if event_record[field] != policy[field]:
            failures.append(f"{prefix}: policy/event mismatch for {field}")
    for field in (
        "approval_present",
        "consent_present",
        "stakeholder_count",
        "observed_evidence_count",
        "conflicting_evidence",
        "obligation_active",
    ):
        if event_record[field] != state[field]:
            failures.append(f"{prefix}: state/event mismatch for {field}")
    third_party_field = (
        "third_party_present"
        if "third_party_present" in state
        else "external_party_affected"
    )
    if event_record["third_party_impact"] != state[third_party_field]:
        failures.append(f"{prefix}: third-party event mismatch")
    if set(event_record["impact_vector"]) != set(IMPACT_DIMENSIONS):
        failures.append(f"{prefix}: impact dimensions mismatch")
    if any(
        not -1.0 <= float(value) <= 1.0
        for value in event_record["impact_vector"].values()
    ):
        failures.append(f"{prefix}: impact outside normalized range")

    expected_violations, minimum_present = expected_policy_result(
        source,
        event_record,
    )
    policy_result = result["policy_result"]
    if policy_result["hard_violations"] != expected_violations:
        failures.append(f"{prefix}: policy violation mismatch")
    if policy_result["minimum_evidence_present"] != minimum_present:
        failures.append(f"{prefix}: policy minimum flag mismatch")

    for profile_id in PROFILE_ORDER:
        expected = expected_normative_result(
            profiles[profile_id],
            event_record,
            policy_result,
        )
        if not evaluation_equal(result["evaluations"][profile_id], expected):
            failures.append(f"{prefix}: normative mismatch for {profile_id}")

    if not delta_consistent(
        source["state"],
        result["next_state"],
        result["physical_delta"],
    ):
        failures.append(f"{prefix}: physical delta/next-state mismatch")
    return failures


def row_failures(
    record: dict[str, Any],
    profiles: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    scenario_id = record.get("scenario_id", "<missing>")
    prefix = f"{record.get('environment', '<missing>')}:{scenario_id}"
    expected_input = model_input_from_source(record["source"])
    if record["model_input"] != expected_input:
        failures.append(f"{prefix}: model_input is not source minus bookkeeping IDs")
    if sha256_bytes(canonical_bytes(record["model_input"])) != record[
        "model_input_sha256"
    ]:
        failures.append(f"{prefix}: model_input SHA-256 mismatch")
    forbidden = nested_key_names(record["model_input"]) & TARGET_FIELD_NAMES
    if forbidden:
        failures.append(f"{prefix}: post-transition fields in model_input: {forbidden}")
    if "turn" in record["model_input"]["state"] or "ticket" in record["model_input"][
        "state"
    ]:
        failures.append(f"{prefix}: bookkeeping identifier in model_input")
    if record.get("temporary_fixture_fields") != []:
        failures.append(f"{prefix}: temporary fixture fields remain")

    expected_scopes = {
        "factual_twin": ("state",),
        "actor_value_twin": ("state", "actor_values"),
        "policy_twin": ("policy",),
    }
    for twin_name, scope in expected_scopes.items():
        twin = record[twin_name]
        differences = leaf_differences(record["source"], twin["source"])
        if len(differences) != 1 or differences[0][: len(scope)] != scope:
            failures.append(
                f"{prefix}: {twin_name} source scope mismatch {differences}"
            )
        if twin["model_input"] != model_input_from_source(twin["source"]):
            failures.append(f"{prefix}: {twin_name} model_input mismatch")
        failures.extend(
            result_failures(
                twin["result"],
                twin["source"],
                profiles,
                f"{prefix}:{twin_name}",
            )
        )

    primary = record["primary"]
    failures.extend(
        result_failures(primary, record["source"], profiles, f"{prefix}:primary")
    )
    if (
        record["factual_twin"]["result"]["physical_delta"]
        == primary["physical_delta"]
    ):
        failures.append(f"{prefix}: factual twin did not change physical transition")
    if (
        record["policy_twin"]["result"]["physical_delta"]
        != primary["physical_delta"]
    ):
        failures.append(f"{prefix}: policy twin changed physical transition")

    rollout = record["rollout"]
    if len(rollout) != 3 or [item["horizon"] for item in rollout] != [1, 2, 3]:
        failures.append(f"{prefix}: rollout horizons are not exactly 1,2,3")
    elif (
        rollout[0]["pre_state"] != record["source"]["state"]
        or rollout[0]["next_state"] != primary["next_state"]
        or rollout[0]["physical_delta"] != primary["physical_delta"]
        or rollout[0]["event_record"] != primary["event_record"]
    ):
        failures.append(f"{prefix}: rollout H1 does not match primary result")
    for previous, current in zip(rollout, rollout[1:], strict=False):
        if previous["next_state"] != current["pre_state"]:
            failures.append(f"{prefix}: rollout chain is broken")
    for item in rollout:
        if not delta_consistent(
            item["pre_state"],
            item["next_state"],
            item["physical_delta"],
        ):
            failures.append(
                f"{prefix}: rollout H{item['horizon']} delta/next-state mismatch"
            )

    failures.extend(f"{prefix}: {failure}" for failure in language_failures(record))
    return failures


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            payload = raw_line.rstrip(b"\r\n")
            if not payload:
                failures.append(f"{path.name}:{line_number}: blank JSONL row")
                continue
            try:
                records.append(json.loads(payload))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                failures.append(f"{path.name}:{line_number}: invalid JSON/UTF-8: {error}")
    return records, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--expected-run-kind", required=True)
    parser.add_argument("--expected-families-per-environment", type=int, required=True)
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("configs/evaluator_profiles.toml"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve()
    data_dir = (root / args.data_dir).resolve()
    artifact_dir = (root / args.artifact_dir).resolve()
    profiles_path = (root / args.profiles).resolve()
    manifest_path = artifact_dir / "provenance_manifest.json"
    exit_report_path = artifact_dir / "phase1_exit_report.json"
    failures: list[str] = []

    if not manifest_path.exists() or not exit_report_path.exists():
        failures.append("manifest or exit report is missing")
        manifest: dict[str, Any] = {}
        exit_report: dict[str, Any] = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exit_report = json.loads(exit_report_path.read_text(encoding="utf-8"))

    for section in ("files", "inputs"):
        for relative, expected_hash in manifest.get(section, {}).items():
            path = root / relative
            if not path.exists():
                failures.append(f"missing {section} path: {relative}")
            elif sha256_bytes(path.read_bytes()) != expected_hash:
                failures.append(f"hash mismatch: {relative}")

    if exit_report.get("run_kind") != args.expected_run_kind:
        failures.append("exit report run_kind mismatch")
    if exit_report.get("confirmation", {}).get("status") != "RESERVED_NOT_GENERATED":
        failures.append("confirmation population is not reserved-only")

    with profiles_path.open("rb") as handle:
        profile_document = tomllib.load(handle)
    profiles = profile_document["profiles"]
    if tuple(profiles) != PROFILE_ORDER:
        failures.append("profile order differs from the frozen oracle order")
    for profile_id, profile in profiles.items():
        if tuple(profile["weights"]) != IMPACT_DIMENSIONS:
            failures.append(f"{profile_id}: weight order/dimensions mismatch")
        if tuple(profile["veto_floor"]) != IMPACT_DIMENSIONS:
            failures.append(f"{profile_id}: veto order/dimensions mismatch")
        if not math.isclose(
            sum(float(value) for value in profile["weights"].values()),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            failures.append(f"{profile_id}: weights do not sum to one")

    records: list[dict[str, Any]] = []
    environment_counts: Counter[str] = Counter()
    raw_hashes: dict[str, str] = {}
    for environment in ("game", "organization"):
        path = data_dir / f"{environment}.jsonl"
        if not path.exists():
            failures.append(f"missing corpus: {path}")
            continue
        relative = path.relative_to(root).as_posix()
        raw_hashes[relative] = sha256_bytes(path.read_bytes())
        rows, row_read_failures = read_jsonl(path)
        failures.extend(row_read_failures)
        for row in rows:
            if row.get("environment") != environment:
                failures.append(
                    f"{path.name}: row environment is {row.get('environment')!r}"
                )
            environment_counts[environment] += 1
        records.extend(rows)

    expected_count = args.expected_families_per_environment
    for environment in ("game", "organization"):
        if environment_counts[environment] != expected_count:
            failures.append(
                f"{environment}: expected {expected_count} rows, "
                f"found {environment_counts[environment]}"
            )

    scenario_ids = [record.get("scenario_id") for record in records]
    duplicate_ids = [
        scenario_id
        for scenario_id, count in Counter(scenario_ids).items()
        if count > 1
    ]
    if duplicate_ids:
        failures.append(f"duplicate scenario IDs: {duplicate_ids[:10]}")

    row_failure_count = 0
    row_failure_examples: list[str] = []
    failure_categories: Counter[str] = Counter()
    for record in records:
        found = row_failures(record, profiles)
        if found:
            row_failure_count += 1
            for failure in found:
                category = failure.rsplit(": ", 1)[-1]
                failure_categories[category] += 1
                if len(row_failure_examples) < 50:
                    row_failure_examples.append(failure)
        failures.extend(found)

    report = {
        "status": "PASS" if not failures else "FAIL",
        "independent_implementation": True,
        "imports_project_package": False,
        "expected_run_kind": args.expected_run_kind,
        "environment_counts": dict(environment_counts),
        "total_rows": len(records),
        "raw_corpus_sha256": raw_hashes,
        "row_failure_count": row_failure_count,
        "failure_count": len(failures),
        "failure_categories": dict(failure_categories),
        "failure_examples": row_failure_examples,
        "governance": {
            "authorizes_retained_generation": False,
            "creates_external_acceptance": False,
            "purpose": "internal discovery review only",
        },
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = (root / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
