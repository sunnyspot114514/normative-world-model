# External smoke acceptance contract — v3

Status: **active lock; no acceptance record exists**

Internal review cannot authorize retained generation. A future retained-v3 entry point must refuse
to run unless `artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json` exists and binds the exact
revision-1 smoke artifacts.

The acceptance record must contain:

```json
{
  "status": "EXTERNAL_ACCEPTED",
  "unconditional": true,
  "preregistration_version": 3,
  "generator_revision": 1,
  "run_kind": "v3_internal_smoke",
  "reviewer": "external reviewer identity",
  "reviewed_at": "ISO-8601 timestamp",
  "provenance_manifest_sha256": "exact sha256",
  "corpus_sha256": {
    "data/generated/phase1_v3_smoke/game.jsonl": "exact sha256",
    "data/generated/phase1_v3_smoke/organization.jsonl": "exact sha256"
  },
  "blocking_findings": []
}
```

Acceptance is invalid if:

- any bound byte changes after review;
- the reviewer leaves a condition, reservation, or blocking finding;
- the record was produced by the project author or an internal automation;
- the record refers to revision 2, v3 revision 0, a sample alone, or a regenerated corpus with
  different hashes;
- confirmation content was generated or inspected during the review.

External acceptance unlocks only retained discovery generation under the same schema, seed,
dynamics, oracles, renderer revision, and gates. It does not unlock confirmation, change practical
margins, or turn exploratory smoke results into retained findings.

