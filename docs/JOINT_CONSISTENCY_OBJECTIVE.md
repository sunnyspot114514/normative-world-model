# Joint-consistency objective and anti-gaming contract

Status: **implementation skeleton; field inventory freezes with the Phase 1 schema**

Time box: define the objective now; fill the exact slot inventory while implementing the two transition schemas. Do not design auxiliary losses unrelated to the primary leakage question.

## 1. Output schema

Structured output is split into a domain-native `physical_delta` and a synthetic institutional `event_record`. Both must be canonical and typed. The initial slot classes are:

- booleans and enums;
- bounded numeric values;
- finite predicate/string sets;
- domain-native physical state changes;
- fixed shared event-record predicates and impact-vector dimensions;
- explicit `no_change` markers where the schema requires a field.

Free-text rationales are generated only after the structured fields and never enter the primary consistency metric or loss.

## 2. Matched paired batch

Each evaluator-twin batch contains:

```text
(same pre-state, same proposed action, same policy, profile v1, common physical target, common event-record target, normative target n1)
(same pre-state, same proposed action, same policy, profile v2, common physical target, common event-record target, normative target n2)
```

Surface-sham pairs use two semantically equivalent renderings of one machine-readable profile. Factual-twin pairs change one causal world variable and therefore do **not** receive an invariance penalty.

## 3. Loss

```text
L = L_physical + L_event + L_norm
    + lambda * (L_physical_invariance + L_event_invariance)
```

- `L_physical`: supervised loss on domain-native transition slots.
- `L_event`: supervised loss on the synthetic event-record slots.
- `L_norm`: supervised loss on the final decision and escalation fields.
- `L_physical_invariance` and `L_event_invariance`: evaluator-twin divergence restricted to their respective target slots.

Primary per-slot divergence:

- boolean/enum/set membership: symmetric Jensen-Shannon divergence over slot distributions;
- bounded numeric slots: Huber distance between predicted means, with a separate calibration loss;
- full free-text/token-distribution KL: prohibited as the primary objective because it confounds wording with facts.

For decoder-only implementations, divergence is measured under a shared gold factual prefix and a fixed schema order. The normative portion is excluded from `L_invariance` so required label flips remain learnable.

## 4. Lambda selection

A small fixed grid is declared before training. The development rule selects the largest factual-consistency improvement among configurations that pass all preregistered factual non-inferiority and normative-responsiveness gates. The confirmation population is never used to choose `lambda`.

The initial proposed grid is:

```text
lambda in {0.00, 0.05, 0.10, 0.25, 0.50}
```

It freezes with preregistration v1 after the P0 attack review.

## 5. Anti-gaming metrics

Consistency is not sufficient. Report all of:

- changed-field macro F1;
- change-set precision and recall;
- factual-twin sensitivity;
- evaluator-twin physical consistency/correctness and event-record consistency/correctness;
- schema coverage/parse rate;
- empty-delta and constant-output rates;
- predicted field entropy by field and arm;
- normative pair accuracy and flip recall.

A model that becomes invariant by omitting information, predicting defaults, or ignoring profiles fails the anti-gaming gate even if its raw pairwise consistency rises. Physical and event-record information metrics are reported separately so an event-record shortcut cannot hide a degraded transition model.

## 6. Required ablations

- `joint_naive` (`lambda=0`).
- `joint_consistency` at the selected lambda.
- Factorized factual model with evaluator input physically absent.
- Surface-sham training removed.
- Semantic evaluator-pair training removed.

Additional representation probes are out of scope until the behavioral gates pass.
