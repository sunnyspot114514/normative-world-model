# Phase-5 AgentWorld preflight audit disposition

Date: 2026-07-19

Status: **ACCEPTED FOR AGENTWORLD INFRASTRUCTURE EVIDENCE ONLY**

This disposition binds the Kimi K3 audit and Codex counter-reviews under `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/`. It does not modify the historical evidence bundle and does not authorize model download, rental, project-scenario inference, confirmation access, or scientific execution.

## Fix in the future protocol or client

1. Add the semantic/toy-oracle check to every reusable preflight PASS gate.
2. Store raw HTTP envelopes and generated text before parsing.
3. Describe deterministic replay as final-content equality; report reasoning and whole-envelope equality separately.
4. Freeze the complete observed AgentWorld runtime and require checkpoint-common settings or predeclared exceptions.
5. Require a fail-closed synthetic remote-payload allowlist that excludes project prompt text and scientific request bodies.

## Immutable historical findings

1. Attempt 1's local `SHA256SUMS` contains the documented invalid self-entry. The outer transfer manifest binds the exact historical bytes.
2. Attempt 1's log contains an earlier incomplete-download execution before the stored final exit-20 execution.
3. Attempt 3 did not preserve its exact raw non-JSON completion text.
4. The historical README's "two guided Chat responses byte-identical" wording is broader than the enforced content comparison.

These files remain unchanged. Their corrections live in this disposition and future evidence requirements.

## Requirements deferred to Lock A or Lock B

1. Publisher-resolved revisions and per-file hashes must be packaged with the source manifest before any weight download.
2. Both official tokenizer packages must be hash-bound and compared locally; after population derivation, every locked common prompt must produce identical token IDs.
3. Base and AgentWorld must pass the same frozen synthetic battery under the new container/runtime, with justified exceptions only.
4. Served-snapshot tokenization equality must be recomputed before Lock B.
5. Throughput and cost measurements must cover both checkpoints and include fixed overhead as well as inference.
6. Final runner/verifier hashes, request plan, cost ceiling, runtime exceptions, and independent two-round review belong to Lock B.

## Independent adjudication of the K3 sequence review

K3 is advisory; this project adopts only the portions independently supported by the repository and retained evidence.

Accepted:

1. Separate Lock A (synthetic-only rental) from Lock B (scientific execution).
2. Do not freeze the final runner/verifier or science budget before Base and throughput evidence exists.
3. Serve both checkpoints sequentially on the same synthetic rental for comparable runtime and cost evidence.
4. Preserve historical evidence unchanged and review only when new primary evidence exists.

Accepted with modification:

1. K3's suggested `max-num-seqs=32` is not frozen in advance. Lock A freezes `[1, 8, 16, 32]` and a deterministic all-checkpoint/all-mode stability rule; Lock B records the selected common value.
2. K3's request/time smoke window is split into an exact protocol-shaped component and a separate long-output decode-ceiling component. Three token-minimum measurement windows and a CV gate are required so a slow condition cannot pass with too little evidence.
3. A synthetic tokenizer probe validates only the checker. The binding proof covers every locked common prompt locally and is repeated from served-snapshot tokenizer files before Lock B.
4. The cost ceiling is exactly `1.5 × (measured fixed overhead + worst-case variable projection)`, not a multiplier on inference alone.
5. Lock A may bind scientific input hashes locally, but a separate fail-closed remote allowlist excludes all project prompt text and request bodies from the synthetic rental.
6. K3's example treating `--language-model-only` as AgentWorld-only is not accepted. At the observed revisions, both checkpoint configs declare `Qwen3_5MoeForConditionalGeneration` with a `vision_config`; the common preflight candidate passes the flag to both and records any forced deviation only after Base evidence.
7. Native Base reasoning is not pre-disabled. Its frozen chat template is thinking-enabled by default, so the native-package diagnostic preserves that package behavior and captures reasoning separately when present.

Rejected:

1. No throughput or concurrency number becomes authoritative solely because K3 proposed it.
2. No claim that a probe subset establishes full-population tokenization equality is accepted.
3. No blanket "no review between R2 and R3" rule applies after a forced Stage-5 change; such a change requires a Lock-A amendment and delta review before another attempt.

## Claim boundary

The accepted evidence supports only that the revision-addressed AgentWorld snapshot bytes recorded in the bundle loaded and served successfully on the documented RTX PRO 6000 SM120 setup with the recorded compatibility settings, and that the two synthetic API paths completed. It does not establish publisher-authenticated weight identity from the audit package alone, Base feasibility, common-serialization equality for the scientific population, throughput feasibility, model quality, normative behavior, leakage performance, or scientific authorization.
