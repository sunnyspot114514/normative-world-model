# Phase-5 two-lock protocol internal review

Date: 2026-07-19

Reviewed commit: `151d748` plus the uncommitted corrections described below.

Status: **PASS_AFTER_CORRECTIONS; K3 REVIEW STILL REQUIRED**

## Primary-source metadata checks

The following files were fetched read-only from the official Hugging Face repositories at the exact observed revisions. These are internal-review observations, not the future Lock-A source manifest.

| Checkpoint | File | Bytes | SHA-256 |
|---|---|---:|---|
| Base `0f081307…` | `config.json` | 3,544 | `5e4d7f74fec2f360eb9cfbfcd6ec0c4c76e684d3a11caaed259d9fd9bfbc7944` |
| Base `0f081307…` | `tokenizer_config.json` | 16,713 | `3891e840d7dc5fca0af33d3a25083a735e36fe06214e3f707024820cb6b9f89c` |
| Base `0f081307…` | `tokenizer.json` | 12,807,196 | `fe000e3ed39ed12b8d2481d527d44f93c65d37e87645d2dcc80d1bf9d50d2927` |
| AgentWorld `60d2b043…` | `config.json` | 3,583 | `740a8ad390a83372ff9dce9470c1b200d508c3ff75306afcb57d5b7be38d8d55` |
| AgentWorld `60d2b043…` | `tokenizer_config.json` | 17,010 | `f6cfa0a87a8845114cb8558aeec119c45731828ec46b7537a0739dc8edd3b6bf` |
| AgentWorld `60d2b043…` | `tokenizer.json` | 12,807,982 | `5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42` |

Both configs declare `Qwen3_5MoeForConditionalGeneration` and contain `vision_config`. Both tokenizer configs contain thinking-enabled chat templates, and their template hashes differ. Therefore:

- Base has a native chat-template path; the native-package diagnostic is mechanically defined.
- `--language-model-only` is a common candidate, not an AgentWorld-only exception.
- `native_base_reasoning_enabled=false` was inconsistent with the package and has been corrected to true.

The tokenizer JSON files each contain the same 248,044-entry core vocabulary with identical token IDs. AgentWorld has four additional added-token entries: IDs 248066–248069 for `<tool_response>`, `</tool_response>`, `<think>`, and `</think>`. The draft's live-metadata statement about the identical core and four additions is supported, but remains non-binding until Lock A re-resolves and packages it.

## Findings on the K3 sequence review

### Accepted

1. Two authorization locks are necessary because final runtime and cost cannot be known before synthetic Base/throughput evidence.
2. Lock-A review cannot freeze the final science runner/verifier.
3. Both checkpoints must be measured on the same synthetic-only rental.
4. Historical AgentWorld evidence remains immutable.

### Corrected

1. K3's fixed concurrency suggestion was replaced by a frozen candidate grid and deterministic common-selection rule.
2. K3's smoke window was under-specified; the protocol now separates protocol-shaped and decode-ceiling components and adds minimum-token, replicate-window, and variation gates.
3. Tokenizer equality covers every locked common prompt, not only probes.
4. The cost ceiling includes fixed overhead and has an exact formula.
5. Lock A binds scientific hashes locally but the remote synthetic payload has an independent fail-closed allowlist.
6. A material Stage-5 change requires delta review despite the normal absence of reviews between R2 and R3.
7. K3's AgentWorld-only `--language-model-only` example was factually unsupported by the two observed configs and was rejected.

## Additional internal findings

1. **Resolved:** Base native reasoning had been set false even though its chat template defaults to thinking enabled. It is now true.
2. **Resolved:** input-length targets did not say whether system/template tokens were included. They now mean total rendered prompt tokens, keeping 6,000 + 2,048 below 8,192.
3. **Non-blocking until Lock A:** official publisher metadata is observed but not yet a bound source manifest; all authorization flags remain false.
4. **Non-blocking until Stage 2:** no Phase-5 selector, renderer, preflight client, runner, verifier, remote allowlist generator, or token-equality checker exists yet. The protocol must not imply otherwise.

## Internal exit decision

After the listed corrections, the Stage-1 protocol is internally coherent enough for independent K3 review. It does not authorize Stage 2 completion, population derivation, downloads, rental, or inference. Stage 2 may begin only after the actual corrected files receive K3 review and Codex counter-adjudication.
