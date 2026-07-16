# Phase-1 revision-2 smoke record

Date: 2026-07-15; audit-contract refresh 2026-07-16

Status: **local PASS; conditional external findings resolved; refreshed manifest re-acceptance pending; retained generation blocked**

Revision 2 is the final implementation revision allowed by preregistration v2. The deterministic
smoke run used seed `20260715` and generated 300 scenario families in each environment. It did not
generate any confirmation scenario or target.

## Local result

All density, split, state-machine, natural-language, nontriviality, model-input-integrity, surface-
leakage, calibration, and replay gates passed. In particular:

- variable-article errors: `0` in both environments;
- forbidden `turn`/`ticket` model-input rows: `0`;
- model-input hash mismatches: `0`;
- ordinal renderer cardinality failures: `0`;
- factual, actor-value, and policy intervention source-scope success: `1.0` in both environments;
- rollout-chain failures: `0`;
- exact oracle-boundary rows in the compact all-row index: `7`.

The maximum row-order/feature correlation was `0.12447` for game and `0.16669` for organization,
below the `0.20` gate. Maximum affine impact R-squared was `0.67416` and `0.70801`; maximum depth-3
tree R-squared was `0.66081` and `0.75688`; direct decision accuracy was `0.48264` and `0.62658`.

Gate C is now enforced independently in each environment. Game word/character macro AUC was
`0.46753/0.47434` with cluster upper bound `0.50466`; organization was
`0.51534/0.49975` with cluster upper bound `0.56988`. Both independently pass the frozen
`0.55` point and `0.60` upper-bound gates. The pooled result is diagnostic only.

Full-corpus SHA-256:

- game: `631d5cdc725cb2011382b630d05417eadaf6d5531db933307656eb20faa7b48c`
- organization: `9277eb9aaa3634a3a3e5363e4f9451b29d70b0688469649c07721a04d02fbc2b`

The provenance manifest binds all four machine-readable configurations, every Python source file
in `src/normative_world_model/`, the human-readable audit/oracle/metric contracts, and the smoke
bundle/check scripts; its SHA-256 is
`72786321f920a5427291c4fd82d7fd5a9e8a904f6dcaaeea5cc69de5fd63a431`.

The audit-contract refresh changed no scenario bytes: both full-corpus hashes are identical before
and after the same-seed rerun. It changed only audit enforcement, documentation, acceptance
semantics, report structure, and provenance-bound source/configuration hashes; it is not a third
data-schema revision.

## Oracle conformance correction

Oracle version `0.4.1` uses exact decimal boundary comparisons. Re-evaluating the archived
revision-1 corpus changed 9 of 32,000 decision/reason labels: eight upper-boundary
`escalate -> allow` corrections and one lower-boundary `escalate -> reject` correction. Score-only
representation changes were excluded. The ignored revision-1 archive contains the row-level change
list and keeps the original corpus intact.

`calibration_cases.json` added exact upper (`0.10 -> allow`) and lower (`-0.08 -> reject`)
boundary assertions. It also corrected the existing `three_target_pairs_diverge` expectation for
`procedure_preserving` from `escalate/weighted_score_band` to `allow/weighted_score`, because its
exact score is `0.10` and the already-frozen rule is inclusive at `score >= 0.10`. This records the
oracle `0.4.1` implementation bug; no profile, policy, or schema semantics changed.

## External audit handoff

`artifacts/phase1_revision2_smoke/external_audit_bundle.zip` contains a 600-row compact index, a
deterministic 49-row inspection sample augmented with every exact-boundary and actor-insensitive
case, the exit report, provenance manifest, and confirmation reservation. It is an inspection aid;
the two raw JSONL files remain authoritative and can be addressed by environment, line number,
scenario ID, and raw-line hash. The refreshed ZIP is 210,150 bytes with SHA-256
`ad9054bebf9019ca9817db678ae518a11c2f12816a8dd75815592af8108481e5`.

No command that writes `data/generated/phase1_discovery_v2/` or `artifacts/phase1_v2/` may run
before external acceptance. An external smoke failure triggers a new preregistration version rather
than a third repair revision.
