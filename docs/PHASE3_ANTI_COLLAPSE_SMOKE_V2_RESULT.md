# Phase 3 anti-collapse smoke v2 result

Status: **BLOCKED**. The formal one-step three-arm comparison was not started.

V2 changed only the optimizer-step count from 256 to 1024 and evaluated on 48
new development records that were scenario-disjoint from the schema gate, v1
smoke, and reserved formal-development population. Its first 32-step mean loss
was bit-for-bit equal to v1 (6.571615278720856), so the initialization and
training prefix replayed successfully. V1 remains BLOCKED as a separate
historical result.

## Frozen gate outcome

| Check | Observed | Frozen requirement | Result |
|---|---:|---:|:---:|
| Loss-window improvement | 0.8349 | >= 0.20 | PASS |
| Normative accuracy | 0.2917 | >= 0.40 | FAIL |
| Largest decision share | 0.3750 | <= 0.85 | PASS |
| Rows with active impacts | 1.0000 | >= 0.50 | PASS |
| Rows with nonempty physical delta | 1.0000 | >= 0.50 | PASS |
| Event MAE improvement over zero | -0.16293 | >= 0.02 | FAIL |
| Strict schema coverage | 1.0000 | >= 1.00 | PASS |
| Peak allocated memory fraction | 0.3123 | <= 0.95 | PASS |
| Deterministic v1-prefix replay | exact | abs diff <= 1e-8 | PASS |

The longer schedule removed the obvious mode collapse: the 48 decisions were
18 allow, 16 escalate, and 14 reject, and only 5.41% of active categorical
slots were constant. Physical field F1 improved from v1's 0.2708 to 0.4250.
These are real engineering improvements.

They did not make the path adequate. Normative accuracy fell to 0.2917 on a
decision-balanced set. More seriously, continuous event MAE was 0.51635 versus
0.35342 for the zero predictor, a deficit of 0.16293. Event field F1 remained
low at 0.4343. The model became more varied without becoming correctly
normative-responsive or numerically predictive.

## Interpretation boundary

This result does not show that joint-consistency training fails or that a
factorized architecture wins: neither scientific comparison was run. It shows
that the frozen Qwen3-1.7B + final-hidden-state linear slot-head path fails its
own basic held-out adequacy gate at the formal joint-arm training budget.
Consequently, running lambda variants and the factorized arm would spend more
compute without an acceptable joint-naive reference.

The preregistered action remains stop_before_formal_arm_comparison. Further
step increases or threshold changes against this v2 population are prohibited.
Any future attempt must be a new representation/objective redesign with new
diagnostic data, or the local small-model path should be recorded as an
engineering null. Confirmation remains RESERVED_NOT_GENERATED; H5 remains
UNIDENTIFIED; server rental remains unauthorized.
