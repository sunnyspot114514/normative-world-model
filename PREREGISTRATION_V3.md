# Preregistration v3 — renderer correction reset

Status: **frozen before v3 smoke generation; internal review only; external acceptance still
required before retained generation**

Preregistration v3 is a narrow reset after the revision-2 internal review found systematic
count-noun, subject-verb, and evaluator-paraphrase grammar defects. Revision 2 remains archived and
is not repaired in place. V3 revision 0 was subsequently archived after deterministic human-readable
review found malformed controlled-language action phrases; revision 1 consumes the first v3 repair
slot without changing the scientific population or thresholds.

## 1. Scientific inheritance

The following v2 components remain unchanged:

- the actor/evaluator value separation and scientific claim boundary;
- environments A and B and their typed pre-transition schema;
- physical transition functions and synthetic event-record definitions;
- policy and normative oracle semantics and evaluator profiles;
- target profile pairs, density gates, Gate C thresholds, split discipline, and nontriviality
  ceilings;
- leakage, incremental-value, anti-gaming, rollout, runtime, comparator, and stopping margins.

The machine-readable copies are frozen in `configs/preregistration_v3.toml`. No practical margin
may be tuned from v2 or v3 smoke/model outcomes.

## 2. Reset boundary

The v3 implementation starts at generator revision 0 under the unchanged typed schema `0.4`.
Revision 1 remains renderer-only. Across the two revisions, allowed changes are limited to:

- count-aware rendering of `clue`, `record`, and `stakeholder`;
- singular subject-verb agreement for the one-stakeholder organization sentence;
- lowercase continuation after the introductory evaluator-profile clause;
- grammatical presentation of action-family identifiers without changing those identifiers or
  their source fields;
- grammar gates that directly test these rules;
- independent audit and internal-review tooling.

Changes to dynamics, impact formulas, policies, profiles, oracle thresholds, labels, split
semantics, or model inputs require a broader preregistration reset.

## 3. New populations and commitments

- Discovery seed: `20260716`.
- Confirmation seed: `20260816`.
- Bootstrap seed: `20260916`.
- A new 256-bit secret nonce is stored only in `.tmp/confirmation_v3_secret.json`.
- Confirmation remains `RESERVED_NOT_GENERATED`.
- The v2 confirmation commitment and population are never reused.
- The commitment input manifest uses an explicit Phase-1 generator/oracle/audit allowlist.
  Unrelated Phase-2 analysis code cannot silently change the Phase-1 population commitment.

## 4. Expanded language gates

In addition to every v2 language gate, each environment must have:

- zero count-noun disagreement for rendered evidence and stakeholder counts;
- zero singular/plural subject-verb disagreement;
- zero evaluator-profile sentence-case join errors;
- zero malformed action-phrase patterns from v3 revision 0;
- zero variable-article errors;
- complete structured-to-language equivalence markers after singularization;
- five distinct rendered markers for every five-level ordinal source field.

These are generator-exit gates, not optional diagnostics.

## 5. Internal-review rule

While external review is unavailable, a v3 smoke candidate must pass both the native audit and
`scripts/independent-smoke-audit.py`. Internal PASS authorizes exploratory infrastructure and
smoke-scale baselines only. It does not authorize retained generation.

The exact v3 smoke manifest and both raw corpus hashes must later receive external, unconditional,
hash-bound acceptance. If that review finds another blocking generator defect, v3 uses its normal
revision budget; thresholds remain fixed.

## 6. Immediate sequence

1. Archive the rejected v3 revision-0 smoke corpus and deterministic review sample.
2. Generate 300 families per environment under v3 revision 1.
3. Repeat the same-seed generation and require byte-identical corpora.
4. Run native, independent, and deterministic-sample review.
5. Build Phase-2 infrastructure against the internally passing smoke data.
6. Wait for external acceptance before any retained or confirmation generation.
