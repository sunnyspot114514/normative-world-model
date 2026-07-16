# Metric comparator v2.1 candidate

Status: **implemented and tested; freeze waits for revision-2 smoke external acceptance and the retained-corpus manifest**

The same comparator is the only equality implementation permitted for one-step correctness,
evaluator-twin invariance, surface-sham invariance, and rollout horizons H1, H3, and H5.

## Continuous fields

The event-record fields `impact_vector.*`, `reversibility`, `recovery_cost`, and `uncertainty` use
absolute tolerance `0.005` and zero relative tolerance. A difference exactly equal to `0.005` is
equal. All physical-delta fields and all event-record boolean, integer, enum, and collection fields
remain exact.

Numeric model spellings are parsed before comparison, so `0.1`, `0.10`, and `.1` are identical.
Booleans, malformed values, and non-finite numbers are invalid numeric predictions and cannot
receive correctness or invariance credit.

The tolerance is below half of the smallest observed event-record grid spacing (`0.0133`) and
therefore cannot merge adjacent generator values.

## Implementation

`src/normative_world_model/comparators.py` owns parsing and equality. Metric code imports that
implementation directly; it may not copy or redefine its tolerance. Exact-boundary, numeric-
normalization, malformed-output, and cross-horizon tests live in `tests/test_comparators.py`.

