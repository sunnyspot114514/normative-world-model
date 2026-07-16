# Phase-1 v3 retained discovery record

Status: **PASS; retained discovery generated; confirmation remains reserved**

The externally accepted v3 revision-1 generator produced the formal retained
discovery corpus with the frozen seed `20260716` and exactly 1,000 scenario
families per environment.

The pre-acceptance status lines in source-locked contracts remain unchanged as
historical frozen bytes. The external acceptance archive and this record describe
the post-acceptance lifecycle.

## Corpus

| Environment | Families | Bytes | SHA-256 |
|---|---:|---:|---|
| game | 1,000 | 42,055,526 | `c0bc4e55e0a4fd1d016accc6583e9ffb97c79db1c97d3de329a792019ab3155d` |
| organization | 1,000 | 43,856,990 | `e459a38f5259981b1eec5ccf99e8699e9330e49127bd2df62902bfc3411b0f02` |

The corpus is local and ignored by Git under
`data/generated/phase1_discovery_v3`.

## Frozen evidence

| Artifact | SHA-256 |
|---|---|
| Retained provenance manifest | `71884458cce25d58311ab982e062e1d490dc5505e613de002da426228bab1d3e` |
| Retained Phase-1 exit report | `268fc0aca0cc134991238baa258ae5c2a0707796276b6da620d3c3436685195b` |
| Confirmation reservation | `f26e5b70338e7a8ee45d5ec4329221de5cb4b199cab40dd547c3b9f4753c5d27` |
| Installed external acceptance | `3374b05aa41b800e79af2b82f82e770f4cdd65c8440eff644202a155766d5949` |

The retained manifest binds:

- every generated retained file;
- all 29 externally reviewed source-lock inputs;
- the new source-lock-safe runner and CLI by exact hash;
- the installed external acceptance, accepted smoke manifest, and source-lock
  file.

## Exit metrics

| Metric | game | organization | Gate |
|---|---:|---:|---|
| No-hard-violation fraction | `0.8700` | `0.8320` | PASS |
| Evaluator-divergent fraction | `0.3910` | `0.3640` | PASS |
| Uncertainty-divergent fraction | `0.2864` | `0.3626` | `>= 0.03` |
| Actor-value physical sensitivity | `0.9990` | `1.0000` | `>= 0.25` |
| Maximum row-order correlation | `0.0787` | `0.0764` | `<= 0.20` |
| Maximum scalar unique fraction | `0.0060` | `0.0060` | `<= 0.10` |
| Maximum affine impact R2 | `0.8046` | `0.7864` | `<= 0.90` |
| Maximum depth-3 tree impact R2 | `0.7585` | `0.7951` | `<= 0.90` |
| Depth-3 direct decision accuracy | `0.5508` | `0.5985` | `<= 0.90` |

All natural-language error counts are zero. Split integrity, state-machine
integrity, calibration, density, nontriviality, and model-input integrity pass in
both environments.

## Leakage gate

| Environment | Word macro AUC | Char-4 macro AUC | 95% cluster upper bound | Status |
|---|---:|---:|---:|---|
| game | `0.4937` | `0.4943` | `0.5093` | PASS |
| organization | `0.4820` | `0.4892` | `0.5021` | PASS |

Both environments have zero direct-token violations and zero conditional surface
imbalance findings.

## Independent replay

The package-independent auditor was rerun against the retained paths:

```powershell
.\.venv\Scripts\python.exe scripts\independent-smoke-audit.py `
  --data-dir data/generated/phase1_discovery_v3 `
  --artifact-dir artifacts/phase1_v3 `
  --expected-run-kind v3_retained_discovery `
  --expected-families-per-environment 1000 `
  --output .tmp/independent_retained_audit.json
```

Result: `PASS`, 2,000 rows, zero row failures, zero failure categories. The
ephemeral audit report SHA-256 was
`d9d1128a444e4801bb3dc99324223ab77a401b699341df706d1b80a7f77f451a`.

## Governance

- Confirmation remains `RESERVED_NOT_GENERATED`.
- No practical margin changed.
- No source-locked file changed.
- The first rollout item still duplicates the primary transition; additional
  horizon information begins at `rollout[1]`.
- The retained corpus now unlocks the frozen Phase-2 baseline computation, not
  confirmation generation or retained model claims.
- All 300 externally reviewed smoke families per environment occur unchanged in
  the retained corpus. Retained discovery is therefore a population extension,
  not an independent replication; only confirmation can provide the locked
  independent test.
