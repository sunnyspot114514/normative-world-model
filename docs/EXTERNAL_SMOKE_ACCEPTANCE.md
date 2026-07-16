# External smoke acceptance contract

Retained revision-2 generation is programmatically blocked until
`artifacts/phase1_revision2_smoke/EXTERNAL_AUDIT_ACCEPTED.json` exists and binds the exact smoke
manifest and both raw corpora.

The external auditor creates the record only after accepting the audit checklist:

```json
{
  "status": "ACCEPTED",
  "unconditional": true,
  "conditions": [],
  "auditor": "name or stable review identifier",
  "accepted_at": "ISO-8601 timestamp",
  "smoke_provenance_manifest_sha256": "sha256 of provenance_manifest.json",
  "smoke_corpus_sha256": {
    "data/generated/phase1_revision2_smoke/game.jsonl": "sha256",
    "data/generated/phase1_revision2_smoke/organization.jsonl": "sha256"
  },
  "notes": "optional"
}
```

The generator requires an explicitly unconditional acceptance with an empty conditions list,
recomputes the manifest hash, requires exact equality for both corpus-hash mappings, and verifies
that the bound exit report is a `revision2_smoke` PASS. A conditional, stale, partial,
self-declared, or malformed record does not unlock retained generation.
