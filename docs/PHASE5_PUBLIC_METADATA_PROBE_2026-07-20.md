# Phase-5 public metadata probe

Date: 2026-07-20

Execution commit: `2dc000d`

Initial ignored-cache manifest SHA-256: `90045b75a1d01588a83c3df539c21f310f8d94324bf00b57015aebf1360151a7`

Status: **DOWNLOAD PASS; TOKENIZER INSPECTOR CORRECTION REQUIRED AND IDENTIFIED**

The first restricted execution ran from a clean commit. It fetched only the frozen public metadata allowlist at the two exact revisions and wrote under `.cache/phase5_public_metadata/v1-d46462f4f4c2/`.

| Checkpoint | Revision | Files | Bytes |
|---|---|---:|---:|
| AgentWorld | `60d2b0434a53d2e62a7c00a489586815d94ebffb` | 9 | 22,982,918 |
| Base | `0f0813072d2358973511097385626f21fcb6d422` | 7 | 23,091,324 |

Bundle bytes: 46,074,242. Redirect hosts were only `huggingface.co` and `us.aws.cdn.hf.co`. Every file matched the publisher size and either its LFS SHA-256 or locally recomputed Git blob ID. No `.safetensors` payload was requested or stored.

The first strict inspector stopped on `tokenizer.json.model` because AgentWorld explicitly stored `ignore_merges=false` while Base omitted the field. Direct comparison then established that `false` is the documented BPE default and the loaded tokenizers agree. It also exposed that effective added tokens must merge declarations from both tokenizer files; see the adjacent external-review erratum.

This initial probe is discovery evidence about the checker itself. It does not close the public source lock. Closure requires the corrected inspector, a new semantic-hash-bound repeat probe, and a committed synthetic token-ID proof summary.
