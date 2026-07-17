"""Training-only positive control for continuous event-record learnability."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
import sklearn
from sklearn.ensemble import (
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.multioutput import MultiOutputRegressor

from normative_world_model.phase3_comparison import select_comparison_pairs
from normative_world_model.slot_objective import load_slot_inventory

ROOT = Path(__file__).resolve().parents[1]


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _families() -> dict[str, dict[str, Any]]:
    root = ROOT / "data/generated/phase1_discovery_v3"
    output = {}
    for environment in ("game", "organization"):
        for line in (root / f"{environment}.jsonl").read_text(
            encoding="utf-8"
        ).splitlines():
            if line:
                family = json.loads(line)
                output[str(family["scenario_id"])] = family
    return output


def _flatten(value: Any, *, prefix: str = "") -> dict[str, Any]:
    output: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            path = f"{prefix}.{key}" if prefix else str(key)
            if path in {"state.actor", "state.surface_context"}:
                continue
            output.update(_flatten(item, prefix=path))
    elif isinstance(value, list):
        output[f"{prefix}.__length__"] = len(value)
        for item in value:
            encoded = json.dumps(item, sort_keys=True, separators=(",", ":"))
            output[f"{prefix}.__member__.{encoded}"] = 1
    else:
        output[prefix] = value
    return output


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for component in path.split("."):
        current = current[component]
    return current


def _rank(seed: int, environment: str, scenario_id: str) -> str:
    value = f"{seed}\t{environment}\t{scenario_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def audit() -> dict[str, Any]:
    with (ROOT / "configs/phase3_retained_arm_comparison.toml").open(
        "rb"
    ) as handle:
        base = tomllib.load(handle)
    with (ROOT / "configs/phase3_diversity_gateway_v3.toml").open(
        "rb"
    ) as handle:
        gateway = tomllib.load(handle)
    records = _records(ROOT / base["data"]["joint"])
    pairs = select_comparison_pairs(
        records,
        seed=int(gateway["training"]["pair_seed"]),
        maximum=int(gateway["training"]["unique_pairs"]),
    )
    families = _families()
    inventory = load_slot_inventory(
        ROOT / base["architecture"]["slot_inventory"]
    )
    slots = [
        slot
        for slot in inventory.slots
        if slot.role == "event" and slot.kind == "continuous"
    ]
    rows = []
    for pair in pairs:
        scenario_id = str(pair.left["scenario_id"])
        family = families[scenario_id]
        rows.append(
            {
                "scenario_id": scenario_id,
                "environment": str(family["environment"]),
                "features": _flatten(family["model_input"]),
                "target": [
                    float(_nested(family["primary"], slot.path))
                    for slot in slots
                ],
            }
        )
    seed = int(gateway["training_only_headroom"]["split_seed"])
    holdout_fraction = float(
        gateway["training_only_headroom"]["holdout_fraction_per_environment"]
    )
    train_indices: list[int] = []
    holdout_indices: list[int] = []
    for environment in ("game", "organization"):
        indices = [
            index
            for index, row in enumerate(rows)
            if row["environment"] == environment
        ]
        indices.sort(
            key=lambda index: _rank(
                seed, environment, str(rows[index]["scenario_id"])
            )
        )
        count = round(len(indices) * holdout_fraction)
        holdout_indices.extend(indices[:count])
        train_indices.extend(indices[count:])
    vectorizer = DictVectorizer(sparse=False, sort=True)
    train_x = vectorizer.fit_transform(
        [rows[index]["features"] for index in train_indices]
    )
    holdout_x = vectorizer.transform(
        [rows[index]["features"] for index in holdout_indices]
    )
    train_y = np.asarray(
        [rows[index]["target"] for index in train_indices], dtype=np.float64
    )
    holdout_y = np.asarray(
        [rows[index]["target"] for index in holdout_indices], dtype=np.float64
    )
    models = {
        "extra_trees_primary": ExtraTreesRegressor(
            n_estimators=400,
            random_state=seed,
            n_jobs=-1,
            max_features=1.0,
            min_samples_leaf=1,
        ),
        "random_forest_sensitivity": RandomForestRegressor(
            n_estimators=400,
            random_state=seed,
            n_jobs=-1,
            max_features=1.0,
            min_samples_leaf=1,
        ),
        "hist_gradient_boosting_sensitivity": MultiOutputRegressor(
            HistGradientBoostingRegressor(
                max_iter=300,
                learning_rate=0.08,
                l2_regularization=1e-6,
                random_state=seed,
            ),
            n_jobs=-1,
        ),
    }
    targets = {"train": train_y, "holdout": holdout_y}
    metrics = {}
    for model_name, model in models.items():
        model.fit(train_x, train_y)
        predictions = {
            "train": model.predict(train_x),
            "holdout": model.predict(holdout_x),
        }
        metrics[model_name] = {}
        for split in ("train", "holdout"):
            r2_values = r2_score(
                targets[split], predictions[split], multioutput="raw_values"
            )
            mae_values = mean_absolute_error(
                targets[split], predictions[split], multioutput="raw_values"
            )
            metrics[model_name][split] = {
                "macro_r2": float(np.mean(r2_values)),
                "macro_mae": float(np.mean(mae_values)),
                "per_slot": {
                    slot.path: {
                        "r2": float(r2_values[index]),
                        "mae": float(mae_values[index]),
                    }
                    for index, slot in enumerate(slots)
                },
            }
    return {
        "status": "DIAGNOSTIC_COMPLETE",
        "scope": "frozen_formal_training_population_only",
        "development_targets_visible": False,
        "confirmation_targets_visible": False,
        "split_seed": seed,
        "records": len(rows),
        "train_records": len(train_indices),
        "holdout_records": len(holdout_indices),
        "feature_count": int(train_x.shape[1]),
        "models": {
            "primary": "extra_trees_primary",
            "sensitivity_added_after_primary_result": True,
            "primary_holdout_macro_r2_seen_before_sensitivity": (
                0.41959495994105744
            ),
            "sklearn": sklearn.__version__,
            "python": platform.python_version(),
        },
        "metrics": metrics,
        "interpretation": (
            "positive_control_only; does not change gateway thresholds or "
            "authorize model training"
        ),
    }


def main() -> int:
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
