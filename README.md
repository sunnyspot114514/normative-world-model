# Normative World Model: Leakage-Controlled Runtime Telemetry Experiments

[🇺🇸 English](README.md) | [🇨🇳 中文说明](README.zh-CN.md)

Normative World Model is an isolated research project for testing when normative predictions can serve as reliable runtime telemetry for agent actions.

It starts from a narrow, falsifiable question:

**Can a policy- and evaluator-conditioned language world model preserve factual transition predictions under evaluator-value interventions while changing normative judgments appropriately?**

This project does not attempt to train a universal human value system. Instead, it provides two symbolic environments, deterministic physical and normative oracles, paired counterfactual families, leakage audits, and preregistered gates for separating world prediction from evaluation.

## Current Status

- **The isolated project scaffold and P0 contracts are complete.**
- Two surface-distinct environments share one frozen normative predicate layer:
  - a narrative game state machine;
  - an organizational-agent simulator.
- Revision 2 is preserved as an internally rejected smoke artifact after full-corpus review found
  systematic natural-language grammar defects.
- V3 revision 0 was also archived after deterministic readable sampling found malformed action
  phrases missed by the machine gates.
- Preregistration-v3 revision 1 changes only controlled-language action rendering and its audits.
  Its smoke corpus contains 300 scenario families per environment and passes native,
  package-independent, deterministic readable-sample, and unconditional external review.
- The signed acceptance record binds the exact v3 smoke corpus, provenance manifest, and 29-file
  source lock. Phase-2 findings M1/M2 have been resolved with explicit parser tests.
- The formal retained discovery corpus now contains 1,000 families per environment and passes
  native plus package-independent replay. Retained Gate C passes independently in both
  environments:

| environment | maximum word/character macro AUC | 95% cluster upper bound | frozen gate |
|---|---:|---:|---|
| game | `0.4943` | `0.5093` | **PASS** |
| organization | `0.4892` | `0.5021` | **PASS** |

- The two v3 raw smoke JSONL files and confirmation reservation are byte-stable across same-seed
  reruns.
- External acceptance has unlocked retained discovery only. Confirmation remains
  `RESERVED_NOT_GENERATED`.
- Cheap Static baselines now emit complete factual and normative outputs and are scored on the same
  `joint_pair_success` estimand as model arms; their v3 smoke results remain exploratory.
- The Phase-2 parser, metric, and transfer harness passes an oracle-fixture check over all 14,400
  v3 smoke presentations. This validates the harness, not a learned model.
- The exact `Qwen/Qwen3-1.7B-Base` revision is cached locally with file hashes. A one-step,
  725-token joint LoRA optimizer smoke passes on the RTX 3060 at 66.7% peak allocated CUDA memory.
  A full-rollout target was separately retained as a failed resource diagnostic because it relied
  on WDDM oversubscription.
- The retained Phase-1 corpus has been generated locally. The confirmation corpus, trained
  adapters/checkpoints, and retained training runs have not been generated.
- The hash-locked Phase-2 retained-v2 baseline/export stage now passes over all 2,000 families.
  Its value-free destination schema repair restores cross-environment Static parse coverage to
  `1.0`; the superseded v1 cross-environment result remains preserved and invalidated.
- Generated data, models, caches, secret nonces, and experiment artifacts are intentionally ignored by Git.

## Motivation

An agent can fail before its final output is committed. A runtime governance system may need to reason across several stages:

1. Pre-transition world state
2. Candidate action and applicable policy
3. Predicted physical state transition
4. Synthetic institutional event record
5. Evaluator-conditioned normative judgment
6. Runtime allow, reject, or escalation decision

This repository studies whether world-model predictions can act as **runtime sensors** without allowing evaluator conditions to rewrite factual forecasts.

The central distinction is:

- `actor_values` are causal variables inside the world and may legitimately change the transition;
- `evaluator_values` define the assessment perspective and must not change the factual target.

## What This Repository Contains

