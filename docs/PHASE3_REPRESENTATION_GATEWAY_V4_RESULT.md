# Phase 3 role-query representation gateway V4 result

Status: **BLOCKED**. The local Qwen3-1.7B path terminates here. The formal
three-arm comparison was not started, confirmation remains
`RESERVED_NOT_GENERATED`, and no fifth local diagnostic population is
authorized.

V4 executed the precommitted engineering rescue at commit
`06022604045188774ab208d4cecb0a4a93d93750`: three role-query hidden states,
role-specific MLP trunks, training-z-score continuous regression, and
training-only normative class weighting. It used 1,024 unique training pairs
for 1,024 optimizer steps and evaluated once on the 48-record population that
had been reserved before V3 ran.

## Frozen gate outcome

| Check | Observed | Requirement | Result |
|---|---:|---:|:---:|
| Fixed-probe loss improvement | 0.1688 | >= 0.20 | FAIL |
| Normative accuracy | 0.4375 | >= 0.40 | PASS |
| Minimum decision recall | 0.0000 | >= 0.20 | FAIL |
| Largest predicted-decision share | 0.6042 | <= 0.85 | PASS |
| Continuous event MAE improvement over training constant | -0.00445 | >= 0.02 | FAIL |
| Physical field-F1 improvement over training constant | 0.00208 | >= 0.02 | FAIL |
| Event field-F1 improvement over training constant | -0.05689 | >= 0.02 | FAIL |
| Strict schema coverage | 1.0000 | >= 1.00 | PASS |
| Active impacts / nonempty physical outputs | 1.0000 / 1.0000 | >= 0.50 / >= 0.50 | PASS |
| Peak allocated memory fraction | 0.3156 | <= 0.95 | PASS |
| Deterministic input/statistics/weight reconstruction | exact | required | PASS |

The fixed 32-pair training probe fell from 3.5402 to 2.9428, an improvement of
16.88% but below the frozen 20% learning gate. Training took 1,320.6 seconds.

The model predicted 29 reject, 18 escalate, and one allow decisions. Recall was
0.8125 for reject, 0.5000 for escalate, and 0.0000 for allow. Aggregate
normative accuracy passed, but the zero allow recall makes this a class failure
rather than an aggregate success.

Continuous event MAE was 0.3293 versus 0.3248 for the environment-conditioned
training constant. Physical F1 was 0.3875 versus 0.3854, only 0.0021 better.
Event F1 was 0.4399 versus 0.4968, 0.0569 worse. The representation package
therefore did not provide reliable held-out event prediction.

## Interpretation boundary

Relative to V3, role queries and class weights redistributed normative outputs:
the escalate recall problem improved, aggregate normative accuracy passed, and
the model no longer concentrated almost entirely on reject. The failure moved
to allow recall and factual fields. This does not establish that class
weighting or role queries caused any individual change because V4 deliberately
changed three mechanisms together and used a different precommitted evaluation
population.

The result is an engineering null for this local checkpoint, budget, and
training path. It is not a test of `joint_consistency`, not evidence that a
factorized model wins, and not a scientific conclusion about larger world
models. Under the frozen decision rule, more epochs, learning-rate tuning, a
fifth diagnostic population, formal arm evaluation, and confirmation are not
allowed as continuations of this protocol.

