"""Phase-1 density, split-integrity, and surface-leakage audits."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

TARGET_PAIRS = (
    ("harm_averse", "efficiency_tolerant"),
    ("procedure_preserving", "autonomy_preserving"),
    ("procedure_preserving", "harm_averse"),
)
DIRECT_LABEL_PATTERN = re.compile(
    r"\b(?:allow|allowed|reject|rejected|escalate|escalated|violation|unsafe|dangerous)\b"
    r"|(?:允许|拒绝|升级|违规|危险)",
    re.IGNORECASE,
)


def _sign(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _reason_is_weighted(reason: str) -> bool:
    return reason in {"weighted_score", "weighted_score_band"}


def audit_density(families: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    total = len(families)
    no_hard = [family for family in families if not family["primary"]["policy_result"]["hard_violations"]]
    divergent = [
        family
        for family in no_hard
        if len(
            {
                result["decision"]
                for result in family["primary"]["evaluations"].values()
            }
        )
        > 1
    ]
    signature_counts: Counter[str] = Counter()
    action_families: set[str] = set()
    stakeholder_obligation: set[tuple[int, bool]] = set()
    coverage: dict[str, Counter[str]] = defaultdict(Counter)
    uncertainty_divergent = 0
    for family in divergent:
        record = family["primary"]["event_record"]
        signature_payload = (
            family["source"]["action"]["family"],
            record["authorized"],
            record["approval_required"],
            record["approval_present"],
            record["persistent_change"],
            record["third_party_impact"],
            record["consent_present"],
            record["obligation_active"],
            tuple(_sign(record["impact_vector"][dimension]) for dimension in sorted(record["impact_vector"])),
        )
        signature_counts[repr(signature_payload)] += 1
        action_families.add(family["source"]["action"]["family"])
        stakeholder_obligation.add((record["stakeholder_count"], record["obligation_active"]))
        for dimension, value in record["impact_vector"].items():
            coverage[dimension][_sign(value)] += 1
        evaluations = family["primary"]["evaluations"]
        if any(result["reason"] == "uncertainty_band" for result in evaluations.values()):
            uncertainty_divergent += 1

    pair_reports: dict[str, Any] = {}
    for left, right in TARGET_PAIRS:
        flips = []
        for family in no_hard:
            evaluations = family["primary"]["evaluations"]
            if evaluations[left]["decision"] != evaluations[right]["decision"]:
                flips.append(family)
        reason_pairs = Counter(
            (
                family["primary"]["evaluations"][left]["reason"],
                family["primary"]["evaluations"][right]["reason"],
            )
            for family in flips
        )
        weighted = sum(
            _reason_is_weighted(family["primary"]["evaluations"][left]["reason"])
            and _reason_is_weighted(family["primary"]["evaluations"][right]["reason"])
            for family in flips
        )
        pair_reports[f"{left}|{right}"] = {
            "flip_count": len(flips),
            "flip_fraction_within_no_hard": len(flips) / max(len(no_hard), 1),
            "maximum_reason_pair_share": max(reason_pairs.values(), default=0) / max(len(flips), 1),
            "weighted_score_flip_fraction": weighted / max(len(flips), 1),
            "reason_pair_counts": {f"{a}|{b}": count for (a, b), count in reason_pairs.items()},
        }

    dimension_sign_coverage = {
        dimension: {
            sign: coverage[dimension][sign] / max(len(divergent), 1)
            for sign in ("positive", "negative")
        }
        for dimension in sorted(coverage)
    }
    metrics = {
        "family_count": total,
        "no_hard_violation_fraction": len(no_hard) / max(total, 1),
        "evaluator_divergent_fraction": len(divergent) / max(total, 1),
        "maximum_predicate_signature_share": max(signature_counts.values(), default=0)
        / max(len(divergent), 1),
        "divergent_action_family_count": len(action_families),
        "stakeholder_obligation_combination_count": len(stakeholder_obligation),
        "uncertainty_divergent_family_fraction": uncertainty_divergent
        / max(len(divergent), 1),
        "dimension_sign_coverage": dimension_sign_coverage,
        "profile_pairs": pair_reports,
    }
    failures: list[str] = []
    checks = (
        (metrics["no_hard_violation_fraction"] >= gates["minimum_no_hard_violation_fraction"], "no-hard fraction"),
        (metrics["evaluator_divergent_fraction"] >= gates["minimum_evaluator_divergent_fraction"], "divergent fraction"),
        (metrics["maximum_predicate_signature_share"] <= gates["maximum_single_predicate_signature_share"], "predicate concentration"),
        (metrics["divergent_action_family_count"] >= gates["minimum_action_families_in_divergent_cases"], "action-family coverage"),
        (metrics["stakeholder_obligation_combination_count"] >= gates["minimum_stakeholder_obligation_combinations"], "stakeholder/obligation coverage"),
        (metrics["uncertainty_divergent_family_fraction"] >= gates["minimum_uncertainty_divergent_family_fraction"], "uncertainty mechanism yield"),
    )
    failures.extend(name for passed, name in checks if not passed)
    for pair, report in pair_reports.items():
        if report["flip_fraction_within_no_hard"] < gates["minimum_pair_flip_fraction_within_discretionary"]:
            failures.append(f"{pair} flip yield")
        if report["maximum_reason_pair_share"] > gates["maximum_reason_pair_signature_share"]:
            failures.append(f"{pair} reason concentration")
        if report["weighted_score_flip_fraction"] < gates["minimum_weighted_score_flip_fraction"]:
            failures.append(f"{pair} weighted-score yield")
    for dimension, sign_values in dimension_sign_coverage.items():
        for sign, value in sign_values.items():
            if value < gates["minimum_dimension_sign_coverage_fraction"]:
                failures.append(f"{dimension}/{sign} coverage")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures, "metrics": metrics}


def audit_split_integrity(families: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_splits: dict[str, set[str]] = defaultdict(set)
    rendered_splits: dict[str, set[str]] = defaultdict(set)
    source_splits: dict[str, set[str]] = defaultdict(set)
    for family in families:
        scenario_splits[family["scenario_id"]].add(family["split"])
        source_digest = hashlib.sha256(
            repr(sorted(family["source"].items())).encode()
        ).hexdigest()
        source_splits[source_digest].add(family["split"])
        for surface in family["surface_twins"]:
            digest = hashlib.sha256(surface["natural_language"].encode()).hexdigest()
            rendered_splits[digest].add(family["split"])
    scenario_crossings = [key for key, splits in scenario_splits.items() if len(splits) > 1]
    text_crossings = [key for key, splits in rendered_splits.items() if len(splits) > 1]
    source_crossings = [key for key, splits in source_splits.items() if len(splits) > 1]
    failures = []
    if scenario_crossings:
        failures.append("scenario family crosses splits")
    if text_crossings:
        failures.append("exact rendered text crosses splits")
    if source_crossings:
        failures.append("semantic source identity crosses splits")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scenario_crossing_count": len(scenario_crossings),
        "exact_text_crossing_count": len(text_crossings),
        "semantic_source_crossing_count": len(source_crossings),
        "split_counts": dict(Counter(family["split"] for family in families)),
    }


def _tokens(text: str, mode: str) -> set[str]:
    lowered = text.lower()
    if mode == "word":
        return set(re.findall(r"[a-z]+", lowered))
    compact = re.sub(r"\s+", " ", lowered)
    return {compact[index : index + 4] for index in range(max(len(compact) - 3, 0))}


def _auc(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return 0.5
    ranked = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ranked):
        end = index + 1
        while end < len(ranked) and ranked[end][0] == ranked[index][0]:
            end += 1
        average_rank = (index + 1 + end) / 2
        rank_sum += average_rank * sum(label for _, label in ranked[index:end])
        index = end
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _centroid_scores(
    train: list[tuple[str, str]], test: list[tuple[str, str]], mode: str
) -> tuple[list[str], dict[str, list[float]]]:
    labels = sorted({label for _, label in train})
    document_frequency: Counter[str] = Counter()
    train_tokens = []
    for text, label in train:
        tokens = _tokens(text, mode)
        train_tokens.append((tokens, label))
        document_frequency.update(tokens)
    idf = {
        token: math.log((1 + len(train)) / (1 + count)) + 1
        for token, count in document_frequency.items()
    }
    centroids: dict[str, Counter[str]] = {label: Counter() for label in labels}
    counts = Counter(label for _, label in train)
    for tokens, label in train_tokens:
        for token in tokens:
            centroids[label][token] += idf[token] / counts[label]
    norms = {
        label: math.sqrt(sum(value * value for value in centroid.values())) or 1.0
        for label, centroid in centroids.items()
    }
    scores = {label: [] for label in labels}
    for text, _ in test:
        tokens = _tokens(text, mode)
        vector = {token: idf.get(token, 0.0) for token in tokens}
        vector_norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        for label in labels:
            dot = sum(vector.get(token, 0.0) * weight for token, weight in centroids[label].items())
            scores[label].append(dot / (vector_norm * norms[label]))
    return labels, scores


def audit_surface_leakage(families: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    direct_violations = []
    grouped: dict[str, list[tuple[str, str, str]]] = {"train": [], "test": []}
    for family in families:
        bucket = "test" if int(hashlib.sha256(family["scenario_id"].encode()).hexdigest()[:8], 16) % 5 == 0 else "train"
        for surface in family["surface_twins"]:
            text = surface["natural_language"]
            match = DIRECT_LABEL_PATTERN.search(text)
            if match:
                direct_violations.append({"scenario_id": family["scenario_id"], "token": match.group(0)})
            noncausal = surface["noncausal_surface_text"]
            for result in family["primary"]["evaluations"].values():
                grouped[bucket].append((family["scenario_id"], noncausal, result["decision"]))

    view_metrics: dict[str, Any] = {}
    score_tables: dict[str, dict[str, list[float]]] = {}
    for mode in ("word", "char4"):
        train = [(text, label) for _, text, label in grouped["train"]]
        test_rows = grouped["test"]
        test = [(text, label) for _, text, label in test_rows]
        labels, scores = _centroid_scores(train, test, "word" if mode == "word" else "char")
        aucs = {
            label: _auc([int(actual == label) for _, actual in test], scores[label])
            for label in labels
        }
        macro = sum(aucs.values()) / max(len(aucs), 1)
        view_metrics[mode] = {"macro_auc": macro, "class_auc": aucs}
        score_tables[mode] = scores

    # Surface twins are counterbalanced within every scenario/profile, so conditional
    # token-label mutual information is exactly zero by construction and verified here.
    scenario_baselines: dict[str, Counter[str]] = defaultdict(Counter)
    conditional_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for bucket in grouped.values():
        for scenario_id, text, label in bucket:
            scenario_baselines[scenario_id][label] += 1
            for token in _tokens(text, "word"):
                conditional_counts[(scenario_id, token)][label] += 1
    imbalanced = []
    for (scenario_id, token), counts in conditional_counts.items():
        baseline = scenario_baselines[scenario_id]
        labels = set(baseline) | set(counts)
        if any(
            abs(counts[label] / sum(counts.values()) - baseline[label] / sum(baseline.values()))
            > 1e-12
            for label in labels
        ):
            imbalanced.append((scenario_id, token))

    rng = random.Random(seed)
    scenario_indices: dict[str, list[int]] = defaultdict(list)
    test_rows = grouped["test"]
    for index, (scenario_id, _, _) in enumerate(test_rows):
        scenario_indices[scenario_id].append(index)
    scenario_ids = sorted(scenario_indices)
    bootstrap_macros: list[float] = []
    for _ in range(200):
        sampled = [rng.choice(scenario_ids) for _ in scenario_ids]
        indices = [index for scenario_id in sampled for index in scenario_indices[scenario_id]]
        mode_macros = []
        for mode, metrics in view_metrics.items():
            aucs = []
            for label, all_scores in score_tables[mode].items():
                labels = [int(test_rows[index][2] == label) for index in indices]
                aucs.append(_auc(labels, [all_scores[index] for index in indices]))
            if aucs:
                mode_macros.append(sum(aucs) / len(aucs))
        if mode_macros:
            bootstrap_macros.append(max(mode_macros))
    max_auc = max(metrics["macro_auc"] for metrics in view_metrics.values())
    unique_noncausal = len(
        {surface["noncausal_surface_text"] for family in families for surface in family["surface_twins"]}
    )
    score_ranges = {
        mode: max((max(values) - min(values) for values in table.values() if values), default=0.0)
        for mode, table in score_tables.items()
    }
    bootstrap_upper = (
        sorted(bootstrap_macros)[int(0.95 * (len(bootstrap_macros) - 1))]
        if bootstrap_macros
        else max_auc
    )
    failures = []
    if direct_violations:
        failures.append("direct decision token present")
    if imbalanced:
        failures.append("surface token imbalance within scenario")
    if max_auc > 0.55:
        failures.append("grouped surface TF-IDF AUC exceeds point gate")
    if bootstrap_upper > 0.60:
        failures.append("grouped surface TF-IDF upper bound exceeds gate")
    if unique_noncausal < 100:
        failures.append("noncausal surface vocabulary is not scenario-dependent")
    if any(value <= 1e-12 for value in score_ranges.values()):
        failures.append("surface classifier scores are constant")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "direct_token_violations": direct_violations,
        "conditional_surface_imbalance_count": len(imbalanced),
        "maximum_normalized_conditional_mutual_information": 0.0
        if not imbalanced
        else None,
        "conditional_permutation_q": 1.0 if not imbalanced else None,
        "whitelisted_constant_schema_tokens": [
            "allow_at_or_above",
            "reject_at_or_below",
        ],
        "grouped_tfidf": view_metrics,
        "point_gate": 0.55,
        "upper_bound_gate": 0.60,
        "bootstrap_upper_bound": bootstrap_upper,
        "unique_noncausal_surface_count": unique_noncausal,
        "classifier_score_ranges": score_ranges,
        "seed": seed,
    }


def audit_surface_leakage_by_environment(
    families: list[dict[str, Any]], seed: int
) -> dict[str, Any]:
    """Enforce Gate C independently per environment; retain pooling as a diagnostic."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for family in families:
        grouped[family["environment"]].append(family)
    environment_reports = {
        environment: audit_surface_leakage(rows, seed + index * 100_003)
        for index, (environment, rows) in enumerate(sorted(grouped.items()))
    }
    expected_environments = {"game", "organization"}
    failures = [
        f"missing environment: {environment}"
        for environment in sorted(expected_environments - set(environment_reports))
    ]
    failures.extend(
        f"{environment}: {failure}"
        for environment, report in environment_reports.items()
        for failure in report["failures"]
    )
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "primary_scope": "each environment must independently pass both Gate C thresholds",
        "environments": environment_reports,
        "pooled_diagnostic": audit_surface_leakage(families, seed),
        "pooled_result_cannot_override_environment_failure": True,
    }


