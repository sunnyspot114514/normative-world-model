# Codex final adjudication: Phase-5 termination v2

Date: 2026-07-20

K3 report: `KIMI_K3_ROUND2_REPORT.md`

Reviewed fix commit: `e04e022`

Repository state independently checked: `d2c5b38`

Decision: **ACCEPT_WITH_CORRECTION FOR LOCAL LOCK-A ASSEMBLY ONLY**

## Review-round accounting

The completed K3 run is accepted as the first valid external review round for
this termination-v2 slice. The quota-interrupted run remains evidence only and
does not count. This Codex adjudication is the second independent counter-review
round for the slice. It does not accept Lock A, does not review the later
runtime-plan module on its merits, and does not authorize execution.

## Independently reproduced

- The v2 plan file, semantic-config hash, plan self-hash, five implementation
  records, eight request-body hashes, tokenizer-probe binding, and stored v1
  preservation all recompute.
- The official vLLM `v0.25.1` stop path supports the v2 contract: request-level
  explicit stop IDs plus `ignore_eos=true` produce integer `stop_reason`; the
  stop-terminated token remains in returned token IDs but is excluded from
  completion text when `include_stop_str_in_output=false`; the completion
  object is `text_completion`; total usage is prompt plus completion tokens.
- Targeted termination/runtime tests ran 10/10 PASS.
- The complete repository check ran 189 tests PASS, the isolation audit PASS,
  every preserved source/result lock PASS, and confirmation remained
  `RESERVED_NOT_GENERATED`.
- The basename-only helper weakness is real:
  `validate_public_metadata_path("subdir/tokenizer.json")` currently accepts the
  nested spelling. Current callers still fail closed through fixed flat
  publisher intersections and exact bundle-set verification.

## Correction to the K3 report

K3 correctly identified `/server_info` as a useful resolved-runtime evidence
source, but omitted its enablement guard. In official vLLM `v0.25.1`:

- `vllm/entrypoints/openai/api_server.py:198-201` registers the development API
  routers only when `envs.VLLM_SERVER_DEV_MODE` is true;
- `vllm/envs.py:1312-1315` defaults `VLLM_SERVER_DEV_MODE` to `0`;
- `/server_info` is defined in the development router at
  `vllm/entrypoints/serve/dev/server_info/api_router.py:43-59`.

The current runtime plan does not set `VLLM_SERVER_DEV_MODE`, so `/server_info`
is not presently a reachable evidence source under that plan. This does not
invalidate termination v2: the runtime runner and capture contract are still
explicitly unresolved and outside the termination-plan artifact. It does mean
the later runtime-plan/client review must not silently assume `/server_info`
exists. Before the reusable runner is frozen, the project must choose and bind
one of these reviewed alternatives:

1. explicitly enable development mode on loopback for both servers and bind the
   raw `/server_info?config_format=json` captures, including the extra endpoint
   and disclosure surface; or
2. leave development mode disabled and bind equivalent evidence through exact
   argv/environment capture, startup logs, `/v1/models`, and a reviewed
   language-only behavioral preflight.

No current artifact may claim resolved-runtime evidence before that choice is
made.

## Finding dispositions

### Termination-v2 semantic and evidence contract

Disposition: **accepted**. No unresolved blocker was found in the local plan or
offline evidence verifier.

### Nested public-metadata path helper

Disposition: **nonblocking for continued local assembly, blocking for final
Lock-A executable-closure freeze**. The helper must be tightened with versioned
regeneration of dependent public artifacts, or the final closure must prove it
unreachable and prohibit new callers. It is not permission to accept nested
metadata paths.

### Remote evidence authenticity

Disposition: **expected current boundary, blocking before rental**. The offline
verifier proves schema and semantic consistency only. A future reviewed runner,
raw-before-parse capture, request ordering, transfer manifest, and external
plan-hash binding must establish provenance.

### Language-only runtime evidence

Disposition: **termination review accepted; runtime review still required**.
The exact `--language-model-only` CLI requirement is supported, but effective
runtime evidence remains a task for the runtime-plan/client slices, with the
development-route correction above.

## Authorized continuation

The project may proceed only with the queued read-only audit of the common
runtime launch plan and then, if accepted, local construction of the public
synthetic client/orchestrator. Model download, rental, HTTP/GPU execution,
retained-population access, scientific inference, and confirmation remain
unauthorized.