```text
configs/
  calibration_cases.json          # End-to-end oracle reachability assertions
  evaluator_profiles.toml         # Four deterministic evaluator profiles
  normative_predicates.toml       # Shared A/B ontology and generator gates
  preregistration.toml            # Machine-readable thresholds and stop rules
  preregistration_v3.toml         # Renderer-reset seeds, locks, and inherited gates

docs/
  NORMATIVE_PREDICATE_CONTRACT.md  # Cross-environment predicate contract
  EVALUATOR_PROFILES.md            # Two-layer N oracle and exact semantics
  LEAKAGE_AUDIT_SPEC.md            # Per-environment generator-exit audits
  METRIC_COMPARATOR_V2_1.md        # Shared correctness/invariance comparator
  INTERNAL_REVIEW_PROTOCOL.md      # Temporary internal discovery-review boundary
  PHASE1_V3_INTERNAL_SMOKE.md      # Hash-bound v3 internal smoke record
  PHASE1_V3_REVISION0_INTERNAL_REVIEW.md # Archived readable-review failure
  EXTERNAL_SMOKE_ACCEPTANCE_V3.md  # V3 hash-bound retained-generation lock
  PHASE2_EVALUATION_CONTRACT.md     # Parser, metrics, anti-gaming, transfer
  MODEL_ARM_DATA_CONTRACT.md        # Joint/factorized data and visibility
  EXTERNAL_SMOKE_ACCEPTANCE.md     # Hash-bound retained-generation lock
  EXTERNAL_AUDIT_ADJUDICATION.md   # Accepted findings and corrected claims

src/normative_world_model/
  environments/game.py             # Narrative game dynamics and renderer
  environments/organization.py     # Organizational-agent dynamics and renderer
  policy_oracle.py                  # Non-waivable hard policy layer
  normative_oracle.py               # Profile-conditioned discretionary oracle
  generator.py                      # Paired-family and rollout generator
  audits.py                         # Density, leakage, integrity, and baseline gates
  comparators.py                    # v2.1 numeric comparison contract
  metrics.py                        # Paired factual/normative metrics
  baselines.py                      # Exploratory static baselines
  bootstrap.py                      # Scenario-family cluster bootstrap
  model_output.py                   # Strict model-output parser
  phase2_dataset.py                 # Paired structured/NL presentations
  phase2_metrics.py                 # Leakage, rollout, and anti-gaming metrics
  transfer_matrix.py                # A→A, B→B, A→B, B→A manifests
  model_arms.py                     # Joint/factorized deterministic records

scripts/
  setup.ps1                         # Project-local Python setup
  check.ps1                         # Unit tests and isolation audit
  check-phase1-smoke.ps1            # Smoke provenance verifier
  check-phase1-v3-smoke.ps1         # Native plus independent v3 verifier
  independent-smoke-audit.py        # Package-independent full-corpus recomputation
  select-internal-review-sample.py  # Deterministic readable-review selector
  run-phase2-baselines.py           # Exploratory smoke baseline runner
  run-phase2-internal-check.py      # End-to-end evaluation-harness check
  export-phase2-arm-data.py         # Compressed smoke datasets for model arms
  build-v3-external-audit-bundle.py # Self-contained compressed v3 review bundle
  build-smoke-audit-bundle.py       # Compact external-audit bundle builder

tests/
  test_*.py                         # Contract, oracle, audit, metric, and lock tests
```

Large or sensitive artifacts are intentionally absent. They can be regenerated locally under ignored project directories.

## Key Experiment

The main comparison holds the pre-transition state and candidate action fixed while changing the evaluator profile:

```text
T(source, actor_values) -> physical_delta, next_state, event_record
N(event_record, policy_result, evaluator_values) -> allow | reject | escalate
```

A successful joint model must satisfy both:

```text
factual prediction remains correct and invariant under evaluator intervention
normative prediction changes when the deterministic oracle says it should
```

The primary engineering comparison is:

| arm | factual model sees evaluator values? | leakage prevented by construction? |
|---|:---:|:---:|
| `joint_naive` | yes | no |
| `joint_consistency` | yes | no; trained with an anti-leakage objective |
| `factorized` | no | yes |
| Static envelope | task-dependent | baseline only |

