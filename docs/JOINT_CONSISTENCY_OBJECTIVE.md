# Joint-consistency objective and anti-gaming contract

Status: **schema-native one-step objective frozen before the Phase-3 anti-collapse smoke**

The exact machine-readable inventory is
`configs/phase3_slot_inventory.json`; the implementation is
`src/normative_world_model/slot_objective.py`. The historical gold-factual-token proxy remains an
exploratory plumbing diagnostic and is not this objective.

## 1. Output schema

Structured output is split into a domain-native `physical_delta`, a synthetic institutional
`event_record`, and one learned normative decision. All arms use identical schema-native heads on
the language model's final prompt representation. The slot classes are:

- booleans and enums;
- bounded numeric values;
- finite predicate/string sets;
- domain-native physical state changes;
- fixed shared event-record predicates and impact-vector dimensions;
- explicit finite no-change values where the schema requires a field.

The head types are categorical distributions, independent Bernoulli set memberships, and bounded
continuous mean/scale predictions. `escalation_required` is derived from the decision, so the model
cannot emit an internally inconsistent pair. JSON is deterministically serialized from the heads.
Free-text generation does not enter training, the primary metric, or the consistency loss.

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

- `L_physical`: macro-mean supervised loss on active domain-native transition slots.
- `L_event`: macro-mean supervised loss on the synthetic event-record slots.
- `L_norm`: cross-entropy on the final decision; escalation is derived.
- `L_physical_invariance` and `L_event_invariance`: evaluator-twin divergence restricted to their respective target slots.

Primary per-slot divergence:

- boolean/enum: symmetric Jensen-Shannon divergence over categorical slot distributions;
- set membership: mean symmetric Jensen-Shannon divergence over Bernoulli membership distributions;
- bounded numeric slots: normalized Huber distance between predicted means, with a separate
  bounded scale-calibration loss;
- full free-text/token-distribution KL: prohibited as the primary objective because it confounds wording with facts.

Both twins are encoded independently from their complete prompts. Divergence is calculated on
named slot-head outputs, not on full-vocabulary token distributions or a gold factual prefix. The
normative head is structurally excluded from `L_invariance`, so required label flips remain
learnable. Joint-naive uses the identical heads and supervised losses with `lambda=0`.

## 4. Lambda selection

A small fixed grid is declared before training. The development rule selects the largest factual-consistency improvement among configurations that pass all preregistered factual non-inferiority and normative-responsiveness gates. The confirmation population is never used to choose `lambda`.

The frozen grid is:

```text
lambda in {0.00, 0.05, 0.10, 0.25, 0.50}
```

It is also recorded in `configs/phase3_retained_arm_comparison.toml`. Ties after applying all
factual and normative gates choose the smaller lambda. Confirmation cannot select lambda.

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

The pre-comparison engineering smoke additionally rejects the exact collapse observed in the
schema gate: single-decision output, all-zero impacts, empty physical deltas, or failure to improve
event MAE over the zero predictor. These checks prevent wasted compute but do not replace or relax
the scientific margins.

## 6. Required ablations

- `joint_naive` (`lambda=0`).
- `joint_consistency` at the selected lambda.
- Factorized factual model with evaluator input physically absent.
- Surface-sham training removed.
- Semantic evaluator-pair training removed.

Additional representation probes are out of scope until the behavioral gates pass.

## 7. Matched budget

The retained comparison is matched on scenario family, presentation, and supervised slot
exposure. Each selected joint pair exposes two factual targets and two normative targets. The
factorized factual component cycles each selected family twice, while the normative component
consumes the corresponding two evaluator records once. Joint-naive and every joint-consistency
lambda receive byte-identical pair order, initialization, and optimizer updates.

Factorization intrinsically uses two model components, so wall time and prompt-token compute are
reported as outcomes rather than hidden by reducing its data. The exact selections and counts are
bound in `configs/phase3_retained_arm_selection_lock.json`. The smoke development families are
disjoint from the later formal development set; both exclude the 16 families already inspected by
the schema gate.
