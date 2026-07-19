# Phase-5 public metadata probe

Date: 2026-07-20

Execution commit: `2dc000d`

Initial ignored-cache manifest SHA-256: `90045b75a1d01588a83c3df539c21f310f8d94324bf00b57015aebf1360151a7`

Status: **REPEAT DOWNLOAD PASS; TOKENIZER PROBE V2 INPUT PASS; LOCK-A EOS ACTION OPEN**

The first restricted execution ran from a clean commit. It fetched only the frozen public metadata allowlist at the two exact revisions and wrote under `.cache/phase5_public_metadata/v1-d46462f4f4c2/`.

| Checkpoint | Revision | Files | Bytes |
|---|---|---:|---:|
| AgentWorld | `60d2b0434a53d2e62a7c00a489586815d94ebffb` | 9 | 22,982,918 |
| Base | `0f0813072d2358973511097385626f21fcb6d422` | 7 | 23,091,324 |

Bundle bytes: 46,074,242. Redirect hosts were only `huggingface.co` and `us.aws.cdn.hf.co`. Every file matched the publisher size and either its LFS SHA-256 or locally recomputed Git blob ID. No `.safetensors` payload was requested or stored.

The first strict inspector stopped on `tokenizer.json.model` because AgentWorld explicitly stored `ignore_merges=false` while Base omitted the field. Direct comparison then established that `false` is the documented BPE default and the loaded tokenizers agree. It also exposed that effective added tokens must merge declarations from both tokenizer files; see the adjacent external-review erratum.

This initial probe is discovery evidence about the checker itself. It does not close the public source lock. Closure requires the corrected inspector, a new semantic-hash-bound repeat probe, and a committed synthetic token-ID proof summary.

## Corrected repeat download

Execution commit: `ee419af`

Current semantic binding: `2a23d1973113694468cd25be92e8932b52f8c4f3d56deda78ea2b5421e7abb76`

Repeat bundle manifest SHA-256: `a8b8544ee8162e1634097b0d7194197d6c03244c98dcf134e818f59b9d872b3a`

The independent verifier rebuilt all 16 file entries and returned PASS at the same 46,074,242-byte total. The superseded cache correctly fails the current semantic-binding check.

## Tokenizer probe V1 invalidation

V1 artifact SHA-256: `56984cf880b4102766e1d2ab3f1475cc236667aa074c6c2cfb19c42a932f007e`

The five public prompts produced exact Base/AgentWorld token-ID equality, and the effective control-token bindings agreed. However, the `long-public` prompt was 8,019 input tokens. With the frozen 2,048-token generation cap, it would require 10,067 tokens and therefore is not a valid protocol-shaped witness for the 8,192 context.

V1 remains valid evidence of tokenizer equality for those exact strings, but it is invalid as the required long-context/headroom probe. It is preserved in the ignored cache and is not overwritten. V2 changes the public repetition count, requires the long row to fall in `[5900, 6144]`, and separately asserts `input_tokens + 2048 <= 8192` before it may pass.

## Tokenizer probe V2 result

Execution commit: `952c0f7`

V2 artifact SHA-256: `57aa5fe28faab15d7780df0243fa700ef9d0089f4c47fc0ade581c4ceee86970`

Bound repeat manifest: `a8b8544ee8162e1634097b0d7194197d6c03244c98dcf134e818f59b9d872b3a`

The independently rebuilt prompt counts were 34, 44, 49, 44, and 6,019 tokens. The long row plus the 2,048 generation allowance is 8,067, leaving 125 tokens under the frozen 8,192 context. All five Base/AgentWorld token-ID sequences matched exactly. The independent verifier reloaded both local packages and reproduced the complete stored artifact, returning PASS.

Runtime versions were `transformers==4.57.6` and `tokenizers==0.22.2`. They are probe evidence, not yet the Lock-A container/source closure.

The artifact status remains `PASS_WITH_LOCK_A_EOS_ACTION`: Base loads `<|endoftext|>`/248044 as EOS while AgentWorld loads `<|im_end|>`/248046. Input serialization is closed for this public probe; matched serving termination is not.
