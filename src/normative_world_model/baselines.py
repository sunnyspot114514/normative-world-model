"""Cheap Phase-2 static baselines scored on the frozen joint estimand."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import median
from typing import Any

from .audits import (
    _centroid_scores,
    _dense_rows,
    _fit_depth_tree,
    _flatten_features,
    _tokens,
    _tree_predict,
)
from .bootstrap import scenario_cluster_bootstrap
from .model_output import ParsedModelOutput, parse_model_output
from .phase2_dataset import (
    PHYSICAL_DELTA_SCHEMAS,
    Phase2Example,
    build_phase2_examples,
    canonical_json,
    neutral_physical_delta,
)
from .phase2_metrics import score_evaluator_pair, score_one_step
from .transfer_matrix import (
    ENVIRONMENT_ALIASES,
    INPUT_CONDITIONS,
    TARGET_PROFILE_PAIRS,
)

BASELINE_ARMS = (
    "profile_majority",
    "structured_depth3",
    "word_tfidf_centroid",
    "char4_tfidf_centroid",
)
FIELDWISE_NEIGHBOR_COUNT = 7


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _classification_summary(
    actual: list[str],
    predicted: list[str],
) -> dict[str, Any]:
    labels = sorted(set(actual) | set(predicted))
    recall = {}
    for label in labels:
        indices = [
            index
            for index, value in enumerate(actual)
            if value == label
        ]
        recall[label] = (
            sum(predicted[index] == label for index in indices) / len(indices)
            if indices
            else None
        )
    valid_recall = [value for value in recall.values() if value is not None]
    return {
        "accuracy": sum(
            left == right
            for left, right in zip(actual, predicted, strict=True)
        )
        / max(len(actual), 1),
        "balanced_accuracy": (
            sum(valid_recall) / max(len(valid_recall), 1)
        ),
        "recall_by_class": recall,
        "support_by_class": dict(Counter(actual)),
    }


def _example_features(
    example: Phase2Example,
    families: dict[str, dict[str, Any]],
) -> dict[str, float]:
    features = _flatten_features(
        families[example.scenario_id]["model_input"]
    )
    features[f"profile={example.profile_id}"] = 1.0
    return features


def _majority_predictions(
    train: list[Phase2Example],
    development: list[Phase2Example],
) -> list[str]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for example in train:
        counts[example.profile_id][
            example.target["normative_decision"]
        ] += 1
    return [
        counts[example.profile_id].most_common(1)[0][0]
        for example in development
    ]


def _structured_tree_predictions(
    train: list[Phase2Example],
    development: list[Phase2Example],
    families: dict[str, dict[str, Any]],
) -> list[str]:
    train_features = [
        _example_features(example, families)
        for example in train
    ]
    development_features = [
        _example_features(example, families)
        for example in development
    ]
    names = sorted(
        {
            name
            for row in train_features
            for name in row
        }
    )
    train_x = _dense_rows(train_features, names)
    development_x = _dense_rows(development_features, names)
    tree = _fit_depth_tree(
        train_x,
        [
            example.target["normative_decision"]
            for example in train
        ],
        list(range(len(train_x))),
        3,
        True,
    )
    return [_tree_predict(tree, row) for row in development_x]


def _tfidf_predictions(
    train: list[Phase2Example],
    development: list[Phase2Example],
    mode: str,
) -> list[str]:
    labels, scores = _centroid_scores(
        [
            (example.prompt, example.target["normative_decision"])
            for example in train
        ],
        [
            (example.prompt, example.target["normative_decision"])
            for example in development
        ],
        mode,
    )
    return [
        max(labels, key=lambda label: (scores[label][index], label))
        for index in range(len(development))
    ]


def _decision_predictions(
    train: list[Phase2Example],
    development: list[Phase2Example],
    families: dict[str, dict[str, Any]],
    condition: str,
) -> dict[str, list[str]]:
    predictions = {
        "profile_majority": _majority_predictions(train, development),
        "word_tfidf_centroid": _tfidf_predictions(
            train,
            development,
            "word",
        ),
        "char4_tfidf_centroid": _tfidf_predictions(
            train,
            development,
            "char",
        ),
    }
    if condition == "structured":
        predictions["structured_depth3"] = _structured_tree_predictions(
            train,
            development,
            families,
        )
    return predictions


def _sparse_squared_distance(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    return sum(
        (left.get(name, 0.0) - right.get(name, 0.0)) ** 2
        for name in set(left) | set(right)
    )


def _structured_factual_predictions(
    train_families: list[dict[str, Any]],
    development_families: list[dict[str, Any]],
) -> dict[tuple[str, int | None], dict[str, Any]]:
    candidates = [
        (
            _flatten_features(family["model_input"]),
            family["scenario_id"],
            {
                "physical_delta": family["primary"]["physical_delta"],
                "event_record": family["primary"]["event_record"],
            },
        )
        for family in train_families
    ]
    predictions = {}
    for family in development_families:
        features = _flatten_features(family["model_input"])
        _, _, factual = min(
            candidates,
            key=lambda item: (
                _sparse_squared_distance(features, item[0]),
                item[1],
            ),
        )
        predictions[(family["scenario_id"], None)] = factual
    return predictions


def _target_leaves(
    value: Any,
    path: tuple[str, ...] = (),
) -> dict[tuple[str, ...], Any]:
    if isinstance(value, dict):
        leaves: dict[tuple[str, ...], Any] = {}
        for key in sorted(value):
            leaves.update(_target_leaves(value[key], (*path, key)))
        return leaves
    return {path: value}


def _replace_path(
    value: dict[str, Any],
    path: tuple[str, ...],
    replacement: Any,
) -> None:
    current = value
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = replacement


def _continuous_factual_path(path: tuple[str, ...]) -> bool:
    return len(path) >= 2 and path[0] == "event_record" and (
        path[-1] in {"reversibility", "recovery_cost", "uncertainty"}
        or "impact_vector" in path
    )


def _fieldwise_factual_vote(
    factual_neighbors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate complete neighbor targets without consulting evaluator values."""

    if not factual_neighbors:
        raise ValueError("fieldwise factual vote requires at least one neighbor")
    prediction = deepcopy(factual_neighbors[0])
    neighbor_leaves = [
        _target_leaves(factual)
        for factual in factual_neighbors
    ]
    for path in sorted(neighbor_leaves[0]):
        values = [leaves[path] for leaves in neighbor_leaves]
        if _continuous_factual_path(path):
            selected = float(median(float(value) for value in values))
        else:
            encoded = [
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                for value in values
            ]
            counts = Counter(encoded)
            selected_text = min(
                counts,
                key=lambda item: (-counts[item], item),
            )
            selected = json.loads(selected_text)
        _replace_path(prediction, path, selected)
    return prediction


