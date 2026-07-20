# Codex counter-review: Phase-5 weight and termination closure

Date: 2026-07-20

Reviewed commits: `a18026f`, `251e045`, `10ecdaa`

K3 evidence record: `KIMI_K3_ROUND1_INCOMPLETE.md`

Disposition: **PASS_WITH_FIXES FOR LOCAL LOCK-A ASSEMBLY ONLY**

External-review status: **INCOMPLETE**. K3 exhausted its quota before returning
a verdict. This counter-review does not convert the interrupted run into an
accepted external round and does not satisfy the two-round review gate.

## Independent reproduction

Codex reproduced the complete public-artifact hash chain, the real 35-shard
publisher plan, the absence of weight bytes, the eight-case termination plan,
the inert-JSON attacks, the plan/evidence tamper attacks, and the authorization
boundary. The post-fix repository check passed **185 tests**, the isolation
audit, and every preserved result/source-lock verifier. Confirmation remains
`RESERVED_NOT_GENERATED`.

The vLLM source review was performed against official tag `v0.25.1`, commit
`752a3a504485790a2e8491cacbb35c137339ad34`:

- `config/model.py` defines `generation_config="vllm"` as loading no model
  generation config and using vLLM defaults;
- `completion/protocol.py` exposes `stop_token_ids`, `ignore_eos`,
  `allowed_token_ids`, `return_token_ids`, `skip_special_tokens`, prompt
  truncation, and `add_special_tokens`; its response contract defines an
  explicit stop-token reason as the integer token ID and default EOS as
  `stop_reason=None`;
- `sampling_params.py` keeps request stop-token IDs in the explicit stop set;
  with `ignore_eos=true`, the checkpoint default is not installed as the
  primary EOS stop;
- `v1/core/sched/utils.py` sets `stop_reason` only on the explicit
  `stop_token_ids` branch, while the primary EOS branch leaves it unset;
- `completion/serving.py` returns generated and prompt token IDs when requested
  and computes `total_tokens = prompt_tokens + completion_tokens`;
- `v1/engine/detokenizer.py` removes the final stop-terminated token from text
  when `include_stop_str_in_output=false`.

Official source links:

- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/config/model.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/completion/protocol.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/entrypoints/openai/completion/serving.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/sampling_params.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/v1/core/sched/utils.py>
- <https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/v1/engine/detokenizer.py>

## Finding adjudication

### C1 — response object and total-token accounting were not bound

Severity: **nonblocking hardening, supported and fixed**

K3 demonstrated that v1 accepted a missing `usage.total_tokens` and did not
check the completion response `object`. V2 now requires
`object="text_completion"`, an integer non-bool `total_tokens`, and the exact
sum of the bound prompt count plus one completion token. Dedicated negative
tests cover wrong object, missing total, and bool total.

### C2 — response text was underconstrained

Severity: **nonblocking hardening, supported; K3's tentative literal fix was
not source-correct**

V1 required only a repeated string. The official detokenizer excludes the first
stop-terminated token when `include_stop_str_in_output=false`; consequently the
correct value for all eight one-token cases is `text=""`, not the visible
`<|endoftext|>` or `<|im_end|>` literal. V2 binds the empty string while retaining
the authoritative generated token in `token_ids` and `stop_reason`. A negative
test proves that visible stop-token text is rejected.

### C3 — metadata path helper accepts an allowlisted basename below a directory

Severity: **low, supported, currently unreachable; deferred**

`validate_public_metadata_path("subdir/tokenizer.json")` succeeds because the
helper checks `path.name`. No current caller can turn this into an accepted
bundle or weight fetch:

- the downloader intersects publisher paths with the fixed flat requested set;
- the bundle verifier compares each manifest projection to that flat publisher
  plan and enforces the exact on-disk set;
- the tokenizer and termination artifacts are independently rebuilt from the
  verified bundle, so an added nested file changes the document and fails.

Changing this shared source now would invalidate the verified public-metadata,
tokenizer, weight, and termination chain without closing a reachable current
path. The exact-flat check is therefore recorded as pre-Lock-A source-hardening
debt. It must either be repaired with versioned regeneration of all dependent
public artifacts or be explicitly excluded from the Lock-A executable closure;
it is not permission to accept nested metadata paths.

### C4 — a schema-consistent fabricated evidence set passes

Severity: **expected boundary, not a verifier false pass**

The current candidate deliberately contains no network client. Its evidence
function proves exact plan/response semantics, not remote provenance. Lock A
must separately bind the runner, raw-before-parse capture, request order,
transfer manifest, source/container identity, and external plan hash. Until
that capture chain exists and is reviewed, no evidence row is authoritative.

### C5 — language-only serving remains provisional

Severity: **Lock-A blocker, outside the current plan-only fix**

Both public configs identify a multimodal conditional-generation architecture.
vLLM 0.25.1 provides a `language_model_only` server setting, but the exact
launch command and returned runtime manifest are not yet frozen. The combined
Lock-A package must bind the same language-only mode for both checkpoints and
fail if either server resolves a different effective runtime.

## V2 artifact

- candidate semantic SHA-256:
  `1a8cdbf5f8071c27f31c1e04ec026655d922703c8aa8c4b30bfcc1a8a485018c`;
- plan field SHA-256:
  `b752a05215d735a5d33e4fb3a70e740876afe2a695759d78ded5828468610002`;
- plan-file SHA-256:
  `9d663e7d7f707bf51a66061bf79ff873e7977f1002985a946365723e9f2e8855`;
- ignored write-once path:
  `.cache/phase5_common_termination_probe_plan/v2-1a8cdbf5f807.json`;
- status: `PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED`;
- cases: 8; public prompt tokens: 32; HTTP execution: false.

The v1 artifact remains present and is explicitly superseded, not deleted or
retroactively described as v2.

## Decision and remaining gates

The project may continue with **local Lock-A package assembly only**. It may not
download weights, rent a server, start vLLM, send the eight probe requests, open
the retained population, run science, or access confirmation yet.

At minimum, Lock A still requires:

1. a separate committed authorization gate before retained population
   derivation, followed by source/exclusion/selection/request-order hashes;
2. exact checkpoint revisions, the accepted public publisher/weight plan, and
   a post-download publisher-versus-local hash verifier;
3. exact common launch commands including language-only mode, served aliases,
   vLLM 0.25.1, container digest, environment manifest, and runtime-exception
   register;
4. the public synthetic runner/orchestrator, raw capture, transfer manifest,
   v2 termination verifier, and fail-closed remote-payload allowlist;
5. the throughput-smoke runner/verifier and deterministic concurrency selection;
6. a provider quote, whole-rental wall-clock cap, and nonzero preflight-only
   spend ceiling;
7. two completed review rounds with no unresolved blocking findings.

Lock A acceptance remains false. Local assembly must preserve that boundary.
