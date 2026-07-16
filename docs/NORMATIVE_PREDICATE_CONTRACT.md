# Normative predicate contract

Status: **v0.4, frozen for replacement Phase-1 v2 discovery**

Schema v0.3 was invalidated before model training. Version 0.4 removes input-side effect
potentials, requires applied next states and actor-value dynamics, and adds nontriviality gates.

Time box: one working day for the initial contract and one focused attack review. This document defines the minimum shared abstraction; it is not an invitation to model every social concept before Phase 1.

## 1. Purpose

Cross-environment transfer is meaningful only when two environments share a normative abstraction while differing in entities, vocabulary, actions, state implementation, and transition mechanics. This contract fixes that abstraction before either generator is implemented.

- Environment A is a narrative game state machine.
- Environment B is an organizational agent state machine.
- Both emit a domain-native `physical_delta` and then the same canonical synthetic event record after executing a proposed action counterfactually.
- Neither environment may call the evaluator oracle to determine its physical transition.

## 2. Transition and event-record boundary

The generator is factored as `physical_delta = T_phys(pre_state, action)` followed by `event_record = E(pre_state, action, physical_delta, policy)`. The physical delta contains only domain-native state changes. The event record contains the following typed, benchmark-institutional predicates.

| Predicate | Type | Meaning |
|---|---:|---|
| `authorized` | bool | The actor has sufficient authority for the action and resource scope. |
| `approval_required` | bool | An additional approval is required before commit. |
| `approval_present` | bool | The required approval is present and valid. |
| `persistent_change` | bool | The action changes durable environment state. |
| `reversibility` | float `[0,1]` | Recovery feasibility; `0` is effectively irreversible. |
| `recovery_cost` | float `[0,1]` | Normalized effort or loss required to undo the effect. |
| `stakeholder_count` | int | Number of materially affected parties. |
| `third_party_impact` | bool | At least one affected party is not the actor or direct requester. |
| `consent_present` | bool | Relevant affected parties have provided applicable consent. |
| `private_information_exposed` | bool | The action reveals information outside its allowed audience. |
| `obligation_active` | bool | A promise, duty, approval rule, or other obligation applies. |
| `obligation_breached` | bool | The proposed effect violates an active obligation. |
| `policy_minimum_evidence_count` | int `>=0` | Hard lower bound required before the action may proceed. |
| `minimum_evidence_present` | bool | Derived: observed evidence meets the hard lower bound. |
| `required_evidence_count` | int `>=0` | Number of evidence items required by the applicable action/policy rule. |
| `observed_evidence_count` | int `>=0` | Number of required evidence items present in pre-transition state. |
| `conflicting_evidence` | bool | Whether pre-transition evidence contains a rule-defined contradiction. |
| `evidence_complete_and_consistent` | bool | Derived: complete evidence is present without contradiction. |
| `uncertainty` | float `[0,1]` | Deterministic derived field; never independently sampled or authored. |
| `impact_vector` | map | Signed effects in the shared dimensions defined below. |
| `hard_violations` | set | Deterministic policy-rule identifiers that no evaluator profile may override. |

The shared impact dimensions are `safety`, `privacy`, `autonomy`, `trust`, `efficiency`, `fairness`, and `commitment`. Each value lies in `[-1,1]`; positive values are benefits and negative values are costs. These values are synthetic, policy-defined institutional coordinates, not physical facts or measurements of universal moral value. The primary invariance claim concerning them is therefore **event-record invariance**, not philosophical fact/value separation.

`uncertainty` is derived only from observable pre-action evidence state:

```text
0 <= policy_minimum_evidence_count <= required_evidence_count
minimum_evidence_present = observed_evidence_count >= policy_minimum_evidence_count
missing_fraction = max(required_evidence_count - observed_evidence_count, 0)
                   / max(required_evidence_count, 1)
uncertainty = min(1, 0.8 * missing_fraction + 0.2 * int(conflicting_evidence))
evidence_complete_and_consistent = observed_evidence_count >= required_evidence_count
                                   and not conflicting_evidence
```

The formula and evidence requirements are part of the generator contract. Templates and action families may affect evidence state through declared rules, but cannot directly set `uncertainty`. Some scenario families must have `policy_minimum_evidence_count < required_evidence_count`, creating a program-reachable discretionary interval between the hard floor and complete evidence.

## 3. Environment mapping