def _structured_fieldwise_factual_predictions(
    train_families: list[dict[str, Any]],
    development_families: list[dict[str, Any]],
    *,
    neighbors: int = FIELDWISE_NEIGHBOR_COUNT,
) -> dict[tuple[str, int | None], dict[str, Any]]:
    candidates = [
        (
            _flatten_features(family["model_input"]),
            family["scenario_id"],
            {
                "physical_delta": family["primary"]["physical_delta"],
                "event_record": family["primary"]["event_record"],
            },
        )
        for family in train_families
    ]
    predictions = {}
    for family in development_families:
        features = _flatten_features(family["model_input"])
        nearest = sorted(
            candidates,
            key=lambda item: (
                _sparse_squared_distance(features, item[0]),
                item[1],
            ),
        )[: min(neighbors, len(candidates))]
        predictions[(family["scenario_id"], None)] = _fieldwise_factual_vote(
            [item[2] for item in nearest]
        )
    return predictions


def _tfidf_nearest_targets(
    train: list[tuple[str, str, dict[str, Any]]],
    development: list[tuple[str, int | None, str]],
    mode: str,
) -> dict[tuple[str, int | None], dict[str, Any]]:
    train_tokens = [
        (_tokens(text, mode), scenario_id, target)
        for text, scenario_id, target in train
    ]
    document_frequency: Counter[str] = Counter()
    for tokens, _, _ in train_tokens:
        document_frequency.update(tokens)
    idf = {
        token: math.log((1 + len(train_tokens)) / (1 + count)) + 1
        for token, count in document_frequency.items()
    }
    candidates = []
    for tokens, scenario_id, target in train_tokens:
        norm = math.sqrt(
            sum(idf[token] ** 2 for token in tokens if token in idf)
        ) or 1.0
        candidates.append((tokens, norm, scenario_id, target))

    predictions = {}
    for scenario_id, variant, text in development:
        tokens = _tokens(text, mode)
        norm = math.sqrt(
            sum(idf.get(token, 0.0) ** 2 for token in tokens)
        ) or 1.0
        best = max(
            candidates,
            key=lambda item: (
                sum(
                    idf.get(token, 0.0) ** 2
                    for token in tokens & item[0]
                )
                / (norm * item[1]),
                item[2],
            ),
        )
        predictions[(scenario_id, variant)] = best[3]
    return predictions


