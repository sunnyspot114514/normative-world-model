# Final Adjudication — Phase-3 V4 Two-Round Model Cross-Review

Date: 2026-07-18

## Decision

**ACCEPTED_WITH_NONBLOCKING_FINDINGS.** Two rounds of Kimi K3/Codex cross-review found no defect that invalidates the preserved V4 result. The result remains `BLOCKED`, and the local Qwen3-1.7B path remains terminated under its frozen decision rule.

This is a model-based cross-review, not a human external audit. It does not replace or modify the earlier human external acceptance of the Phase-1 v3 corpus.

## Review sequence

1. Kimi K3 independently audited the V4 primary files and returned `PASS_WITH_FINDINGS`, with no blocking finding.
2. Codex independently recomputed the row summaries, failed-gate map, hashes, git history, and project-local execution closure. It returned `ACCEPT_WITH_CORRECTIONS`.
3. A fresh Kimi K3 session reviewed the counter-review, repeated the disputed checks, ran the complete 135-test suite, and returned `CONCUR_WITH_CORRECTIONS`, again with no blocking finding.

## Settled corrections

1. The V4 input lock contains 26 `bound_hashes` entries. All **26/26** match. The first K3 report's “24/24” is a prose-only arithmetic error.
2. `bd1a383` is the V3 lock/freeze commit and is also the `git_head_before_execution` recorded by the V3 result. `931b6fc` is the later V3 preserved-result commit. `0602260` is the V4 lock/freeze commit and recorded execution HEAD; `e9ef49c` preserves the V4 result.

The second clarification preserves the important temporal fact: the V3 fallback reservation was committed before execution and was the exact reservation later used by V4.

## Preserved findings

The following are real but non-blocking for the already executed result:

1. Five project-local transitive executable dependencies were outside the V4 input lock: `comparators.py`, `contracts.py`, `local_pilot.py`, `result_lock.py`, and `transfer_matrix.py`. They are byte-identical to execution commit `0602260`, so the remaining exposure is only that historical uncommitted edits on those paths would not have been detected by the path-scoped cleanliness gate.
2. The V4 result verifier derives gate checks from the stored `evaluation` summary rather than rebuilding that summary from `rows`. Both model reviewers independently rebuilt the summary from all 48 rows and found exact agreement.
3. `deterministic_training_contract` is asserted by the runner and trusted by the result verifier, although it is backed by earlier fail-fast contract checks.
4. `strict_schema_coverage` is weakly discriminative for the schema-head architecture because valid schema output is largely guaranteed by construction.

These items must be addressed prospectively in any new execution protocol. They do not authorize alteration, rerun, threshold change, extra epoch, new diagnostic population, formal-set opening, or confirmation generation under V4.

## Final evidence summary

- Result SHA-256: `8471c46a636f28102afe78d0d7f5376c1e03f4abdcca8647ca98b4235b50aa68`.
- Input-lock SHA-256: `56ce02b4ee07355f81e2eff97b0bda71ffe671e8ca840030e8a2e7de922db677`.
- Selection-lock SHA-256: `0df787815cc2f16a4d77bc93515c6b934849b5d22369a3ee69f1cd9cf6e89903`.
- Bound inputs: 26/26 exact.
- Preserved run files: 5/5 exact.
- Evaluation: 48 rows, 48 unique buckets, 16 targets per decision class.
- Failed blocking gates: fixed-probe improvement, minimum per-class recall, event-MAE improvement, physical-F1 improvement, and event-F1 improvement.
- Full unit suite in round 2: 135/135 passed.
- Confirmation: `RESERVED_NOT_GENERATED`.
- Formal comparison and fifth diagnostic population: not opened.

## Permitted continuation

V4 is terminal. The project may continue only by drafting a separate protocol with a new scope and new authorization. Any such protocol must bind the full project-local executable import closure and use a verifier that re-derives summary metrics from raw rows. Drafting is permitted; server rental, model download, training, formal evaluation, and confirmation remain unauthorized until that new protocol is reviewed and frozen.
