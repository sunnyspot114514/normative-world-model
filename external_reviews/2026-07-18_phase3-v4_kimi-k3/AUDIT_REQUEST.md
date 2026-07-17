# Independent read-only audit request: Phase-3 V4

Reviewer model: `kimi-code/k3`

Repository commit under audit: `e9ef49c`

## Non-negotiable operating constraints

- Work read-only. Do not create, edit, delete, move, stage, commit, or push files.
- Do not run training or generate any new evaluation population.
- Do not access sibling projects or files outside this repository, except the
  installed Kimi runtime required to perform the review.
- Treat reports and result locks as claims. Recompute against primary files.
- This is an independent model audit, not an independent human audit.

## Primary evidence to inspect

- `AGENTS.md`
- `docs/PHASE3_REPRESENTATION_GATEWAY_V4_DESIGN.md`
- `configs/phase3_representation_gateway_v4.toml`
- `configs/phase3_representation_gateway_v4_selection_lock.json`
- `configs/phase3_representation_gateway_v4_input_lock.json`
- `src/normative_world_model/phase3_gateway_v4.py`
- `scripts/run-phase3-representation-gateway-v4.py`
- `tests/test_phase3_gateway_v4.py`
- `tests/test_phase3_representation_gateway_v4.py`
- `artifacts/phase3_representation_gateway_v4/result.json`
- `configs/phase3_representation_gateway_v4_result_lock.json`
- `docs/PHASE3_REPRESENTATION_GATEWAY_V4_RESULT.md`
- `src/normative_world_model/gateway_v4_result_lock.py`
- `EXECUTION_PLAN.md`

Read additional referenced files only when necessary to verify a claim.

## Required independent checks

1. Recompute SHA-256 for the result, input lock, every bound input, and every
   preserved V4 run file. Check the execution commit and clean working tree.
2. Recompute every V4 gate from raw `result.json` metrics and frozen thresholds.
   Confirm whether `BLOCKED` follows mechanically, without relying on result
   prose or the result lock's booleans.
3. Verify that the evaluation binding is exactly the V3 fallback reservation,
   is disjoint from training/prior development populations, and has 48 balanced
   buckets. Confirm confirmation was not generated or opened.
4. Audit implementation semantics: marker uniqueness and no truncation;
   role-hidden-state routing; continuous training statistics and decode;
   per-example normative weighting at batch size one; factual consistency loss;
   strict output decoding; atomic output promotion.
5. Search for target leakage, decorative locks, unbound executable inputs,
   baseline mismatches, metric gaming, result-verifier blind spots, or any route
   by which formal/confirmation execution could have started.
6. Judge the interpretation boundary. In particular, decide whether the data
   support only an engineering null for this checkpoint/budget/path, and whether
   stopping the local Qwen3-1.7B path follows from the frozen contract.

## Required output

Return one Markdown audit report with these sections:

1. `Verdict` — PASS, PASS_WITH_FINDINGS, or FAIL.
2. `Blocking findings` — numbered, or `None`.
3. `Non-blocking findings` — numbered, with severity.
4. `Independent recomputations` — exact key hashes and gate numbers.
5. `Implementation and governance audit`.
6. `Claim boundary`.
7. `Recommended next action`.

For every finding, cite the local file and relevant line or JSON path. Do not
recommend threshold changes, extra V4 epochs, a fifth diagnostic population,
formal evaluation, or confirmation unless you first identify a concrete defect
that invalidates the frozen V4 result.
