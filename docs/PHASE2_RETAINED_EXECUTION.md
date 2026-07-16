# Phase-2 retained-v2 execution contract

Status: **frozen before retained-v2 baseline computation**

Phase-2 retained work must use `data/generated/phase1_discovery_v3`. The
historical smoke scripts retain their smoke defaults and must not be used to
freeze a retained result.

The machine-readable lock is `configs/phase2_retained.toml`. It binds:

- both retained corpus SHA-256 values;
- the Phase-1 retained provenance and exit-report hashes;
- the confirmation reservation, external acceptance, and Phase-1 source-lock
  hashes;
- 1,000 families per environment and the frozen bootstrap configuration;
- separate retained output paths that cannot overwrite smoke artifacts.
- the value-free destination physical-schema prompt contract and the distinct
  within-environment versus cross-environment estimands.

The first retained Phase-2 run is preserved under
`artifacts/phase2_retained` and `data/generated/phase2_retained`. Its
cross-environment comparison was invalidated before model training because all
Static outputs failed strict parsing when domain-native physical schemas
changed. See `PHASE2_RETAINED_V1_INVALIDATION.md`.

## Execution

Validate without producing outputs:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts\run-phase2-retained.py `
  --mode validate-inputs
```

Run the retained stage exactly once:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts\run-phase2-retained.py --mode run
```

Verify every promoted input and output hash:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts\run-phase2-retained.py --mode verify
```

The run produces:

- an oracle-fixture evaluation over all retained presentations;
- the frozen Static baseline table with 5,000 scenario-cluster bootstrap draws;
- deterministic joint and factorized gzip JSONL exports;
- transfer and split-ID manifests;
- a Phase-2 provenance manifest binding source and output hashes.

## Interpretation and governance

- The retained corpus includes all 300 smoke families per environment, exactly
  unchanged, plus 700 additional families per environment.
- Retained discovery is therefore an extension of smoke discovery, not an
  independent replication or confirmation population.
- Confirmation remains `RESERVED_NOT_GENERATED`.
- Phase-2 retained export does not authorize model training by itself.
- H5 remains `UNIDENTIFIED`; stored rollout targets are H1/H2/H3.
- Within-environment cells retain strict full `joint_pair_success`.
- Cross-environment bootstrap uses strict shared
  `event_normative_pair_success`; domain-native `physical_delta` remains a
  separate diagnostic.
- Existing Phase-1 retained orchestration files remain byte-frozen and are not
  modified by this stage.
- The retained runner refuses to execute until every Phase-2 code/config input
  named in its provenance contract is committed and byte-clean in Git.

## Backup

Create a redundant evidence copy outside the project:

```powershell
.\scripts\create-evidence-backup.ps1 `
  -Destination "D:\normative-world-model-evidence-20260717"
```

The nonce copy uses Windows DPAPI and is recoverable only under the same Windows
user profile. The resulting directory must still be copied or synchronized
off-machine to protect against device failure.
