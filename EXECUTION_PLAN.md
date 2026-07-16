# Execution plan

## Operating principles

- The data/evaluation harness is the first dependency; compute scale cannot rescue a confounded benchmark.
- Every phase has an exit criterion. Later, more expensive phases do not begin because an earlier result merely looks interesting.
- Pilot and confirmation artifacts are kept separate.
- The project never writes to sibling repositories. External sources, if later approved, are imported as immutable snapshots with hashes and provenance.
- Contract work is time-boxed. Only the predicate contract and evaluator profiles receive a full design-and-attack pass before coding; other specifications begin as implementation-constraining skeletons.

## Phase 0 — isolated scaffold

Status: **complete**

Deliverables:

- Standalone Git repository.
- Python 3.12 environment in `.venv/`.
- Project-local caches, temporary directories, data paths, model paths, and run paths.
- Isolation audit and standard-library unit tests.
- Design note and initial experiment contract.

Exit criterion: `scripts/check.ps1` passes and reports every configured writable path inside the project root.

## Phase 0.5 — P0 contract lock

Status: **complete; replacement schema v0.4 frozen before v2 discovery generation**

Time box: two working days plus one focused attack review.

Deliverables:

- Manual claim and ambiguity review of `DESIGN_NOTE.md`.
- Shared predicate contract mapping game A and organization B.
- Four machine-readable evaluator profiles and deterministic N oracle.
- Hand-checkable label-flip calibration cases.
- Skeleton preregistration, consistency objective, and leakage audit.

Exit criterion: the predicate/profile attack review finds no unresolved causal ambiguity or trivial profile exploit; any accepted change lands before discovery generation and increments the relevant schema version.

## Phase 1 — simulator and dataset generator

Status: **revision 2 and v3 revision 0 internally rejected; preregistration-v3 revision-1 smoke
passed all three internal review paths; external acceptance still required before retained
generation**

Estimated effort: 2–4 working days.

Tasks:

1. Implement independent game and organizational state machines with irreversible flags, permissions, resources, actor attributes, and stakeholder effects.
2. Implement transition and policy oracles independently from natural-language rendering and from the evaluator oracle.
3. Generate evaluator, factual, policy, surface, and composition twins.
4. Assign `scenario_id` before paraphrasing and create train/development/confirmation manifests.
5. Add leakage audits for label words, duplicated templates, and cross-split semantic identity.

Deliverables:

- Versioned schema and generator.
- At least 1,000 scenario families per environment for discovery/smoke auditing.
- Dataset card, provenance manifest, and split audit report.

The invalidated v1 and v2 corpora and source snapshots remain archived. Revision 2 is preserved
unchanged after internal review found systematic natural-language grammar defects. Preregistration
v3 resets only the renderer and grammar gates. Revision 0 was additionally archived after
deterministic readable sampling found malformed action phrases missed by machine gates. Revision 1
consumes the first v3 repair slot and changes only action-identifier presentation plus its audits.
Its current smoke artifacts use `data/generated/phase1_v3_smoke/` and
`artifacts/phase1_v3_smoke/`; revision-0 artifacts use the corresponding
`phase1_v3_revision0_smoke/` paths, and historical revision-2 artifacts remain under their original
paths. The v3 retained paths remain absent until the exact raw corpus hashes and provenance manifest
receive unconditional external acceptance. Confirmation remains ungenerated; only a new salted
commitment and paired-presentation contract are reserved.

Exit criterion: deterministic replay produces identical targets; no `scenario_id` or paraphrase
family crosses splits; both environments pass the discretionary-density contract; direct-token,
conditional-association, grouped TF-IDF, affine/depth-three nontriviality, natural-language
richness, actor-intervention, next-state, and three-step rollout gates pass. A chance AUC with
constant features is an explicit failure. V3 allows at most two generator revisions before stopping
for redesign. Internal review cannot satisfy the external-acceptance exit condition.

## Phase 2 — metrics and cheap baselines

Status: **evaluation harness complete on v3 smoke; retained baseline/result freeze waits for
external acceptance**

Estimated effort: 1–2 working days.

Tasks:

1. Implement separate physical-delta, event-record, pair, rollout, runtime, and compute metrics.
2. Run majority, structured-rule, and grouped word/character TF-IDF decision baselines, each
   composed with an evaluator-blind static factual predictor and scored on the same
   `joint_pair_success` estimand as model arms. Decision-only accuracy remains diagnostic.
3. Freeze scenario-level aggregation and paired bootstrap procedures.

Implemented internal infrastructure now includes a strict JSON parser, paired structured/NL
presentation builder, correctness-aware leakage correction, changed-field and information
anti-gaming diagnostics, rollout scoring, mechanism/margin strata, shared scenario-cluster
bootstrap, and all eight A/B transfer cells. The oracle-fixture self-check covers 14,400 smoke
presentations. It is an integrity result, not evidence about a trained model.

