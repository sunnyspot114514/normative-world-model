"""Post-hoc train-fit diagnostic for the preserved BLOCKED smoke."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from safetensors.torch import load_file
from transformers import AutoModel, AutoTokenizer

from normative_world_model.model_output import parse_model_output
from normative_world_model.phase2_metrics import score_one_step
from normative_world_model.phase3_comparison import (
    compact_binding,
    pair_binding,
    select_comparison_pairs,
)
from normative_world_model.slot_objective import (
    build_slot_head_bank,
    decode_slot_predictions,
    load_slot_inventory,
)
from normative_world_model.smoke_result_lock import (
    verify_phase3_anti_collapse_smoke_result,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/phase3_retained_arm_comparison.toml"
ADAPTER_PATH = ROOT / "runs/phase3_anti_collapse_smoke/adapter"
HEAD_PATH = ROOT / "runs/phase3_anti_collapse_smoke/slot_heads.safetensors"


def _records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for component in path.split("."):
        current = current[component]
    return current


def _entropy(values: list[str]) -> float:
    counts = Counter(values)
    total = len(values)
    return -sum(
        (count / total) * math.log(count / total)
        for count in counts.values()
    )


def _load_model(config: dict[str, Any]) -> tuple[Any, Any, Any]:
    model_dir = ROOT / config["model"]["local_dir"]
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        local_files_only=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    base = AutoModel.from_pretrained(
        model_dir,
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.float16,
        attn_implementation=config["model"]["attention_implementation"],
    ).to("cuda")
    model = PeftModel.from_pretrained(
        base,
        ADAPTER_PATH,
        is_trainable=False,
    )
    inventory = load_slot_inventory(ROOT / config["architecture"]["slot_inventory"])
    heads = build_slot_head_bank(int(model.config.hidden_size), inventory).to(
        "cuda"
    )
    heads.load_state_dict(load_file(HEAD_PATH))
    model.eval()
    heads.eval()
    return tokenizer, model, heads


def audit(batch_size: int) -> dict[str, Any]:
    failures = verify_phase3_anti_collapse_smoke_result(ROOT)
    if failures:
        raise RuntimeError("; ".join(failures))
    with CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)
    records = _records(ROOT / config["data"]["joint"])
    pairs = select_comparison_pairs(
        records,
        seed=int(config["selection"]["pair_seed"]),
        maximum=int(config["selection"]["formal_training_pairs"]),
    )[: int(config["selection"]["smoke_training_pairs"])]
    presentations = [
        record
        for pair in pairs
        for record in (pair.left, pair.right)
    ]
    tokenizer, model, heads = _load_model(config)
    inventory = load_slot_inventory(ROOT / config["architecture"]["slot_inventory"])
    continuous = [slot for slot in inventory.slots if slot.kind == "continuous"]
    decisions: Counter[str] = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    values_by_slot: dict[str, list[str]] = defaultdict(list)
    physical_scores: list[float] = []
    event_scores: list[float] = []
    normative_scores: list[float] = []
    absolute_errors: list[float] = []
    zero_errors: list[float] = []
    maximum = int(config["data"]["max_prompt_tokens"])
    with torch.inference_mode():
        for start in range(0, len(presentations), batch_size):
            batch_records = presentations[start : start + batch_size]
            encoded = tokenizer(
                [record["input_text"].rstrip() + "\n" for record in batch_records],
                add_special_tokens=False,
                padding=True,
                return_tensors="pt",
            )
            if int(encoded["attention_mask"].sum(dim=1).max().item()) > maximum:
                raise ValueError("training-fit prompt exceeds frozen token cap")
            encoded = {key: value.to("cuda") for key, value in encoded.items()}
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = model(**encoded, use_cache=False, return_dict=True)
                last = encoded["attention_mask"].sum(dim=1).long() - 1
                hidden = output.last_hidden_state[
                    torch.arange(len(batch_records), device="cuda"),
                    last,
                ]
                predictions = heads(hidden)
            for row, record in enumerate(batch_records):
                expected = json.loads(record["target_text"])
                decoded = decode_slot_predictions(
                    predictions,
                    inventory,
                    environment=str(record["environment"]),
                    row=row,
                )
                parsed = parse_model_output(
                    json.dumps(
                        decoded,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                    expected,
                )
                if not parsed.ok:
                    raise RuntimeError(
                        f"decoded training output failed schema: {parsed.error}"
                    )
                score = score_one_step(parsed.output, expected)
                physical_scores.append(score.physical.f1)
                event_scores.append(score.event_record.f1)
                normative_scores.append(float(score.normative_correct))
                predicted_decision = str(decoded["normative_decision"])
                target_decision = str(expected["normative_decision"])
                decisions[predicted_decision] += 1
                confusion[(target_decision, predicted_decision)] += 1
                for slot in continuous:
                    predicted = float(_nested(decoded, slot.path))
                    target = float(_nested(expected, slot.path))
                    absolute_errors.append(abs(predicted - target))
                    zero_errors.append(abs(target))
                for slot in inventory.slots:
                    if (
                        record["environment"] in slot.environments
                        and slot.kind in {"categorical", "set"}
                    ):
                        values_by_slot[slot.path].append(
                            json.dumps(
                                _nested(decoded, slot.path),
                                sort_keys=True,
                                ensure_ascii=False,
                            )
                        )
    count = len(presentations)
    return {
        "status": "EXPLORATORY_POST_HOC",
        "population": "frozen_smoke_training_presentations_only",
        "may_reclassify_blocked_gate": False,
        "pair_binding": compact_binding(pair_binding(pairs)),
        "presentations": count,
        "normative_accuracy": sum(normative_scores) / count,
        "predicted_decision_counts": dict(sorted(decisions.items())),
        "target_by_prediction_counts": {
            f"{target}->{prediction}": value
            for (target, prediction), value in sorted(confusion.items())
        },
        "mean_physical_field_f1": sum(physical_scores) / count,
        "mean_event_field_f1": sum(event_scores) / count,
        "event_continuous_mae": sum(absolute_errors) / len(absolute_errors),
        "event_zero_predictor_mae": sum(zero_errors) / len(zero_errors),
        "categorical_constant_slot_fraction": sum(
            len(set(values)) == 1 for values in values_by_slot.values()
        )
        / len(values_by_slot),
        "categorical_output_entropy_by_slot": {
            path: _entropy(values)
            for path, values in sorted(values_by_slot.items())
        },
        "formal_arm_comparison_started": False,
        "confirmation_status": "RESERVED_NOT_GENERATED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    print(
        json.dumps(
            audit(args.batch_size),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
