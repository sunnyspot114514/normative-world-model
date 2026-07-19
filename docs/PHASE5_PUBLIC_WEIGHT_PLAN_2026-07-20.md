# Phase-5 public publisher weight-plan result

Date: 2026-07-20

Status: **METADATA-ONLY V3 PASS; MODEL DOWNLOAD REMAINS FORBIDDEN**

This step consumed only the already verified public metadata bundle
`v1-2a23d1973113`, whose manifest SHA-256 is
`a8b8544ee8162e1634097b0d7194197d6c03244c98dcf134e818f59b9d872b3a`.
It made no network request and did not fetch, create, or open a `.safetensors`
payload.

## Corrected size semantics

`model.safetensors.index.json/metadata.total_size` is the publisher's declared
sum of tensor storage bytes. Hugging Face API/LFS sizes describe complete
safetensors files and include container headers. They are therefore separate
quantities, not two copies of the same checksum.

| Checkpoint | Shards | Tensor bytes from index | Publisher/LFS bytes | Container overhead |
|---|---:|---:|---:|---:|
| AgentWorld | 21 | 69,321,221,376 | 69,321,314,576 | 93,200 |
| Base | 14 | 71,903,655,008 | 71,903,877,960 | 222,952 |
| Total | 35 | 141,224,876,384 | 141,225,192,536 | 316,152 |

Every index-referenced shard has one exact publisher LFS SHA-256 and positive
byte count. Neither repository exposes an unreferenced `.safetensors` file at
the pinned revision.

## Artifact lifecycle

The exploratory v1 artifact was generated before the plan bound its own
implementation sources. It is preserved under the ignored cache and is not an
accepted closure artifact.

- v1 artifact field: `ba19e5b1b7ec034e3a503066e96a7f546651de6fc72effffc7586a218b8d79fc`
- v1 file SHA-256: `c3a6bad19bb826eccee197cab8f14880d66fb7a5560cad7cc674b7e5eaf343ea`

V2 added implementation-source binding, then correctly failed after the inert
JSON parser was hardened against large integer-valued floats that could round
into binary64 range. It remains preserved as an intermediate artifact and is
not accepted.

- v2 artifact field: `e008319b55580c56c51d975c94a778d69bbc389d726da84cbfe9927864d8eab5`
- v2 file SHA-256: `c640d5b24ad6b3469d6d20281e967778bb01ea33e8b2961cc2250ed24cb47a80`

V3 binds the exact API response and model-index bytes, repo IDs, 40-hex
revisions, verified metadata manifest, Stage-2 semantic configuration, all 35
publisher paths/sizes/LFS digests, and four implementation source files. The
independent verifier rebuilt the complete document exactly.

- v3 artifact field: `ee5eaa6d9fb3b9da9ede408743dacad0ed6c9bf6e4495307a662deff23ab6c8c`
- v3 file SHA-256: `c5e6fa190934011849afe5759477c892d27bc6fa8a593f7677a479e6575ce1f4`
- v3 local path: `.cache/phase5_public_weight_plan/v3-2a23d1973113.json`

Reproduction and verification commands:

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts/run-phase5-public-weight-plan.py
.\.venv\Scripts\python.exe scripts/verify-phase5-public-weight-plan.py
```

The run command is write-once and will refuse to replace an existing artifact.
The verifier rejects symlinks, multiple hard links, duplicate JSON keys,
non-finite numbers, source/input drift, manifest drift, missing or extra weight
references, and any independently rebuilt difference.

## Boundary

The plan is a prospective byte-and-digest list, not download authorization.
`authorization.model_download=false`, `remote_fetch_performed=false`, and
`weight_bytes_present=false` are carried in the artifact and re-reported by the
verifier. Population selection, real project prompts, rental, GPU inference,
confirmation, and scientific execution remain closed.