Deliverables:

- Baseline table with confidence intervals.
- Metric contract and exclusions.
- Draft preregistration for pilot success/failure gates.

Exit criterion: pair metrics distinguish “physical/event records invariant but judgment unresponsive” from “judgment responsive but transition/event record distorted”; no headline result is reducible to a class-imbalance or template baseline.

## Phase 3 — local small-model pilot

Status: **exact 1.7B checkpoint, dependency lock, one-step exports, token audit, matched joint
multi-record plumbing, and factorized closed-loop plumbing complete on exploratory smoke; retained
pilot waits for external Phase-1 acceptance**

Estimated effort: 2–5 working days after the harness is stable.

Tasks:

1. Select one locally supportable roughly 2B model and record the exact checkpoint, tokenizer, quantization, and dependency lock.
2. Run `joint_naive`, `joint_consistency`, and `factorized` with matched scenario and token budgets.
3. Evaluate one-step behavior first; add three-step rollouts only after one-step gates pass.
4. Use development data only to estimate nuisance variance and, under the preregistered power rule, increase confirmation sample size. Practical effect margins are already frozen and may not be tuned from pilot effects.

Deliverables:

- Reproducible pilot configs and seed manifests.
- Leakage/accuracy/cost trade-off report.
- Go/no-go recommendation for server experiments.

Exit criterion: at least one non-static arm demonstrates a measurable OOD or runtime-relevant difference; otherwise stop or redesign before renting compute.

## Phase 4 — locked confirmation

Estimated effort: 1–2 working days.

Tasks:

1. Freeze code, model configs, exclusions, and random seeds.
2. Open the confirmation manifest once.
3. Report scenario-macro metrics and paired confidence intervals without post-hoc threshold tuning.

Exit criterion: results either clear the preregistered practical threshold or are recorded as a null result. Confirmation data does not return to the development loop.

## Phase 5 — short server scale study

Estimated compute: begin with an inference-only rental; authorize training only after reviewing that result.

Questions:

1. Does normative leakage diminish with model scale?
2. Does native world-model initialization help beyond the corresponding base model?

Initial comparison candidates:

- `Qwen/Qwen-AgentWorld-35B-A3B`.
- Its corresponding `Qwen3.5-35B-A3B-Base` checkpoint, after live availability verification.

Sequence:

1. Run zero-/few-shot inference on the already locked paired test harness.
2. Compare factual fidelity, paired invariance, normative responsiveness, latency, and cost.
3. Only if the result changes the scientific picture, run matched LoRA/QLoRA versions of `joint_naive`, `joint_consistency`, and `factorized`.

Isolation on the server:

- Use an ephemeral instance or dedicated volume containing only this repository snapshot.
- Set all cache/data/run variables to directories under the remote project root.
- Upload no sibling-project files and no local `.env`.
- Pull secrets from the provider's secret store into process environment only.
- Download results as a manifest plus checksums; destroy the instance after verification.

Exit criterion: determine whether the observed mechanism is scale-dependent and whether AgentWorld initialization provides an advantage under matched data and training budgets.

## Phase 6 — proposal/commit runtime evaluation

Estimated effort: 3–5 working days.

Tasks:

1. Make an execution agent emit structured candidate proposals.
2. Bind actual execution parameters to the reviewed proposal.
3. Compare no guard, static guard, joint telemetry, factorized telemetry, and oracle transition arms.
4. Evaluate action sequences that decompose one risky plan into apparently benign steps.

Exit criterion: safety improvements are accompanied by bounded benign rejection and task-success costs; reported effects survive multi-step and policy-revision tests.

## Phase 7 — optional extensions

These are not part of the minimum paper:

- Human multi-annotator rubrics and disagreement distributions.
- Probabilistic stakeholder-impact forecasting and calibration.
- Internal probes as appendix sanity checks.
- Selective causal interventions after behavioral evidence exists.
- CPT or RL only when SFT results identify a specific remaining limitation.

## Immediate next actions

1. Keep the exact v3 smoke corpora and manifest byte-frozen while external review is unavailable.
2. Preserve the completed, self-contained v3 external-review bundle and request unconditional
   acceptance of its exact corpus and manifest hashes when the reviewer returns.
3. Replace the local gold-token consistency proxy/free-generation bottleneck with a schema-native
   slot objective or strict constrained decoding, then rerun a target-token-matched exploratory
   joint/factorized comparison.
4. If and only if external acceptance passes, generate the full
   1,000-family-per-environment retained corpus without changing schema, generator, oracle, gates,
   or seed.
5. Verify retained provenance, then freeze comparator v2.1 and the retained baseline table before a
   local small-model pilot.
6. If v3 external review finds another blocking generator defect, use the preregistered v3 revision
   budget or stop for a new preregistration; never bypass the retained lock.
