"""Pure helpers for local causal-LM smoke training."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .transfer_matrix import TARGET_PROFILE_PAIRS


@dataclass(frozen=True)
class SftEncoding:
    input_ids: list[int]
    labels: list[int]
    prompt_tokens: int
    target_tokens: int
    factual_target_tokens: int = 0
    normative_target_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return len(self.input_ids)

    @property
    def factual_logit_slice(self) -> slice:
        if self.factual_target_tokens <= 0:
            raise ValueError("encoding has no declared factual target prefix")
        if self.prompt_tokens <= 0:
            raise ValueError("factual target requires at least one prompt token")
        start = self.prompt_tokens - 1
        return slice(start, start + self.factual_target_tokens)


@dataclass(frozen=True)
class ConsistencyPair:
    pair_type: str
    left: Mapping[str, Any]
    right: Mapping[str, Any]


@dataclass(frozen=True)
class PaddedSftBatch:
    input_ids: list[list[int]]
    labels: list[list[int]]
    attention_mask: list[list[int]]
    encodings: tuple[SftEncoding, ...]


def encode_sft_record(
    tokenizer: Any,
    record: Mapping[str, Any],
    *,
    max_sequence_tokens: int,
) -> SftEncoding:
    """Encode one record while masking every prompt token from the LM loss."""

    prompt = str(record["input_text"]).rstrip() + "\n"
    target = str(record["target_text"])
    prompt_ids = list(tokenizer.encode(prompt, add_special_tokens=False))
    factual_prefix = record.get("factual_prefix_text")
    normative_suffix = record.get("normative_suffix_text")
    if (factual_prefix is None) != (normative_suffix is None):
        raise ValueError(
            "factual_prefix_text and normative_suffix_text must appear together"
        )
    if factual_prefix is None:
        target_ids = list(tokenizer.encode(target, add_special_tokens=False))
        factual_target_tokens = 0
        normative_target_tokens = len(target_ids) + 1
    else:
        if f"{factual_prefix}{normative_suffix}" != target:
            raise ValueError("target parts do not reconstruct target_text")
        encoded = tokenizer(
            target,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        target_ids = list(encoded["input_ids"])
        offsets = list(encoded["offset_mapping"])
        if len(offsets) != len(target_ids):
            raise ValueError(
                "tokenizer offset mapping length differs from input IDs"
            )
        boundary = len(str(factual_prefix))
        factual_target_tokens = sum(
            int(start) < boundary
            for start, _ in offsets
        )
        if factual_target_tokens <= 0 or factual_target_tokens >= len(target_ids):
            raise ValueError(
                "factual target boundary is outside tokenized target"
            )
        normative_target_tokens = (
            len(target_ids) - factual_target_tokens + 1
        )
    eos_token_id = tokenizer.eos_token_id
    if eos_token_id is None:
        raise ValueError("tokenizer must define eos_token_id")
    target_with_eos = [*target_ids, int(eos_token_id)]
    input_ids = [*prompt_ids, *target_with_eos]
    if len(input_ids) > max_sequence_tokens:
        raise ValueError(
            f"record requires {len(input_ids)} tokens, above "
            f"max_sequence_tokens={max_sequence_tokens}"
        )
    return SftEncoding(
        input_ids=input_ids,
        labels=[-100] * len(prompt_ids) + target_with_eos,
        prompt_tokens=len(prompt_ids),
        target_tokens=len(target_with_eos),
        factual_target_tokens=factual_target_tokens,
        normative_target_tokens=normative_target_tokens,
    )


def build_consistency_pairs(
    records: list[Mapping[str, Any]],
) -> list[ConsistencyPair]:
    """Build deterministic semantic and surface-sham factual pairs."""

    semantic_groups: dict[str, list[Mapping[str, Any]]] = {}
    surface_groups: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        semantic_groups.setdefault(
            str(record["semantic_pair_group"]),
            [],
        ).append(record)
        surface_groups.setdefault(
            str(record["surface_sham_group"]),
            [],
        ).append(record)

    semantic_pairs = []
    for group_id in sorted(semantic_groups):
        by_profile = {
            str(record["profile_id"]): record
            for record in semantic_groups[group_id]
        }
        for left_profile, right_profile in TARGET_PROFILE_PAIRS:
            if left_profile not in by_profile or right_profile not in by_profile:
                continue
            semantic_pairs.append(
                ConsistencyPair(
                    "semantic_evaluator",
                    by_profile[left_profile],
                    by_profile[right_profile],
                )
            )

    surface_pairs = []
    for group_id in sorted(surface_groups):
        group = sorted(
            surface_groups[group_id],
            key=lambda record: (
                int(record["profile_surface_variant"]),
                str(record["record_id"]),
            ),
        )
        if len(group) != 2:
            continue
        surface_pairs.append(
            ConsistencyPair("surface_sham", group[0], group[1])
        )

    paired = []
    for index in range(max(len(semantic_pairs), len(surface_pairs))):
        if index < len(semantic_pairs):
            paired.append(semantic_pairs[index])
        if index < len(surface_pairs):
            paired.append(surface_pairs[index])
    return paired


def pad_sft_encodings(
    encodings: list[SftEncoding],
    *,
    pad_token_id: int,
) -> PaddedSftBatch:
    if not encodings:
        raise ValueError("cannot pad an empty SFT batch")
    width = max(encoding.total_tokens for encoding in encodings)
    input_ids = []
    labels = []
    attention_mask = []
    for encoding in encodings:
        padding = width - encoding.total_tokens
        input_ids.append(
            [*encoding.input_ids, *([pad_token_id] * padding)]
        )
        labels.append([*encoding.labels, *([-100] * padding)])
        attention_mask.append(
            [1] * encoding.total_tokens + [0] * padding
        )
    return PaddedSftBatch(
        input_ids=input_ids,
        labels=labels,
        attention_mask=attention_mask,
        encodings=tuple(encodings),
    )


def factual_target_token_ids(
    encoding: SftEncoding,
) -> list[int]:
    if encoding.factual_target_tokens <= 0:
        raise ValueError("encoding has no factual target span")
    start = encoding.prompt_tokens
    stop = start + encoding.factual_target_tokens
    return encoding.input_ids[start:stop]
