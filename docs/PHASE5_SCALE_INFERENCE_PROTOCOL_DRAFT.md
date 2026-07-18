# Phase 5 matched scale-inference protocol — draft

Status: **DRAFT TWO-LOCK PROTOCOL; NEITHER LOCK EXISTS; NO MODEL DOWNLOAD OR SERVER EXECUTION AUTHORIZED**.

The AgentWorld synthetic preflight has been accepted only as infrastructure evidence. It does not establish Base feasibility, common-serialization equality for the scientific population, throughput feasibility, model quality, or authorization. Its historical evidence bundle is immutable; corrections discovered by review are carried in the audit disposition and future code rather than rewritten into that bundle.

## Purpose

The local Qwen3-1.7B sequence is a preserved engineering null. This separate protocol asks a narrower scale question without reopening V4:

> Under identical one-step inputs, decoding, hardware class, and evaluation code, does `Qwen-AgentWorld-35B-A3B` produce better physical/event predictions than its declared `Qwen3.5-35B-A3B-Base` parent without increasing evaluator-conditioned factual leakage or losing normative responsiveness?

This is an exploratory matched-checkpoint inference study. It is not Phase-4 confirmation, not a rerun of V4, and not a causal attribution to CPT, SFT, or RL. AgentWorld differs from the base through all three stages, so a positive result supports only a checkpoint-family difference consistent with world-model training.

## Live availability observation

The official Qwen Hugging Face repositories were checked on 2026-07-18:

- `Qwen/Qwen-AgentWorld-35B-A3B`, observed revision `60d2b0434a53d2e62a7c00a489586815d94ebffb`;
- `Qwen/Qwen3.5-35B-A3B-Base`, observed revision `0f0813072d2358973511097385626f21fcb6d422`.

Both repositories were public and ungated. The AgentWorld model card identifies the latter as its base, lists 35B total / 3B activated parameters and 262,144-token context, and requires `--language-model-only` for vLLM because the checkpoint contains language-model weights while its architecture declares visual components. These observations are not yet frozen inputs; the revisions must be resolved again and copied into a source manifest immediately before protocol freeze.

Primary sources:

- <https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B>
- <https://huggingface.co/Qwen/Qwen3.5-35B-A3B-Base>
- <https://github.com/QwenLM/Qwen-AgentWorld>

## Population

No Phase-1 confirmation file and no previously reserved formal population may be opened. The source is the already-opened retained-discovery export `data/generated/phase2_retained_v2/arms/joint_examples.jsonl.gz`, whose frozen SHA-256 is `bfe421a733d92c009c4e37a2326a6c0cf3eb05ba4a997ab90d549bfad3513660`.

Before any remote execution, a separate selector must be implemented, reviewed, and committed. It will hash-rank only remaining `development` scenarios after excluding every Phase-3 schema-gate, V1, formal-reserved, V2, V3, and V4 scenario. The intended diagnostic population is 96 scenario families:

- 72 discretionary families with a deterministic evaluator-profile pair whose oracle decisions differ;
- 24 hard-policy families whose decision is invariant across the selected profiles;
- equal environment counts within each stratum;
- for each family: two profiles × structured/NL × canonical/surface-sham, giving eight semantic presentations;
- each presentation is run in two separately reported serialization modes, giving 1,536 requests per checkpoint.

Scenario families, not presentations, are the bootstrap and split unit. If the remaining pool cannot fill every frozen stratum without replacement, selection fails; it may not silently relax balance, reuse a prior scenario, or substitute after seeing model output. This population is opened discovery data and supports only an exploratory engineering claim.

The first population-deriving operation is the selector's first execution over the real retained-discovery export that emits any family ranking or selection. Selector implementation and fixture tests, renderer/verifier work, public tokenizer downloads, and synthetic tokenization probes are non-deriving. A real-source selection lock is provisional until the Lock-A review accepts it; any selector change invalidates and re-derives the superseded lock.

## Prompt and decoding contract

Both checkpoints receive byte-identical user content and the same common system instruction. The instruction describes the one-step prediction task and output fields but does not tell the model that factual fields must be invariant to evaluator profiles. This avoids turning the primary leakage test into a direct instruction-following test.

A live metadata check found that the two observed tokenizer packages share the same 248,044-entry core vocabulary with identical token IDs, normalizer, pre-tokenizer, and decoder, while AgentWorld adds four reasoning/tool-response tokens and uses a different chat template. Therefore prompt serialization is a predeclared factor rather than an uncontrolled difference:

