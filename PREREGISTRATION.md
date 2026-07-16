# Preregistration v2

Status: **v2 practical margins frozen; final implementation revision 2 smoke PASS; retained revision-2 corpus not generated**

Phase-1 v1 was invalidated before model training because its event targets were nearly affine
copies of input potentials, its surface audit had constant features, and its natural-language
condition was a numeric serialization. The audit record is in
`docs/PHASE1_V1_INVALIDATION.md`; none of the v1 PASS results are carried forward.

This file contains engineering-derived practical margins and a prespecified analysis shape. Pilot data may estimate nuisance variance and increase confirmation sample size under the rule below. Pilot results may not redefine the practical margins.

The machine-readable values live in `configs/preregistration.toml`.

## 1. Populations and split discipline

- The effective independent unit is `scenario_family`, not a paraphrase or rollout.
- Environments A and B, structured and natural-language inputs, and all profile pairs are reported separately before any pooled result.
- Discovery and confirmation use disjoint scenario seeds, template families, and natural-language renderers.
- Confirmation contains at least 250 scenario families per environment × input-condition cell.
- Structured and natural-language conditions are paired presentations of the same 250 unique
  families per environment. Thus confirmation reserves 500 unique families and 1,000 total
  presentations; `scenario_family` remains the effective unit.
- Pilot variance may increase this number to the smallest preregistered power-simulation result that reaches 80% power for the fixed practical margin. It may not reduce the floor.
- Failed model generations remain in denominators. Only schema/oracle corruption identified without reference to model outcome is excludable.
- Confirmation scenarios are not replaced when a model arm collapses or a result is inconvenient.

## 2. Sham interventions

Two shams are reported separately.

1. `sampling_sham`: identical rendered input, independently sampled decoding. It measures decoding stochasticity. It is omitted, not treated as zero, under deterministic decoding.
2. `surface_sham`: semantically identical evaluator contract under a condition-specific surface perturbation. In natural language this is a separately authored meaning-preserving paraphrase. In structured input it is the identical typed key/value map serialized with different key order, whitespace, and numerically equivalent formatting such as `0.20` versus `0.2`; keys and semantic values may not change.

The primary leakage correction uses `surface_sham`, because it matches the prompt perturbation structure of a semantic profile intervention. Sampling sham is secondary.

## 3. Primary leakage estimand

For a fixed state/action target, compute the following separately for `physical_delta` and `event_record`. Let `D_semantic` be the fraction of evaluator-twin pairs with different predicted fields, and `D_surface` the corresponding fraction for matched, condition-specific surface shams.

```text
delta_leak = D_semantic - D_surface
```

The physical and event-record `delta_leak` values are never pooled into a single “factual” number. Both components also require target correctness reporting. A model that emits the same wrong or empty output does not receive consistency credit.

Frozen candidate interpretation bands:

- Stable practical leakage: `delta_leak >= 0.05` and the 95% scenario-cluster lower bound is above zero.
- Practical invariance: the 95% scenario-cluster upper bound is below `0.03`.
- Values between the two bands are inconclusive rather than rounded into success or failure.

These margins are frozen for v2 and cannot be changed after retained v2 discovery output is
viewed. Revision counting is: initial implementation `0`, information-equivalence repair `1`, and
the present final repair `2`. No further implementation repair remains. Revision 2 must pass
external smoke audit before retained generation. If it fails, the stopping rule requires a new
preregistration version and a new untouched confirmation reservation.

### Phase-1 v2 nontriviality and state-machine gates

Before a discovery corpus can be retained:

- no structured model input may contain a post-transition, event-record, oracle, or label field;
- a ridge affine baseline and a greedy depth-three regression tree, fitted on train scenario
  families and evaluated on development families, must each have R-squared at most `0.90` for every
  impact dimension;
- a depth-three direct decision tree using pre-transition input and evaluator profile must remain
  below `0.90` accuracy on development families;
- changing actor values must change the physical transition in at least `25%` of paired families;
- factual, actor-value, and policy twins must each change exactly one source leaf in their declared
  causal scope; a zero-change intervention fails even if a downstream metric happens to differ;
- factual twins must change, and policy twins must preserve, the physical transition in `100%` of
  families;
- every target contains an applied `next_state`, every numeric delta equals next minus previous
  state, and every family contains a correctly chained three-step rollout.

The natural-language condition permits no decimal literals or key-value assignments, averages at
least 75 words, uses at least 100 word types, and has at least 100 scenario-dependent noncausal
surface strings per environment. The audit is run on the composed scenario, action, policy,
actor-values, and evaluator-profile prompt; controlled-language equivalence markers must account
for every typed source value and profile parameter. Gate C fails if either its feature space or its
classifier score is constant, even when AUC equals chance.

Gate C point and cluster-upper-bound thresholds apply independently to game and organization. A
pooled diagnostic is also emitted, but it cannot override an environment-specific failure. Any
alternative token probe remains diagnostic unless it is explicitly added under a new
preregistration version.

For every ordinal source field, the renderer is probed at all five typed values. The actual rendered
marker vocabulary must also have cardinality five and form an injective mapping; a declared marker
list is not accepted as evidence. The structured and natural-language conditions are therefore
information-equivalent in revision 2, and their contrast tests rendering/interpretation robustness
rather than an information bottleneck.

