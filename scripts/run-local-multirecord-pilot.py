"""Run an exploratory multi-record LoRA pilot without retained/confirmation data."""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import math
import time
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as functional
from peft import (
    LoraConfig,
    PeftModel,
    TaskType,
    get_peft_model,
)
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    set_seed,
)

from normative_world_model.local_pilot import (
    ConsistencyPair,
    SftEncoding,
    build_consistency_pairs,
    encode_sft_record,
    factual_target_token_ids,
    pad_sft_encodings,
)
from normative_world_model.model_arms import (
    build_factorized_factual_records,
    factorized_normative_input_text,
    recompute_factorized_policy_result,
)
from normative_world_model.model_output import (
    combine_factorized_output,
    parse_factual_output,
    parse_model_output,
    parse_normative_output,
)
from normative_world_model.phase2_metrics import (
    score_evaluator_pair,
    score_one_step,
)
from normative_world_model.transfer_matrix import TARGET_PROFILE_PAIRS

ARM_DATASETS = {
    "joint_naive": "joint_one_step.jsonl.gz",
    "joint_consistency": "joint_one_step.jsonl.gz",
    "factorized_factual": "factorized_factual_one_step.jsonl.gz",
    "factorized_normative": "factorized_normative.jsonl.gz",
}
ALL_ARMS = tuple(ARM_DATASETS)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _load_jsonl_gzip(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line]


def _load_families(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _base_model(config: dict[str, Any]) -> Any:
    runtime = config["runtime"]
    model_config = config["model"]
    model = AutoModelForCausalLM.from_pretrained(
        Path(model_config["local_dir"]),
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.float16,
        attn_implementation=runtime["attention_implementation"],
    ).to("cuda")
    model.config.use_cache = False
    if runtime["gradient_checkpointing"]:
        model.gradient_checkpointing_enable()
    return model


def _lora_model(config: dict[str, Any]) -> Any:
    lora = config["lora"]
    return get_peft_model(
        _base_model(config),
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            target_modules=list(lora["target_modules"]),
            bias="none",
        ),
    )


