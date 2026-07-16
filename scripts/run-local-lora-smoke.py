"""Run one masked causal-LM LoRA optimizer step on the shortest joint record."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import platform
import time
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

from normative_world_model.local_pilot import encode_sft_record


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _iter_records(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line:
                yield json.loads(line)


def _shortest_record(
    tokenizer: Any,
    path: Path,
    max_sequence_tokens: int,
) -> tuple[dict[str, Any], Any]:
    selected = None
    selected_encoding = None
    for record in _iter_records(path):
        try:
            encoding = encode_sft_record(
                tokenizer,
                record,
                max_sequence_tokens=max_sequence_tokens,
            )
        except ValueError:
            continue
        candidate = (encoding.total_tokens, record["record_id"])
        if selected is None or candidate < (
            selected_encoding.total_tokens,
            selected["record_id"],
        ):
            selected = record
            selected_encoding = encoding
    if selected is None:
        raise RuntimeError("no record fits the configured sequence cap")
    return selected, selected_encoding


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local_pilot_qwen3_1_7b.toml"),
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(
            "data/generated/phase3_internal/arms/joint_one_step.jsonl.gz"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/phase3_internal/lora_smoke_one_step.json"),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    runtime = config["runtime"]
    lora = config["lora"]
    smoke = config["smoke"]
    model_config = config["model"]
    set_seed(int(runtime["seed"]))
    model_dir = Path(model_config["local_dir"])
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        local_files_only=True,
        trust_remote_code=False,
    )
    record, encoding = _shortest_record(
        tokenizer,
        args.dataset,
        int(runtime["max_sequence_tokens"]),
    )
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.float16,
        attn_implementation=runtime["attention_implementation"],
    ).to("cuda")
    model.config.use_cache = False
    if runtime["gradient_checkpointing"]:
        model.gradient_checkpointing_enable()
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            target_modules=list(lora["target_modules"]),
            bias="none",
        ),
    )
    trainable_parameters = sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
    input_ids = torch.tensor(
        [encoding.input_ids],
        dtype=torch.long,
        device="cuda",
    )
    labels = torch.tensor(
        [encoding.labels],
        dtype=torch.long,
        device="cuda",
    )
    attention_mask = torch.ones_like(input_ids)
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=float(smoke["learning_rate"]),
    )
    optimizer.zero_grad(set_to_none=True)
    with torch.autocast(device_type="cuda", dtype=torch.float16):
        output = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
        )
        loss = output.loss
    if not math.isfinite(float(loss.detach().cpu())):
        raise RuntimeError(f"non-finite forward loss: {loss}")
    loss.backward()
    optimizer.step()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    total_device_memory = torch.cuda.get_device_properties(0).total_memory
    peak_allocated = torch.cuda.max_memory_allocated()
    peak_reserved = torch.cuda.max_memory_reserved()
    max_peak_fraction = float(runtime["max_peak_memory_fraction"])
    peak_fraction = peak_allocated / total_device_memory
    report = {
        "status": "PASS" if peak_fraction <= max_peak_fraction else "FAIL",
        "scope": config["governance"]["scope"],
        "arm": smoke["arm"],
        "model_id": model_config["model_id"],
        "model_revision": model_config["revision"],
        "dataset": str(args.dataset),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "record_id": record["record_id"],
        "scenario_id": record["scenario_id"],
        "input_condition": record["input_condition"],
        "prompt_tokens": encoding.prompt_tokens,
        "target_tokens": encoding.target_tokens,
        "total_tokens": encoding.total_tokens,
        "loss": float(loss.detach().cpu()),
        "optimizer_steps": 1,
        "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters,
        "trainable_fraction": trainable_parameters / total_parameters,
        "wall_clock_seconds": elapsed,
        "device_total_memory_bytes": total_device_memory,
        "peak_allocated_bytes": peak_allocated,
        "peak_reserved_bytes": peak_reserved,
        "peak_allocated_fraction": peak_fraction,
        "max_peak_memory_fraction": max_peak_fraction,
        "gpu": torch.cuda.get_device_name(0),
        "cuda_runtime": torch.version.cuda,
        "platform": platform.platform(),
        "packages": {
            name: version(name)
            for name in ("peft", "torch", "transformers")
        },
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
