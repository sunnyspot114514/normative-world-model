# Phase 5 matched scale-inference protocol — draft

Status: **DRAFT ONLY; NOT FROZEN; NO MODEL DOWNLOAD OR SERVER EXECUTION AUTHORIZED**.

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

## Prompt and decoding contract

Both checkpoints receive byte-identical user content and the same common system instruction. The instruction describes the one-step prediction task and output fields but does not tell the model that factual fields must be invariant to evaluator profiles. This avoids turning the primary leakage test into a direct instruction-following test.

A live metadata check found that the two observed tokenizer packages share the same 248,044-entry core vocabulary with identical token IDs, normalizer, pre-tokenizer, and decoder, while AgentWorld adds four reasoning/tool-response tokens and uses a different chat template. Therefore prompt serialization is a predeclared factor rather than an uncontrolled difference:

1. `native_package`: each checkpoint uses its own frozen tokenizer and chat template; this measures the deployable checkpoint package and includes template/reasoning-token effects.
2. `common_base_serialization`: the client renders one raw prompt string with the frozen base tokenizer/template, thinking disabled, and sends it through the completions path for both checkpoints. Before serving, the runner encodes that string with each checkpoint's frozen server tokenizer; the two token-ID sequences must be byte-identical, are stored in every row, and are independently recomputed by the verifier. This is the primary matched-training comparison. If the freeze-time tokenizer audit no longer confirms identical core vocabulary and preprocessing, or the recomputed token IDs differ, the protocol stops instead of approximating a common serialization.

Metrics are never pooled across these modes. A native-only advantage is a package result, not evidence that the learned world-model weights are responsible.

The primary serving implementation is vLLM's OpenAI-compatible API.

The native condition uses `/v1/chat/completions`. The common condition uses a client-rendered base-template string through `/v1/completions`; it does not ask the AgentWorld server to apply its native chat template. JSON guidance is identical at the final-content layer in both endpoints.

Frozen runtime requirements:

- native checkpoint serialization in `native_package`, and the same frozen base serialization in `common_base_serialization`;
- `--language-model-only` and `--reasoning-parser qwen3`;
- final-content JSON-schema guidance applied identically to both checkpoints;
- thinking/reasoning enabled and captured separately from final JSON in the native AgentWorld condition; disabled for both checkpoints in the common-serialization condition;
- `temperature=0`, `top_p=1`, one completion, and a fixed request order;
- maximum model length 8,192 and maximum generated tokens 2,048;
- no truncation of any source presentation;
- identical vLLM/container revision and tensor-parallel setting for both checkpoints;
- exactly one retry only for a transport error or server 5xx response, using the same request body, request ID, and seed; both attempts are retained, and a second failure makes the comparison `TECHNICALLY_BLOCKED`.

Guided JSON makes schema validity an operational condition, not a scientific success metric. Content metrics remain fully scored. The deterministic setting intentionally differs from AgentWorld's sampling recommendation because paired factual invariance and exact replay are primary here. A sampling sensitivity run is outside the minimum protocol and cannot be added after results.

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

## Prospective execution lock

The execution lock must close the two gaps found in the V4 model audit:

1. Hash every project-local executable file in the import/dynamic-load closure and also record the committed Git tree. Before download, the remote repository must be fully clean. During execution, tracked or untracked changes are allowed only under declared ignored roots for model files, caches, temporary staging, and outputs; those roots are excluded from source cleanliness but governed by their own manifests. Path-scoped source cleanliness is insufficient.
2. Bind the selector, selected row order, source data, prompt bytes, JSON schema, comparator, metric reducer, bootstrap indices, model revisions, tokenizer/chat-template files, container image digest, vLLM version and flags, hardware inventory, and request order.
3. Recompute raw-row summaries, decision labels, and all bound hashes in an independent result verifier. Derived status flags may not be trusted from the runner report.
4. Stage outputs under the remote project root, hash before transfer, rehash locally, and preserve failures as well as successes.

## Authorization and stop rules

Before rental, the following must all exist in one clean commit: reviewed selector, population lock, executable input lock, exact model revisions, runtime/container digest, provider/hardware quote, maximum spend, runner, independent verifier, and two-round internal/model audit disposition.

Until then:

- model download: unauthorized;
- server rental: unauthorized;
- performance inference: unauthorized;
- training: unauthorized;
- formal evaluation: unopened;
- confirmation: `RESERVED_NOT_GENERATED`.

A preflight, once separately authorized, may use only synthetic public prompts to verify model loading, reasoning separation, guided JSON, resource use, and deterministic replay. It may not contain any project scenario or set a scientific threshold.