def _tokenizer(config: dict[str, Any]) -> Any:
    tokenizer = AutoTokenizer.from_pretrained(
        Path(config["model"]["local_dir"]),
        local_files_only=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer


def _encoding(
    tokenizer: Any,
    record: dict[str, Any],
    config: dict[str, Any],
) -> SftEncoding:
    return encode_sft_record(
        tokenizer,
        record,
        max_sequence_tokens=int(
            config["runtime"]["max_sequence_tokens"]
        ),
    )


def _balanced_shortest_records(
    records: list[dict[str, Any]],
    tokenizer: Any,
    config: dict[str, Any],
    maximum: int,
    *,
    split: str = "train",
) -> list[tuple[dict[str, Any], SftEncoding]]:
    buckets: dict[
        tuple[str, str, str],
        list[tuple[dict[str, Any], SftEncoding]],
    ] = defaultdict(list)
    for record in records:
        if record.get("split") != split:
            continue
        try:
            encoding = _encoding(tokenizer, record, config)
        except ValueError:
            continue
        bucket = (
            str(record["environment"]),
            str(record["input_condition"]),
            str(record.get("profile_id", "")),
        )
        buckets[bucket].append((record, encoding))
    for bucket in buckets.values():
        bucket.sort(
            key=lambda item: (
                item[1].total_tokens,
                item[0]["scenario_id"],
                item[0]["record_id"],
            )
        )
    selected = []
    seen_scenarios = set()
    positions = {name: 0 for name in buckets}
    while len(selected) < maximum:
        progress = False
        for name in sorted(buckets):
            bucket = buckets[name]
            while positions[name] < len(bucket):
                item = bucket[positions[name]]
                positions[name] += 1
                if item[0]["scenario_id"] in seen_scenarios:
                    continue
                selected.append(item)
                seen_scenarios.add(item[0]["scenario_id"])
                progress = True
                break
            if len(selected) >= maximum:
                break
        if not progress:
            break
    return selected


def _balanced_shortest_pairs(
    records: list[dict[str, Any]],
    tokenizer: Any,
    config: dict[str, Any],
    maximum: int,
    *,
    split: str = "train",
) -> list[tuple[ConsistencyPair, SftEncoding, SftEncoding]]:
    eligible = [record for record in records if record["split"] == split]
    candidates = []
    for pair in build_consistency_pairs(eligible):
        try:
            left = _encoding(tokenizer, dict(pair.left), config)
            right = _encoding(tokenizer, dict(pair.right), config)
        except ValueError:
            continue
        if factual_target_token_ids(left) != factual_target_token_ids(right):
            raise RuntimeError("paired factual targets are not token-identical")
        candidates.append((pair, left, right))
    candidates.sort(
        key=lambda item: (
            max(item[1].total_tokens, item[2].total_tokens),
            item[0].pair_type,
            item[0].left["scenario_id"],
            item[0].left["record_id"],
            item[0].right["record_id"],
        )
    )
    buckets: dict[
        tuple[str, str, str, str],
        list[tuple[ConsistencyPair, SftEncoding, SftEncoding]],
    ] = defaultdict(list)
    for item in candidates:
        pair = item[0]
        bucket = (
            pair.pair_type,
            str(pair.left["environment"]),
            str(pair.left["input_condition"]),
            (
                f"{pair.left['profile_id']}|{pair.right['profile_id']}"
                if pair.pair_type == "semantic_evaluator"
                else str(pair.left["profile_id"])
            ),
        )
        buckets[bucket].append(item)
    selected = []
    seen_scenarios = set()
    positions = {name: 0 for name in buckets}
    while len(selected) < maximum:
        progress = False
        for name in sorted(buckets):
            bucket = buckets[name]
            while positions[name] < len(bucket):
                item = bucket[positions[name]]
                positions[name] += 1
                scenario_id = str(item[0].left["scenario_id"])
                if scenario_id in seen_scenarios:
                    continue
                selected.append(item)
                seen_scenarios.add(scenario_id)
                progress = True
                break
            if len(selected) >= maximum:
                break
        if not progress:
            break
    return selected


def _tensor_batch(
    encodings: list[SftEncoding],
    *,
    pad_token_id: int,
) -> tuple[dict[str, torch.Tensor], Any]:
    padded = pad_sft_encodings(
        encodings,
        pad_token_id=pad_token_id,
    )
    tensors = {
        "input_ids": torch.tensor(
            padded.input_ids,
            dtype=torch.long,
            device="cuda",
        ),
        "labels": torch.tensor(
            padded.labels,
            dtype=torch.long,
            device="cuda",
        ),
        "attention_mask": torch.tensor(
            padded.attention_mask,
            dtype=torch.long,
            device="cuda",
        ),
    }
    return tensors, padded


def _gold_token_consistency_loss(
    logits: torch.Tensor,
    encodings: tuple[SftEncoding, ...],
) -> torch.Tensor:
    """Memory-bounded local proxy; not the retained slot-level objective."""

    if len(encodings) != 2:
        raise ValueError("consistency proxy requires exactly two records")
    token_ids = [
        factual_target_token_ids(encoding)
        for encoding in encodings
    ]
    if token_ids[0] != token_ids[1]:
        raise ValueError("paired factual target token IDs differ")
    factual_log_probabilities = []
    for row, encoding in enumerate(encodings):
        span = encoding.factual_logit_slice
        target = torch.tensor(
            token_ids[row],
            dtype=torch.long,
            device=logits.device,
        )
        row_logits = logits[row, span, :]
        factual_log_probabilities.append(
            functional.log_softmax(row_logits.float(), dim=-1)
            .gather(-1, target.unsqueeze(-1))
            .squeeze(-1)
        )
    return functional.smooth_l1_loss(
        factual_log_probabilities[0],
        factual_log_probabilities[1],
    )


def _teacher_forced_evaluation(
    model: Any,
    arm: str,
    records: list[dict[str, Any]],
    tokenizer: Any,
    config: dict[str, Any],
    *,
    maximum: int,
) -> dict[str, Any]:
    if arm in {"joint_naive", "joint_consistency"}:
        items: list[Any] = _balanced_shortest_pairs(
            records,
            tokenizer,
            config,
            maximum,
            split="development",
        )
    else:
        items = _balanced_shortest_records(
            records,
            tokenizer,
            config,
            maximum,
            split="development",
        )
    supervised_losses = []
    consistency_losses = []
    model.eval()
    with torch.inference_mode():
        for item in items:
            if arm in {"joint_naive", "joint_consistency"}:
                _, left, right = item
                encodings = [left, right]
            else:
                _, encoding = item
                encodings = [encoding]
            tensors, padded = _tensor_batch(
                encodings,
                pad_token_id=int(tokenizer.pad_token_id),
            )
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = model(**tensors)
                supervised_losses.append(float(output.loss.detach().cpu()))
                if arm in {"joint_naive", "joint_consistency"}:
                    consistency_losses.append(
                        float(
                            _gold_token_consistency_loss(
                                output.logits,
                                padded.encodings,
                            )
                            .detach()
                            .cpu()
                        )
                    )
            del tensors, output
    model.train()
    return {
        "item_count": len(items),
        "supervised_loss_mean": (
            sum(supervised_losses) / len(supervised_losses)
            if supervised_losses
            else None
        ),
        "consistency_proxy_loss_mean": (
            sum(consistency_losses) / len(consistency_losses)
            if consistency_losses
            else None
        ),
    }


def _train_arm(
    arm: str,
    records: list[dict[str, Any]],
    tokenizer: Any,
    config: dict[str, Any],
    *,
    optimizer_steps: int,
    maximum_records: int,
    consistency_lambda: float,
    adapter_dir: Path,
) -> dict[str, Any]:
    set_seed(int(config["runtime"]["seed"]))
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    model = _lora_model(config)
    optimizer = torch.optim.AdamW(
        (
            parameter
            for parameter in model.parameters()
            if parameter.requires_grad
        ),
        lr=float(config["pilot"]["learning_rate"]),
    )
    if arm in {"joint_naive", "joint_consistency"}:
        selected_pairs = _balanced_shortest_pairs(
            records,
            tokenizer,
            config,
            maximum_records,
        )
        if not selected_pairs:
            raise RuntimeError("no consistency pair fits the sequence cap")
        training_items: list[Any] = selected_pairs
    else:
        selected_records = _balanced_shortest_records(
            records,
            tokenizer,
            config,
            maximum_records,
        )
        if not selected_records:
            raise RuntimeError("no training record fits the sequence cap")
        training_items = selected_records

    losses = []
    supervised_losses = []
    consistency_losses = []
    training_prompt_tokens = 0
    training_target_tokens = 0
    started = time.perf_counter()
    model.train()
    for step in range(optimizer_steps):
        item = training_items[step % len(training_items)]
        if arm in {"joint_naive", "joint_consistency"}:
            pair, left_encoding, right_encoding = item
            encodings = [left_encoding, right_encoding]
        else:
            _, encoding = item
            encodings = [encoding]
        training_prompt_tokens += sum(
            encoding.prompt_tokens for encoding in encodings
        )
        training_target_tokens += sum(
            encoding.target_tokens for encoding in encodings
        )
        tensors, padded = _tensor_batch(
            encodings,
            pad_token_id=int(tokenizer.pad_token_id),
        )
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            output = model(**tensors)
            supervised = output.loss
            if arm in {"joint_naive", "joint_consistency"}:
                consistency = _gold_token_consistency_loss(
                    output.logits,
                    padded.encodings,
                )
                loss = (
                    supervised + consistency_lambda * consistency
                    if arm == "joint_consistency"
                    else supervised
                )
            else:
                consistency = torch.zeros(
                    (),
                    device=supervised.device,
                )
                loss = supervised
        if not math.isfinite(float(loss.detach().cpu())):
            raise RuntimeError(f"non-finite loss at step {step}")
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        supervised_losses.append(float(supervised.detach().cpu()))
        consistency_losses.append(float(consistency.detach().cpu()))
        del tensors, output, loss, supervised, consistency
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    development = _teacher_forced_evaluation(
        model,
        arm,
        records,
        tokenizer,
        config,
        maximum=int(config["pilot"]["teacher_forced_eval_items"]),
    )
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(adapter_dir)
    peak_allocated = torch.cuda.max_memory_allocated()
    device_total = torch.cuda.get_device_properties(0).total_memory
    selected_ids = []
    pair_types = []
    if arm in {"joint_naive", "joint_consistency"}:
        for pair, _, _ in training_items:
            selected_ids.append(
                [
                    pair.left["record_id"],
                    pair.right["record_id"],
                ]
            )
            pair_types.append(pair.pair_type)
    else:
        selected_ids = [item[0]["record_id"] for item in training_items]
    result = {
        "status": (
            "PASS"
            if peak_allocated / device_total
            <= float(config["runtime"]["max_peak_memory_fraction"])
            else "RESOURCE_FAIL"
        ),
        "arm": arm,
        "optimizer_steps": optimizer_steps,
        "selected_training_item_count": len(training_items),
        "unique_training_scenario_count": len(
            {
                (
                    str(item[0].left["scenario_id"])
                    if arm in {"joint_naive", "joint_consistency"}
                    else str(item[0]["scenario_id"])
                )
                for item in training_items
            }
        ),
        "training_prompt_tokens_seen": training_prompt_tokens,
        "training_target_tokens_seen": training_target_tokens,
        "selected_record_ids": selected_ids,
        "pair_types": pair_types,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "loss_minimum": min(losses),
        "supervised_loss_last": supervised_losses[-1],
        "consistency_proxy_loss_last": consistency_losses[-1],
        "consistency_lambda": (
            consistency_lambda if arm == "joint_consistency" else 0.0
        ),
        "consistency_objective_status": (
            "LOCAL_GOLD_TOKEN_PROXY_NOT_RETAINED_SLOT_LOSS"
            if arm == "joint_consistency"
            else "NOT_APPLICABLE"
        ),
        "wall_clock_seconds": elapsed,
        "development_teacher_forced": development,
        "peak_allocated_bytes": peak_allocated,
        "device_total_memory_bytes": device_total,
        "peak_allocated_fraction": peak_allocated / device_total,
        "adapter_dir": adapter_dir.as_posix(),
    }
    del model, optimizer
    gc.collect()
    torch.cuda.empty_cache()
    return result


def _load_adapter_model(
    config: dict[str, Any],
    adapter_dir: Path,
) -> Any:
    model = PeftModel.from_pretrained(
        _base_model(config),
        adapter_dir,
        is_trainable=False,
    )
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    model.eval()
    return model


def _generate(
    model: Any,
    tokenizer: Any,
    input_text: str,
    *,
    max_new_tokens: int,
) -> str:
    encoded = tokenizer(
        input_text.rstrip() + "\n",
        add_special_tokens=False,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"].to("cuda")
    attention_mask = encoded["attention_mask"].to("cuda")
    with torch.inference_mode():
        generated = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    continuation = generated[0, input_ids.shape[1] :]
    return tokenizer.decode(
        continuation,
        skip_special_tokens=True,
    )


def _joint_generation_check(
    arm: str,
    records: list[dict[str, Any]],
    tokenizer: Any,
    config: dict[str, Any],
    adapter_dir: Path,
    *,
    maximum: int,
) -> dict[str, Any]:
    development = sorted(
        (
            record
            for record in records
            if record["split"] == "development"
            and record["input_condition"] == "structured"
            and record["profile_surface_variant"] == 0
        ),
        key=lambda record: (
            record["scenario_id"],
            record["profile_id"],
        ),
    )
    selected = development[:maximum]
    model = _load_adapter_model(config, adapter_dir)
    rows = []
    for record in selected:
        expected = json.loads(record["target_text"])
        text = _generate(
            model,
            tokenizer,
            record["input_text"],
            max_new_tokens=min(
                int(config["pilot"]["generation_max_new_tokens"]),
                _encoding(tokenizer, record, config).target_tokens + 32,
            ),
        )
        parsed = parse_model_output(text, expected)
        score = score_one_step(
            parsed.output if parsed.ok else None,
            expected,
        )
        rows.append(
            {
                "record_id": record["record_id"],
                "scenario_id": record["scenario_id"],
                "profile_id": record["profile_id"],
                "parse_ok": parsed.ok,
                "parse_error": parsed.error_code,
                "physical_field_f1": score.physical.f1,
                "event_field_f1": score.event_record.f1,
                "normative_correct": score.normative_correct,
                "generated_text": text,
            }
        )
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "arm": arm,
        "attempt_count": len(rows),
        "parse_rate": (
            sum(row["parse_ok"] for row in rows) / len(rows)
            if rows
            else 0.0
        ),
        "rows": rows,
    }


def _factorized_closed_loop(
    config: dict[str, Any],
    tokenizer: Any,
    factual_adapter: Path,
    normative_adapter: Path,
    *,
    family_count: int,
) -> dict[str, Any]:
    source_dir = Path(config["data"]["source_phase1_dir"])
    families = []
    for environment in ("game", "organization"):
        candidates = [
            family
            for family in _load_families(
                source_dir / f"{environment}.jsonl"
            )
            if family["split"] == "development"
        ]
        families.extend(candidates[:family_count])

    factual_model = _load_adapter_model(config, factual_adapter)
    factual_rows = []
    for family in families:
        factual_record = build_factorized_factual_records(
            [family],
            include_rollout=False,
        )[0]
        expected = json.loads(factual_record["target_text"])
        text = _generate(
            factual_model,
            tokenizer,
            factual_record["input_text"],
            max_new_tokens=min(
                int(config["pilot"]["generation_max_new_tokens"]),
                _encoding(tokenizer, factual_record, config).target_tokens + 32,
            ),
        )
        parsed, error = parse_factual_output(text, expected)
        factual_rows.append(
            {
                "family": family,
                "record": factual_record,
                "expected": expected,
                "parsed": parsed,
                "parse_error": error,
                "generated_text": text,
            }
        )
    del factual_model
    gc.collect()
    torch.cuda.empty_cache()

    normative_model = _load_adapter_model(config, normative_adapter)
    reports = []
    for factual_row in factual_rows:
        family = factual_row["family"]
        factual = factual_row["parsed"]
        if factual is None:
            reports.append(
                {
                    "scenario_id": family["scenario_id"],
                    "factual_parse_ok": False,
                    "factual_parse_error": factual_row["parse_error"],
                    "joint_pair_success": False,
                }
            )
            continue
        policy_result = recompute_factorized_policy_result(
            family["model_input"],
            factual.event_record,
        )
        factual_context = {
            "event_record": factual.event_record,
            "policy_result": policy_result,
        }
        pair_outputs = []
        pair_targets = []
        generated_normative = []
        left_profile, right_profile = TARGET_PROFILE_PAIRS[0]
        for profile_id in (left_profile, right_profile):
            evaluator = family["evaluator_twins"][profile_id]
            prompt = factorized_normative_input_text(
                factual_context,
                evaluator,
                condition="structured",
                profile_variant=0,
            )
            text = _generate(
                normative_model,
                tokenizer,
                prompt,
                max_new_tokens=64,
            )
            parsed, error = parse_normative_output(text)
            generated_normative.append(
                {
                    "profile_id": profile_id,
                    "parse_ok": parsed is not None,
                    "parse_error": error,
                    "generated_text": text,
                }
            )
            pair_outputs.append(
                combine_factorized_output(factual, parsed)
                if parsed is not None
                else None
            )
            decision = evaluator["target"]["decision"]
            pair_targets.append(
                {
                    "physical_delta": factual_row["expected"][
                        "physical_delta"
                    ],
                    "event_record": factual_row["expected"]["event_record"],
                    "normative_decision": decision,
                    "escalation_required": decision == "escalate",
                    "rollout": [],
                }
            )
        score = score_evaluator_pair(
            pair_outputs[0],
            pair_outputs[1],
            pair_targets[0],
            pair_targets[1],
        )
        reports.append(
            {
                "scenario_id": family["scenario_id"],
                "environment": family["environment"],
                "factual_parse_ok": True,
                "normative_generations": generated_normative,
                "physical_consistent_and_correct": (
                    score.physical_consistent_and_correct
                ),
                "event_consistent_and_correct": (
                    score.event_record_consistent_and_correct
                ),
                "normative_pair_correct": score.normative_pair_correct,
                "joint_pair_success": score.joint_pair_success,
            }
        )
    del normative_model
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "status": "EXPLORATORY_CLOSED_LOOP_SMOKE",
        "family_count": len(reports),
        "factual_parse_rate": (
            sum(row["factual_parse_ok"] for row in reports)
            / len(reports)
            if reports
            else 0.0
        ),
        "joint_pair_success_rate": (
            sum(row["joint_pair_success"] for row in reports)
            / len(reports)
            if reports
            else 0.0
        ),
        "rows": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local_pilot_qwen3_1_7b.toml"),
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        choices=(*ALL_ARMS, "all"),
        default=["all"],
    )
    parser.add_argument("--optimizer-steps", type=int)
    parser.add_argument("--max-train-items", type=int)
    parser.add_argument("--generation-records", type=int)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(
            "artifacts/phase3_internal/multirecord_pilot.json"
        ),
    )
    args = parser.parse_args()
    config = _load_config(args.config)
    pilot = config["pilot"]
    set_seed(int(config["runtime"]["seed"]))
    arms = list(ALL_ARMS) if "all" in args.arms else args.arms
    optimizer_steps = (
        args.optimizer_steps
        if args.optimizer_steps is not None
        else int(pilot["optimizer_steps"])
    )
    maximum_records = (
        args.max_train_items
        if args.max_train_items is not None
        else int(pilot["max_train_items"])
    )
    generation_records = (
        args.generation_records
        if args.generation_records is not None
        else int(pilot["generation_records"])
    )
    tokenizer = _tokenizer(config)
    data_dir = Path(config["data"]["output_dir"])
    run_root = Path(config["pilot"]["output_dir"])
    report = {
        "status": "EXPLORATORY_SMOKE_ONLY",
        "retained_or_confirmation_result": False,
        "model_id": config["model"]["model_id"],
        "model_revision": config["model"]["revision"],
        "optimizer_steps": optimizer_steps,
        "max_train_items": maximum_records,
        "generation_records": generation_records,
        "arms": {},
        "generation_checks": {},
        "factorized_closed_loop": None,
    }
    datasets = {}
    for arm in arms:
        path = data_dir / ARM_DATASETS[arm]
        datasets[arm] = _load_jsonl_gzip(path)
        adapter_dir = run_root / arm
        report["arms"][arm] = _train_arm(
            arm,
            datasets[arm],
            tokenizer,
            config,
            optimizer_steps=optimizer_steps,
            maximum_records=maximum_records,
            consistency_lambda=float(
                pilot["consistency_proxy_lambda"]
            ),
            adapter_dir=adapter_dir,
        )
        report["arms"][arm]["dataset_sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        if arm in {"joint_naive", "joint_consistency"}:
            report["generation_checks"][arm] = (
                _joint_generation_check(
                    arm,
                    datasets[arm],
                    tokenizer,
                    config,
                    adapter_dir,
                    maximum=generation_records,
                )
            )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if {
        "factorized_factual",
        "factorized_normative",
    }.issubset(report["arms"]):
        report["factorized_closed_loop"] = _factorized_closed_loop(
            config,
            tokenizer,
            run_root / "factorized_factual",
            run_root / "factorized_normative",
            family_count=generation_records,
        )
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
