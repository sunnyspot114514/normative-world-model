## Verdict

**ACCEPT_WITH_RESEQUENCING.**

The skeleton (commit dispositions → revise protocol → local implementation → local checks → review → synthetic-only GPU rental → evidence-bound final lock → audited scientific run) is internally consistent only if the pre-rental review dispositions a **synthetic-preflight authorization lock**, with the science runner and verifier treated as runtime-parameterized candidates rather than frozen artifacts. The final runner/verifier freeze must occur only after Base-preflight and throughput evidence exists.

The current draft's single all-in-one authorization clause is incompatible with this staging because it requires a final maximum spend and runtime/container digest before the rental that is needed to measure them. Two locks are required. The throughput smoke must also cover both checkpoints, not Base alone.

## Critical sequencing findings

1. **Undefined review object before Base preflight (critical).** A pre-Base review cannot certify the final science runner. It may certify only the synthetic-preflight authorization package and runtime-parameterized candidate code.
2. **The draft's one-lock authorization rule contradicts the proposed staging (critical).** Replace it with an explicit preflight authorization lock followed by a post-evidence scientific execution lock.
3. **A Base-only throughput smoke cannot close the cost ceiling (high).** AgentWorld native reasoning may be the dominant condition. Both checkpoints must be served sequentially on the same rental and measured at the frozen concurrency.
4. **The runtime table is incomplete (high).** It must include the observed working settings: Triton MoE, eager execution, bfloat16, GPU-memory utilization, max sequences, native sampler override, OMP thread setting, TP=1, exact engine/container identity, and all other effective flags.
5. **Historical evidence must remain immutable (medium).** Wording corrections and forward fixes belong in review dispositions and future clients, not in the retained AgentWorld evidence bundle.
6. **The population-derivation boundary must be explicit (medium).** The first real derivation is the selector's first execution over the retained-discovery export that emits a family ranking/selection. The lock is provisional until reviewed; any selector change forces re-derivation and invalidation of the superseded lock.
7. **A CPU tokenizer proof is a required pre-rental gate (low).** Official tokenizer/config/template packages can be downloaded, hashed, compared, and exercised without GPU.

## Corrected stage plan

### Stage 0 — Commit the audit disposition

- Add only the files under `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/`.
- Do not edit the historical AgentWorld bundle, project data, protocol, or configuration in that commit.
- Exit: the audit records are committed, the worktree is clean, and the historical archive hash remains unchanged.

### Stage 1 — Protocol revision, documents only

- Replace the single authorization gate with the two-lock staging.
- Freeze the complete observed AgentWorld runtime set and define checkpoint-specific exception rules.
- Narrow deterministic replay wording to final-content equality while distinguishing reasoning and full-envelope equality.
- Require publisher-anchored source hashes, Base feasibility evidence, served-tokenizer equality proof, and a throughput/cost gate.
- State explicitly that AgentWorld feasibility does not establish Base feasibility.
- Record the disposition of every current K3/Codex finding.
- Exit: revision committed; no execution authorization granted.

### Stage 2 — Local implementation, no GPU and no real population derivation

- Implement the selector with synthetic fixtures, renderer, token-ID checker, reusable preflight client, runtime-parameterized runner, independent verifier, import-closure hashing, and cleanliness tooling.
- The preflight client must gate the semantic check and save raw envelopes/text before parsing.
- Download official tokenizer/config/template files for both checkpoints, bind their revisions and hashes, and produce the CPU equality proof.
- Exit: full tests and `scripts/check.ps1` pass; tokenizer proof committed.

### Stage 3 — Population derivation and Lock-A candidate

- Run the selector against the real retained-discovery export.
- Build the population lock, executable input lock, publisher source manifest, preflight runtime/exception table, preflight quote and spend cap, closure manifest, and cleanliness attestation.
- Do not rent a server, download weights, or run inference.
- Exit: every Lock-A component exists in one clean commit; all strata fill without replacement or the process stops without relaxation; confirmation remains `RESERVED_NOT_GENERATED`.

### Stage 4 — Pre-rental two-round review

- Review Lock A and its local evidence.
- Exit: no unresolved blocking findings. Material changes regenerate Lock A and receive a delta review.

### Stage 5 — Synthetic-only GPU rental for both checkpoints

- Download both checkpoints at pinned revisions; mirror bytes are acceptable only when every downloaded file matches the publisher-anchored manifest.
- Serve both checkpoints sequentially under the frozen common runtime and predeclared exceptions.
- Run the synthetic interface battery on both checkpoints, recompute serialization equality from the served snapshots, and run the throughput smoke.
- Preserve raw responses, failures, manifests, and locally reverified transfer bundles.
- Do not send project scenarios, derive scientific metrics, or change frozen flags. A forced change stops the affected line and returns to protocol/lock amendment plus delta review.
- Exit: both checkpoints serve as frozen; all synthetic checks pass; publisher hashes match; token-ID equality holds; transferred evidence verifies byte-for-byte.

### Stage 6 — Close Lock B

- Ingest the synthetic evidence and cost measurements.
- Adopt the final spend ceiling by a predeclared rule.
- Freeze the final runner/verifier, request bodies/order, seeds, retry policy, runtime table, exceptions, and cleanliness manifest.
- Do not change margins, labels, population, prompts, or decoding.
- Exit: all Lock-B contents exist in one clean commit.

