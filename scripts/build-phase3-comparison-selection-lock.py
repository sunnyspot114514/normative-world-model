"""Inspect or verify the deterministic retained Phase-3 selections."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
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
from normative_world_model.phase3_schema_gate import (
    select_unique_development_records,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/phase3_retained_arm_comparison.toml"
LOCK_PATH = ROOT / "configs/phase3_retained_arm_selection_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def build_lock() -> dict[str, Any]:
    with CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)
    data = config["data"]
    selection = config["selection"]
    joint_path = ROOT / data["joint"]
    records = _records(joint_path)
    formal_pairs = select_comparison_pairs(
        records,
        seed=int(selection["pair_seed"]),
        maximum=int(selection["formal_training_pairs"]),
    )
    smoke_count = int(selection["smoke_training_pairs"])
    smoke_pairs = formal_pairs[:smoke_count]

    schema_records = select_unique_development_records(records)
    schema_scenarios = {
        str(record["scenario_id"]) for record in schema_records
    }
    smoke_evaluation = select_balanced_evaluation_records(
        records,
        seed=int(selection["smoke_evaluation_seed"]),
        per_bucket=int(selection["smoke_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios,
    )
    smoke_scenarios = {
        str(record["scenario_id"]) for record in smoke_evaluation
    }
    formal_evaluation = select_balanced_evaluation_records(
        records,
        seed=int(selection["formal_evaluation_seed"]),
        per_bucket=int(selection["formal_evaluation_records_per_bucket"]),
        excluded_scenarios=schema_scenarios | smoke_scenarios,
    )
    formal_evaluation_scenarios = {
        str(record["scenario_id"]) for record in formal_evaluation
    }
    formal_training_scenarios = {
        str(pair.left["scenario_id"]) for pair in formal_pairs
    }
    checks = {
        "smoke_pairs_are_formal_prefix": (
            [pair.left["record_id"] for pair in smoke_pairs]
            == [
                pair.left["record_id"]
                for pair in formal_pairs[:smoke_count]
            ]
        ),
        "schema_and_smoke_development_disjoint": not (
            schema_scenarios & smoke_scenarios
        ),
        "smoke_and_formal_development_disjoint": not (
            smoke_scenarios & formal_evaluation_scenarios
        ),
        "schema_and_formal_development_disjoint": not (
            schema_scenarios & formal_evaluation_scenarios
        ),
        "training_and_formal_development_disjoint": not (
            formal_training_scenarios & formal_evaluation_scenarios
        ),
        "confirmation_absent": all(
            record.get("split") != "confirmation" for record in records
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"selection checks failed: {checks}")
    return {
        "version": "1.0-schema-native-selection-lock",
        "status": "PASS",
        "config_sha256": _sha256(CONFIG_PATH),
        "joint_data_sha256": _sha256(joint_path),
        "selector_sha256": _sha256(
            ROOT / "src/normative_world_model/phase3_comparison.py"
        ),
        "seeds": {
            "pair": int(selection["pair_seed"]),
            "smoke_evaluation": int(
                selection["smoke_evaluation_seed"]
            ),
            "formal_evaluation": int(
                selection["formal_evaluation_seed"]
            ),
        },
        "schema_gate_consumed_development": {
            "count": len(schema_records),
            "scenario_order_sha256": canonical_digest(
                [record["scenario_id"] for record in schema_records]
            ),
        },
        "smoke_training": compact_binding(pair_binding(smoke_pairs)),
        "formal_training": compact_binding(pair_binding(formal_pairs)),
        "smoke_evaluation": compact_binding(
            evaluation_binding(smoke_evaluation)
        ),
        "formal_evaluation": compact_binding(
            evaluation_binding(formal_evaluation)
        ),
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
            failures.append("selection lock is missing")
        else:
            expected = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            if actual != expected:
                failures.append("selection lock differs from deterministic rebuild")
    output = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "lock": actual,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
