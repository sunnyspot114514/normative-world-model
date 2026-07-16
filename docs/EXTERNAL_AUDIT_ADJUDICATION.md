# External smoke audit adjudication

Date: 2026-07-16

The full-corpus external audit conditionally accepted the two revision-2 smoke JSONL files and
reconciled their hashes, 600-row index binding, oracle evaluations, twins, language, rollout,
density, nontriviality, and row-order diagnostics. Its two actionable conditions were accepted in
narrowed form and implemented before retained generation.

## Accepted and implemented

- Gate C now reports and gates game and organization independently; a pooled PASS cannot mask an
  environment failure.
- The oracle contract now states six-decimal input canonicalization, Decimal arithmetic without
  intermediate rounding, inclusive boundaries, and deterministic veto-reason order.
- The audit contract now defines exact UTF-8 preimages for natural-language, raw-line, and canonical
  model-input hashes.
- Acceptance must be explicitly unconditional with an empty condition list. A conditional review
  cannot unlock retained generation merely by setting `status` to `ACCEPTED`.

## Corrections to the review narrative

- The weighted-harm formula and inclusive irreversibility comparison were already present in
  `docs/EVALUATOR_PROFILES.md`; only rounding and veto-order details were missing.
- The exploratory organization probe reported as approximately `0.586` is not the preregistered
  Gate C estimand. Under the implemented word/character TF-IDF contract, organization scores
  `0.51534/0.49975` with cluster upper bound `0.56988`, so it independently passes. Alternative
  probes remain named diagnostics.
- Full train/development composition-signature sets are not disjoint (20 shared game signatures and
  22 shared organization signatures). The frozen split gate instead prevents scenario, source, and
  rendered-family crossings and reserves explicitly flagged composition holdouts. The external
  phrase claiming general composition-signature disjointness is not used as acceptance evidence.

## Provenance consequence

The same-seed refresh left both raw JSONL SHA-256 values unchanged but changed manifest-bound audit
code and contracts. Therefore the prior conditional review's manifest hash cannot unlock retained
generation. The refreshed manifest requires a short external re-acceptance that binds its new hash
and contains no remaining conditions.
