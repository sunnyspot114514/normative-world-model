# Phase 3 diversity gateway v3 and predeclared representation fallback

Status: **FROZEN DESIGN REVISION 1; NOT EXECUTED**. This document authorizes selection
construction and implementation review only. Training requires a separately
hash-bound runner and input lock.

Revision 1 was frozen before any V3 training or evaluation. It repairs four
internal-review findings in the original `bda99ec` design: incomparable online
loss windows, a constant-baseline false-pass route, an overclaimed blind
population, and premature V4/formal authorization. The earlier commit remains
historical evidence and is not rewritten.

## Why a third engineering gate is justified

V2 was correctly recorded as BLOCKED and remains so. It used 1,024 optimizer
steps, but only 128 unique comparison pairs: the same formal-selection prefix
was repeated eight times. The frozen formal joint arm instead specifies 1,024
unique pairs and 1,024 steps. Calling v2 a test "at the formal training budget"
therefore conflated update count with training-population diversity.

This was not a label-balance confound. Local deterministic recounting gives
147/256 reject presentations in the 128-pair population (57.42%) and
1,168/2,048 in the formal population (57.03%). Nor are the continuous targets
unstructured noise: the ten continuous event fields have only 6--16 distinct
values each in the formal population. The unresolved question is whether the
v2 adapter memorized a narrow population while failing to learn the shared
dynamics.

The earlier v2 result text said any next attempt must change the representation
or objective. That conclusion was too strong. This design records the narrower
correction without changing or erasing the v2 result.

## V3: one-variable diversity adjudication

Within the training procedure, V3 changes one thing relative to v2:

| item | v2 | v3 |
|---|---:|---:|
| optimizer steps | 1,024 | 1,024 |
| unique training pairs | 128 | 1,024 |
| passes over each pair | 8 | 1 |
| model, LoRA, heads, objective, seed | frozen | identical |

The pair order is the already frozen formal training selection. Its first 128
pairs must be byte-identical to the v1/v2 prefix. Each scenario family appears
once. V3 uses a new 48-record development population balanced across the same
48 environment/input/decision/profile buckets and disjoint from the schema
gate, v1, v2, and the untouched formal development population.

The evaluation population necessarily changes as well because an opened
engineering population cannot be reused. Therefore v2-to-v3 metric differences
are not a paired causal estimate. V3 is an adequacy adjudication under the same
balanced gate, not a claim that diversity alone explains an exact change in
accuracy.

The original online first/last loss comparison is diagnostic only because V3
uses different examples at the beginning and end of its one pass. The blocking
learning check instead measures the same first 32 training pairs before and
after training, without gradients, and requires a 20% loss reduction.

The held-out gate is strengthened before V3 outputs are observed. Every
normative class must have recall at least 0.20. Factual predictions are compared
with an environment-conditioned training-only constant: typed modes for
categorical slots, majority membership for set slots, and medians for
continuous slots. V3 must improve continuous event MAE, physical field F1, and
event field F1 by at least 0.02 each. The former zero-event baseline remains a
diagnostic because a constant median already beats it on the frozen training
distribution.

A training-only table-model positive control was run without accessing any
development or confirmation target. Extra Trees reached holdout macro R2
0.4196; a disclosed post-result HistGradientBoosting sensitivity reached
0.7348, with several derived evidence/reversibility fields near 1.0 but
autonomy below zero. This establishes partial, not universal, learnable
headroom. It does not change the V3 gate. A V3 failure blocks this local model
path but cannot be attributed to architecture alone.

If V3 passes, it only becomes a candidate formal joint-naive artifact. Promotion
requires hashes for the exact adapter and heads, a certificate covering model
initialization, input order and optimizer semantics, and reuse without
retraining. The formal runner must also provide an oracle re-decode diagnostic
checking whether the learned normative decision agrees with applying the frozen
N oracle to the predicted event record. All three formal arm mappings must be
frozen before the formal 96-record population is opened.

If V3 fails any blocking check, the present representation is stopped. More
epochs, a different learning rate, or a new threshold on the V3 population are
not allowed.

## V4 fallback, frozen before V3 is observed

The population is reserved now, but V4 is only a design sketch. It is not an
authorized fallback and is not described as frozen implementation. A V3 failure
records the current architecture as BLOCKED and stops. V4 cannot run or unlock
a three-arm comparison until a separate contract freezes executable code,
factorized factual/normative mappings, consistency losses, budgets, tests, and
an input lock.

The prompt receives a fixed suffix with three ordinary-text query markers.
Physical, event, and normative heads consume the hidden state at their own
marker rather than sharing the final prompt token. Each role has a
`LayerNorm -> Linear(2048, 256) -> GELU` trunk followed by schema-native slot
heads. All query positions still attend to the full prompt, including
`evaluator_values`; factual invariance is therefore learned and tested rather
than made true by hiding the intervention.

The implementation must prove that each marker occurs exactly once and that
the complete prompt plus suffix remains within the frozen 1,536-token limit;
truncating either the source prompt or the query suffix is forbidden.

The continuous variance head is removed. Training-only means and standard
deviations from all 2,048 presentations in the frozen 1,024-pair population
(`ddof=0`, independently per slot, with a `1e-6` standard-deviation floor)
standardize each continuous target. A raw
scalar is trained with Smooth L1 (`beta=0.25` in z units) and decoded as
`mean + std * prediction`, then clipped to the existing contract range. This
removes bounded-sigmoid saturation and an unused variance nuisance parameter
without changing target semantics.

Only the normative three-way cross entropy receives class weights. For class
`c`, let `r_c = count_c ** -0.5`. Divide each `r_c` by its exposure-weighted
mean, cap at 2.0, and renormalize once more to exposure-weighted mean one. The
counts come only from the frozen training labels; no evaluation labels are
used. Other categorical and set losses remain unchanged.

The sketch uses 1,024 unique pairs once and a second, already reserved 48-record
precommitted but unopened
development population. In addition to the original gate, every normative
class must have recall at least 0.20 and continuous event MAE must beat the
training-slot-median constant baseline by at least 0.02. A V4 failure terminates
the local Qwen3-1.7B path as an engineering null; it does not authorize a fifth
diagnostic population.

The V4 sketch deliberately changes representation, continuous regression, and normative
class weighting together. It is an engineering rescue, so a pass cannot be
attributed to any one of those changes. It currently authorizes neither a run
nor a three-arm comparison; mixing V3 and V4 adapters remains forbidden.

## Governance boundary

- V1 and v2 remain independently BLOCKED.
- Neither V3 nor V4 is a scientific joint-consistency/factorized comparison.
- Confirmation remains `RESERVED_NOT_GENERATED`.
- H5 remains `UNIDENTIFIED`.
- No server rental is authorized.
- No practical margin or scientific success criterion changes here.
- Development selections are reconstructible from local labeled data. They are
  called precommitted and unopened, not cryptographically blind.
