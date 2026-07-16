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
- The Phase-1 revision-2 smoke corpus contains 300 scenario families per environment and passes every local gate.
- Gate C now passes independently in both environments:

| environment | maximum word/character macro AUC | 95% cluster upper bound | frozen gate |
|---|---:|---:|---|
| game | `0.4743` | `0.5047` | **PASS** |
| organization | `0.5153` | `0.5699` | **PASS** |

- The two raw smoke JSONL files are byte-stable across same-seed reruns.
- External-audit conditions have been implemented. The refreshed provenance manifest awaits unconditional re-acceptance before retained generation can unlock.
- The full retained corpus, confirmation corpus, model weights, and training runs have not been generated.
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

docs/
  NORMATIVE_PREDICATE_CONTRACT.md  # Cross-environment predicate contract
  EVALUATOR_PROFILES.md            # Two-layer N oracle and exact semantics
  LEAKAGE_AUDIT_SPEC.md            # Per-environment generator-exit audits
  METRIC_COMPARATOR_V2_1.md        # Shared correctness/invariance comparator
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

scripts/
  setup.ps1                         # Project-local Python setup
  check.ps1                         # Unit tests and isolation audit
  check-phase1-smoke.ps1            # Smoke provenance verifier
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

## Phase-1 Smoke Result

The revision-2 smoke run uses 600 total scenario families and does not generate confirmation examples.

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

The raw corpus remains local. Repository documents record the protocol and hashes, not the generated JSONL contents.

See:

- [Phase-1 revision-2 smoke record](docs/PHASE1_REVISION2_SMOKE.md)
- [External audit adjudication](docs/EXTERNAL_AUDIT_ADJUDICATION.md)
- [External smoke acceptance contract](docs/EXTERNAL_SMOKE_ACCEPTANCE.md)

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

Generate the local revision-2 smoke corpus:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe -m normative_world_model phase1-smoke --families 300
.\.venv\Scripts\python.exe .\scripts\build-smoke-audit-bundle.py
.\scripts\check-phase1-smoke.ps1
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
- Standard-library unit tests and Windows isolation scripts

It does **not** yet provide:

- A committed generated training or confirmation corpus
- Trained language-model checkpoints
- Joint-versus-factorized model results
- Cross-environment model-transfer results
- Runtime intervention results
- Claims about universal values or general moral reasoning

## Experiment Stages

- [x] Isolated project scaffold
- [x] Shared A/B predicate contract
- [x] Actor/evaluator value separation
- [x] Deterministic policy and normative oracles
- [x] Uncertainty reachability analysis
- [x] Revision-2 paired-family generator
- [x] Natural-language and structured-input audits
- [x] Causal twin and rollout integrity gates
- [x] Per-environment Gate C
- [x] External full-corpus conditional audit
- [x] Resolve external-audit conditions
- [ ] Unconditional acceptance of refreshed provenance manifest
- [ ] Retained Phase-1 corpus
- [ ] Frozen Phase-2 baseline table
- [ ] Local small-model pilot
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

## License

This project is released under the Apache License 2.0. See [LICENSE](LICENSE) for details.