### Stage 7 — Pre-science two-round review

- Review Lock B and all new Base/AgentWorld evidence.
- Exit: no unresolved blocking findings and the rental plan matches the frozen hardware/container.

### Stage 8 — Not authorized by this review

Only after Stage 7 may the scientific run be considered. Raw rows must be independently verified and the result lock reviewed before reporting any label.

## Two-lock specification

### Lock A — synthetic-preflight authorization lock

Minimum contents:

1. Hashes of the revised protocol and runtime configuration, with science authorization false.
2. Selector and selection lock: source hash, all exclusion-manifest hashes, seed, strata, selected family IDs/order hashes, no-replacement and stop-without-relaxation attestations.
3. Executable input lock: system/prompt bytes, JSON schema, renderer, presentation manifest, and request-order hashes.
4. CPU tokenizer proof: official revisions and file hashes, structural diff, frozen probes, token-ID hashes, and equality verdict.
5. Publisher source manifest: official revisions and per-file identifiers/hashes for both checkpoints, official URLs, resolution time, and mirror policy.
6. Preflight runner/client/orchestrator hashes and tests for the forward fixes.
7. Complete preflight runtime table and checkpoint-specific exception register.
8. Provider/hardware quote, preflight-only maximum spend, and synthetic-only scope statement.
9. Import-closure/source manifest, Git tree, cleanliness attestation, and allowed ignored-root policy.
10. Local tests and non-GPU smoke evidence.
11. Pre-rental two-round disposition.

### Lock B — scientific execution lock

Minimum contents:

1. Carry-forward hashes from Lock A and an explicit supersede ledger for changes.
2. Both preflight evidence bundles and local transfer verification, including publisher-vs-downloaded hashes for all files.
3. Served-snapshot token-ID proof and common prompt-byte hashes.
4. Final per-checkpoint runtime table, actual container digest, software versions, hardware inventory, and closed exception register.
5. Throughput/cost evidence, cost model, adopted maximum spend, and science-rental quote.
6. Final science runner and independent verifier hashes plus verifier tamper/self tests.
7. All request-body hashes, request order, seeds, and retry policy.
8. Lock-B cleanliness manifest and remote cleanliness procedure.
9. Pre-science two-round disposition.
10. Confirmation and exploratory-claim boundaries, with no post-lock changes.

## Runtime and serialization rules

Checkpoint-common by default: container/software versions, tensor parallelism, dtype, context/output limits, concurrency, GPU memory utilization, eager setting, MoE and sampler backends, decoding, seeds, request order, and retry policy.

A checkpoint-specific setting is allowed only when:

1. The difference is architecture/packaging-forced rather than selected for performance or output quality.
2. It is predeclared in the lock with evidence.
3. Load-path-only differences are justified; kernel/precision differences require a synthetic temperature-zero neutrality test or a shared common setting; decoding/length/seed/retry settings never differ.
4. If a required setting is harmless for the other checkpoint, use it for both rather than register a difference.

Every surviving exception enters the scientific claim boundary. A failed neutrality demonstration makes the affected comparison `TECHNICALLY_BLOCKED`; the protocol does not approximate around it.

`native_package` uses each checkpoint's frozen native tokenizer/template through Chat. `common_base_serialization` uses one Base-rendered, thinking-disabled raw prompt through Completions for both checkpoints. Token IDs are stored and independently recomputed; any mismatch stops the affected comparison.

The pre-GPU tokenizer proof records official revisions, file hashes, structural differences, rendered prompt hashes, token-ID hashes, and equality. It establishes only tokenizer-package identity and common-serialization viability; it does not establish weight integrity, serving feasibility, server-side behavior, or model quality.

## Throughput smoke specification

- Use a frozen, public synthetic prompt set disjoint from project scenarios.
- Cover approximately 1k/3k/6k input-token classes and short/long output-elicitation classes.
- Measure native Chat and common-serialization Completions for each checkpoint, serving them sequentially on the same GPU.
- At the frozen `max-num-seqs`, exclude one warm-up block, then measure a predeclared request/time window subject to hard wall-clock and spend caps.
- Record prefill/decode throughput, achieved output lengths, latency percentiles, KV/GPU memory, failures/retries, provider price, and derived 3,072-request projections.
- Set the maximum spend using a predeclared conservative multiplier on the long-output projection; keep expected and worst-case forecasts separate.
- Stop on server crash, post-retry failure, or cap exhaustion; partial evidence cannot close Lock B unless the required expensive conditions were measured for both checkpoints.
- The smoke may support only a throughput/cost envelope. It may not compute project metrics or support a model-quality claim.

## Audit schedule

- **R0 closed:** AgentWorld evidence audit and Codex counter-review. Do not re-review unchanged evidence.
- **R1 closed by this report:** sequencing/governance review.
- **R2 required before rental:** two-round review of Lock A and its new local evidence.
- **R3 required before science:** two-round review of Lock B and its new runtime/cost/Base evidence.
- **R4 required before reporting results:** raw-row verification and result-lock review.
- Do not add review loops when no new primary evidence exists.

## Immediate next action

Commit the completed review records in a standalone commit that touches nothing else. Then begin the document-only protocol revision.
