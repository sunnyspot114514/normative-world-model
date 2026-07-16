# Phase-1 v3 internal smoke record

Date: 2026-07-16

Status: **REVISION-1 THREE-PATH INTERNAL PASS; RETAINED GENERATION LOCKED**

Preregistration v3 is a renderer-only reset after revision 2 was internally rejected for systematic
natural-language grammar defects. V3 revision 0 was also archived after deterministic readable
sampling found malformed action phrases that the machine gates had missed. Revision 1 consumes the
first v3 repair slot and changes only controlled-language action presentation plus the corresponding
audits. It does not retroactively repair or relabel either rejected corpus. The current smoke run
contains 300 scenario families in each environment and generates no confirmation examples.

## Governance boundary

The revision-1 smoke candidate passed all three review paths defined in
`docs/INTERNAL_REVIEW_PROTOCOL.md`:

- the native generator and contract checks;
- `scripts/independent-smoke-audit.py`, which imports no project package and recomputes the stored
  rows from raw JSONL and evaluator-profile inputs.
- a 36-row deterministic human-readable sample selected from scenario-ID hashes, coverage buckets,
  exact boundaries, grammar warnings, and actor-twin exceptions.

This is an internal discovery result. It may support exploratory baselines and implementation work,
but it cannot create external acceptance, generate the retained corpus, or reveal confirmation
content.

## Fixed corpus hashes

- game JSONL:
  `afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768`
- organization JSONL:
  `ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92`
- confirmation reservation:
  `f26e5b70338e7a8ee45d5ec4329221de5cb4b199cab40dd547c3b9f4753c5d27`
- provenance manifest:
  `caa9beb6236663823b5126c94c318ca20e59aca2e99efa0c735b72f68f91e88a`
- deterministic readable-review sample:
  `56578482b19755b4342150aab8eea74fd2be16da70c149be304f35c4ab69cf89`

A same-seed rerun reproduced all three generated files byte for byte. Confirmation remains
`RESERVED_NOT_GENERATED`.

## Language and leakage checks

The expanded v3 language gates reported zero failures in both environments:

| check | game | organization |
|---|---:|---:|
| variable-article errors | 0 | 0 |
| count-agreement errors | 0 | 0 |
| subject-verb agreement errors | 0 | 0 |
| evaluator sentence-case errors | 0 | 0 |
| malformed action-phrase errors | 0 | 0 |
| structured/NL equivalence-marker omissions | 0 | 0 |
| ordinal marker-cardinality failures | 0 | 0 |

Gate C also passed separately in each environment:

| environment | maximum word/character macro AUC | 95% cluster upper bound | result |
|---|---:|---:|---|
| game | `0.4942` | `0.5220` | **PASS** |
| organization | `0.4818` | `0.5110` | **PASS** |

## Nontriviality checks

| environment | maximum affine impact R² | maximum depth-3 impact R² | depth-3 direct accuracy |
|---|---:|---:|---:|
| game | `0.6875` | `0.7117` | `0.5278` |
| organization | `0.7332` | `0.6552` | `0.5696` |

All values remain below the frozen `0.90` nontriviality ceilings.

## Exploratory Phase-2 baselines

The following smoke-scale development results are implementation diagnostics, not retained or
confirmation findings:

| environment | profile majority acc./balanced | structured depth-3 acc./balanced | word TF-IDF acc./balanced | char-4 TF-IDF acc./balanced |
|---|---:|---:|---:|---:|
| game | `.534 / .333` | `.528 / .468` | `.540 / .540` | `.546 / .549` |
| organization | `.576 / .333` | `.570 / .432` | `.509 / .502` | `.516 / .515` |

These decision-only accuracy values are retained as diagnostics. The repaired Phase-2 Static
envelope composes every decision baseline with an evaluator-blind factual predictor and is
recomputed from scenario-macro `joint_pair_success` inside every bootstrap replicate. On this smoke
corpus the complete exact-field Static envelope is `0.0` in both input conditions; that value is an
exploratory baseline result, not permission to weaken the frozen `0.05` practical margin.

The organization majority accuracy is visibly inflated by the reject-class prevalence, so later
reports must retain balanced accuracy and mechanism/profile strata rather than relying on aggregate
accuracy.

## Next authorized work

Until external review resumes:

1. keep the v3 JSONL and provenance manifest byte-frozen;
2. implement parsers, paired metrics, rollout metrics, anti-gaming diagnostics, transfer schemas,
   model-arm configuration, and smoke-scale training infrastructure;
3. keep all model outcomes explicitly exploratory;
4. prepare a compact external bundle bound to the hashes above;
5. do not generate retained or confirmation data.

The compact bundle is now available locally at
`artifacts/phase1_v3_smoke/external_audit_bundle_v3.zip`. It includes both complete JSONL files and
is approximately 1.8 MiB after deterministic compression. Its SHA-256 is
`b071c4e0b5271e835f2df2c7a87d2626a29ff34149d23e60eee6c561ae34ad66`.
