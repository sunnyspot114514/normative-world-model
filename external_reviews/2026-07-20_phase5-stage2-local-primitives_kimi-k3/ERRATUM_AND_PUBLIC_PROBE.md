# Erratum and public-snapshot probe

Date: 2026-07-20

## Erratum to the Codex counter-review

The counter-review's additional finding inferred from `tokenizer.json` alone that AgentWorld registered four control tokens that Base did not share. That inference was wrong at the effective package level.

The first restricted public-snapshot probe showed:

- AgentWorld's `tokenizer.json` contains IDs 248066–248069 for `<tool_response>`, `</tool_response>`, `<think>`, and `</think>`;
- Base's `tokenizer.json` omits those four rows;
- both `tokenizer_config.json` files contain the same 33-entry `added_tokens_decoder`, including those four tokens with identical IDs and attributes;
- `AutoTokenizer.from_pretrained(..., local_files_only=true, trust_remote_code=false)` loads both as `Qwen2TokenizerFast` with length 248077 and identical effective IDs for all four tokens;
- the old Base render containing an empty `<think>...</think>` block and the new reasoning-envelope-free render both produced identical Base/AgentWorld token IDs on the public synthetic probe.

Therefore the counter-review's predicted *necessary token-ID mismatch* was false. The adopted common renderer remains preferable because it removes an empty reasoning envelope and forbids control-literal collisions, but that is a protocol-cleanliness decision rather than a repair for a demonstrated tokenizer mismatch.

## Additional real findings

The public bytes exposed three package facts that the synthetic review could not establish:

1. `tokenizer.json` differs only by explicit `model.ignore_merges=false` in AgentWorld versus an absent key in Base. The official Tokenizers BPE default is `false`, and real loaded tokenizers produced identical IDs. The inspector now normalizes only this documented default-equivalence.
2. Effective added tokens must be compared over the union of `tokenizer.json.added_tokens` and `tokenizer_config.json.added_tokens_decoder`. Comparing only the first file is incomplete.
3. `eos_token` differs (`<|endoftext|>` for Base, `<|im_end|>` for AgentWorld), and `model_max_length` differs (262144 versus 131072). These do not change the current raw input encoding with `add_special_tokens=false` and a common 8192 runtime cap, but EOS may change server termination. It is now an explicit Lock-A runtime item, not evidence of identical packages.

## Governance effect

The K3 report remains preserved verbatim. The counter-review remains preserved as the historical adjudication, and this file corrects its factual premise without rewriting history.

No weight, project scenario, confirmation record, GPU, or scientific result was opened. The initial public download is retained only in the ignored project cache. A new semantic binding and repeatable public tokenizer probe are required before Stage 2 can close.
