"""Build or verify the exact training and reserved V4 evaluation bindings."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import tomllib
from pathlib import Path
from typing import Any

from normative_world_model.phase3_comparison import (
    canonical_digest,
    compact_binding,
    evaluation_binding,
    pair_binding,
    select_balanced_evaluation_records,
    select_comparison_pairs,
)
from normative_world_model.phase3_gateway_v4 import (
    build_continuous_statistics,
    build_normative_class_weights,
)
from normative_world_model.phase3_schema_gate import select_unique_development_records
from normative_world_model.slot_objective import load_slot_inventory

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/phase3_representation_gateway_v4.toml"
BASE_CONFIG_PATH = ROOT / "configs/phase3_retained_arm_comparison.toml"
BASE_SELECTION_PATH = ROOT / "configs/phase3_retained_arm_selection_lock.json"
V2_SELECTION_PATH = ROOT / "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"
V3_CONFIG_PATH = ROOT / "configs/phase3_diversity_gateway_v3.toml"
V3_SELECTION_PATH = ROOT / "configs/phase3_diversity_gateway_v3_selection_lock.json"
LOCK_PATH = ROOT / "configs/phase3_representation_gateway_v4_selection_lock.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one object")
    return value


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def select_v4_populations() -> tuple[list[Any], list[dict[str, Any]]]:
    config = _load_toml(CONFIG_PATH)
    base = _load_toml(BASE_CONFIG_PATH)
    v3 = _load_toml(V3_CONFIG_PATH)
    v2_lock = _load_json(V2_SELECTION_PATH)
    records = _records(ROOT / base["data"]["joint"])
    pairs = select_comparison_pairs(
        records,
        seed=int(config["training"]["pair_seed"]),
        maximum=int(config["training"]["unique_pairs"]),
    )
    base_selection = base["selection"]
    schema = select_unique_development_records(records)
    schema_ids = {str(row["scenario_id"]) for row in schema}
    v1 = select_balanced_evaluation_records(
        records,
        seed=int(base_selection["smoke_evaluation_seed"]),
        per_bucket=int(base_selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_ids,
    )
    v1_ids = {str(row["scenario_id"]) for row in v1}
    formal = select_balanced_evaluation_records(
        records,
        seed=int(base_selection["formal_evaluation_seed"]),
        per_bucket=int(base_selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_ids | v1_ids,
    )
    formal_ids = {str(row["scenario_id"]) for row in formal}
    v2 = select_balanced_evaluation_records(
        records,
        seed=int(v2_lock["seed"]),
        per_bucket=1,
        excluded_scenarios=schema_ids | v1_ids | formal_ids,
    )
    v2_ids = {str(row["scenario_id"]) for row in v2}
    v3_rows = select_balanced_evaluation_records(
        records,
        seed=int(v3["evaluation"]["gateway_seed"]),
        per_bucket=int(v3["evaluation"]["records_per_bucket"]),
        excluded_scenarios=schema_ids | v1_ids | formal_ids | v2_ids,
    )
    v3_ids = {str(row["scenario_id"]) for row in v3_rows}
    v4_rows = select_balanced_evaluation_records(
        records,
        seed=int(config["evaluation"]["seed"]),
        per_bucket=int(config["evaluation"]["records_per_bucket"]),
        excluded_scenarios=schema_ids | v1_ids | formal_ids | v2_ids | v3_ids,
    )
    return pairs, v4_rows


def build_lock() -> dict[str, Any]:
    config = _load_toml(CONFIG_PATH)
    base = _load_toml(BASE_CONFIG_PATH)
    base_lock = _load_json(BASE_SELECTION_PATH)
    v3_lock = _load_json(V3_SELECTION_PATH)
    pairs, evaluation = select_v4_populations()
    inventory = load_slot_inventory(ROOT / config["representation"]["slot_inventory"])
    training_binding = compact_binding(pair_binding(pairs))
    evaluation_binding_value = compact_binding(evaluation_binding(evaluation))
    statistics = build_continuous_statistics(
        pairs,
        inventory,
        standard_deviation_floor=float(
            config["continuous_objective"]["standard_deviation_floor"]
        ),
    )
    class_weights = build_normative_class_weights(
        pairs,
        inventory,
        exponent=float(config["normative_weighting"]["raw_exponent"]),
        cap=float(config["normative_weighting"]["pre_renormalization_cap"]),
    )
    checks = {
        "base_selection_lock_pass": base_lock.get("status") == "PASS",
        "v3_selection_lock_pass": v3_lock.get("status") == "PASS",
        "training_reuses_frozen_formal_selection": (
            training_binding == base_lock.get("formal_training")
            and training_binding == v3_lock.get("formal_training")
        ),
        "evaluation_is_exact_v3_fallback_reservation": (
            evaluation_binding_value == v3_lock.get("fallback_reservation")
        ),
        "training_has_1024_unique_scenarios": (
            training_binding["count"] == 1024
            and training_binding["unique_scenario_count"] == 1024
        ),
        "evaluation_has_one_record_in_each_of_48_buckets": (
            evaluation_binding_value["count"] == 48
            and evaluation_binding_value["unique_scenario_count"] == 48
            and evaluation_binding_value["bucket_count"] == 48
            and evaluation_binding_value["minimum_bucket_count"] == 1
            and evaluation_binding_value["maximum_bucket_count"] == 1
        ),
        "training_and_evaluation_are_scenario_disjoint": not (
            {str(pair.left["scenario_id"]) for pair in pairs}
            & {str(row["scenario_id"]) for row in evaluation}
        ),
        "continuous_statistics_cover_every_continuous_slot": (
            set(statistics)
            == {slot.path for slot in inventory.slots if slot.kind == "continuous"}
        ),
        "continuous_statistics_use_all_2048_presentations": all(
            int(item["count"]) == 2048 for item in statistics.values()
        ),
        "all_normative_classes_have_positive_training_exposure": all(
            int(count) > 0 for count in class_weights["counts"].values()
        ),
        "normative_weights_have_exposure_weighted_mean_one": math.isclose(
            float(class_weights["exposure_weighted_mean"]),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"V4 selection checks failed: {checks}")
    return {
        "version": "4.0-role-query-selection-lock",
        "status": "PASS",
        "v4_config_sha256": _sha256(CONFIG_PATH),
        "base_config_sha256": _sha256(BASE_CONFIG_PATH),
        "base_selection_lock_sha256": _sha256(BASE_SELECTION_PATH),
        "v3_config_sha256": _sha256(V3_CONFIG_PATH),
        "v3_selection_lock_sha256": _sha256(V3_SELECTION_PATH),
        "joint_data_sha256": _sha256(ROOT / base["data"]["joint"]),
        "selector_sha256": _sha256(
            ROOT / "src/normative_world_model/phase3_comparison.py"
        ),
        "v4_objective_sha256": _sha256(
            ROOT / "src/normative_world_model/phase3_gateway_v4.py"
        ),
        "seeds": {
            "training": int(config["training"]["pair_seed"]),
            "evaluation": int(config["evaluation"]["seed"]),
        },
        "formal_training": training_binding,
        "v4_evaluation": evaluation_binding_value,
        "continuous_statistics": statistics,
        "continuous_statistics_sha256": canonical_digest(statistics),
        "normative_class_weights": class_weights,
        "normative_class_weights_sha256": canonical_digest(class_weights),
        "checks": checks,
        "formal_arm_comparison_started": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("inspect", "verify"), default="inspect")
    args = parser.parse_args()
    actual = build_lock()
    failures: list[str] = []
    if args.mode == "verify":
        if not LOCK_PATH.is_file():
            failures.append("V4 selection lock is missing")
        elif _load_json(LOCK_PATH) != actual:
            failures.append("V4 selection lock differs from deterministic rebuild")
    print(
        json.dumps(
            {
                "status": "PASS" if not failures else "FAIL",
                "failures": failures,
                "lock": actual,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