def _tfidf_fieldwise_targets(
    train: list[tuple[str, str, dict[str, Any]]],
    development: list[tuple[str, int | None, str]],
    mode: str,
    *,
    neighbors: int = FIELDWISE_NEIGHBOR_COUNT,
) -> dict[tuple[str, int | None], dict[str, Any]]:
    train_tokens = [
        (_tokens(text, mode), scenario_id, target)
        for text, scenario_id, target in train
    ]
    document_frequency: Counter[str] = Counter()
    for tokens, _, _ in train_tokens:
        document_frequency.update(tokens)
    idf = {
        token: math.log((1 + len(train_tokens)) / (1 + count)) + 1
        for token, count in document_frequency.items()
    }
    candidates = []
    for tokens, scenario_id, target in train_tokens:
        norm = math.sqrt(
            sum(idf[token] ** 2 for token in tokens if token in idf)
        ) or 1.0
        candidates.append((tokens, norm, scenario_id, target))

    predictions = {}
    for scenario_id, variant, text in development:
        tokens = _tokens(text, mode)
        norm = math.sqrt(
            sum(idf.get(token, 0.0) ** 2 for token in tokens)
        ) or 1.0
        ranked = sorted(
            candidates,
            key=lambda item: (
                -sum(
                    idf.get(token, 0.0) ** 2
                    for token in tokens & item[0]
                )
                / (norm * item[1]),
                item[2],
            ),
        )[: min(neighbors, len(candidates))]
        predictions[(scenario_id, variant)] = _fieldwise_factual_vote(
            [item[3] for item in ranked]
        )
    return predictions


def _text_factual_predictions(
    train_families: list[dict[str, Any]],
    development_families: list[dict[str, Any]],
    condition: str,
    mode: str,
) -> dict[tuple[str, int | None], dict[str, Any]]:
    train = []
    development = []
    for family in train_families:
        factual = {
            "physical_delta": family["primary"]["physical_delta"],
            "event_record": family["primary"]["event_record"],
        }
        if condition == "structured":
            train.append(
                (
                    canonical_json(family["model_input"]),
                    family["scenario_id"],
                    factual,
                )
            )
        else:
            for surface in family["surface_twins"]:
                train.append(
                    (
                        surface["natural_language"],
                        family["scenario_id"],
                        factual,
                    )
                )
    for family in development_families:
        if condition == "structured":
            development.append(
                (
                    family["scenario_id"],
                    None,
                    canonical_json(family["model_input"]),
                )
            )
        else:
            for variant, surface in enumerate(family["surface_twins"]):
                development.append(
                    (
                        family["scenario_id"],
                        variant,
                        surface["natural_language"],
                    )
                )
    return _tfidf_nearest_targets(train, development, mode)


def _text_fieldwise_factual_predictions(
    train_families: list[dict[str, Any]],
    development_families: list[dict[str, Any]],
    condition: str,
    mode: str,
) -> dict[tuple[str, int | None], dict[str, Any]]:
    train = []
    development = []
    for family in train_families:
        factual = {
            "physical_delta": family["primary"]["physical_delta"],
            "event_record": family["primary"]["event_record"],
        }
        if condition == "structured":
            train.append(
                (
                    canonical_json(family["model_input"]),
                    family["scenario_id"],
                    factual,
                )
            )
        else:
            for surface in family["surface_twins"]:
                train.append(
                    (
                        surface["natural_language"],
                        family["scenario_id"],
                        factual,
                    )
                )
    for family in development_families:
        if condition == "structured":
            development.append(
                (
                    family["scenario_id"],
                    None,
                    canonical_json(family["model_input"]),
                )
            )
        else:
            for variant, surface in enumerate(family["surface_twins"]):
                development.append(
                    (
                        family["scenario_id"],
                        variant,
                        surface["natural_language"],
                    )
                )
    return _tfidf_fieldwise_targets(train, development, mode)


