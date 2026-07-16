# Phase-1 v3 retained execution

Status: **external acceptance installed; retained runner is source-lock-safe**

The external acceptance record is installed at
`artifacts/phase1_v3_smoke/EXTERNAL_AUDIT_ACCEPTED.json`. The retained runner
validates that exact record, both accepted corpus hashes, the accepted smoke
provenance manifest, the smoke exit report, and all 29 source-lock entries before
it writes any retained output.

The 29 frozen files are not modified. Retained orchestration is implemented in
new files outside the source lock and calls the frozen v3 generator and audit
functions directly.

## Lifecycle

1. Run the isolated dry run:

   ```powershell
   .\.venv\Scripts\python.exe scripts\run-phase1-v3-retained.py --mode dry-run
   ```

2. Inspect and verify the dry-run outputs under:
   `data/generated/phase1_v3_retained_dry_run` and
   `artifacts/phase1_v3_retained_dry_run`.

3. Run the formal retained discovery exactly once:

   ```powershell
   .\.venv\Scripts\python.exe scripts\run-phase1-v3-retained.py --mode retained
   ```

   Formal execution requires the frozen discovery seed and exactly 1,000
   families per environment. Existing output directories are never overwritten.

4. Verify the promoted corpus:

   ```powershell
   .\.venv\Scripts\python.exe scripts\check-phase1-v3-post-acceptance.py --require-retained
   ```

## Governance

- Retained output: `data/generated/phase1_discovery_v3`
- Retained evidence: `artifacts/phase1_v3`
- Confirmation content remains `RESERVED_NOT_GENERATED`.
- The existing smoke confirmation reservation is copied byte-for-byte; no
  confirmation scenario or target is generated.
- All generation occurs in `.tmp` staging directories. Outputs are promoted only
  after the applicable audits pass.
- A dry run applies structural gates only. Density, leakage, and nontriviality
  results are diagnostic at that size and become binding only in the formal
  1,000-family-per-environment execution.
