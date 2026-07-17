# Phase 3 schema-native anti-collapse smoke

Status: frozen before execution on retained discovery data.

## Purpose

This is an engineering gate, not a scientific arm comparison. It asks whether
the frozen Qwen3-1.7B Base + LoRA representation path and schema-native slot
heads can learn non-degenerate one-step outputs before compute is spent on the
three-arm comparison. A PASS does not establish any Phase-3 research claim.

## Frozen population and exposure

- Data: retained discovery only. Confirmation remains
  `RESERVED_NOT_GENERATED`.
- Training: the first 128 pairs of the separately locked, hash-ranked formal
  selection; 256 optimizer steps; one pair (two presentations) per step.
- Arm: joint-naive only, with consistency lambda fixed to `0.0`.
- Evaluation: 48 held-out development records, exactly one from every
  environment x input-condition x normative-decision x evaluator-profile
  bucket. These records are excluded from formal development selection.
- The 16 development families consumed by the historical schema gate are also
  excluded.

The exact identities and bucket digests are in
`configs/phase3_retained_arm_selection_lock.json`.

## Frozen model and objective

- Model: `Qwen/Qwen3-1.7B-Base` at revision
  `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`.
- Representation: final non-padding prompt hidden state.
- Trainable parameters: LoRA adapters plus one linear head per frozen slot.
- Supervision: macro categorical CE, set BCE, and normalized continuous Huber
  plus scale calibration.
- Output: deterministic strict JSON decoded from slot heads. No free-text
  generation is used for the primary smoke metrics.
- `escalation_required` is derived from `normative_decision`; it is not a
  separately learned slot.
- Deterministic algorithms, a fixed seed, disabled TF32, and disabled cuDNN
  benchmarking are required by the runner.

The exact slot support and objective are frozen in
`configs/phase3_slot_inventory.json` and
`src/normative_world_model/slot_objective.py`.

## PASS gate

All comparisons are inclusive. Every item must pass:

- first-window to last-window training-loss improvement >= 0.20;
- normative accuracy >= 0.40;
- largest predicted-decision share <= 0.85;
- fraction of rows with at least one absolute impact prediction > 0.05 >=
  0.50;
- fraction of rows with a nonempty/nonzero physical delta >= 0.50;
- continuous event MAE improvement over the zero predictor >= 0.02;
- strict schema coverage >= 1.00; and
- peak allocated CUDA memory <= 0.95 of device memory.

The smoke report must also preserve row-level predictions, loss/resource
diagnostics, exact output-file hashes, the frozen selection bindings, and all
bound input hashes.

## Decision rule

- PASS: the project may freeze and run the formal one-step three-arm
  comparison on retained discovery.
- Any failure: stop before the formal comparison. Preserve the result as a
  failed engineering gate; do not tune these thresholds against the same
  48-record evaluation set.

Neither branch authorizes confirmation generation, changes practical margins,
identifies H5 rollout behavior, or authorizes server rental.