def _one_step_target(example: Phase2Example) -> dict[str, Any]:
    return {
        "physical_delta": example.target["physical_delta"],
        "event_record": example.target["event_record"],
        "normative_decision": example.target["normative_decision"],
        "escalation_required": example.target["escalation_required"],
        "rollout": [],
    }


def _parsed_static_output(
    example: Phase2Example,
    decision: str,
    factual: dict[str, Any],
) -> ParsedModelOutput | None:
    physical_delta = factual["physical_delta"]
    source_schema = set(physical_delta)
    target_schema = set(PHYSICAL_DELTA_SCHEMAS[example.environment])
    known_schemas = {
        environment: set(schema)
        for environment, schema in PHYSICAL_DELTA_SCHEMAS.items()
    }
    if (
        source_schema != target_schema
        and source_schema in known_schemas.values()
    ):
        physical_delta = neutral_physical_delta(example.environment)
    payload = {
        "physical_delta": physical_delta,
        "event_record": factual["event_record"],
        "normative_decision": decision,
        "escalation_required": decision == "escalate",
        "rollout": [],
    }
    parsed = parse_model_output(
        json.dumps(payload, ensure_ascii=False),
        _one_step_target(example),
    )
    return parsed.output if parsed.ok else None


def _scenario_joint_scores(
    development: list[Phase2Example],
    decision_predictions: list[str],
    factual_predictions: dict[
        tuple[str, int | None],
        dict[str, Any],
    ],
) -> dict[str, dict[str, float]]:
    decisions = {
        example.example_id: decision
        for example, decision in zip(
            development,
            decision_predictions,
            strict=True,
        )
    }
    lookup = {
        (
            example.scenario_id,
            example.scenario_surface_variant,
            example.profile_surface_variant,
            example.profile_id,
        ): example
        for example in development
    }
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    scenario_variants: dict[str, set[int | None]] = defaultdict(set)
    profile_variants: dict[str, set[int]] = defaultdict(set)
    for example in development:
        scenario_variants[example.scenario_id].add(
            example.scenario_surface_variant
        )
        profile_variants[example.scenario_id].add(
            example.profile_surface_variant
        )

    for scenario_id in sorted(scenario_variants):
        for scenario_variant in sorted(
            scenario_variants[scenario_id],
            key=lambda value: -1 if value is None else value,
        ):
            factual = factual_predictions[
                (scenario_id, scenario_variant)
            ]
            for profile_variant in sorted(profile_variants[scenario_id]):
                for left_profile, right_profile in TARGET_PROFILE_PAIRS:
                    left = lookup[
                        (
                            scenario_id,
                            scenario_variant,
                            profile_variant,
                            left_profile,
                        )
                    ]
                    right = lookup[
                        (
                            scenario_id,
                            scenario_variant,
                            profile_variant,
                            right_profile,
                        )
                    ]
                    predicted_left = _parsed_static_output(
                        left,
                        decisions[left.example_id],
                        factual,
                    )
                    predicted_right = _parsed_static_output(
                        right,
                        decisions[right.example_id],
                        factual,
                    )
                    left_target = _one_step_target(left)
                    right_target = _one_step_target(right)
                    score = score_evaluator_pair(
                        predicted_left,
                        predicted_right,
                        left_target,
                        right_target,
                    )
                    for member_score in (
                        score_one_step(predicted_left, left_target),
                        score_one_step(predicted_right, right_target),
                    ):
                        values[scenario_id]["physical_field_f1"].append(
                            member_score.physical.f1
                        )
                        values[scenario_id]["event_field_f1"].append(
                            member_score.event_record.f1
                        )
                    values[scenario_id]["joint_pair_success"].append(
                        float(score.joint_pair_success)
                    )
                    values[scenario_id][
                        "event_normative_pair_success"
                    ].append(
                        float(
                            score.event_record_consistent_and_correct
                            and score.normative_pair_correct
                        )
                    )
                    values[scenario_id]["normative_pair_accuracy"].append(
                        float(score.normative_pair_correct)
                    )
                    values[scenario_id][
                        "physical_consistent_and_correct"
                    ].append(float(score.physical_consistent_and_correct))
                    values[scenario_id][
                        "event_consistent_and_correct"
                    ].append(
                        float(score.event_record_consistent_and_correct)
                    )
                    values[scenario_id]["parse_complete"].append(
                        float(score.parse_complete)
                    )
    return {
        scenario_id: {
            name: sum(scores) / len(scores)
            for name, scores in metrics.items()
        }
        for scenario_id, metrics in values.items()
    }