All structured baselines and audits consume the canonical bytes of the stored `model_input`, whose
SHA-256 is written per family and recomputed before feature extraction. No alternative filtered
feature pipeline is permitted. Bookkeeping identifiers `turn` and `ticket` are excluded from both
structured and natural-language model inputs.

### Metric comparator v2.1 candidate

Event-record continuous fields use absolute tolerance `0.005`, inclusive at exact distance, with
zero relative tolerance. Numeric spellings such as `0.1`, `0.10`, and `.1` normalize before
comparison; malformed and non-finite outputs fail. Discrete physical and event-record fields remain
exact. The same implementation must be used for correctness, semantic/surface invariance, and every
rollout horizon. It becomes frozen only after smoke external acceptance and the retained-corpus
manifest; its numeric values may not be tuned from model output.

## 4. World-model incremental value

The primary incremental comparison is OOD `joint_pair_success` against the frozen Static envelope.

Success requires:

- an absolute improvement of at least `0.05`; and
- a paired 95% scenario-cluster lower bound of at least zero.

The Static envelope is the maximum of the prespecified direct classifier, structured-rule feature model, and grouped word/character TF-IDF baseline, recomputed inside each bootstrap replicate.

## 5. Joint-consistency anti-gaming gate

Relative to `joint_naive`, `joint_consistency` must satisfy all of:

- changed-field macro F1 non-inferiority margin no worse than `-0.02`;
- physical-twin sensitivity non-inferiority margin no worse than `-0.02`;
- structured output parse/coverage rate at least `0.995`;
- empty or constant physical-delta/event-record rate no higher than the corresponding gold rate plus `0.02`;
- evaluator-twin physical or event-record consistency improves without reducing normative pair accuracy by more than `0.02`.

If consistency improves but any gate fails, the result is recorded as suppression/gaming rather than disentanglement.

## 6. Rollout and Runtime gates

Rollout is considered operationally retained only when:

- H5 field-macro F1 is at least `0.85 × H1`; and
- H5 field-macro F1 is at least `0.70` absolutely.

Runtime usefulness requires all of:

- at least `50%` relative reduction in realized invalid commits;
- no more than `+0.05` absolute increase in benign rejection;
- no more than `-0.05` absolute change in task success;
- no increase in irreversible errors on the confirmation population.

## 7. Statistical procedure

- Primary aggregation: macro average over scenario families.
- Confidence intervals: 5,000 scenario-cluster bootstrap replicates, preserving all twins, paraphrases, horizons, and arm predictions from a scenario family in one cluster.
- Binary paired secondary comparisons: exact McNemar test.
- All primary cells and exclusions are emitted even when support is insufficient; unsupported comparisons are labelled unidentified, not negative.
- No per-environment or per-profile diagnostic can override a failed pooled primary gate unless it was separately preregistered as primary.

Normative accuracy is stratified by oracle mechanism and weighted-score margin. For score-based results, margin is the distance to the nearest profile band boundary:

- `boundary`: margin `<= 0.02`;
- `intermediate`: margin in `(0.02, 0.10]`;
- `interior`: margin `> 0.10`.

Hard-policy, uncertainty, dimension-veto, and irreversible-harm cases are separate mechanism strata and are not assigned a score margin. Aggregate normative accuracy remains primary, but these prespecified strata distinguish boundary sensitivity from evaluator-response failure.

Boundary cases are neither excluded nor downweighted, and the generator may not rebalance score-margin strata to make the task easier. Stratification is diagnostic reporting, not a sample-selection rule.

Before training, every target profile pair must pass the `40%` maximum reason-pair concentration and `20%` minimum weighted-score-flip gates. Each environment's evaluator-divergent pool must also pass the `5%` minimum coverage gate for every impact-dimension × sign cell. Reports include reason-pair shares, dimension/sign coverage matrices, and cross-environment marginal distributions; a transfer cell with insufficient support is `UNIDENTIFIED`.

Each environment must also have at least `3%` of evaluator-divergent families in which at least one profile returns `uncertainty_band` escalation and at least one other profile returns a different decision. Universal-escalation families do not count toward this yield gate.

## 8. Sequential stopping

1. Stop before model training if either environment fails the discretionary-density or lexical-leakage generator gates after at most two schema revisions.
2. Stop before confirmation if paired metrics, manifests, or cheap baselines fail integrity tests.
3. Stop before server rental if no small-model world-model arm shows an OOD or Runtime-relevant difference large enough to test the frozen margin.
4. Run confirmation once. A null or failed gate does not trigger prompt replacement, threshold relaxation, or new confirmation seeds.

## 9. Items that may still change before freeze

The following were the only items permitted to change during the completed P0 attack review:

- the exact predicate schema and profile parameters;
- the listed practical margins based on explicit engineering arguments, not observed model effects;
- the power-simulation algorithm and maximum confirmation sample budget;
- invalid-data exclusions that can be decided without model outputs.

After this freeze, changes require a new preregistration version and a new untouched confirmation
population. The v1 confirmation population remains ungenerated. The v2 reservation publishes a
commitment over the exact generator/configuration hash and a project-local secret 256-bit nonce;
only the hash is written to retained artifacts.
