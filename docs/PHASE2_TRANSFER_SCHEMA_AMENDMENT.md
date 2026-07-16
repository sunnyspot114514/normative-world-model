# Phase-2 transfer-schema amendment

Status: **frozen after retained Static v1 inspection and before any retained
model training**

## Problem

Both environments emit the same canonical institutional `event_record` but
different domain-native `physical_delta` fields. A-to-B and B-to-A therefore
cannot be interpreted cleanly if the destination output schema is neither
provided to the model nor respected by a Static comparator. Strict parsing of
the entire object turns a field-name mismatch into zero parse coverage for
every component.

## Frozen repair

Every joint and factorized-factual prompt receives the exact destination
`physical_delta` field names and primitive types. This metadata contains no
post-transition values, labels, event records, evaluator decisions, or reason
codes. The same schema applies to the one-step output and stored rollout
items.

For a cross-environment Static prediction, a source-native physical object is
replaced by a destination-schema-valid neutral object (integer fields `0`,
list fields `[]`). This deliberately grants no physical correctness. It only
prevents the parser from erasing the shared event and normative diagnostics.

## Estimands

- A-to-A and B-to-B retain full strict `joint_pair_success`.
- A-to-B and B-to-A bootstrap strict
  `event_normative_pair_success`: the predicted event record must be
  evaluator-invariant and exactly correct, and the evaluator decision pair
  must be correct.
- Cross-environment domain-native physical exactness and field F1 remain
  separately reported diagnostics and are not silently mapped into the shared
  ontology.

This amendment changes neither the Phase-1 corpus nor the confirmation
reservation. It was triggered by a structural parse-coverage failure, not by
retained model performance; no retained model had been trained or evaluated.
