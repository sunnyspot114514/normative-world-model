# Phase-2 retained-v2 result

Status: **PASS for retained discovery infrastructure; no learned-model claim**

The retained-v2 run used 2,000 Phase-1 families at frozen code commit
`b3010c91505a7fbadb8502a3166f49b4ec41f57c`. It produced 48,000 joint
presentations, 6,000 factorized-factual records, and 32,000
factorized-normative records. The exact result hashes are recorded in
`configs/phase2_retained_result_lock.json`.

## Gates

- provenance and independent hash verification: PASS;
- oracle fixture: 2,000 families / 48,000 presentations, PASS;
- transfer support manifest: READY;
- factorized factual evaluator-visibility failures: 0;
- A-to-B and B-to-A Static parse coverage: 1.0 in structured and natural
  language;
- confirmation: `RESERVED_NOT_GENERATED`;
- H5 rollout: `UNIDENTIFIED`.

Within-environment cells retain full strict `joint_pair_success`. The Static
envelope remains zero because no inexpensive baseline reconstructs every
physical and event field for both evaluator-pair members. This severe
conjunction was already disclosed on smoke data, so component metrics remain
mandatory diagnostics.

Cross-environment cells use strict shared
`event_normative_pair_success`. Their Static envelope is also zero under exact
event-record matching, but the result is no longer a parser artifact:
event-record field F1 is approximately 0.53--0.63 and normative pair accuracy
approximately 0.44--0.50 across the four direction/input cells.

## Interpretation

This stage freezes a valid retained discovery evaluation/data interface. It
does not authorize confirmation, does not identify H5, and does not establish
world-model capability. The superseded v1 files and their invalidation record
remain preserved.
