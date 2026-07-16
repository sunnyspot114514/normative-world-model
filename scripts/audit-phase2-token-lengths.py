"""Audit every smoke arm record against the locked tokenizer and sequence cap."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

from normative_world_model.local_pilot import encode_sft_record


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _quantile(values: list[int], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _iter_jsonl_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line:
                yield json.loads(line)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local_pilot_qwen3_1_7b.toml"),
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/generated/phase2_internal/arms"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/phase3_internal/token_length_audit.json"),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    model_dir = Path(config["model"]["local_dir"])
    max_tokens = int(config["runtime"]["max_sequence_tokens"])
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        local_files_only=True,
        trust_remote_code=False,
    )
    report = {
        "status": "PASS",
        "max_sequence_tokens": max_tokens,
        "files": {},
    }
    for path in sorted(args.data_dir.glob("*.jsonl.gz")):
        totals: list[int] = []
        prompts: list[int] = []
        targets: list[int] = []
        above_cap = []
        by_condition = Counter()
        shortest: tuple[int, str] | None = None
        for record in _iter_jsonl_gzip(path):
            try:
                encoded = encode_sft_record(
                    tokenizer,
                    record,
                    max_sequence_tokens=max_tokens,
                )
            except ValueError:
                uncapped = encode_sft_record(
                    tokenizer,
                    record,
                    max_sequence_tokens=10**9,
                )
                above_cap.append(
                    {
                        "record_id": record["record_id"],
                        "total_tokens": uncapped.total_tokens,
                    }
                )
                encoded = uncapped
            totals.append(encoded.total_tokens)
            prompts.append(encoded.prompt_tokens)
            targets.append(encoded.target_tokens)
            by_condition[record["input_condition"]] += 1
            candidate = (encoded.total_tokens, record["record_id"])
            if shortest is None or candidate < shortest:
                shortest = candidate
        file_status = "PASS" if not above_cap else "FAIL"
        if file_status == "FAIL":
            report["status"] = "FAIL"
        report["files"][path.name] = {
            "status": file_status,
            "record_count": len(totals),
            "input_conditions": dict(sorted(by_condition.items())),
            "prompt_tokens": {
                "max": max(prompts),
                "p50": _quantile(prompts, 0.50),
                "p95": _quantile(prompts, 0.95),
            },
            "target_tokens": {
                "max": max(targets),
                "p50": _quantile(targets, 0.50),
                "p95": _quantile(targets, 0.95),
            },
            "total_tokens": {
                "max": max(totals),
                "p50": _quantile(totals, 0.50),
                "p95": _quantile(totals, 0.95),
            },
            "shortest_record": {
                "record_id": shortest[1],
                "total_tokens": shortest[0],
            },
            "above_cap_count": len(above_cap),
            "above_cap_examples": above_cap[:20],
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