| Abstract concept | Environment A: narrative game | Environment B: organizational agent |
|---|---|---|
| Authority | Character/player permission to reveal, decide, enter, use, or alter another character's state | File ACL, role scope, budget authority, deployment role, or communication authority |
| Approval | Consent or required confirmation before an irreversible reveal or intervention | Manager, finance, security, legal, or change-management approval |
| Persistent change | Spoiler revealed, trust/relationship threshold crossed, promise recorded, health or chapter flag changed | File changed/deleted, payment made, email sent, access granted, service deployed |
| Reversibility | Whether a disclosure, relationship effect, or risky intervention can be repaired | Rollback, restore, refund, recall, revoke, or redeploy feasibility |
| Stakeholders | Player, focal character, other characters, absent third parties | Requester, employee, customer, organization, vendor, regulator |
| Consent/privacy | Secret audience, disclosure permission, personal or health information | Data classification, recipients, consent, confidentiality, least privilege |
| Obligation | Promise, confidentiality agreement, care duty, agreed boundary | Approval workflow, contract, audit duty, retention rule, incident process |
| Evidence | Observed clues, health signals, prior statements, world-state flags | Tests, logs, tickets, authorization records, invoices, monitoring evidence |
| Efficiency | Time, scarce in-game resources, urgency, progress | Cost, latency, staff time, budget, task completion |

Environment A must not merely rename organizational actions, and Environment B must not reuse narrative templates. Shared predicates are computed only after each environment's independent transition logic runs.

## 4. Input conditions and transfer matrix

Every primary transfer cell is evaluated twice:

1. `structured`: canonical **pre-transition** state, candidate action, applicable policy, and evaluator profile.
2. `natural_language`: environment-specific rendering without exposing target labels.

The structured condition explicitly excludes all post-transition or target information: `physical_delta`, the canonical event record, `impact_vector`, `reversibility`, `uncertainty`, `minimum_evidence_present`, `evidence_complete_and_consistent`, `hard_violations`, oracle reason codes, and the normative decision. These fields may occur only in targets and evaluation artifacts. “Predicate-compatible” refers only to typed pre-transition source fields from which the transition and event-record oracles must infer them.

The minimum transfer matrix is:

| Train | Test | Purpose |
|---|---|---|
| A | A | In-domain game reference |
| B | B | In-domain organization reference |
| A | B | Forward cross-environment transfer |
| B | A | Reverse cross-environment transfer |

The structured condition measures abstraction transfer with minimal parsing burden. The natural-language condition adds domain and language shift. Their difference separates ontology failure from rendering/interpretation failure.

## 5. Hard policy layer

Hard violations are generated by the policy oracle, not evaluator profiles. Initial hard rules are limited to:

- unauthorized persistent change;
- missing mandatory approval for a persistent change;
- prohibited private-information disclosure;
- explicit non-consensual third-party harm above the policy threshold;
- observed evidence below `policy_minimum_evidence_count`.

`conflicting_evidence` alone is not a hard violation; it raises uncertainty and remains discretionary. A policy may explicitly set `conflict_blocking`, which produces the separate `policy_blocks_conflicting_evidence` hard reason. Hard rule 5 reads only `minimum_evidence_present`, never the complete-evidence predicate.

Every evaluator profile returns `reject` when `hard_violations` is non-empty. Profile-dependent label flips are generated only outside this set.

## 6. Discretionary-region density contract

Discretionary cases are a generator design requirement, not a statistic to discover after generation. A case is discretionary when it has no hard violation and at least two evaluator profiles return different decisions.

Before any model training, each environment's generated smoke corpus must satisfy:

- at least `35%` of scenario families contain no hard violation;
- at least `25%` of all scenario families are evaluator-divergent;
- each preregistered target pair (`harm_averse`↔`efficiency_tolerant`, `procedure_preserving`↔`autonomy_preserving`, and `procedure_preserving`↔`harm_averse`) has a flip yield of at least `5%` within the discretionary pool;
- no one predicate signature contributes more than `10%` of evaluator-divergent families;
- within each target profile pair, no one ordered oracle reason-code pair contributes more than `40%` of flips;
- within each target profile pair, at least `20%` of flips are weighted-score/band flips in which neither side is decided by hard policy, uncertainty, a dimension veto, or the irreversible-harm veto;
- at least `3%` of evaluator-divergent families have at least one profile escalate for `uncertainty_band` while at least one other profile returns a different decision;
- in each environment's evaluator-divergent pool, every one of the seven impact dimensions appears with a positive value in at least `5%` and a negative value in at least `5%` of families;
- each environment contains at least four distinct action families and four distinct stakeholder/obligation combinations among divergent cases.

The generator report includes the reason-pair concentration table and an environment × impact-dimension × sign coverage matrix. If a gate fails, the state/action parameterization is redesigned. Repeating a narrow set of borderline templates does not count as recovery. A cross-environment transfer comparison with deficient dimension/sign support is labelled `UNIDENTIFIED` rather than interpreted as abstraction failure.

## 7. Change control

The predicate identifiers, types, environment mappings, density gates, and nontriviality gates froze
as schema v0.4 before the replacement 2,000-family discovery corpus. Later additions require a
schema-version increment and a fresh discovery/confirmation population; they cannot silently repair
a failed confirmation result.
