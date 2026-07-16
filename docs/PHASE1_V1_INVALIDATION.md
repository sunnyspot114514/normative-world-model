# Phase-1 v1 invalidation record

Status: **invalidated on 2026-07-15 before model training or confirmation generation**

The schema-v0.3 discovery corpus is retained only as an audit artifact under
`artifacts/phase1_v1_invalidated/` and `data/generated/phase1_v1_invalidated/`.
It must not be used as evidence for the project claims.

## Cause

Three independent checks showed that the paper gates did not test the intended task:

1. Each event-record impact was almost exactly the corresponding input potential multiplied by
   action intensity. The maximum absolute reconstruction error was `1.3618e-6` in the game
   environment and `1.331e-6` in the organization environment. Potential-only univariate affine
   fits reached R-squared values from approximately `0.9972` to `0.9982`.
2. The noncausal leakage view contained only two constant sentences. Its AUC of `0.50` therefore
   reflected an empty audit, not demonstrated absence of surface leakage.
3. The nominal natural-language condition was a numeric key-value dump rather than an independent
   linguistic rendering of the structured input.

Code inspection additionally found no applied `next_state`, no chained rollout, and no
`actor_values` field in the retained families. This violated the causal-state contract even though
the v1 exit script returned PASS.

## Governance decision

- No Phase-2 model was trained from v1.
- No confirmation scenario was generated or opened.
- The original data, reports, provenance files, and a 45-file source/configuration snapshot were
  moved intact into the invalidated archive before v2 source changes.
- Schema v0.4 and preregistration v2 add affine and depth-three reconstruction baselines,
  state-transition integrity tests, qualitative-language checks, and a nondegenerate Gate C.
- The v2 discovery population is new and uses separate output paths. A successful v2 report does
  not retroactively validate v1.

