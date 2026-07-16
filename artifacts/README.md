# Artifacts

Final tables, plots, reports, audit bundles, and exportable manifests belong here. Large or
regenerable artifacts remain untracked; only intentionally curated small summaries should be
considered for version control.

The preregistration-v3 smoke generator writes its exit report, dataset card, provenance manifest,
uncertainty reachability table, and independent internal-audit report under `phase1_v3_smoke/`.
Rejected v3 revision-0 artifacts remain under `phase1_v3_revision0_smoke/`. Revision-2 artifacts
remain archived under `phase1_revision2_smoke/` as an internally rejected historical record.

Exploratory Phase-2 smoke baselines are written under `phase2_internal/`. They cannot be presented
as retained or confirmation findings. Retained Phase-1 artifacts are created only after the
external acceptance lock is satisfied.

`phase1_v3_smoke/external_audit_bundle_v3.zip` is a deterministic, self-contained review archive
that includes both complete smoke JSONL files. It is an inspection transport, not an acceptance
record.

Phase-3 local-model snapshot, token, resource, and one-step optimizer-smoke manifests belong under
`phase3_internal/`. They are ignored and remain infrastructure diagnostics until the hash-bound
Phase-1 corpus receives external acceptance.
