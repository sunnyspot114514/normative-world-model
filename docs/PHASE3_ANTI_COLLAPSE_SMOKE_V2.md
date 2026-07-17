# Phase 3 anti-collapse smoke v2

Status: frozen before execution on a new retained-discovery diagnostic set.

## Why v2 exists

The original 256-step smoke remains `BLOCKED`. Its saved model predicted
`reject` for every held-out record and, in a read-only post-hoc diagnostic,
also for every training presentation. It therefore did not separate the three
normative classes even in-sample. The original result, thresholds, adapter,
heads, row predictions, and execution commit remain independently locked.

V2 tests one narrow engineering hypothesis: two passes over 128 pairs were too
few for the newly initialized schema heads and LoRA path. It is not an attempt
to overwrite or reclassify v1.

## The single change

Only `optimization.smoke_optimizer_steps` changes, from 256 to 1024. The new
value is not selected from the failed held-out scores: 1024 was already frozen
as the formal joint-arm budget before v1 ran. It gives eight deterministic
passes over the same 128 ordered pairs.

The following remain byte- or value-identical:

- model checkpoint, tokenizer, LoRA configuration, initialization seed, and
  deterministic CUDA settings;
- all 128 training-pair identities and their order;
- prompt representation, slot inventory, supervised objective, lambda `0.0`,
  decoder, and strict parser;
- optimizer types, learning rates, clipping, and component weighting; and
- every anti-collapse threshold.

The runner must reproduce v1's first 32-step loss-window mean within `1e-8`.
Failure of that replay check blocks v2 because the claimed single-variable
comparison would not be valid.

## New diagnostic population

V1's 48 gate-deciding records are never reused. V2 allocates 48 new balanced
development records, one per environment x input-condition x decision x
profile bucket. Scenario families used by the 16-record schema gate, the 48
v1 smoke records, and the 96 already reserved formal-development records are
all excluded before hash ranking. Exact identities are represented by the
order digest in
`configs/phase3_anti_collapse_smoke_v2_selection_lock.json`.

## Decision rule

The v1 thresholds apply without modification. V2 passes only if every original
anti-collapse check and the deterministic prefix-replay check pass. A PASS may
unlock implementation and freezing of the formal one-step three-arm runner; it
does not itself establish a scientific claim. Any failure stops the formal
comparison and records the small-model path as an engineering null unless a
new, separately justified redesign is approved.

Confirmation remains `RESERVED_NOT_GENERATED`, H5 remains `UNIDENTIFIED`, and
server rental remains unauthorized.
