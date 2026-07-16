# Phase-2 evaluation contract

Status: **implemented for exploratory v3 smoke use; retained-result freeze waits for external
acceptance and the retained manifest**

This contract defines how model text becomes a scored structured prediction. It does not change the
Phase-1 corpus, oracle, renderer, comparator tolerance, or confirmation commitment.

## 1. Presentations and pair construction

Each scenario/profile has both input conditions:

- `structured`: canonical pre-transition `model_input` plus one stored structured profile
  serialization;
- `natural_language`: one scenario rendering plus one natural-language evaluator-profile
  rendering.

Natural-language examples cross two scenario renderings with two profile renderings. Structured
examples hold the canonical source serialization fixed and vary only the profile serialization.

Pair construction is constrained as follows:

- semantic evaluator pairs hold scenario rendering and profile-rendering index fixed while changing
  the profile semantics;
- surface-sham pairs hold the scenario, profile semantics, and every typed value fixed while
  changing only the profile rendering;
- scenario-rendering robustness is reported separately and is never substituted for the profile
  surface sham.

The smoke corpus therefore produces 24 presentations per family: 8 structured and 16
natural-language.

## 2. Strict output parser

The parser accepts either one JSON object or one `json`/plain Markdown code fence containing one
JSON object. Surrounding prose is invalid.

Required keys are:

```text
physical_delta
event_record
normative_decision
escalation_required
rollout
```

`confidence` is optional. No other top-level key is accepted. Physical and event-record keys and
types must exactly match the frozen environment schema. The parser uses target objects only as type
and key exemplars; target values never repair, impute, or coerce predictions.

- physical discrete values are exact and are not coerced from strings;
- event-record continuous values use the shared v2.1 finite-decimal parser;
- malformed and non-finite numbers fail;
- `escalation_required` must agree with whether `normative_decision == "escalate"`;
- rollout horizons and schemas must exactly match the requested horizon set.

Failed generations remain in every denominator. A parse failure receives no correctness,
invariance, or pair-success credit.

## 3. Field scoring

Nested objects are flattened into canonical leaf paths. Lists and other typed collections remain
single leaf values. A prediction is treated as a set of `path=value` facts:

```text
precision = correct predicted facts / predicted facts
recall    = correct predicted facts / target facts
F1        = harmonic mean
```

Continuous event fields use the shared inclusive absolute tolerance `0.005`; all other comparisons
are exact. Physical and event-record scores are never pooled into one factual headline.

## 4. Evaluator pairs and leakage

Evaluator-pair correctness requires:

- both physical predictions correct and invariant;
- both event-record predictions correct and invariant;
- both normative decisions correct.

Constant but wrong facts cannot pass. `joint_pair_success` requires all three conditions for the
same pair.

For each factual component:

```text
D_semantic = fraction of semantic evaluator pairs with divergent predictions
D_surface  = fraction of matched profile-surface shams with divergent predictions
delta_leak = D_semantic - D_surface
```

If either member is unparsable, divergence is conservatively recorded as `1`. This may cancel in
the sham correction when both pair types fail, but the same rows still receive zero correctness and
zero joint-pair success, preventing parse collapse from being interpreted as disentanglement.

## 5. Factual twins and anti-gaming

A factual change is represented by:

```text
(component, leaf path, correct base value, correct twin value)
```

`changed_field_macro_f1` scores these full changes. Change-set precision/recall separately score
only whether the correct paths changed. Physical-twin sensitivity reports whether the predicted
physical delta changed when the oracle physical target changed.

The information diagnostics additionally report:

- parse coverage;
- empty physical/event rates;
- maximum constant-output rate across all attempts;
- whole-output entropy;
- per-field entropy.

The joint-consistency arm must satisfy the frozen non-inferiority, parse-coverage, constant/empty,
and normative-response margins in `configs/preregistration_v3.toml`.

## 6. Normative and rollout strata

Normative results are stratified into:

- `hard_policy_violation`;
- `uncertainty_band`;
- `dimension_veto`;
- `irreversible_harm_veto`;
- score `boundary`, `intermediate`, and `interior`.

The current smoke generator provides chained H1/H2/H3 targets. The locked model study requires
H1/H3/H5. Until an H5 target exists under an accepted retained protocol, the H5 gate is reported as
`UNIDENTIFIED`, never inferred from H3.

## 7. Four-way transfer

The manifest contains all eight cells:

```text
A→A structured / natural_language
B→B structured / natural_language
A→B structured / natural_language
B→A structured / natural_language
```

Training uses source-environment `train` families; evaluation uses destination-environment
`development` families during exploration. Scenario-ID lists are hash-bound and checked for zero
overlap. Each destination environment must retain the preregistered impact-dimension × sign support;
otherwise its transfer result is `UNIDENTIFIED`.

## 8. Internal harness result

`scripts/run-phase2-internal-check.py` exercised the contract against the exact v3 revision-1 smoke
targets:

- 600 families;
- 14,400 presentations;
- 14,400/14,400 strict parser successes;
- zero forbidden post-transition target fields in prompts;
- oracle-fixture physical/event correctness, normative pair accuracy, joint-pair success,
  changed-field F1, physical-twin sensitivity, and H1/H2/H3 rollout scores all equal to `1.0`;
- physical and event `delta_leak` both equal to `0`;
- A→A, B→B, A→B, and B→A support all identified.

These are harness integrity tests, not model results.
