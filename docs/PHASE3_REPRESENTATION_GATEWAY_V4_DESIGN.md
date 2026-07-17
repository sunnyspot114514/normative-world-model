# Phase 3 role-query representation gateway V4

Status: **FROZEN EXECUTABLE CONTRACT; NOT YET EXECUTED**.

This is a one-shot engineering adequacy gate for the local
`Qwen/Qwen3-1.7B-Base` path after V3 was preserved as `BLOCKED`. It is not a
scientific comparison of `joint_naive`, `joint_consistency`, and `factorized`,
and it does not open formal development or confirmation data.

## Why V4 is allowed

V3 resolved the training-diversity confound but failed four repaired ability
checks: normative accuracy, minimum class recall, continuous event MAE against
the training constant, and event field F1 against the training constant. The
most serious failures were escalate recall of 0.0625 and event F1 below the
constant predictor. More steps, a learning-rate search, and threshold changes
on the opened V3 population are forbidden.

V4 therefore changes the representation/objective package that was declared
before V3 execution. It changes three things together, so a pass cannot be
attributed to any one of them:

1. physical, event, and normative heads read separate role-query hidden states;
2. continuous slots use training-z-score Smooth L1 without a variance head;
3. normative cross entropy uses training-only inverse-frequency weights.

## Executable representation contract

The original prompt is followed by three manually tokenized ordinary-text
markers, in this causal order:

```text
[PHYSICAL_TRANSITION_QUERY]
[EVENT_RECORD_QUERY]
[NORMATIVE_DECISION_QUERY]
```

The last token of each marker segment is the only hidden state passed to that
role's trunk. Each trunk is `LayerNorm(2048) -> Linear(2048, 256) -> GELU`,
followed by heads for slots of that role. Continuous heads emit one raw scalar;
other schema-native heads retain their frozen support. Source prompts must
contain zero reserved markers, every suffix marker is appended exactly once,
and source plus suffix may not exceed 1,536 tokens. Truncation is an error.

The input audit covers all 2,048 training presentations and all 48 precommitted
V4 evaluation presentations. Its observed range is 572--692 tokens, with zero
source-marker collisions and zero truncations. Factual query states still
attend to the complete source prompt, including `evaluator_values`; invariance
is therefore not true by construction.

## Training-only transforms

For each continuous slot, all 2,048 presentations in the frozen 1,024-pair
training population determine a population mean and population standard
deviation (`ddof=0`, floor `1e-6`). The model predicts z units and trains with
Smooth L1 beta 0.25. Decoding applies `mean + std * raw` and then clips to the
unchanged slot range.

The normative training counts are allow 488, reject 1,168, and escalate 392.
For class `c`, the raw value is `count_c ** -0.5`; values are divided by their
exposure-weighted mean, capped at 2.0, and divided by the new
exposure-weighted mean. The frozen final weights are 1.2187960037,
0.7878064118, and 1.3598715847 respectively.

The implementation deliberately computes unreduced cross entropy, multiplies
each example by its class weight, and then averages. Passing `weight=` to
PyTorch's default mean reduction is forbidden because its normalization makes
the weight cancel at batch size one. A regression test locks this behavior.

## Population and gate

Training is byte-identical to the frozen formal training selection: 1,024
unique scenario families, one pass, 1,024 optimizer steps, seed 2026071705,
and the existing LoRA/optimizer settings. The fixed 32-pair training probe is
measured before and after optimization.

Evaluation is byte-identical to the 48-record `fallback_reservation` committed
before V3 ran. It is disjoint from training, schema-gate development, V1, the
reserved formal population, V2, and V3. It contains one record in each
environment/input/decision/profile bucket. No fifth diagnostic population is
available.

Every repaired V3 threshold remains blocking and byte-equivalent:

- fixed-probe loss improvement at least 0.20;
- normative accuracy at least 0.40 and recall for every class at least 0.20;
- largest predicted decision share at most 0.85;
- active impact and nonempty physical-output fractions at least 0.50;
- continuous event MAE, physical F1, and event F1 each improve over the
  environment-conditioned training constant by at least 0.02;
- strict schema coverage 1.0, peak memory fraction at most 0.95, and exact
  deterministic input/statistics/weight reconstruction.

## Formal mapping boundary

The consistency implementation is frozen for future use: categorical slots
use symmetric Jensen-Shannon, set slots use mean symmetric Bernoulli
Jensen-Shannon, and continuous slots use Smooth L1 between raw z predictions.
The V4 gateway itself uses `consistency_lambda = 0`.

The future factorized mapping is also fixed at the contract level. Factual
prompts physically omit evaluator values and expose physical/event markers.
Normative training uses gold event records; evaluation must use the factorized
factual prediction plus a recomputed policy-oracle result. Prompt construction
and policy recomputation use `factorized_normative_input_text` and
`recompute_factorized_policy_result` in `model_arms.py`.

These mappings do not authorize formal execution. A V4 pass only permits a
separate hash-bound three-arm runner to be frozen and reviewed. The formal
population remains unopened until all three executable arm mappings, artifact
reuse rules, and the oracle re-decode diagnostic are locked together.

## Decision rule

- **PASS:** preserve the exact adapter, heads, training transform contract, row
  predictions, and hashes; authorize only the next runner-freeze step.
- **BLOCKED:** terminate the local Qwen3-1.7B path as an engineering null. Do
  not add epochs, tune against this population, or create another diagnostic
  population.

In either case V1, V2, and V3 remain `BLOCKED`; confirmation remains
`RESERVED_NOT_GENERATED`; H5 remains `UNIDENTIFIED`; server rental and formal
arm execution remain unauthorized by this contract.

