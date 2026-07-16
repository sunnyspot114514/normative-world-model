"""Exercise the Phase-2 harness against exact smoke targets."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from normative_world_model.bootstrap import cluster_bootstrap_means
from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_dataset import (
    Phase2Example,
    build_phase2_examples,
    target_output,
)
from normative_world_model.phase2_metrics import (
    evaluate_anti_gaming_gate,
    information_diagnostics,
    normative_stratum,
    score_evaluator_pair,
    score_factual_twin,
    score_leakage,
    score_rollout,
)
from normative_world_model.transfer_matrix import (
    TARGET_PROFILE_PAIRS,
    build_transfer_manifest,
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _exact_parse(example: Phase2Example):
    result = parse_model_output(
        json.dumps(
            example.target,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        example.target,
    )
    return result


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def run_internal_check(
    data_dir: Path,
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    families = []
    for environment in ("game", "organization"):
        families.extend(_load_jsonl(data_dir / f"{environment}.jsonl"))
    examples = build_phase2_examples(families)
    lookup = {
        (
            example.scenario_id,
            example.input_condition,
            example.scenario_surface_variant,
            example.profile_surface_variant,
            example.profile_id,
        ): example
        for example in examples
    }

    parse_errors: Counter[str] = Counter()
    forbidden_prompt_rows = 0
    for example in examples:
        result = _exact_parse(example)
        if not result.ok:
            parse_errors[result.error_code or "unknown"] += 1
        if any(
            token in example.prompt
            for token in (
                '"impact_vector"',
                '"hard_violations"',
                '"next_state"',
                '"normative_decision"',
            )
        ):
            forbidden_prompt_rows += 1

    pair_values: dict[str, list[float]] = defaultdict(list)
    pair_by_scenario: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for family in families:
        scenario_id = family["scenario_id"]
        for condition in ("structured", "natural_language"):
            scenario_variants = (
                (None,)
                if condition == "structured"
                else (0, 1)
            )
            for scenario_variant in scenario_variants:
                for left_profile, right_profile in TARGET_PROFILE_PAIRS:
                    left_example = lookup[
                        (
                            scenario_id,
                            condition,
                            scenario_variant,
                            0,
                            left_profile,
                        )
                    ]
                    right_example = lookup[
                        (
                            scenario_id,
                            condition,
                            scenario_variant,
                            0,
                            right_profile,
                        )
                    ]
                    left_output = _exact_parse(left_example).output
                    right_output = _exact_parse(right_example).output
                    pair = score_evaluator_pair(
                        left_output,
                        right_output,
                        left_example.target,
                        right_example.target,
                    )
                    surface_example = lookup[
                        (
                            scenario_id,
                            condition,
                            scenario_variant,
                            1,
                            left_profile,
                        )
                    ]
                    surface_output = _exact_parse(surface_example).output
                    leakage = score_leakage(
                        left_output,
                        right_output,
                        left_output,
                        surface_output,
                    )
                    values = {
                        "physical_consistent_and_correct": float(
                            pair.physical_consistent_and_correct
                        ),
                        "event_consistent_and_correct": float(
                            pair.event_record_consistent_and_correct
                        ),
                        "normative_pair_accuracy": float(
                            pair.normative_pair_correct
                        ),
                        "joint_pair_success": float(pair.joint_pair_success),
                        "physical_delta_leak": leakage.physical_delta_leak,
                        "event_delta_leak": leakage.event_delta_leak,
                    }
                    for name, value in values.items():
                        pair_values[name].append(value)
                        pair_by_scenario[scenario_id][name].append(value)

    scenario_metrics = {
        scenario_id: {
            name: _mean(values)
            for name, values in metrics.items()
        }
        for scenario_id, metrics in pair_by_scenario.items()
    }
    pair_bootstrap = cluster_bootstrap_means(
        scenario_metrics,
        samples=bootstrap_samples,
        confidence_level=0.95,
        seed=bootstrap_seed,
    )

    factual_twin_scores = []
    for family in families:
        profile_id = "procedure_preserving"
        base_target = target_output(family["primary"], profile_id)
        twin_target = target_output(
            family["factual_twin"]["result"],
            profile_id,
        )
        base = parse_model_output(
            json.dumps(base_target, separators=(",", ":")),
            base_target,
        ).output
        twin = parse_model_output(
            json.dumps(twin_target, separators=(",", ":")),
            twin_target,
        ).output
        factual_twin_scores.append(
            score_factual_twin(base, twin, base_target, twin_target)
        )

    diagnostic_outputs = []
    for family in families:
        for condition in ("structured", "natural_language"):
            scenario_variant = None if condition == "structured" else 0
            for profile_id in family["evaluator_twins"]:
                example = lookup[
                    (
                        family["scenario_id"],
                        condition,
                        scenario_variant,
                        0,
                        profile_id,
                    )
                ]
                diagnostic_outputs.append(_exact_parse(example).output)
    information = information_diagnostics(diagnostic_outputs)

    rollout_metrics: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for family in families:
        example = lookup[
            (
                family["scenario_id"],
                "structured",
                None,
                0,
                "procedure_preserving",
            )
        ]
        for horizon, values in score_rollout(
            _exact_parse(example).output,
            example.target,
        ).items():
            for name, value in values.items():
                rollout_metrics[horizon][name].append(float(value))

    normative_strata = Counter(
        normative_stratum(evaluation)
        for family in families
        for evaluation in family["primary"]["evaluations"].values()
    )
    changed_field_f1 = _mean(
        [score.changed_field_macro_f1 for score in factual_twin_scores]
    )
    physical_twin_sensitivity = _mean(
        [
            float(score.physical_twin_sensitive)
            for score in factual_twin_scores
        ]
    )
    normative_pair_accuracy = _mean(pair_values["normative_pair_accuracy"])
    anti_gaming = evaluate_anti_gaming_gate(
        candidate_information=information,
        baseline_information=information,
        gold_information=information,
        candidate_changed_field_f1=changed_field_f1,
        baseline_changed_field_f1=changed_field_f1,
        candidate_physical_twin_sensitivity=physical_twin_sensitivity,
        baseline_physical_twin_sensitivity=physical_twin_sensitivity,
        candidate_normative_pair_accuracy=normative_pair_accuracy,
        baseline_normative_pair_accuracy=normative_pair_accuracy,
    )
    transfer = build_transfer_manifest(families)
    failures = []
    if parse_errors:
        failures.append("exact target outputs did not parse")
    if forbidden_prompt_rows:
        failures.append("a Phase-2 prompt contains a forbidden target field")
    if any(
        not math_value
        for name, math_value in (
            (
                "physical correctness",
                _mean(pair_values["physical_consistent_and_correct"]),
            ),
            (
                "event correctness",
                _mean(pair_values["event_consistent_and_correct"]),
            ),
            (
                "normative pair accuracy",
                normative_pair_accuracy,
            ),
            ("joint pair success", _mean(pair_values["joint_pair_success"])),
            ("changed field F1", changed_field_f1),
            ("physical twin sensitivity", physical_twin_sensitivity),
        )
    ):
        failures.append("oracle-perfect harness metric is below one")
    if _mean(pair_values["physical_delta_leak"]) != 0.0:
        failures.append("oracle-perfect physical leakage is nonzero")
    if _mean(pair_values["event_delta_leak"]) != 0.0:
        failures.append("oracle-perfect event leakage is nonzero")
    if anti_gaming["status"] != "PASS":
        failures.append("oracle-perfect anti-gaming fixture failed")
    if transfer["status"] != "READY":
        failures.append("transfer matrix is not identified and ready")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "scope": "EXPLORATORY_V3_SMOKE_HARNESS_ONLY",
        "retained_or_confirmation_result": False,
        "data_dir": data_dir.as_posix(),
        "family_count": len(families),
        "example_count": len(examples),
        "example_counts": dict(
            Counter(example.input_condition for example in examples)
        ),
        "parser": {
            "attempt_count": len(examples),
            "success_count": len(examples) - sum(parse_errors.values()),
            "error_counts": dict(parse_errors),
            "forbidden_target_prompt_count": forbidden_prompt_rows,
        },
        "oracle_fixture_pair_metrics": {
            name: _mean(values)
            for name, values in pair_values.items()
        },
        "scenario_cluster_bootstrap": pair_bootstrap,
        "factual_twin": {
            "changed_field_macro_f1": changed_field_f1,
            "change_set_precision": _mean(
                [score.change_set_precision for score in factual_twin_scores]
            ),
            "change_set_recall": _mean(
                [score.change_set_recall for score in factual_twin_scores]
            ),
            "physical_twin_sensitivity": physical_twin_sensitivity,
        },
        "rollout": {
            str(horizon): {
                name: _mean(values)
                for name, values in metrics.items()
            }
            for horizon, metrics in sorted(rollout_metrics.items())
        },
        "information_diagnostics": information,
        "anti_gaming_fixture": anti_gaming,
        "normative_strata_support": dict(sorted(normative_strata.items())),
        "transfer": transfer,
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
            "artifacts/phase2_internal/evaluation_harness_check.json"
        ),
    )
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--bootstrap-seed", type=int, default=20260916)
    args = parser.parse_args()
    report = run_internal_check(
        args.data_dir,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "failures": report["failures"],
                "family_count": report["family_count"],
                "example_count": report["example_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
