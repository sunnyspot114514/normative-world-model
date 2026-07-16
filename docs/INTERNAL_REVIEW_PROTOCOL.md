# Internal discovery review protocol

Status: **active while external review is unavailable**

Internal review is a temporary discovery-phase substitute for finding defects. It is not an
external acceptance mechanism and cannot unlock retained generation or confirmation.

## Review paths

Every smoke candidate must pass three paths.

### Path A — native contract checks

Run the generator's density, split, state-machine, language, nontriviality, model-input, leakage,
calibration, deterministic-replay, and provenance checks.

### Path B — independent full-corpus recomputation

Run `scripts/independent-smoke-audit.py`. This script:

- imports no `normative_world_model` module;
- reads the stored JSONL bytes and TOML evaluator profiles directly;
- recomputes model-input hashes, intervention scope, rollout chaining, derived evidence fields,
  policy reasons, evaluator decisions, exact boundaries, and language grammar;
- emits an internal report whose governance section explicitly forbids retained authorization.

Agreement between Paths A and B is required but does not constitute external acceptance.

### Path C — deterministic human-readable inspection

Inspect a sample chosen only from scenario-ID hashes, augmented with:

- every exact score-boundary row;
- every actor-value twin whose physical result is unchanged;
- every grammar or equivalence warning;
- at least one example per environment, action family, split, hard-policy reason, evaluator reason,
  and uncertainty-disagreement mechanism.

The reviewer records row identifiers and findings. Rows are never selected by model performance.

## Allowed work after internal PASS

An internally passing smoke candidate may be used to:

- implement parsers, comparators, dataloaders, model arms, and training infrastructure;
- run cheap static and tabular discovery baselines;
- perform smoke-scale exploratory model runs;
- estimate runtime and storage requirements;
- prepare an external-review bundle.

All such outputs remain explicitly exploratory.

## Prohibited work before external acceptance

Internal review may not:

- create or imitate `EXTERNAL_AUDIT_ACCEPTED.json`;
- generate the 1,000-family-per-environment retained corpus;
- generate, reveal, replace, or inspect confirmation scenarios;
- tune frozen practical margins from observed model results;
- describe internal review as independent external validation.

The retained generator must remain technically unable to run without a hash-bound external
acceptance record.

