# Phase-3 post-schema-gate internal review

Status: **schema-gate result retained; scientific arm comparison still blocked**

This review was performed after the retained-discovery schema-convergence gate and before any
formal `joint_naive` / `joint_consistency` / `factorized` comparison. It does not authorize
confirmation and does not change preregistered practical effect margins.

## Integrity checks

- Phase-2 retained v2 verification: PASS.
- Phase-3 frozen input validation: PASS.
- Phase-3 result, input-lock, and adapter hashes: 8/8 match.
- Repository unit tests: 90/90 PASS after adding the independent result verifier.
- Selected schema-gate train/development scenario overlap: zero.
- Confirmation: `RESERVED_NOT_GENERATED`.

The Phase-3 historical result can be checked without importing the training runner:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts\verify-phase3-retained-schema-gate-result.py
```

The verifier checks the result and adapter hashes, current locked inputs and retained sources, and
the execution-time bound source blobs at the recorded Git revision. Later source improvements do
not rewrite the historical execution snapshot.

## Schema-gate behavior audit

The schema gate remains a valid PASS for its declared question: all 16 frozen generations were
strictly parseable. It is not a model-quality result. The generated outputs also show clear
collapse diagnostics:

- all 16 decisions are `allow`, while the targets contain 2 allow, 8 reject, and 6 escalate;
- all 112 generated impact coordinates are zero;
- all 16 generated uncertainty values are zero, while six targets are nonzero;
- 9/16 physical deltas contain only zero/empty values.

Consequently, mean event-field F1 is not evidence that the event model has converged. The formal
comparison must first pass a bounded anti-collapse engineering smoke that reports constant rates,
field entropy, changed-field metrics, and normative responsiveness. This smoke is a compute-safety
gate; it does not replace or relax the frozen scientific margins.

## Blocking contract repairs

1. The historical machine preregistration names OOD `joint_pair_success`, while the retained
   Phase-2 amendment assigns cross-environment cells to `event_normative_pair_success`. A versioned
   executable amendment must make the per-cell mapping unambiguous before training.
2. The slot-level JS/Huber objective still lacks an exact machine-readable field inventory and
   implementation. The historical gold-token proxy is ineligible.
3. The formal arm comparison still lacks one executable lock for scenario families, presentations,
   optimizer updates, target-token exposure, initialization, lambda selection, and factorized
   two-component budget accounting.
4. H5 remains `UNIDENTIFIED`; the next experiment is one-step only.

No retained corpus, oracle, renderer, practical margin, or confirmation reservation is changed by
these repairs.