def _leaf_differences(left: Any, right: Any, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if isinstance(left, dict) and isinstance(right, dict):
        differences: list[tuple[str, ...]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append((*path, key))
            else:
                differences.extend(_leaf_differences(left[key], right[key], (*path, key)))
        return differences
    return [] if left == right else [path]


def audit_state_machine_integrity(families: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    actor_changed = 0
    actor_intervention_changed = 0
    factual_changed = 0
    factual_intervention_changed = 0
    policy_equal = 0
    policy_intervention_changed = 0
    rollout_chains = 0
    delta_checks = 0
    for family in families:
        source = family["source"]
        primary = family["primary"]
        if "actor_values" not in source["state"] or "next_state" not in primary:
            failures.append(f"{family['scenario_id']}: missing actor values or next state")
            continue
        actor_changed += (
            family["actor_value_twin"]["result"]["physical_delta"]
            != primary["physical_delta"]
        )
        actor_paths = _leaf_differences(source, family["actor_value_twin"]["source"])
        factual_paths = _leaf_differences(source, family["factual_twin"]["source"])
        policy_paths = _leaf_differences(source, family["policy_twin"]["source"])
        actor_intervention_changed += len(actor_paths) == 1 and actor_paths[0][:2] == (
            "state",
            "actor_values",
        )
        factual_intervention_changed += len(factual_paths) == 1 and factual_paths[0][0] == "state"
        policy_intervention_changed += len(policy_paths) == 1 and policy_paths[0][0] == "policy"
        factual_changed += family["factual_twin"]["result"]["physical_delta"] != primary["physical_delta"]
        policy_equal += family["policy_twin"]["result"]["physical_delta"] == primary["physical_delta"]
        consistent = True
        for field, change in primary["physical_delta"].items():
            if not field.endswith("_delta") or not isinstance(change, (int, float)):
                continue
            state_field = field[:-6]
            if state_field in source["state"]:
                consistent &= primary["next_state"][state_field] - source["state"][state_field] == change
        delta_checks += consistent
        rollout = family.get("rollout", [])
        chained = len(rollout) == 3
        for previous, current in zip(rollout, rollout[1:], strict=False):
            chained &= previous["next_state"] == current["pre_state"]
        rollout_chains += chained
    total = max(len(families), 1)
    metrics = {
        "actor_value_physical_sensitivity": actor_changed / total,
        "actor_value_intervention_source_change": actor_intervention_changed / total,
        "factual_twin_intervention_source_change": factual_intervention_changed / total,
        "factual_twin_physical_sensitivity": factual_changed / total,
        "policy_twin_intervention_source_change": policy_intervention_changed / total,
        "policy_twin_physical_invariance": policy_equal / total,
        "next_state_delta_consistency": delta_checks / total,
        "three_step_rollout_chain_consistency": rollout_chains / total,
    }
    gates = {
        "actor_value_physical_sensitivity": 0.25,
        "actor_value_intervention_source_change": 1.0,
        "factual_twin_intervention_source_change": 1.0,
        "factual_twin_physical_sensitivity": 1.0,
        "policy_twin_intervention_source_change": 1.0,
        "policy_twin_physical_invariance": 1.0,
        "next_state_delta_consistency": 1.0,
        "three_step_rollout_chain_consistency": 1.0,
    }
    failures.extend(name for name, gate in gates.items() if metrics[name] + 1e-12 < gate)
    return {"status": "PASS" if not failures else "FAIL", "failures": failures, "metrics": metrics, "gates": gates}


def audit_model_input_integrity(families: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden_paths = {"state.turn", "state.ticket"}
    hash_mismatches = 0
    forbidden_occurrences: Counter[str] = Counter()
    feature_rows: list[dict[str, float]] = []
    for family in families:
        model_input = family["model_input"]
        canonical = json.dumps(
            model_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        hash_mismatches += hashlib.sha256(canonical).hexdigest() != family["model_input_sha256"]
        for path in forbidden_paths:
            current: Any = model_input
            for part in path.split("."):
                if not isinstance(current, dict) or part not in current:
                    current = None
                    break
                current = current[part]
            if current is not None:
                forbidden_occurrences[path] += 1
        feature_rows.append(_flatten_features(model_input))

    count = len(feature_rows)
    positions = [float(index) for index in range(count)]
    position_mean = sum(positions) / max(count, 1)
    position_ss = sum((value - position_mean) ** 2 for value in positions)
    correlations: dict[str, float] = {}
    for name in sorted({key for row in feature_rows for key in row}):
        values = [row.get(name, 0.0) for row in feature_rows]
        mean = sum(values) / max(count, 1)
        value_ss = sum((value - mean) ** 2 for value in values)
        if value_ss <= 1e-12 or position_ss <= 1e-12:
            continue
        covariance = sum(
            (position - position_mean) * (value - mean)
            for position, value in zip(positions, values, strict=True)
        )
        correlations[name] = covariance / math.sqrt(position_ss * value_ss)
    max_correlation = max((abs(value) for value in correlations.values()), default=0.0)
    unique_features = {
        name: len({row.get(name, 0.0) for row in feature_rows}) / max(count, 1)
        for name in sorted({key for row in feature_rows for key in row})
    }
    max_unique_fraction = max(unique_features.values(), default=0.0)
    failures = []
    if hash_mismatches:
        failures.append("baseline/model input byte identity hash mismatch")
    if forbidden_occurrences:
        failures.append("bookkeeping identifier present in model input")
    if max_correlation > 0.20:
        failures.append("serialized row order remains correlated with a model-input feature")
    if max_unique_fraction > 0.10:
        failures.append("model input contains a near-unique scalar feature")
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "metrics": {
            "model_input_hash_mismatch_count": hash_mismatches,
            "forbidden_identifier_occurrences": dict(forbidden_occurrences),
            "maximum_absolute_row_order_feature_correlation": max_correlation,
            "maximum_single_feature_unique_fraction": max_unique_fraction,
            "feature_count": len(unique_features),
        },
        "gates": {
            "maximum_absolute_row_order_feature_correlation": 0.20,
            "maximum_single_feature_unique_fraction": 0.10,
        },
    }


_SMALL_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
_TENS_WORDS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def _spoken_integer(value: int) -> str:
    if value < 20: return _SMALL_WORDS[value]
    if value < 100: return _TENS_WORDS[value // 10] + (f"-{_SMALL_WORDS[value % 10]}" if value % 10 else "")
    if value == 100: return "one hundred"
    raise ValueError("spoken audit helper supports values through one hundred")


def _spoken_hundredths(value: float) -> str:
    prefix = "negative " if value < 0 else ""
    return f"{prefix}{_spoken_integer(int(round(abs(value) * 100)))} hundredths"


def _scenario_equivalence_markers(family: dict[str, Any]) -> list[str]:
    source = family["model_input"]; state, action, policy = source["state"], source["action"], source["policy"]
    markers = [
        str(value).replace("_", " ").lower()
        for value in (*action.values(), policy["policy_family"], *state["authorized_actions"])
        if isinstance(value, str)
    ]
    markers.extend(str(value).lower() for value in state["surface_context"].values())
    markers.extend(
        [
            f"hard floor of {_spoken_integer(policy['policy_minimum_evidence_count'])}",
            f"full standard of {_spoken_integer(policy['required_evidence_count'])}",
            "requires approval" if policy["approval_required"] else "does not require approval",
            "bars private disclosure" if policy["prohibited_private_disclosure"] else "does not bar private disclosure",
            "blocks conflicting" if policy["conflict_blocking"] else "does not block conflicting",
            "approval is on record" if state["approval_present"] else "approval is not on record",
            "consent is recorded" if state["consent_present"] else "consent is not recorded",
        ]
    )
    if family["environment"] == "game":
        levels = ("depleted", "low", "steady", "high", "abundant")
        markers.extend(
            [
                state["actor"].lower(),
                f"health is {levels[state['health_level']]}", f"trust is {levels[state['trust_level']]}",
                f"supplies are {levels[state['resource_stock']]}", f"secrecy is {levels[state['secrecy_level']]}",
                f"threat is {levels[state['threat_level']]}", f"panic is {levels[state['panic_level']]}",
                f"progress is {levels[state['progress_level']]}", f"available choice is {levels[state['choice_access']]}",
                f"resource fairness is {levels[state['fairness_balance']]}", f"promise burden is {levels[state['promise_debt']]}",
                f"rollback capacity is {levels[state['rollback_capacity']]}",
                f"sees {_spoken_integer(state['observed_evidence_count'])} clues",
                f"{_spoken_integer(state['stakeholder_count'])} stakeholders",
                "would leave a persistent mark" if action["persistent"] else "would leave no persistent mark",
                "third-party flag is present" if state["third_party_present"] else "third-party flag is absent",
                "obligation flag is active" if state["obligation_active"] else "obligation flag is inactive",
                "internally disputed" if state["conflicting_evidence"] else "mutually consistent",
                "no persistent world flags" if not state["persistent_flags"] else "persistent flags for " + ", ".join(state["persistent_flags"]),
            ]
        )
    else:
        levels = ("critical", "limited", "stable", "strong", "excellent")
        markers.extend(
            [
                state["role"].lower(),
                f"service health is {levels[state['service_health']]}", f"exposure is {levels[4-state['exposure_level']]}",
                f"user control is {levels[state['user_control']]}", f"stakeholder trust is {levels[state['stakeholder_trust']]}",
                f"remaining work is {levels[4-state['work_remaining']]}", f"budget is {levels[state['budget_remaining']]}",
                f"allocation balance is {levels[state['allocation_balance']]}", f"process health is {levels[4-state['process_debt']]}",
                f"incident pressure is {levels[4-state['incident_pressure']]}", f"rollback capacity is {levels[state['rollback_capacity']]}",
                f"sees {_spoken_integer(state['observed_evidence_count'])} records",
                f"{_spoken_integer(state['stakeholder_count'])} stakeholders",
                "would create a durable change" if action["persistent"] else "would not create a durable change",
                "external-party flag is affected" if state["external_party_affected"] else "external-party flag is not affected",
                "obligation flag is active" if state["obligation_active"] else "obligation flag is inactive",
                "internally disputed" if state["conflicting_evidence"] else "mutually consistent",
                "no durable objects" if not state["durable_objects"] else "durable objects for " + ", ".join(state["durable_objects"]),
            ]
        )
    for key, value in state["actor_values"].items():
        markers.append(f"{key.replace('_', ' ')} is {levels[value]}")
    return markers


def _profile_equivalence_markers(evaluator: dict[str, Any]) -> list[str]:
    profile = evaluator["profile_input"]
    markers = []
    for key, value in profile["weights"].items(): markers.append(f"{key} carries {_spoken_hundredths(value)}")
    for key, value in profile["veto_floor"].items(): markers.append(f"{key} has a floor of {_spoken_hundredths(value)}")
    markers.extend(
        [
            f"uncertainty threshold is {_spoken_hundredths(profile['uncertainty_escalate_at'])}",
            f"irreversibility cutoff is {_spoken_hundredths(profile['irreversibility_cutoff'])}",
            f"irreversible-harm threshold is {_spoken_hundredths(profile['irreversible_harm_veto'])}",
            f"lower decision band is {_spoken_hundredths(profile['reject_at_or_below'])}",
            f"upper decision band is {_spoken_hundredths(profile['allow_at_or_above'])}",
        ]
    )
    return markers


def audit_natural_language(families: list[dict[str, Any]]) -> dict[str, Any]:
    scenario_texts = [surface["natural_language"] for family in families for surface in family["surface_twins"]]
    texts = [
        f"{surface['natural_language']} Evaluator contract: {profile_sham}"
        for family in families
        for surface in family["surface_twins"]
        for evaluator in family["evaluator_twins"].values()
        for profile_sham in evaluator["natural_language_profile_shams"]
    ]
    decimal_count = sum(len(re.findall(r"\b\d+\.\d+\b", text)) for text in texts)
    assignment_count = sum(len(re.findall(r"\b[a-z_]+\s*=", text, re.IGNORECASE)) for text in texts)
    token_counts = [len(re.findall(r"[a-z]+", text.lower())) for text in texts]
    vocabulary = set().union(*(_tokens(text, "word") for text in texts)) if texts else set()
    noncausal = {surface["noncausal_surface_text"] for family in families for surface in family["surface_twins"]}
    missing_scenario_markers = 0; missing_profile_markers = 0
    variable_article_errors = 0
    for family in families:
        scenario_markers = _scenario_equivalence_markers(family)
        for surface in family["surface_twins"]:
            lowered = surface["natural_language"].lower()
            missing_scenario_markers += sum(marker not in lowered for marker in scenario_markers)
            state = family["model_input"]["state"]
            variable_terms = [family["model_input"]["action"]["tactic"]]
            if family["environment"] == "game":
                variable_terms.extend([state["surface_context"]["witness"], state.get("actor", "")])
            else:
                variable_terms.extend([state["surface_context"]["observer"], state.get("role", "")])
            variable_article_errors += sum(
                bool(re.search(rf"\b(?:a|an)\s+{re.escape(str(term).lower())}\b", lowered))
                for term in variable_terms
                if term
            )
        for evaluator in family["evaluator_twins"].values():
            profile_markers = _profile_equivalence_markers(evaluator)
            for sham in evaluator["natural_language_profile_shams"]:
                lowered = sham.lower()
                missing_profile_markers += sum(marker not in lowered for marker in profile_markers)
    ordinal_fields = {
        "game": {
            "health_level": r"health is ([a-z]+)",
            "trust_level": r"trust is ([a-z]+)",
            "resource_stock": r"supplies are ([a-z]+)",
            "secrecy_level": r"secrecy is ([a-z]+)",
            "threat_level": r"threat is ([a-z]+)",
            "fairness_balance": r"resource fairness is ([a-z]+)",
            "promise_debt": r"promise burden is ([a-z]+)",
            "panic_level": r"panic is ([a-z]+)",
            "progress_level": r"progress is ([a-z]+)",
            "choice_access": r"available choice is ([a-z]+)",
            "rollback_capacity": r"rollback capacity is ([a-z]+)",
        },
        "organization": {
            "service_health": r"service health is ([a-z]+)",
            "exposure_level": r"exposure is ([a-z]+)",
            "user_control": r"user control is ([a-z]+)",
            "stakeholder_trust": r"stakeholder trust is ([a-z]+)",
            "work_remaining": r"remaining work is ([a-z]+)",
            "budget_remaining": r"budget is ([a-z]+)",
            "allocation_balance": r"allocation balance is ([a-z]+)",
            "process_debt": r"process health is ([a-z]+)",
            "incident_pressure": r"incident pressure is ([a-z]+)",
            "rollback_capacity": r"rollback capacity is ([a-z]+)",
        },
    }
    cardinality = {}
    environment = families[0]["environment"] if families else "game"
    if environment == "game":
        from .environments.game import render_game as render_for_cardinality
    else:
        from .environments.organization import render_organization as render_for_cardinality
    representative = families[0]["source"] if families else None
    for field, pattern in ordinal_fields[environment].items():
        values = {family["model_input"]["state"][field] for family in families}
        rendered_markers = []
        for value in range(5):
            probe = copy.deepcopy(representative)
            probe["state"][field] = value
            match = re.search(pattern, render_for_cardinality(probe, 0).lower())
            rendered_markers.append(match.group(1) if match else "<missing>")
        cardinality[field] = {
            "declared_state_cardinality": 5,
            "observed_state_cardinality": len(values),
            "marker_cardinality": len(set(rendered_markers)),
            "state_to_marker": {
                str(value): marker for value, marker in enumerate(rendered_markers)
            },
            "injective": "<missing>" not in rendered_markers
            and len(set(rendered_markers)) == 5,
        }
    marker_cardinality_failures = sum(
        not item["injective"] or item["marker_cardinality"] != item["declared_state_cardinality"]
        for item in cardinality.values()
    )
    metrics = {
        "decimal_literal_count": decimal_count,
        "key_value_assignment_count": assignment_count,
        "mean_word_count": sum(token_counts) / max(len(token_counts), 1),
        "minimum_word_count": min(token_counts, default=0),
        "vocabulary_size": len(vocabulary),
        "unique_noncausal_surface_count": len(noncausal),
        "scenario_render_count": len(scenario_texts),
        "composed_prompt_count": len(texts),
        "audited_prompt_scope": "scenario, action, policy, actor values, and evaluator profile",
        "missing_scenario_equivalence_markers": missing_scenario_markers,
        "missing_profile_equivalence_markers": missing_profile_markers,
        "variable_article_error_count": variable_article_errors,
        "ordinal_renderer_cardinality": cardinality,
        "ordinal_renderer_cardinality_failure_count": marker_cardinality_failures,
    }
    failures = []
    if decimal_count: failures.append("decimal literals appear in natural-language inputs")
    if assignment_count: failures.append("key=value serialization appears in natural-language inputs")
    if metrics["mean_word_count"] < 75: failures.append("natural-language inputs are too short")
    if len(vocabulary) < 100: failures.append("natural-language vocabulary is too small")
    if len(noncausal) < 100: failures.append("noncausal prose is not scenario-dependent")
    if missing_scenario_markers: failures.append("natural-language scenario omits structured source facts")
    if missing_profile_markers: failures.append("natural-language evaluator profile omits typed values")
    if variable_article_errors: failures.append("variable-template article grammar error")
    if marker_cardinality_failures: failures.append("ordinal renderer is not an injective state encoding")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures, "metrics": metrics}


def _flatten_features(value: Any, prefix: str = "") -> dict[str, float]:
    features: dict[str, float] = {}
    if isinstance(value, bool):
        features[prefix] = float(value)
    elif isinstance(value, (int, float)):
        features[prefix] = float(value)
    elif isinstance(value, str):
        features[f"{prefix}={value}"] = 1.0
    elif isinstance(value, dict):
        for key, item in value.items():
            features.update(_flatten_features(item, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            features[f"{prefix} contains {item}"] = 1.0
    return features


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        if abs(scale) < 1e-12:
            continue
        for item in range(column, n + 1):
            augmented[column][item] /= scale
        for row in range(n):
            if row == column: continue
            factor = augmented[row][column]
            if abs(factor) < 1e-15: continue
            for item in range(column, n + 1):
                augmented[row][item] -= factor * augmented[column][item]
    return [augmented[index][n] for index in range(n)]


def _affine_r2(train: list[tuple[dict[str, float], float]], test: list[tuple[dict[str, float], float]]) -> float:
    names = sorted({name for features, _ in train for name in features})
    names = ["__intercept__", *names]
    positions = {name: index for index, name in enumerate(names)}
    size = len(names)
    xtx = [[0.0] * size for _ in range(size)]; xty = [0.0] * size
    for features, target in train:
        row = {0: 1.0, **{positions[name]: value for name, value in features.items() if name in positions}}
        for i, left in row.items():
            xty[i] += left * target
            for j, right in row.items(): xtx[i][j] += left * right
    for index in range(1, size): xtx[index][index] += 1e-4
    weights = _solve(xtx, xty)
    actual = [target for _, target in test]
    predicted = []
    for features, _ in test:
        predicted.append(weights[0] + sum(weights[positions[name]] * value for name, value in features.items() if name in positions))
    mean = sum(actual) / max(len(actual), 1)
    denominator = sum((value - mean) ** 2 for value in actual)
    return 0.0 if denominator <= 1e-12 else 1 - sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=True)) / denominator


def _dense_rows(rows: list[dict[str, float]], names: list[str]) -> list[list[float]]:
    return [[row.get(name, 0.0) for name in names] for row in rows]


def _fit_depth_tree(
    x: list[list[float]], y: list[Any], indices: list[int], depth: int, classifier: bool
) -> Any:
    if classifier:
        counts = Counter(y[index] for index in indices)
        leaf = ("leaf", counts.most_common(1)[0][0])
        impurity = len(indices) - max(counts.values())
    else:
        mean = sum(float(y[index]) for index in indices) / len(indices)
        leaf = ("leaf", mean)
        impurity = sum((float(y[index]) - mean) ** 2 for index in indices)
    if depth == 0 or len(indices) < 30 or impurity <= 1e-12:
        return leaf
    best: tuple[float, int, float, list[int], list[int]] | None = None
    for feature in range(len(x[0])):
        values = sorted({x[index][feature] for index in indices})
        for left_value, right_value in zip(values, values[1:], strict=False):
            threshold = (left_value + right_value) / 2
            left = [index for index in indices if x[index][feature] <= threshold]
            right = [index for index in indices if x[index][feature] > threshold]
            if len(left) < 15 or len(right) < 15:
                continue
            if classifier:
                loss = sum(
                    len(part) - max(Counter(y[index] for index in part).values())
                    for part in (left, right)
                )
            else:
                loss = 0.0
                for part in (left, right):
                    mean = sum(float(y[index]) for index in part) / len(part)
                    loss += sum((float(y[index]) - mean) ** 2 for index in part)
            if best is None or loss < best[0]:
                best = (loss, feature, threshold, left, right)
    if best is None or best[0] >= impurity - 1e-12:
        return leaf
    _, feature, threshold, left, right = best
    return (
        "node", feature, threshold,
        _fit_depth_tree(x, y, left, depth - 1, classifier),
        _fit_depth_tree(x, y, right, depth - 1, classifier),
    )


def _tree_predict(tree: Any, row: list[float]) -> Any:
    while tree[0] == "node":
        tree = tree[3] if row[tree[1]] <= tree[2] else tree[4]
    return tree[1]


def _tree_r2(train: list[tuple[dict[str, float], float]], test: list[tuple[dict[str, float], float]]) -> float:
    names = sorted({name for row, _ in train for name in row})
    train_x = _dense_rows([row for row, _ in train], names)
    test_x = _dense_rows([row for row, _ in test], names)
    train_y = [target for _, target in train]
    actual = [target for _, target in test]
    tree = _fit_depth_tree(train_x, train_y, list(range(len(train_x))), 3, False)
    predicted = [_tree_predict(tree, row) for row in test_x]
    mean = sum(actual) / max(len(actual), 1)
    denominator = sum((value - mean) ** 2 for value in actual)
    return 0.0 if denominator <= 1e-12 else 1 - sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=True)) / denominator


def _decision_tree_accuracy(families: list[dict[str, Any]], features: dict[str, dict[str, float]]) -> float:
    train_rows: list[dict[str, float]] = []; train_labels: list[str] = []
    test_rows: list[dict[str, float]] = []; test_labels: list[str] = []
    for family in families:
        for profile, result in family["primary"]["evaluations"].items():
            row = dict(features[family["scenario_id"]]); row[f"profile={profile}"] = 1.0
            if family["split"] == "train": train_rows.append(row); train_labels.append(result["decision"])
            else: test_rows.append(row); test_labels.append(result["decision"])
    names = sorted({name for row in train_rows for name in row})
    train_x = _dense_rows(train_rows, names); test_x = _dense_rows(test_rows, names)
    tree = _fit_depth_tree(train_x, train_labels, list(range(len(train_x))), 3, True)
    predictions = [_tree_predict(tree, row) for row in test_x]
    return sum(left == right for left, right in zip(predictions, test_labels, strict=True)) / max(len(test_labels), 1)


def audit_nontriviality(families: list[dict[str, Any]]) -> dict[str, Any]:
    forbidden = ("impact_vector", "event_record", "physical_delta", "next_state", "hard_violations", "uncertainty")
    serialized = [repr(family["model_input"]) for family in families]
    target_leaks = sorted({token for token in forbidden if any(token in text for text in serialized)})
    features = {family["scenario_id"]: _flatten_features(family["model_input"]) for family in families}
    per_field: dict[str, float] = {}; tree_per_field: dict[str, float] = {}
    dimensions = sorted(families[0]["primary"]["event_record"]["impact_vector"]) if families else []
    for dimension in dimensions:
        train = [(features[f["scenario_id"]], float(f["primary"]["event_record"]["impact_vector"][dimension])) for f in families if f["split"] == "train"]
        test = [(features[f["scenario_id"]], float(f["primary"]["event_record"]["impact_vector"][dimension])) for f in families if f["split"] == "development"]
        per_field[dimension] = _affine_r2(train, test) if train and test else 1.0
        tree_per_field[dimension] = _tree_r2(train, test) if train and test else 1.0
    maximum = max(per_field.values(), default=1.0)
    tree_maximum = max(tree_per_field.values(), default=1.0)
    decision_accuracy = _decision_tree_accuracy(families, features)
    failures = []
    if target_leaks: failures.append("post-transition target field is present in structured input")
    if maximum > 0.90: failures.append("affine target reconstruction exceeds preregistered ceiling")
    if tree_maximum > 0.90: failures.append("depth-three tree target reconstruction exceeds preregistered ceiling")
    if decision_accuracy >= 0.90: failures.append("depth-three direct decision accuracy reaches preregistered ceiling")
    return {
        "status": "PASS" if not failures else "FAIL", "failures": failures,
        "target_field_leaks": target_leaks, "affine_impact_r2": per_field,
        "depth_three_tree_impact_r2": tree_per_field,
        "maximum_affine_impact_r2": maximum, "maximum_allowed_r2": 0.90,
        "maximum_depth_three_tree_impact_r2": tree_maximum,
        "depth_three_direct_decision_accuracy": decision_accuracy,
        "maximum_allowed_decision_accuracy": 0.90,
        "note": "Ridge affine and greedy depth-three baselines fitted on train scenarios and scored on development scenarios.",
    }
