# Phase-1 v3 / Phase-2 External Audit Archive

This directory preserves the seven external-audit deliverables exactly as received.
The original files are not edited; `archive_manifest.json` records their byte sizes
and SHA-256 digests.

## Accepted scope

- Phase-1 v3 smoke corpus: externally accepted without blocking findings.
- Bound source lock: 29/29 files match commit
  `1f9f7f3418dcfa353a9efcbb9a493d4a0914138b`.
- Bound corpus and provenance hashes: locally re-computed and matched.
- Confirmation data: remains `RESERVED_NOT_GENERATED`.
- Phase-2 implementation: `APPROVE_WITH_FIXES`; M1 and M2 test coverage must be
  added before the retained baseline is frozen.

## Activation status

The signed record is installed byte-for-byte at
`artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json`. A v3-specific,
source-lock-safe acceptance validator, retained runner, and post-acceptance check
have been added outside the 29-file source lock. The isolated 10-family-per-
environment dry run passed before formal retained generation. Formal generation
then passed with 1,000 families per environment and left confirmation reserved.

## Recorded non-blocking issues

1. The correct rollout relationship is:
   `rollout[0].pre_state == source.state`,
   `rollout[0].next_state == primary.next_state`, and
   `rollout[i+1].pre_state == rollout[i].next_state`.
2. Phase-2 M1 lacks explicit tests for plain fenced JSON and uppercase `JSON`
   fences.
3. Phase-2 M2 lacks explicit negative tests for out-of-range/non-finite confidence
   and an extra confidence field in factorized factual output.
4. The first rollout transition duplicates the primary transition; genuine
   additional-horizon evaluation starts at `rollout[1]`.

Changing a source-locked input, the accepted corpus, or the bound provenance
manifest invalidates the Phase-1 acceptance. Unrelated documentation and Phase-2
test-only changes are outside the 29-file source lock, but must still be reviewed
normally.
