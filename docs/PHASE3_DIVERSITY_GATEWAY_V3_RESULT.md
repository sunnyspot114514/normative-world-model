# Phase 3 diversity gateway v3 result

Status: **BLOCKED**. The formal one-step three-arm comparison was not started.
Confirmation remains `RESERVED_NOT_GENERATED`, and the V4 sketch is not an
authorized fallback.

V3 trained the original Qwen3-1.7B final-hidden-state linear slot-head path for
1,024 steps on 1,024 unique comparison pairs. Its first 32 online losses exactly
replayed v1/v2, and the same fixed 32-pair training probe improved by 63.57%.
This establishes that optimization occurred and resolves the v2 diversity
confound. It does not establish adequate held-out prediction.

## Frozen gate outcome

| Check | Observed | Requirement | Result |
|---|---:|---:|:---:|
| Fixed-probe loss improvement | 0.6357 | >= 0.20 | PASS |
| Normative accuracy | 0.3958 | >= 0.40 | FAIL |
| Minimum decision recall | 0.0625 | >= 0.20 | FAIL |
| Largest predicted-decision share | 0.6250 | <= 0.85 | PASS |
| Continuous event MAE improvement over training constant | 0.01466 | >= 0.02 | FAIL |
| Physical field-F1 improvement over training constant | 0.07083 | >= 0.02 | PASS |
| Event field-F1 improvement over training constant | -0.05929 | >= 0.02 | FAIL |
| Strict schema coverage | 1.0000 | >= 1.00 | PASS |
| Active impacts / nonempty physical outputs | 1.0000 / 1.0000 | >= 0.50 / >= 0.50 | PASS |
| Peak allocated memory fraction | 0.3123 | <= 0.95 | PASS |
| Deterministic prefix replay | exact | abs diff <= 1e-8 | PASS |

The model recalled reject at 0.75, allow at 0.375, and escalate at only 0.0625.
It produced just four escalate predictions and correctly placed one. Normative
accuracy missed the aggregate threshold by one of 48 records, but the escalate
failure makes the result substantively non-borderline.

Physical field F1 rose to 0.4771 versus the environment-conditioned training
constant's 0.4063. Continuous event MAE was 0.2891 versus 0.3037 for that
constant, an improvement of 0.0147 but below the frozen 0.02 margin. Overall
event field F1 was 0.4599 versus the constant's 0.5192. The old zero-event gate
would have passed by 0.0649, confirming the internal audit finding that it was
too weak.

## Interpretation boundary

Training diversity materially improved the path relative to v2: physical F1,
continuous event MAE, normative accuracy, and decision diversity all moved in
the expected direction. It did not make the representation adequate under the
repaired held-out gate. The current local final-token linear-head path is
therefore blocked before scientific arm comparison.

The training-only positive control showed partial rather than universal
headroom, so this result is not attributed to architecture alone. It also does
not test joint-consistency or prove a factorized advantage. Under revision 1,
the only authorized action is to preserve this result and stop. A future V4
experiment would require a separate complete executable contract and may not
reuse this result to relax thresholds or open the reserved formal population.

