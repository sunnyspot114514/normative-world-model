# Phase-3 retained schema-convergence result

Status: **PASS for strict-schema viability; no arm-quality claim**

The single frozen run at commit
`c6ad17d2a7591a1412231c3ea0657c6b1220ddf2` trained the cached 1.7B base
model's `joint_naive` LoRA adapter for 64 updates over 64 unique retained
discovery families.

## Frozen gate result

- strict parse coverage: 16/16 (`1.0`, threshold `0.25`);
- unique development families: 16/16;
- balance: 8 game / 8 organization and 4 per evaluator profile;
- first/final training loss: `1.20991` / `0.14258`;
- development teacher-forced loss: `0.15197`;
- peak allocated GPU fraction: `0.63054`;
- confirmation: `RESERVED_NOT_GENERATED`.

The schema repair therefore resolves the previous generation-plumbing
blocker. Exact hashes for the report, frozen inputs, and adapter are recorded
in `configs/phase3_retained_schema_gate_result_lock.json`.

## Diagnostics, not success claims

Among the 16 strictly parseable generations:

- mean physical field F1: `0.3625`;
- mean event-record field F1: `0.6947`;
- normative accuracy: `0.125`.

These numbers are deliberately not gate criteria. In particular, low
normative accuracy prevents any interpretation that the model has learned the
task merely because its JSON is valid.

## Decision

Do not rent a server and do not run the retained arm comparison yet. The next
stage is to implement and freeze the declared slot-level categorical JS and
continuous Huber consistency objective, with byte-identical joint-naive and
joint-consistency data/budgets. The historical gold-token proxy remains
ineligible for retained claims.
