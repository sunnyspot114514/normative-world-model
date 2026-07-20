# Kimi K3 round-1 audit request: Phase-5 public-synthetic client plan V3

Audit target commit: `d67121d7cc2340f7685d2d7731a119f65cfb2237`

You are an external technical auditor. Do **not** modify any repository file.
Codex remains the adjudicator; recompute every material claim. Review only the
fixed commit and return Markdown.

## Primary scope

- `src/normative_world_model/phase5_synthetic_client_plan.py`
- `tests/test_phase5_synthetic_client_plan.py`
- `docs/PHASE5_SYNTHETIC_CLIENT_PLAN_CANDIDATE_2026-07-20.md`
- every review/status file in this directory
- upstream runtime, termination, serialization, Stage-2 configuration, and
  Phase-5 protocol files named by the plan's implementation source inventory

V3 ignored artifact:

`.cache/phase5_synthetic_client_plan/v3-b2887ba90d81-b752a05215d7.json`

- expected plan SHA-256:
  `37ca3afaf8b2b6d465d695ecbc324f7ee0f78b14439a4876c10c76ff099efdf8`;
- expected file SHA-256:
  `e0307cc074135d99c4585d91bf0ff11e1d2fd5dbe8818c9a89e066c53686b7bb`;
- expected requests: 20;
- expected common prompt token count: 64 under both tokenizers.

## Mandatory attacks

1. Recompute the plan, both hashes, every source binding, all request identity
   and canonical body-byte hashes, request counts/order, and tokenizer equality.
2. Verify every request field against vLLM **v0.25.1** official source on both
   `/v1/chat/completions` and `/v1/completions`.
3. Determine from source whether thinking-enabled native chat + qwen3 reasoning
   parsing + JSON-schema structured output is coherent; label any remaining
   uncertainty as runtime-only rather than inventing a source conclusion.
4. Fully parse the embedded PNG independently: base64, signature, chunk bounds,
   exact chunk order, per-chunk CRC, IHDR dimensions/type, zlib IDAT, scanline
   length, and IEND. Confirm the OpenAI/vLLM multimodal body is valid.
5. Trace `--language-model-only` through vLLM source. Attack the V3 requirement
   for 400 `BadRequestError`, parameter `image|vision_chunk`, and zero-limit
   message fragments. Try to find false-pass paths for 400 malformed input,
   401, 404, 2xx, or 5xx.
6. Attack retry identity and retention, especially termination-v2 bodies that
   use a header logical ID rather than adding a new body `request_id`.
7. Attack both raw-before-parse boundaries and find any state/order wording that
   permits parsing or PASS before required bytes/text are durable.
8. Attack schema-only gaming, wrong arithmetic, missing cases, replay mismatch,
   reasoning/envelope variation, transport failures, and second-failure policy.
9. Attack lifecycle feasibility and evidence: prelaunch port, argv/environment,
   start/log order, every health poll, readiness timeout, shutdown/force branch,
   exit/final log, port release, and prohibition on simultaneous/next launch.
10. Attack mutation-plus-rehash and builder trust boundaries; distinguish a
    trusted independent upstream verification from caller-forged fixture data.
11. Confirm V1/V2 are honestly preserved and superseded rather than silently
    relabelled, including the recorded V2 module hashes/reconstruction claim.
12. Confirm this slice exposes no network/subprocess/download/GPU/rental,
    retained-data, confirmation, or science execution path.

Run the repository check chain. Report exact counts and confirmation state.

## Required verdict

Return `PASS`, `PASS_WITH_FIXES`, or `FAIL`; blocking and nonblocking findings
with precise evidence/minimal fixes; explicit answers to attacks 1-12; all
recomputed hashes/counts; and a final authorization boundary. This is a plan
review only. Do not upgrade the still-incomplete runtime-plan-v2 external
review, do not authorize Lock A, and do not treat the earlier quota 403 as a
review round.
