# Phase-1 v2 internal review record

Date: 2026-07-16

Status: **INTERNALLY REJECTED BEFORE RETAINED GENERATION**

The external reviewer is temporarily unavailable. A stricter internal review was therefore run
without changing or bypassing the external-acceptance lock. The review used both the native
generator audits and a separately implemented standard-library audit that imports no project
package code.

## What remained valid

The independent audit reproduced the following results across all 600 revision-2 smoke families:

- both raw corpus hashes and the provenance-manifest hash;
- canonical model-input hashes and exclusion of `turn` and `ticket`;
- one-leaf factual, actor-value, and policy interventions;
- factual physical sensitivity and policy physical invariance;
- primary/H1 equality and three-step rollout chaining;
- numeric delta versus applied next-state consistency;
- derived uncertainty, minimum-evidence, and complete-evidence fields;
- hard-policy reasons and all four evaluator decisions under Decimal boundary semantics.

No retained or confirmation corpus was generated.

## Blocking language finding

The natural-language grammar gate was too narrow. It checked variable `a/an` templates but did not
check number agreement, subject-verb agreement, or sentence-case joins in evaluator paraphrases.
The stored revision-2 corpus therefore contains systematic surface defects:

| Environment/surface | Affected families | Affected scenario surfaces | Examples |
|---|---:|---:|---|
| game | 86 / 300 | 172 / 600 | `one clues`, `one stakeholders` |
| organization | 64 / 300 | 128 / 600 | `one records`, `one stakeholders are` |
| evaluator profile shams | 600 / 600 | 2,400 shams | `For the ... evaluator, The uncertainty ...` |

These defects do not change structured inputs, physical transitions, event records, oracle labels,
or Gate C's noncausal surface features. They do invalidate the repository's broader claim that the
natural-language condition passed grammar review and would confound a language-versus-structured
comparison.

## Governance decision

Revision 2 is preserved unchanged as an invalidated smoke artifact. It is not retrospectively
relabelled as successful, and no `EXTERNAL_AUDIT_ACCEPTED.json` is created. The next attempt uses
preregistration v3 with:

- unchanged scientific hypotheses, practical margins, typed schema, dynamics, oracles, and gates;
- a new discovery seed, confirmation commitment, and secret nonce;
- renderer-only grammar corrections;
- expanded number-agreement, subject-verb, and profile-paraphrase grammar gates;
- an independent full-corpus audit that cannot authorize retained generation.

The revision-2 authoritative hashes remain:

- game JSONL: `631d5cdc725cb2011382b630d05417eadaf6d5531db933307656eb20faa7b48c`
- organization JSONL:
  `9277eb9aaa3634a3a3e5363e4f9451b29d70b0688469649c07721a04d02fbc2b`
- provenance manifest:
  `72786321f920a5427291c4fd82d7fd5a9e8a904f6dcaaeea5cc69de5fd63a431`
