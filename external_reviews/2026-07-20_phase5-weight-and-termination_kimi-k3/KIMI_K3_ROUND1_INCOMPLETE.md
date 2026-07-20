# Kimi K3 round-1 audit: incomplete evidence record

Date: 2026-07-20

Reviewer invocation: `kimi-code/k3`

Requested scope: `ROUND1_AUDIT_REQUEST.md`

Status: **INCOMPLETE — QUOTA EXHAUSTED BEFORE VERDICT**

This file is not a `PASS`, `PASS_WITH_FIXES`, or `BLOCK` verdict. The reviewer
completed most mechanical attacks but was interrupted while checking the
official vLLM 0.25.1 source and before it could write a final report. The CLI
ended with:

```text
provider.api_error: 403 You've reached your usage limit for this billing cycle.
```

The partial evidence below is retained so that completed work is not silently
discarded or misrepresented as a signed review.

## Repository and artifact identity

K3 independently confirmed:

- clean worktree at request commit `10ecdaa`;
- primary termination commit `251e045` and weight-plan commit `a18026f`;
- Stage-2 semantic SHA-256
  `2a23d1973113694468cd25be92e8932b52f8c4f3d56deda78ea2b5421e7abb76`;
- termination semantic SHA-256
  `832c06e718b9436f708fa0db9d4ed78e09936b2d0253a692e13958a6986d69f7`;
- source records, self-hashes, snapshot hashes, and all eight request-body
  hashes matched their stored artifacts.

Its independent rebuilds matched the stored weight plan and termination plan.
Self-hash substitution, authorization flips followed by rehashing, weight-hash
replacement, forced-token shifts, seed changes, and `http_execution` changes
were all rejected by independent rebuild comparison.

## Publisher weight-plan recomputation

K3 recomputed the plan without using the project's resolver and obtained:

| checkpoint | shards | publisher bytes | index tensor bytes | container overhead | unreferenced weights |
|---|---:|---:|---:|---:|---:|
| AgentWorld | 21 | 69,321,314,576 | 69,321,221,376 | 93,200 | 0 |
| Base | 14 | 71,903,877,960 | 71,903,655,008 | 222,952 | 0 |
| Total | 35 | 141,225,192,536 | 141,224,876,384 | 316,152 | 0 |

The recomputed rows, sizes, and LFS SHA-256 values matched the stored plan.
K3 found no Phase-5 path that fetches `.safetensors`: the only Phase-5 network
path is the restricted public-metadata fetcher and the weight-plan module has
no network client. It also confirmed that the configuration and artifact keep
`model_download=false`.

## Inert-JSON and path attacks

The partial review exercised bools, `NaN`, infinities, exponent overflow and
underflow, duplicate keys, trailing data, non-UTF-8, integer-valued floats,
fractional values rounded to an integer, and the binary64 boundary around
`2**53`. Numeric consumers rejected bool-as-int, non-finite values, lossy
integer-valued floats, nonpositive sizes, tensor totals above publisher bytes,
and LFS/size/digest disagreement.

One helper-level hardening observation remained: `validate_public_metadata_path`
accepts `subdir/tokenizer.json` because it allowlists `path.name`. K3 traced all
current callers and found no path to a false pass: the downloader intersects
against fixed flat names, bundle verification compares the publisher
projection, and tokenizer-probe independent rebuilds detect an added nested
file. This was therefore a nonblocking, unreachable helper-contract weakness,
not a demonstrated artifact or download escape.

## Future termination-evidence verifier attacks

The verifier rejected wrong external plan bindings, missing/extra/duplicate
cases, changed request bodies, bad HTTP status, duplicate/non-finite raw JSON,
wrong model aliases, bool/string stop reasons, wrong finish reasons, extra or
wrong token IDs, wrong prompt IDs, wrong prompt/completion usage, repeat drift,
extra evidence keys, multiple choices, and oversized responses.

The partial review found that a response could still pass with any repeated
string in `choice.text`, and that `usage.total_tokens` and the response `object`
were not checked. K3 called these nonblocking hardening gaps. It did not finish
the official-source adjudication of what the exact response text should be.

A fully fabricated but internally consistent eight-row evidence set can pass
this schema verifier. That is expected of a verifier that has no network client:
future Lock-A authenticity must also bind the authorized runner, raw capture,
transfer manifest, and external plan hash. The current candidate alone does not
authorize or claim remote provenance.

## Tests and authorization boundary

K3 reported all **184** unit tests passing. Its initial isolation check failed
because its shell had not loaded `scripts/project-env.ps1`; it then reran with
project-local environment variables. It found no Phase-5 server launcher,
rental path, GPU execution, project-prompt access, population selection,
confirmation access, or scientific execution authorized by the audited files.

## Work not completed by K3

- final official-source disposition for vLLM 0.25.1 termination semantics;
- final severity and exact fixes for response text/object/total usage;
- final Lock-A blocker enumeration;
- an overall `PASS`, `PASS_WITH_FIXES`, or `BLOCK` verdict;
- the required second review round.

Codex must independently adjudicate the partial findings. A later K3 review
must not cite this file as an accepted first-round verdict without reproducing
the unfinished official-source and final-disposition work.
