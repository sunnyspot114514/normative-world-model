# Kimi K3 round-1 audit request: Phase-5 public-synthetic client plan

Audit target commit: `c3d9f1366a6d350f278306a698df70cee5e26529`

You are an external technical auditor. Do **not** modify any repository file.
Codex remains the adjudicator; unsupported assertions will be independently
recomputed. Review only the fixed commit and report in Markdown.

## Scope

Primary files:

- `src/normative_world_model/phase5_synthetic_client_plan.py`
- `tests/test_phase5_synthetic_client_plan.py`
- `docs/PHASE5_SYNTHETIC_CLIENT_PLAN_CANDIDATE_2026-07-20.md`
- `external_reviews/2026-07-20_phase5-synthetic-client-plan_kimi-k3/CODEX_ROUND1_INTERNAL_REVIEW.md`

Required upstream bindings:

- `src/normative_world_model/phase5_runtime_plan.py`
- `src/normative_world_model/phase5_termination_probe.py`
- `src/normative_world_model/phase5_serialization.py`
- `configs/phase5_scale_inference_draft.toml`
- `configs/phase5_common_termination_probe_candidate.toml`
- `docs/PHASE5_SCALE_INFERENCE_PROTOCOL_DRAFT.md`
- `docs/PHASE5_AGENTWORLD_PREFLIGHT_AUDIT_DISPOSITION.md`

Ignored artifact to recompute locally:

`.cache/phase5_synthetic_client_plan/v1-b2887ba90d81-b752a05215d7.json`

Expected plan SHA-256:
`a8d892819d6dc416f810a5749485b4b6968c5ba5237299416927d939dcd317ac`

Expected file SHA-256:
`22586f3e3dc4be0a10107896dacce143b268d2c0bb92a98bc85678ef823e2787`

## Required attacks

1. Verify vLLM **v0.25.1** source-level compatibility of every request field on
   `/v1/chat/completions` and `/v1/completions`, including JSON-schema guidance,
   reasoning capture, token-ID return, explicit stop handling, and request IDs.
2. Decide whether combining thinking-enabled native chat, `reasoning_parser=qwen3`,
   and JSON-schema structured output is a coherent preflight case. Separate a
   source-proved incompatibility from a live-runtime uncertainty.
3. Verify the 1x1 data-URI PNG is structurally valid and the multimodal body is a
   valid OpenAI/vLLM content-part request. Check whether `--language-model-only`
   should reject it and whether the candidate's 4xx-only gate is too strict,
   too weak, or correctly left pending.
4. Recompute all 20 request identities, canonical body-byte hashes, tokenizer
   equality/headroom, plan self-hash, file hash, and independent rebuild.
5. Attack retry identity: method, endpoint, header ID, body bytes, seed, both
   attempts, and the frozen termination-v2 bodies that lack body `request_id`.
6. Attack raw-before-parse ordering. Confirm envelope bytes are durable before
   envelope parsing and exact generated text is durable before generated JSON
   parsing. Look for failure paths that can report PASS without either capture.
7. Attack semantic gaming: schema-valid but wrong arithmetic, missing toy case,
   repeat mismatch, reasoning/envelope mismatch, transport errors, 4xx/5xx, and
   missing raw text.
8. Attack lifecycle ordering, readiness/shutdown timeouts, port-release proof,
   two simultaneous servers, second launch after a failed first shutdown, and
   case ordering across checkpoints.
9. Check the plan builder's trust boundaries and mutation-plus-rehash behavior.
   Distinguish acceptable dependence on an independently verified upstream
   object from a forgeable authorization path.
10. Verify no network, subprocess, model download, retained-data, GPU, rental,
    or science execution is reachable from this slice.

## Governance boundary

This is a non-executing plan review. Do not demand runtime evidence as though it
already existed; instead identify which exact claims remain unproved until
runtime. Do not upgrade runtime-plan v2's incomplete K3 review. Confirmation
must remain `RESERVED_NOT_GENERATED`.

## Required verdict format

- `PASS`, `PASS_WITH_FIXES`, or `FAIL`;
- blocking findings, each with exact evidence and a minimal fix;
- nonblocking findings;
- explicit answers to attacks 1-10;
- exact recomputed hashes/counts;
- a final statement of what this verdict does and does not authorize.
