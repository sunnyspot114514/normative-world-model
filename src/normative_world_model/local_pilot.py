"""Pure helpers for local causal-LM smoke training."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


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
        factual_ids: list[int] = []
        normative_ids = target_ids
    else:
        if f"{factual_prefix}{normative_suffix}" != target:
            raise ValueError("target parts do not reconstruct target_text")
        factual_ids = list(
            tokenizer.encode(factual_prefix, add_special_tokens=False)
        )
        normative_ids = list(
            tokenizer.encode(normative_suffix, add_special_tokens=False)
        )
        target_ids = [*factual_ids, *normative_ids]
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
        factual_target_tokens=len(factual_ids),
        normative_target_tokens=len(normative_ids) + 1,
    )