def _mean_scenario_metrics(
    scores: dict[str, dict[str, float]],
) -> dict[str, float]:
    metric_names = sorted(
        {
            name
            for metrics in scores.values()
            for name in metrics
        }
    )
    return {
        name: sum(metrics[name] for metrics in scores.values())
        / len(scores)
        for name in metric_names
    }


def _run_cell(
    families: list[dict[str, Any]],
    examples: list[Phase2Example],
    train_environment: str,
    test_environment: str,
    condition: str,
    *,
    bootstrap_samples: int,
    confidence_level: float,
    seed: int,
) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    family_index = {
        family["scenario_id"]: family
        for family in families
    }
    train_families = [
        family
        for family in families
        if family["environment"] == train_environment
        and family["split"] == "train"
    ]
    development_families = [
        family
        for family in families
        if family["environment"] == test_environment
        and family["split"] == "development"
    ]
    train = [
        example
        for example in examples
        if example.environment == train_environment
        and example.split == "train"
        and example.input_condition == condition
    ]
    development = [
        example
        for example in examples
        if example.environment == test_environment
        and example.split == "development"
        and example.input_condition == condition
    ]
    decisions = _decision_predictions(
        train,
        development,
        family_index,
        condition,
    )
    factual_by_mode = {
        "structured_knn1": _structured_factual_predictions(
            train_families,
            development_families,
        ),
        "structured_fieldwise_knn7": (
            _structured_fieldwise_factual_predictions(
                train_families,
                development_families,
            )
        ),
        "word_knn1": _text_factual_predictions(
            train_families,
            development_families,
            condition,
            "word",
        ),
        "word_fieldwise_knn7": _text_fieldwise_factual_predictions(
            train_families,
            development_families,
            condition,
            "word",
        ),
        "char_knn1": _text_factual_predictions(
            train_families,
            development_families,
            condition,
            "char",
        ),
        "char_fieldwise_knn7": _text_fieldwise_factual_predictions(
            train_families,
            development_families,
            condition,
            "char",
        ),
    }
    factual_mode = {
        "profile_majority": (
            "structured_knn1" if condition == "structured" else "word_knn1"
        ),
        "structured_depth3": "structured_knn1",
        "word_tfidf_centroid": "word_knn1",
        "char4_tfidf_centroid": "char_knn1",
    }
    stronger_factual_mode = {
        "profile_majority": (
            "structured_fieldwise_knn7"
            if condition == "structured"
            else "word_fieldwise_knn7"
        ),
        "structured_depth3": "structured_fieldwise_knn7",
        "word_tfidf_centroid": "word_fieldwise_knn7",
        "char4_tfidf_centroid": "char_fieldwise_knn7",
    }
    scenario_scores = {}
    for arm, predicted in decisions.items():
        scenario_scores[arm] = _scenario_joint_scores(
            development,
            predicted,
            factual_by_mode[factual_mode[arm]],
        )
        scenario_scores[f"{arm}+fieldwise_knn7"] = _scenario_joint_scores(
            development,
            predicted,
            factual_by_mode[stronger_factual_mode[arm]],
        )
    bootstrap_estimand = (
        "joint_pair_success"
        if train_environment == test_environment
        else "event_normative_pair_success"
    )
    estimand_scores = {
        arm: {
            scenario_id: metrics[bootstrap_estimand]
            for scenario_id, metrics in scores.items()
        }
        for arm, scores in scenario_scores.items()
    }
    actual = [
        example.target["normative_decision"]
        for example in development
    ]
    report = {
        "train_environment": train_environment,
        "test_environment": test_environment,
        "input_condition": condition,
        "train_scenario_count": len(train_families),
        "development_scenario_count": len(development_families),
        "development_presentation_count": len(development),
        "eligible_arms": sorted(decisions),
        "eligible_joint_arms": sorted(scenario_scores),
        "bootstrap_estimand": bootstrap_estimand,
        "classification_diagnostics": {
            arm: _classification_summary(actual, predicted)
            for arm, predicted in decisions.items()
        },
        "scenario_macro_joint_estimand": {
            arm: _mean_scenario_metrics(scores)
            for arm, scores in scenario_scores.items()
        },
        "scenario_cluster_bootstrap": scenario_cluster_bootstrap(
            estimand_scores,
            samples=bootstrap_samples,
            confidence_level=confidence_level,
            seed=seed,
        ),
    }
    return report, estimand_scores