The scientific question is whether a joint model can learn internal separation. The factorized arm answers the separate engineering question of whether modular architecture is sufficient for reliable invariance.

## Phase-1 Internal Smoke Result

The preregistration-v3 revision-1 smoke run uses 600 total scenario families and does not generate
confirmation examples. Revision 2 and v3 revision 0 remain archived as internally rejected rather
than being repaired in place.

Locally reproduced checks include:

- deterministic replay;
- scenario-family split integrity;
- exact physical-delta and `next_state` consistency;
- three-step rollout chaining;
- one-leaf factual, actor-value, and policy interventions;
- natural-language grammar and information-equivalence checks;
- per-field ordinal marker cardinality;
- affine and depth-three nontriviality baselines;
- per-environment word/character TF-IDF leakage gates;
- exact Decimal oracle-boundary tests;
- source, corpus, report, and bundle provenance hashes.
- a second full-corpus audit that imports no `normative_world_model` package code.
- a deterministic, coverage-augmented 36-row readable review.

The raw corpus remains local. Repository documents record the protocol and hashes, not the generated JSONL contents.

See:

- [Phase-1 v3 internal smoke record](docs/PHASE1_V3_INTERNAL_SMOKE.md)
- [Phase-1 v3 revision-0 internal rejection](docs/PHASE1_V3_REVISION0_INTERNAL_REVIEW.md)
- [Internal review protocol](docs/INTERNAL_REVIEW_PROTOCOL.md)
- [Phase-3 internal one-step pilot](docs/PHASE3_INTERNAL_PILOT.md)
- [Phase-1 v2 internal rejection](docs/PHASE1_V2_INTERNAL_REVIEW.md)
- [External audit adjudication](docs/EXTERNAL_AUDIT_ADJUDICATION.md)
- [V3 external smoke acceptance contract](docs/EXTERNAL_SMOKE_ACCEPTANCE_V3.md)
- [V3 retained execution contract](docs/PHASE1_V3_RETAINED_EXECUTION.md)
- [V3 retained discovery record](docs/PHASE1_V3_RETAINED_DISCOVERY.md)
- [Historical v2 external smoke acceptance contract](docs/EXTERNAL_SMOKE_ACCEPTANCE.md)

## Quick Start

This project currently targets Windows PowerShell and Python `>=3.12,<3.13`.

Clone and create the isolated environment:

```powershell
git clone https://github.com/sunnyspot114514/normative-world-model.git
cd normative-world-model
.\scripts\setup.ps1
. .\scripts\enter.ps1
```

Run the repository checks:

```powershell
.\scripts\check.ps1
```

Generate and independently check the local v3 smoke corpus:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe .\scripts\run-phase1-v3-smoke.py --families 300
.\scripts\check-phase1-v3-smoke.ps1
.\.venv\Scripts\python.exe .\scripts\run-phase2-baselines.py
```

Prepare the optional isolated local-model stack and run the one-step training smoke:

```powershell
.\scripts\setup-model.ps1
.\.venv\Scripts\python.exe .\scripts\prepare-local-model.py
.\.venv\Scripts\python.exe .\scripts\export-local-pilot-data.py
.\.venv\Scripts\python.exe .\scripts\audit-phase2-token-lengths.py `
  --data-dir .\data\generated\phase3_internal\arms `
  --report .\artifacts\phase3_internal\token_length_audit_one_step.json
.\.venv\Scripts\python.exe .\scripts\run-local-lora-smoke.py
.\.venv\Scripts\python.exe .\scripts\run-local-multirecord-pilot.py `
  --arms joint_naive joint_consistency `
  --optimizer-steps 32 `
  --max-train-items 32 `
  --generation-records 0