1. `native_package`: each checkpoint uses its own frozen tokenizer and chat template; this measures the deployable checkpoint package and includes template/reasoning-token effects.
2. `common_base_serialization`: the client renders one raw prompt string with the frozen base tokenizer/template, thinking disabled, and sends it through the completions path for both checkpoints. Before serving, the runner encodes that string with each checkpoint's frozen server tokenizer; the two token-ID sequences must be byte-identical, are stored in every row, and are independently recomputed by the verifier. This is the primary matched-training comparison. If the freeze-time tokenizer audit no longer confirms identical core vocabulary and preprocessing, or the recomputed token IDs differ, the protocol stops instead of approximating a common serialization.

Before rental, official tokenizer/config/template files for both checkpoints are re-resolved and hash-bound. A synthetic probe validates the checker before population derivation. After selection, the CPU proof must cover every locked common-serialization prompt, not only a probe subset. Lock B repeats the proof using tokenizer files rehashed from the served snapshots. A single mismatch blocks the common mode.

Metrics are never pooled across these modes. A native-only advantage is a package result, not evidence that the learned world-model weights are responsible.

The primary serving implementation is vLLM's OpenAI-compatible API.

The native condition uses `/v1/chat/completions`. The common condition uses a client-rendered base-template string through `/v1/completions`; it does not ask the AgentWorld server to apply its native chat template. JSON guidance is identical at the final-content layer in both endpoints.

Prospective runtime requirements:

- native checkpoint serialization in `native_package`, and the same frozen base serialization in `common_base_serialization`;
- the observed AgentWorld compatibility baseline: vLLM 0.25.1, `--language-model-only`, `--reasoning-parser qwen3`, `--moe-backend triton`, `--enforce-eager`, `--dtype bfloat16`, `--tensor-parallel-size 1`, `--gpu-memory-utilization 0.90`, `VLLM_USE_FLASHINFER_SAMPLER=0`, and `OMP_NUM_THREADS=1`;
- final-content JSON-schema guidance applied identically to both checkpoints;
- each native package uses its own default thinking-enabled chat template and captures any reasoning separately from final JSON; thinking is disabled for both checkpoints in the common-serialization condition;
- `temperature=0`, `top_p=1`, one completion, and a fixed request order;
- maximum model length 8,192 and maximum generated tokens 2,048;
- no truncation of any source presentation;
- identical vLLM/container revision and tensor-parallel setting for both checkpoints;
- exactly one retry only for a transport error or server 5xx response, using the same request body, request ID, and seed; both attempts are retained, and a second failure makes the comparison `TECHNICALLY_BLOCKED`.

Guided JSON makes schema validity an operational condition, not a scientific success metric. Content metrics remain fully scored. The deterministic setting intentionally differs from AgentWorld's sampling recommendation because paired factual invariance and exact replay are primary here. A sampling sensitivity run is outside the minimum protocol and cannot be added after results.

The interface preflight value `max-num-seqs=1` is an observed feasibility setting, not the science-throughput setting. Lock A freezes the candidate grid `[1, 8, 16, 32]` and a deterministic rule: choose the largest candidate that passes every checkpoint-by-serialization stability probe. The selected common value is recorded only in Lock B. This predeclared selection is part of the throughput smoke, not an ad hoc flag change; a value outside the grid or a change to the rule requires a Lock-A amendment and delta review.

Runtime settings are checkpoint-common by default. A checkpoint-specific setting is allowed only when architecture or packaging forces it, it is predeclared with evidence, and it follows the exception class below:

- a load-path-only difference may be justified from checkpoint structure;
- a kernel or precision difference requires a frozen synthetic temperature-zero neutrality test, otherwise both checkpoints use the common denominator;
- decoding, length, seed, request-order, and retry settings may never differ.

If a setting required by one checkpoint is harmless for the other, both receive it. Every surviving exception enters the claim boundary. A failed token-affecting neutrality test makes the affected mode `TECHNICALLY_BLOCKED`; the protocol does not approximate around it.

Deterministic replay means byte equality of the guided **final content** under the frozen request, seed, and serving stack. Reasoning equality and whole-response-envelope equality are separate diagnostics; request IDs and timestamps are not expected to replay byte-for-byte.

