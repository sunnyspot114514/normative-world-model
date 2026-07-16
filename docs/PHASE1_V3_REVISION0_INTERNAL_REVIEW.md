# Phase-1 v3 revision-0 internal review record

Date: 2026-07-16

Status: **INTERNALLY REJECTED BEFORE EXTERNAL REVIEW**

V3 revision 0 passed the native and package-independent machine audits, but the deterministic
human-readable sample required by `docs/INTERNAL_REVIEW_PROTOCOL.md` found systematic malformed
action phrases in the natural-language condition. Examples include:

- `proposes to read or write file across the single record`;
- `suggests the renegotiate read or write file`;
- `plan to allocate resource for the group`.

The underlying action identifiers, structured inputs, state transitions, event records, oracle
labels, split assignments, and leakage/nontriviality results remain valid. The defect nevertheless
confounds the structured-versus-natural-language comparison and is therefore blocking.

Revision 0 is archived unchanged under:

- `data/generated/phase1_v3_revision0_smoke/`;
- `artifacts/phase1_v3_revision0_smoke/`.

Its authoritative hashes are:

- game JSONL:
  `83555e8f6b3634b703635d010c15598c1ccc92542e13fed33462738ba5c4776b`
- organization JSONL:
  `6f85adf999bbea0e4d1a27150f60d5c802faa63c8ffb25a6be518f91fce23557`
- provenance manifest:
  `2694c009e77dc4796258324b9af7c2932ea7c38daf8b6e20ff20deb343469bf4`
- deterministic review sample:
  `eb827241d3f6a6b16cf1e50b8dbbdb543c27248cae536c9744805b1f03e2830b`

Revision 1 may change only the rendering of action identifiers into grammatical controlled-language
phrases and the audits that reject the revision-0 patterns. It consumes one of the two v3 generator
revision slots. No scientific threshold, typed source field, dynamics, oracle, label, split, or
confirmation content may change.
