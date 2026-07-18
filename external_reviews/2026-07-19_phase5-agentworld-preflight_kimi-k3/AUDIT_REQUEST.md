# Independent read-only audit request: Phase-5 AgentWorld synthetic preflight

Reviewer model: `kimi-code/k3`

Repository HEAD at request creation: `7653fcb27017d484b8d0118277dedc2dbde99bd7`

## Scope and claim under review

Audit only the narrow claim that the exact AgentWorld checkpoint can be served on the rented single-GPU runtime and that the two required API paths passed a synthetic interface preflight after documented compatibility fixes.

This is not a model-quality result, not the matched AgentWorld-vs-base comparison, not confirmation, and not authorization to run the Phase-5 scientific population.

## Non-negotiable constraints

- Work read-only. Do not create, edit, delete, move, stage, commit, or push files.
- Do not start a server, download a model, run inference, or access confirmation data.
- Treat `README.md`, `summary.json`, `PASS`, and stored exit codes as claims. Recompute from primary evidence.
- Inspect only this repository and the installed Kimi runtime required for review.
- This is an independent model review, not a human external audit.

## Primary evidence

- `docs/PHASE5_SCALE_INFERENCE_PROTOCOL_DRAFT.md`
- `artifacts/phase5_agentworld_preflight_20260718/README.md`
- `artifacts/phase5_agentworld_preflight_20260718/summary.json`
- `artifacts/phase5_agentworld_preflight_20260718/raw_transfer/phase5-preflight-evidence-20260718.tar.gz`
- `artifacts/phase5_agentworld_preflight_20260718/raw_transfer/phase5-preflight-evidence-20260718.tar.gz.sha256`
- `artifacts/phase5_agentworld_preflight_20260718/raw_transfer/extracted/phase5-preflight-transfer-manifest.sha256`
- all four extracted attempt directories under the same `extracted/` root;
- especially each attempt's `runner-used.sh`, `client-used.py`, `orchestrator.log`, `vllm-server.log`, `orchestrator-exit-code.txt`, and attempt 3/4 `client-result.json`.

Read additional repository files only when needed to verify a claim.

## Required independent checks

1. Recompute the compressed archive SHA-256, the transfer-manifest self hash, and all 48 file hashes. Separately check each attempt-local `SHA256SUMS`; assess the documented attempt-1 self-reference defect without repairing it.
2. Reconstruct the four-attempt chronology from raw logs and scripts. Confirm the actual exit codes and root causes rather than trusting the summary.
3. Audit the final runner and client for a false PASS: exception handling, required-check list, output-path binding, shutdown trap, model revision/weight validation, HTTP failures, schema checks, replay comparison, and toy semantics.
4. Assess whether accepting either `reasoning` or `reasoning_content`, disabling FlashInfer sampling, forcing Triton MoE, and rendering the raw completion prompt with `enable_thinking=False` are legitimate compatibility fixes or weaken the preflight claim.
5. Check alignment with the Phase-5 draft. In particular, decide what must be identically frozen for the future AgentWorld/base comparison and whether this AgentWorld-only preflight can say anything about base-checkpoint feasibility or scientific performance.
6. Search for omitted runtime blockers, misleading resource claims, evidence loss, secret leakage, or governance overclaim. Distinguish correctness blockers from performance-only warnings.
7. State exactly what this PASS unlocks and what remains blocked.

## Required output

Return one Markdown report with:

1. `Verdict`: PASS, PASS_WITH_FINDINGS, or FAIL.
2. `Blocking findings`: numbered or `None`.
3. `Non-blocking findings`: numbered with severity.
4. `Independent recomputations`: exact hashes, attempt exit codes, and final checks.
5. `Runner/API audit`.
6. `Claim boundary`.
7. `Recommended next action`.

For each finding, cite a local file and line, log line, or JSON path. Do not recommend opening confirmation or running the scientific population unless the draft's prospective execution lock is independently satisfied.
