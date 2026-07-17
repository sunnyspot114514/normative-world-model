# Phase 3 diversity gateway v3 and predeclared representation fallback

Status: **FROZEN DESIGN; NOT EXECUTED**. This document authorizes selection
construction and implementation review only. Training requires a separately
hash-bound runner and input lock.

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

All original anti-collapse thresholds remain blocking. Additional per-class
recall, train-median MAE, constant-slot, and train/evaluation-gap diagnostics
are reported but cannot change the V3 verdict. This preserves the original
gate while making a misleading pass easier to recognize.

If V3 passes, its adapter may be promoted to the formal joint-naive arm only if
the runner proves that model initialization, input order, optimizer semantics,
objective, and output bytes are exactly the formal contract. No retraining or
hyperparameter selection may use the V3 evaluation labels. The reserved formal
96-record evaluation remains unopened until that proof passes.

If V3 fails any blocking check, the present representation is stopped. More
epochs, a different learning rate, or a new threshold on the V3 population are
not allowed.

## V4 fallback, frozen before V3 is observed

The fallback is reserved now so that a V3 failure cannot drive population or
architecture shopping. It is not authorized unless V3 is BLOCKED.

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

V4 uses 1,024 unique pairs once and a second, already reserved 48-record blind
development population. In addition to the original gate, every normative
class must have recall at least 0.20 and continuous event MAE must beat the
training-slot-median constant baseline by at least 0.02. A V4 failure terminates
the local Qwen3-1.7B path as an engineering null; it does not authorize a fifth
diagnostic population.

V4 deliberately changes representation, continuous regression, and normative
class weighting together. It is an engineering rescue, so a pass cannot be
attributed to any one of those changes. A pass authorizes a new hash-bound arm
implementation contract in which all scientific arms use V4; mixing V3 and V4
adapters in one comparison is forbidden.

## Governance boundary

- V1 and v2 remain independently BLOCKED.
- Neither V3 nor V4 is a scientific joint-consistency/factorized comparison.
- Confirmation remains `RESERVED_NOT_GENERATED`.
- H5 remains `UNIDENTIFIED`.
- No server rental is authorized.
- No practical margin or scientific success criterion changes here.