```

Generated content is written under:

```text
data/generated/
artifacts/
runs/
models/
.cache/
.tmp/
```

These paths are project-local and ignored by Git.

## Reproduction Level

The repository currently provides:

- Two independent deterministic environments
- A shared frozen normative predicate contract
- Four deterministic evaluator profiles
- Hard-policy and discretionary normative layers
- Factual, policy, actor-value, evaluator, and surface counterfactuals
- Three-step chained rollouts
- Exact-boundary oracle calibration
- Per-environment leakage and nontriviality gates
- A shared v2.1 numeric comparator
- Hash-bound external acceptance before retained generation
- A 2,000-family retained Phase-1 corpus with frozen provenance and independent replay
- A hash-locked 1.7B local base checkpoint and isolated CUDA/PEFT dependency stack
- Deterministic one-step model-arm exports and a no-truncation tokenizer audit
- Matched joint multi-record and factorized closed-loop exploratory plumbing
- Standard-library unit tests and Windows isolation scripts

It does **not** yet provide:

- A committed generated training or confirmation corpus
- Trained language-model checkpoints
- Retained or conclusive joint-versus-factorized model results
- Cross-environment model-transfer results
- Runtime intervention results
- Claims about universal values or general moral reasoning

## Experiment Stages

- [x] Isolated project scaffold
- [x] Shared A/B predicate contract
- [x] Actor/evaluator value separation
- [x] Deterministic policy and normative oracles
- [x] Uncertainty reachability analysis
- [x] Preserve revision-2 as an internally rejected smoke artifact
- [x] Preserve v3 revision 0 after readable review rejected malformed action phrases
- [x] Preregistration-v3 revision-1 renderer repair and paired-family generator
- [x] Natural-language and structured-input audits
- [x] Causal twin and rollout integrity gates
- [x] Per-environment Gate C
- [x] External full-corpus conditional audit
- [x] Resolve external-audit conditions
- [x] Independent internal full-corpus audit
- [x] Deterministic coverage-augmented readable review
- [x] Exploratory static baselines and cluster bootstrap
- [x] Strict output parser and oracle-fixture Phase-2 harness
- [x] Paired leakage, changed-field, rollout, anti-gaming, and transfer metrics
- [x] Deterministic self-contained v3 external-review bundle
- [x] Joint-naive, joint-consistency, and factorized smoke data interfaces
- [x] Exact local checkpoint/dependency lock, token audit, and one-step LoRA plumbing smoke
- [x] Matched joint multi-record and factorized closed-loop exploratory plumbing
- [x] Unconditional external acceptance of the exact v3 corpus hashes
- [x] Retained Phase-1 corpus
- [x] Frozen Phase-2 retained-v2 baseline table and model-arm exports
- [ ] Retained local small-model pilot
- [ ] Locked confirmation
- [ ] Optional server-scale study
- [ ] Proposal/commit Runtime evaluation

## Project Isolation

The repository is designed not to contaminate sibling projects:

- `.venv/` contains the only Python environment used by the project.
- `.cache/` contains package, Hugging Face, Torch, and tool caches.
- `.tmp/` contains process-local temporary files and the secret nonce.
- `data/`, `models/`, `runs/`, and `artifacts/` contain project-only inputs and outputs.
- `PYTHONNOUSERSITE=1` prevents packages from the Windows user site from leaking into the environment.
- Future external inputs must be imported as versioned, read-only snapshots with hash manifests.

## Research Contracts

- [Design note](DESIGN_NOTE.md)
- [Execution plan](EXECUTION_PLAN.md)
- [Preregistration](PREREGISTRATION.md)
- [Normative predicate contract](docs/NORMATIVE_PREDICATE_CONTRACT.md)
- [Evaluator profiles](docs/EVALUATOR_PROFILES.md)
- [Joint-consistency objective](docs/JOINT_CONSISTENCY_OBJECTIVE.md)
- [Leakage audit specification](docs/LEAKAGE_AUDIT_SPEC.md)
- [Metric comparator v2.1](docs/METRIC_COMPARATOR_V2_1.md)
- [Phase-2 evaluation contract](docs/PHASE2_EVALUATION_CONTRACT.md)
- [Model-arm data contract](docs/MODEL_ARM_DATA_CONTRACT.md)
- [Local small-model pilot contract](docs/LOCAL_PILOT_CONTRACT.md)

## License

This project is released under the Apache License 2.0. See [LICENSE](LICENSE) for details.
