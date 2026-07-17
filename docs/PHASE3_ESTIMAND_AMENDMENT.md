# Phase-3 executable estimand amendment

Status: **frozen before any retained scientific model comparison**

The historical preregistration used the shorthand `ood_joint_pair_success`. Retained Phase-2 v1
then established that the two environments have intentionally different domain-native
`physical_delta` schemas. Requiring exact target-domain physical fields in a cross-environment
cell would make schema identity, rather than transfer of the shared event ontology, the primary
estimand.

This amendment makes the already documented Phase-2 repair executable:

| cell | primary estimand |
|---|---|
| A→A | `joint_pair_success` |
| A→B | `event_normative_pair_success` |
| B→B | `joint_pair_success` |
| B→A | `event_normative_pair_success` |

Cross-environment physical-delta correctness and field F1 remain mandatory separate diagnostics.
They are not mapped into a fabricated shared physical ontology and cannot override a failed shared
event-plus-normative primary gate.

The machine contract is `configs/phase3_estimand_amendment.json`. It binds the historical
preregistration, retained Phase-2 amendment, retained transfer config, and unopened confirmation
reservation by SHA-256. No practical effect margin, scenario population, generator, oracle, or
confirmation seed changes. The amendment was triggered by a Static schema-conformance failure and
was frozen before any retained scientific model output existed. The earlier files remain unchanged
and the amendment is disclosed rather than represented as part of the original preregistration.
