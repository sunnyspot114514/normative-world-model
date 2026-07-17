"""Inspect or verify the disjoint Phase-3 anti-collapse v2 selection."""

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
    select_balanced_evaluation_records,
)
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)

ROOT = Path(__file__).resolve().parents[1]
V2_CONFIG_PATH = ROOT / "configs/phase3_anti_collapse_smoke_v2.toml"
BASE_CONFIG_PATH = ROOT / "configs/phase3_retained_arm_comparison.toml"
BASE_SELECTION_PATH = ROOT / "configs/phase3_retained_arm_selection_lock.json"
LOCK_PATH = ROOT / "configs/phase3_anti_collapse_smoke_v2_selection_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def build_lock() -> dict[str, Any]:
    with V2_CONFIG_PATH.open("rb") as handle:
        v2 = tomllib.load(handle)
    with BASE_CONFIG_PATH.open("rb") as handle:
        base = tomllib.load(handle)
    base_lock = json.loads(BASE_SELECTION_PATH.read_text(encoding="utf-8"))
    records = _records(ROOT / base["data"]["joint"])
    selection = base["selection"]
    schema_records = select_unique_development_records(records)
    schema_scenarios = {
        str(record["scenario_id"]) for record in schema_records
    }
    v1_records = select_balanced_evaluation_records(
        records,
        seed=int(selection["smoke_evaluation_seed"]),
        per_bucket=int(selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios,
    )
    v1_scenarios = {str(record["scenario_id"]) for record in v1_records}
    formal_records = select_balanced_evaluation_records(
        records,
        seed=int(selection["formal_evaluation_seed"]),
        per_bucket=int(selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios | v1_scenarios,
    )
    formal_scenarios = {
        str(record["scenario_id"]) for record in formal_records
    }
    exclusions = schema_scenarios | v1_scenarios | formal_scenarios
    v2_records = select_balanced_evaluation_records(
        records,
        seed=int(v2["evaluation"]["seed"]),
        per_bucket=int(v2["evaluation"]["records_per_bucket"]),
        excluded_scenarios=exclusions,
    )
    v2_scenarios = {str(record["scenario_id"]) for record in v2_records}
    binding = compact_binding(evaluation_binding(v2_records))
    checks = {
        "base_selection_lock_pass": base_lock.get("status") == "PASS",
        "base_selection_lock_rebuilt_v1": (
            compact_binding(evaluation_binding(v1_records))
            == base_lock.get("smoke_evaluation")
        ),
        "base_selection_lock_rebuilt_formal": (
            compact_binding(evaluation_binding(formal_records))
            == base_lock.get("formal_evaluation")
        ),
        "v2_has_48_balanced_records": (
            binding["count"] == 48
            and binding["bucket_count"] == 48
            and binding["minimum_bucket_count"] == 1
            and binding["maximum_bucket_count"] == 1
        ),
        "v2_scenarios_are_unique": len(v2_scenarios) == len(v2_records),
        "v2_is_disjoint_from_all_prior_development": not (
            v2_scenarios & exclusions
        ),
        "confirmation_absent": all(
            record.get("split") != "confirmation" for record in records
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"v2 selection checks failed: {checks}")
    return {
        "version": "2.0-disjoint-anti-collapse-selection",
        "status": "PASS",
        "v2_config_sha256": _sha256(V2_CONFIG_PATH),
        "base_config_sha256": _sha256(BASE_CONFIG_PATH),
        "base_selection_lock_sha256": _sha256(BASE_SELECTION_PATH),
        "joint_data_sha256": _sha256(ROOT / base["data"]["joint"]),
        "selector_sha256": _sha256(
            ROOT / "src/normative_world_model/phase3_comparison.py"
        ),
        "seed": int(v2["evaluation"]["seed"]),
        "excluded": {
            "schema_gate": len(schema_scenarios),
            "v1_smoke": len(v1_scenarios),
            "reserved_formal": len(formal_scenarios),
        },
        "v2_evaluation": binding,
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
            failures.append("v2 selection lock is missing")
        else:
            expected = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            if actual != expected:
                failures.append("v2 selection lock differs from rebuild")
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