def _pooled_bootstrap(
    cell_scores: dict[str, dict[str, dict[str, float]]],
    cell_names: tuple[str, ...],
    *,
    bootstrap_samples: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    common_arms = set.intersection(
        *(
            set(cell_scores[cell])
            for cell in cell_names
        )
    )
    pooled = {
        arm: {
            f"{cell}:{scenario_id}": score
            for cell in cell_names
            for scenario_id, score in cell_scores[cell][arm].items()
        }
        for arm in sorted(common_arms)
    }
    return scenario_cluster_bootstrap(
        pooled,
        samples=bootstrap_samples,
        confidence_level=confidence_level,
        seed=seed,
    )


def run_smoke_baselines(
    data_dir: Path,
    *,
    bootstrap_samples: int = 5000,
    confidence_level: float = 0.95,
    seed: int = 20260916,
) -> dict[str, Any]:
    """Run static decision+fact baselines on the same pair metric as model arms."""

    families = []
    for environment in ENVIRONMENT_ALIASES.values():
        families.extend(_load_jsonl(data_dir / f"{environment}.jsonl"))
    examples = build_phase2_examples(families)

    transfer_cells = {}
    scores_by_condition: dict[
        str,
        dict[str, dict[str, dict[str, float]]],
    ] = defaultdict(dict)
    offset = 0
    for train_alias, train_environment in ENVIRONMENT_ALIASES.items():
        for test_alias, test_environment in ENVIRONMENT_ALIASES.items():
            cell_name = f"{train_alias}->{test_alias}"
            transfer_cells[cell_name] = {}
            for condition in INPUT_CONDITIONS:
                report, scores = _run_cell(
                    families,
                    examples,
                    train_environment,
                    test_environment,
                    condition,
                    bootstrap_samples=bootstrap_samples,
                    confidence_level=confidence_level,
                    seed=seed + offset * 100_003,
                )
                offset += 1
                transfer_cells[cell_name][condition] = report
                scores_by_condition[condition][cell_name] = scores

    pooled = {}
    for condition in INPUT_CONDITIONS:
        pooled[condition] = {
            "primary_development_ood": _pooled_bootstrap(
                scores_by_condition[condition],
                ("A->A", "B->B"),
                bootstrap_samples=bootstrap_samples,
                confidence_level=confidence_level,
                seed=seed + offset * 100_003,
            ),
            "cross_environment_transfer": _pooled_bootstrap(
                scores_by_condition[condition],
                ("A->B", "B->A"),
                bootstrap_samples=bootstrap_samples,
                confidence_level=confidence_level,
                seed=seed + (offset + 1) * 100_003,
            ),
        }
        offset += 2

    return {
        "status": "EXPLORATORY_SMOKE_ONLY",
        "retained_or_confirmation_result": False,
        "data_scope": str(data_dir.as_posix()),
        "effective_unit": "scenario_family",
        "primary_estimand": "ood_joint_pair_success",
        "cross_environment_estimand": (
            "event_normative_pair_success; domain-native physical_delta "
            "is reported separately"
        ),
        "primary_population": (
            "within-environment development families, including declared "
            "composition holdouts; cross-environment cells are reported separately"
        ),
        "static_composition": {
            "factual_component": (
                "evaluator-blind nearest-neighbor and seven-neighbor fieldwise "
                "prediction of physical_delta and event_record from the exact "
                "input condition"
            ),
            "normative_component": (
                "profile-majority, structured depth-three, or grouped "
                "word/character TF-IDF decision prediction"
            ),
            "scoring": (
                "predictions pass through the strict parser and the same "
                "evaluator-pair implementation as model arms; cross-environment "
                "bootstrap uses the shared event-record plus normative pair"
            ),
        },
        "static_envelope_rule": (
            "maximum scenario-macro joint_pair_success recomputed inside "
            "each scenario-cluster bootstrap replicate"
        ),
        "transfer_cells": transfer_cells,
        "pooled": pooled,
    }
