# Phase 3 anti-collapse smoke result

Status: **BLOCKED**. The formal retained one-step three-arm comparison was not
started.

The smoke ran from Git commit `5dfc599b80ce65f59f01a45949306498f5948386`
on the exact 128 training pairs and 48 balanced development records frozen in
the input lock. Confirmation remained `RESERVED_NOT_GENERATED`.

## Frozen gate outcome

| Check | Observed | Frozen requirement | Result |
|---|---:|---:|:---:|
| Loss-window improvement | 0.5708 | >= 0.20 | PASS |
| Normative accuracy | 0.3333 | >= 0.40 | FAIL |
| Largest decision share | 1.0000 | <= 0.85 | FAIL |
| Rows with active impacts | 1.0000 | >= 0.50 | PASS |
| Rows with nonempty physical delta | 1.0000 | >= 0.50 | PASS |
| Event MAE improvement over zero | -0.00771 | >= 0.02 | FAIL |
| Strict schema coverage | 1.0000 | >= 1.00 | PASS |
| Peak allocated memory fraction | 0.3123 | <= 0.95 | PASS |

All 48 balanced development records were decoded as `reject`, so normative
accuracy was exactly one third and the decision head failed the explicit
collapse gate. Continuous event MAE was 0.35372 versus 0.34601 for the frozen
zero predictor. Across active categorical slots, 81.08% emitted a constant
value on the development set. These observations make this a broad
representation/learning collapse, not merely a JSON-generation or resource
failure.

The training objective itself was finite and decreased from a first-window
mean of 6.5716 to a last-window mean of 2.8204 over 256 steps. Strict JSON,
impact activity, physical non-emptiness, and resource gates passed. Therefore
the result does not support the narrower claim that the path failed because it
could not run or serialize the schema; it failed to learn sufficiently
responsive held-out predictions under the frozen smoke budget.

## Post-result diagnostic (not a new gate)

The 256 normative training exposures were imbalanced: 147 `reject`, 60
`allow`, and 49 `escalate`. The development selection was deliberately balanced
across all three decisions. A read-only evaluation of the saved model on those
256 training presentations also produced 256 `reject` decisions. Its normative
accuracy was therefore 0.5742, exactly the training reject share, while 78.38%
of active categorical slots were constant. Training event MAE did beat its zero
predictor (0.33991 versus 0.38257), but this advantage reversed on held-out
development. Physical/event field F1 was only 0.3691/0.4153 on training versus
0.2708/0.4087 on development.

This makes the diagnosis stronger than a held-out distribution-shift story:
the frozen 256-step path learned some continuous-event signal but did not even
separate the three normative classes on its own training presentations. Label
imbalance is a plausible contributor, but not a demonstrated sole cause because
physical and event categorical heads also showed extensive constant output.
Any follow-up that changes selection, objective weighting, representation, or
optimizer budget is a redesign and must use a new frozen diagnostic population;
the same 48 records cannot be tuned against and then presented as a passed
gate.

## Governance consequence

The preregistered action is `stop_before_formal_arm_comparison`. No threshold
is relaxed, no failed gate is reclassified, and no formal or confirmation run
is unlocked. The byte-level result and adapter/head hashes are recorded in
`configs/phase3_anti_collapse_smoke_result_lock.json`.