## Synthetic throughput and cost smoke

The synthetic-only rental serves both checkpoints sequentially on the same GPU. It runs no selected project prompt and computes no scientific metric. The remote payload is governed by a fail-closed allowlist; selected prompt text and scientific request bodies are forbidden even though their hashes may already be bound locally.

The smoke has two separately reported components:

1. A **protocol-shaped** component uses the exact endpoints, reasoning settings, JSON guidance, and decoding parameters planned for science, but only public synthetic content. It runs 16 requests in each checkpoint-by-mode-by-input-length cell at approximately 1,024/3,072/6,000 **total rendered prompt tokens**, including system and template tokens. The 6,000-token cell therefore leaves 2,192 tokens within the 8,192 context budget and can accommodate the frozen 2,048-token generation cap without truncation. It measures request overhead, schema-path stability, achieved output lengths, and latency without pretending that synthetic output lengths reproduce the scientific population.
2. A **decode-ceiling** component uses a frozen synthetic long-output task targeting 1,800 generated tokens. It first tests the concurrency grid `[1, 8, 16, 32]` with eight stability requests per checkpoint and mode, then selects the largest value passing all four checkpoint-by-mode probes. At the selected common value it records three measurement windows per checkpoint and mode, each with at least 8,192 generated tokens. The across-window decode-throughput coefficient of variation must be at most 0.20. Each checkpoint-by-mode condition has a 30-minute measurement cap, and total measured time per checkpoint is capped at one GPU-hour.

Both components retain raw synthetic rows. The long-output schema may differ from the scientific output schema only to create a decode-load ceiling and is never used as a behavioral or schema-quality result. Both checkpoints' native and common conditions must be valid. A server crash, a request that still fails after the frozen retry, or exhaustion of the wall-clock/spend cap before the minimum evidence makes the smoke insufficient for Lock B.

The smoke records prefill and aggregate decode throughput, achieved output lengths, latency percentiles, KV/GPU memory, failures/retries, wall time, and provider price. Expected and worst-case projections are separate. The exact maximum-spend rule is `1.5 × (measured fixed overhead + worst-case variable projection)`. Fixed overhead includes both model downloads, publisher-hash verification, loading/unloading, JIT/warm-up, and evidence packaging/transfer; the variable projection includes all 3,072 requests and the frozen retry allowance. This is an engineering cost ceiling, never a model-quality result.

## Metrics

All headline metrics are scenario-macro averages with a shared 10,000-resample scenario bootstrap, reported separately by serialization mode. The matched scientific contrast uses `common_base_serialization`; `native_package` is a deployment-package diagnostic.

Factual capability:

- physical-delta field F1;
- event-record field F1;
- event continuous-field MAE;
- physical/event information and nonempty-output diagnostics;
- comparison with the existing evaluator-blind training/static baseline rebuilt only from the retained training split.

Separation and normative behavior:

- evaluator-twin factual disagreement minus surface-sham factual disagreement, using the frozen continuous comparator;
- factual accuracy on both members of each evaluator pair, preventing agreement through vague or constant outputs;
- decision accuracy and per-class recall;
- exact two-member response accuracy on discretionary flip pairs;
- hard-policy invariant-pair accuracy reported separately;
- structured/NL deltas and request latency/token/cost totals.

The verifier must rebuild every summary from raw request/response rows. A stored summary is never authoritative by itself.

## Precommitted practical margins

These margins are engineering choices made before any 35B output is generated:

1. An AgentWorld matched factual advantage in `common_base_serialization` requires at least two of:
   - physical-field F1 higher than base by at least 0.05;
   - event-field F1 higher than base by at least 0.05;
   - event continuous MAE lower than base by at least 0.03.
2. For each counted advantage, the paired 95% bootstrap interval must exclude zero in the favorable direction.
3. In `common_base_serialization`, corrected evaluator leakage must be at most 0.05 for AgentWorld and may not exceed base by more than 0.03.
4. In `common_base_serialization`, AgentWorld discretionary flip-pair accuracy may not be more than 0.03 below base, and its minimum decision-class recall must be at least 0.20.
5. Both checkpoints must return one complete guided final object for every request; an engine/parser failure makes the affected comparison `TECHNICALLY_BLOCKED`, not a model-quality zero.

Decision labels:

