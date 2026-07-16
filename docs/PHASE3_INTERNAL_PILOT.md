# Phase-3 internal one-step pilot

Status: **exploratory smoke only; not retained evidence**

This note records the first multi-record local run over the byte-frozen Phase-1 v3 smoke corpus.
It does not replace external Phase-1 acceptance, authorize retained generation, or expose
confirmation data.

## Implemented paths

- `joint_naive` and `joint_consistency` use the same deterministic evaluator/sham pairs, base
  checkpoint, LoRA initialization, prompts, targets, optimizer updates, and token exposure.
- The local consistency implementation is explicitly a memory-bounded gold-factual-token
  log-probability proxy. It validates paired optimization plumbing but is not the retained
  slot-level JS/Huber objective in `JOINT_CONSISTENCY_OBJECTIVE.md`.
- `factorized_factual` receives no evaluator profile.
- Factorized closed-loop evaluation uses the factual model prediction, recomputes hard-policy output
  from the deterministic policy oracle, and only then invokes the normative component.
- Every generation passes through the strict parser. Invalid or schema-incomplete JSON receives no
  imputation.

## Matched joint run

The corrected 32-update run used:

- 32 unique scenario families;
- 32 paired batches / 64 presentations per arm;
- 30,962 prompt tokens and 17,713 target tokens per arm;
- byte-identical selected record pairs between `joint_naive` and `joint_consistency`;
- the same seed and LoRA initialization.

| diagnostic | joint naive | joint consistency |
|---|---:|---:|
| final supervised train loss | 0.22361 | 0.22424 |
| development teacher-forced loss (4 pairs) | 0.30130 | 0.30042 |
| peak allocated fraction of 12 GiB | 57.15% | 61.15% |

The development difference is too small and the sample too limited to support a behavioral claim.
It only shows that the paired consistency path is trainable within physical VRAM and does not
obviously destabilize supervised learning at this scale.

## Generation and factorized result

After 32 updates, the joint arms began emitting JSON-like target fields, but the sampled generations
still failed the exact schema/parser gate. The exploratory factorized run likewise reached low
teacher-forced loss but produced zero valid factual outputs in two closed-loop attempts, so the
normative component was correctly not given gold factual context.

The factorized component run was a plumbing check and was not target-token matched to the corrected
joint comparison. It must not appear in an arm-quality table.

## Static diagnostic

Adding evaluator-blind seven-neighbor fieldwise voting improved within-environment component F1
without changing the exact joint envelope:

| cell | input | physical F1, 1-NN → fieldwise | event F1, 1-NN → fieldwise |
|---|---|---:|---:|
| A→A | structured | 0.4370 → 0.4383 | 0.5679 → 0.5945 |
| A→A | natural language | 0.4253 → 0.4790 | 0.6199 → 0.6332 |
| B→B | structured | 0.3975 → 0.4671 | 0.5458 → 0.5896 |
| B→B | natural language | 0.4304 → 0.4835 | 0.5764 → 0.6105 |

`joint_pair_success` remains exactly zero because no static prediction reconstructs every physical
and event field for both pair members. The zero envelope is therefore not merely an artifact of
using one nearest neighbor, but component metrics must remain visible because the exact conjunction
is deliberately severe.

## Decision

Do not rent a larger server yet. The current blocker is structured output convergence/objective
fidelity, not physical memory. The next implementation gate is a schema-native slot prediction path
or equivalently strict constrained decoding that:

1. preserves the frozen output schema and evaluator-blind factual boundary;
2. supports the declared per-slot JS/Huber consistency objective;
3. reports complete component metrics even before all-field exact match becomes nonzero;
4. matches factorized and joint scenario/target-token budgets before any arm comparison.

Only after that gate passes locally should longer smoke training or server scale be considered.
