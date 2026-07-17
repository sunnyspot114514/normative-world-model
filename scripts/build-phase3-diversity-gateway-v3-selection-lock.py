"""Build or verify the disjoint v3 gateway and v4 fallback populations."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

from normative_world_model.phase3_comparison import (
    compact_binding,
    evaluation_binding,
    pair_binding,
    select_balanced_evaluation_records,
    select_comparison_pairs,
)
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/phase3_diversity_gateway_v3.toml"
BASE_CONFIG_PATH = ROOT / "configs/phase3_retained_arm_comparison.toml"
BASE_SELECTION_PATH = ROOT / "configs/phase3_retained_arm_selection_lock.json"
V2_SELECTION_PATH = (
    ROOT / "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"
)
LOCK_PATH = ROOT / "configs/phase3_diversity_gateway_v3_selection_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def build_lock() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as handle:
        gateway = tomllib.load(handle)
    with BASE_CONFIG_PATH.open("rb") as handle:
        base = tomllib.load(handle)
    base_lock = json.loads(BASE_SELECTION_PATH.read_text(encoding="utf-8"))
    v2_lock = json.loads(V2_SELECTION_PATH.read_text(encoding="utf-8"))
    records = _records(ROOT / base["data"]["joint"])
    selection = base["selection"]

    formal_pairs = select_comparison_pairs(
        records,
        seed=int(gateway["training"]["pair_seed"]),
        maximum=int(gateway["training"]["unique_pairs"]),
    )
    schema = select_unique_development_records(records)
    schema_scenarios = {str(row["scenario_id"]) for row in schema}
    v1 = select_balanced_evaluation_records(
        records,
        seed=int(selection["smoke_evaluation_seed"]),
        per_bucket=int(selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios,
    )
    v1_scenarios = {str(row["scenario_id"]) for row in v1}
    formal = select_balanced_evaluation_records(
        records,
        seed=int(selection["formal_evaluation_seed"]),
        per_bucket=int(selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios | v1_scenarios,
    )
    formal_scenarios = {str(row["scenario_id"]) for row in formal}
    v2 = select_balanced_evaluation_records(
        records,
        seed=int(v2_lock["seed"]),
        per_bucket=1,
        excluded_scenarios=(
            schema_scenarios | v1_scenarios | formal_scenarios
        ),
    )
    v2_scenarios = {str(row["scenario_id"]) for row in v2}
    prior = schema_scenarios | v1_scenarios | formal_scenarios | v2_scenarios
    gateway_rows = select_balanced_evaluation_records(
        records,
        seed=int(gateway["evaluation"]["gateway_seed"]),
        per_bucket=int(gateway["evaluation"]["records_per_bucket"]),
        excluded_scenarios=prior,
    )
    gateway_scenarios = {str(row["scenario_id"]) for row in gateway_rows}
    fallback_rows = select_balanced_evaluation_records(
        records,
        seed=int(gateway["evaluation"]["fallback_reservation_seed"]),
        per_bucket=int(gateway["evaluation"]["records_per_bucket"]),
        excluded_scenarios=prior | gateway_scenarios,
    )
    fallback_scenarios = {str(row["scenario_id"]) for row in fallback_rows}

    training_binding = compact_binding(pair_binding(formal_pairs))
    training_prefix_binding = compact_binding(pair_binding(formal_pairs[:128]))
    training_scenarios = {
        str(pair.left["scenario_id"]) for pair in formal_pairs
    }
    v2_binding = compact_binding(evaluation_binding(v2))
    gateway_binding = compact_binding(evaluation_binding(gateway_rows))
    fallback_binding = compact_binding(evaluation_binding(fallback_rows))
    all_populations = (
        schema_scenarios,
        v1_scenarios,
        formal_scenarios,
        v2_scenarios,
        gateway_scenarios,
        fallback_scenarios,
    )
    disjoint_total = set().union(*all_populations)
    checks = {
        "base_selection_lock_pass": base_lock.get("status") == "PASS",
        "v2_selection_lock_pass": v2_lock.get("status") == "PASS",
        "training_is_frozen_formal_selection": (
            training_binding == base_lock.get("formal_training")
        ),
        "first_128_training_pairs_replay_v1_and_v2_prefix": (
            training_prefix_binding == base_lock.get("smoke_training")
        ),
        "v2_evaluation_rebuilds_its_frozen_binding": (
            v2_binding == v2_lock.get("v2_evaluation")
        ),
        "training_has_1024_unique_scenarios": (
            training_binding["count"] == 1024
            and training_binding["unique_scenario_count"] == 1024
        ),
        "gateway_has_one_record_in_each_of_48_buckets": (
            gateway_binding["count"] == 48
            and gateway_binding["bucket_count"] == 48
            and gateway_binding["minimum_bucket_count"] == 1
            and gateway_binding["maximum_bucket_count"] == 1
        ),
        "fallback_has_one_record_in_each_of_48_buckets": (
            fallback_binding["count"] == 48
            and fallback_binding["bucket_count"] == 48
            and fallback_binding["minimum_bucket_count"] == 1
            and fallback_binding["maximum_bucket_count"] == 1
        ),
        "all_development_populations_are_scenario_disjoint": (
            len(disjoint_total) == sum(len(group) for group in all_populations)
        ),
        "training_is_disjoint_from_all_development_populations": not (
            training_scenarios & disjoint_total
        ),
        "confirmation_absent": all(
            row.get("split") != "confirmation" for row in records
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"gateway selection checks failed: {checks}")
    return {
        "version": "3.0-diversity-gateway-selection-lock",
        "status": "PASS",
        "gateway_config_sha256": _sha256(CONFIG_PATH),
        "base_config_sha256": _sha256(BASE_CONFIG_PATH),
        "base_selection_lock_sha256": _sha256(BASE_SELECTION_PATH),
        "v2_selection_lock_sha256": _sha256(V2_SELECTION_PATH),
        "joint_data_sha256": _sha256(ROOT / base["data"]["joint"]),
        "selector_sha256": _sha256(
            ROOT / "src/normative_world_model/phase3_comparison.py"
        ),
        "seeds": {
            "training": int(gateway["training"]["pair_seed"]),
            "gateway": int(gateway["evaluation"]["gateway_seed"]),
            "fallback_reservation": int(
                gateway["evaluation"]["fallback_reservation_seed"]
            ),
        },
        "excluded": {
            "schema_gate": len(schema_scenarios),
            "v1_smoke": len(v1_scenarios),
            "reserved_formal": len(formal_scenarios),
            "v2_smoke": len(v2_scenarios),
        },
        "formal_training": training_binding,
        "gateway_evaluation": gateway_binding,
        "fallback_reservation": fallback_binding,
        "checks": checks,
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
            failures.append("gateway selection lock is missing")
        else:
            expected = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            if actual != expected:
                failures.append("gateway selection lock differs from rebuild")
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