- `AGENTWORLD_MATCHED_ADVANTAGE`: factual rule 1 passes and rules 2–5 all pass in common serialization;
- `NATIVE_PACKAGE_ONLY_ADVANTAGE`: the same factual pattern appears only with native serialization; this cannot be attributed to learned world-model weights;
- `SCALE_ONLY_SIGNAL`: at least one checkpoint beats the retained static baseline by 0.05 F1 or 0.02 MAE, but AgentWorld does not clear the matched advantage rule;
- `MIXED_LEAKAGE_TRADEOFF`: AgentWorld clears factual advantage but violates rule 3 or 4;
- `INFERENCE_SCALE_NULL`: neither checkpoint clears a scale signal;
- `TECHNICALLY_BLOCKED`: model loading, schema-guided reasoning, completeness, or source-lock verification fails.

No label authorizes confirmation. Only `AGENTWORLD_MATCHED_ADVANTAGE` or `SCALE_ONLY_SIGNAL` may justify drafting a separate training study, which still requires its own review and authorization. `NATIVE_PACKAGE_ONLY_ADVANTAGE` justifies at most a packaging/template follow-up.

## Two prospective execution locks

### Lock A: synthetic-preflight authorization

Lock A authorizes only a synthetic infrastructure rental. It must bind, in one clean commit:

1. the revised protocol/config and complete preflight runtime table;
2. the selector, provisional population lock, source/exclusion hashes, and selected order;
3. the locally retained executable-input hashes, prompt/schema/renderer hashes, and full request-order hashes;
4. the publisher-resolved model/tokenizer/config manifest, including every file referenced by each checkpoint's own index rather than a hard-coded shard count;
5. the CPU tokenizer proof over every locked common prompt;
6. the preflight runner/client/orchestrator, synthetic prompt set, semantic PASS gate, raw-before-parse evidence path, and independent verifier;
7. the fail-closed **remote synthetic payload allowlist**, which excludes project prompt text and scientific request bodies;
8. the runtime-exception register, container pinning policy, provider quote, preflight-only maximum spend, source-closure manifest, cleanliness attestation, and local test evidence;
9. a two-round review disposition with no unresolved blocking findings.

Science runner/verifier code may exist at Lock A only as `candidate_only`; their execution-authoritative hashes are not frozen until Lock B. A material Lock-A change requires a delta review before another rental attempt.

### Lock B: scientific execution

After both-checkpoint preflight and throughput evidence returns and verifies locally, Lock B must bind, in one clean commit:

1. every still-valid Lock-A hash plus an explicit supersede ledger;
2. both evidence bundles, transfer manifests, and publisher-versus-downloaded file-hash comparisons;
3. served-snapshot tokenizer hashes and the all-common-prompt token-ID proof;
4. the final common runtime, every checkpoint exception, actual container digest, software versions, and hardware inventory;
5. the throughput/cost evidence, fixed and variable cost model, final provider quote, and adopted science-run maximum spend;
6. the final runner and independent verifier, with verifier tamper tests and raw-row summary reconstruction;
7. every scientific request-body hash, request order, seeds, retry policy, bootstrap indices, comparator, metric reducer, and cleanliness manifest;
8. a two-round review disposition with no unresolved blocking findings.

Every project-local executable file in the import/dynamic-load closure and the committed Git tree are hash-bound at each lock. Remote writes are allowed only under declared ignored roots governed by their own manifests. Outputs are hashed before transfer, rehashed locally, and failures are preserved.

## Authorization and stop rules

Before a **synthetic-only** rental, Lock A must be complete and accepted. Before any scientific request, Lock B must be complete and accepted. These are separate authorization events; accepting Lock A never implies acceptance of Lock B.

Until then:

- model download: unauthorized until Lock A acceptance;
- server rental: unauthorized;
- performance inference: unauthorized;
- training: unauthorized;
- formal evaluation: unopened;
- confirmation: `RESERVED_NOT_GENERATED`.

A preflight, once separately authorized, may use only synthetic public prompts to verify model loading, reasoning separation, guided JSON, resource use, and deterministic replay. It may not contain any project scenario or set a scientific threshold.

If the synthetic rental forces a runtime, client, source, or payload change, the affected attempt is preserved and stops. Lock A is amended and receives a delta review before another attempt; the change may not be improvised on the same rental and silently carried into Lock B.

After a scientific run, the independent verifier rebuilds every result from raw rows and a result-lock review is required before any decision label is reported.
