# Phase-5 common termination probe candidate

Date: 2026-07-20

Status: **LOCAL PLAN PASS — HTTP/GPU EXECUTION NOT AUTHORIZED**

The public tokenizer proof established identical common-prompt token IDs but
also showed different checkpoint defaults: Base uses `<|endoftext|>`/248044 and
AgentWorld uses `<|im_end|>`/248046. This candidate defines the smallest
synthetic serving test that can close that remaining interface ambiguity.

## Candidate policy

Both common-mode servers must be launched with vLLM 0.25.1 and
`--generation-config vllm`. Every common-mode completion request uses:

- `ignore_eos=true`;
- `stop_token_ids=[248044, 248046]` in that order;
- `skip_special_tokens=false` and `return_token_ids=true`;
- no stop strings, no truncation, temperature zero, and the same seed;
- one forced `allowed_token_ids` value per test case.

The plan forces 248044 and 248046 separately against both checkpoints, with two
identical repetitions per cell: 2 checkpoints × 2 tokens × 2 repetitions = 8
requests. The public common-serialized prompt is 32 tokens for both packages.

The distinction between default EOS and explicit stop is observable in vLLM's
response contract: `stop_reason` carries the stop token ID for an explicit token
stop and is `None` for an EOS-only finish. A cell passes only if the response
reports `finish_reason="stop"`, the exact forced integer `stop_reason`, exactly
one generated token ID equal to that reason, exact prompt token IDs, and one
completion token. Because `include_stop_str_in_output=false`, vLLM removes the
first stop-terminated token from detokenized text even when
`skip_special_tokens=false`; the exact expected text is therefore the empty
string, while `token_ids` retains the forced token. The v2 verifier also requires
`object="text_completion"` and exact `total_tokens = prompt_tokens + 1`. Both
repetitions must have identical semantic fields.

Official vLLM 0.25.1 references:

- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/completion/protocol.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/completion/serving.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/sampling_params.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/v1/core/sched/utils.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/v1/engine/detokenizer.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/config/model.py>

## Local plan result

Candidate config semantic SHA-256:
`1a8cdbf5f8071c27f31c1e04ec026655d922703c8aa8c4b30bfcc1a8a485018c`

Plan artifact field:
`b752a05215d735a5d33e4fb3a70e740876afe2a695759d78ded5828468610002`

Plan file SHA-256:
`9d663e7d7f707bf51a66061bf79ff873e7977f1002985a946365723e9f2e8855`

Ignored local path:
`.cache/phase5_common_termination_probe_plan/v2-1a8cdbf5f807.json`

The plan binds the candidate TOML, four implementation modules, the verified
public tokenizer-probe hash, both effective default EOS bindings, the complete
public prompt/token IDs, and all eight exact request bodies and hashes. Its
independent verifier reloaded both public tokenizer packages and rebuilt the
document exactly.

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe scripts/run-phase5-common-termination-plan.py
.\.venv\Scripts\python.exe scripts/verify-phase5-common-termination-plan.py
```

The future evidence verifier accepts raw-before-parse responses only when the
caller supplies the exact Lock-A `expected_plan_sha256`; a self-hash alone is not
a trust anchor. Duplicate JSON keys, non-finite numbers, missing/extra cases,
request drift, bool-as-int fields, ambiguous/default EOS stops, and repeat drift
all fail closed. It also rejects the wrong completion object, visible or
otherwise nonempty stop-token text, and missing, bool, or inconsistent
`usage.total_tokens`.

## Revision ledger

The original v1 artifact at
`.cache/phase5_common_termination_probe_plan/v1-832c06e718b9.json` is preserved.
K3's incomplete first-round attack showed that v1 did not bind the response
`object`, exact detokenized text, or `usage.total_tokens`. Codex checked the
official vLLM 0.25.1 source and replaced the initially suggested literal-token
text assertion with the source-correct empty-string assertion. V2 supersedes v1
for any future Lock-A package; v1 remains historical plan-only evidence and does
not authorize execution.

## Boundary and next gate

This result validates a plan and verifier against local fixtures; it does not
show that either served model implements the policy. The main Phase-5 TOML
therefore remains `PENDING_LOCK_A_SYNTHETIC_TERMINATION_PROBE`. No HTTP request,
model download, rental, GPU execution, project prompt, population selection,
confirmation access, or scientific metric was opened here.

The candidate may enter the combined Lock-A package. Only a later accepted Lock
A may authorize the eight public synthetic requests on both served checkpoints.
