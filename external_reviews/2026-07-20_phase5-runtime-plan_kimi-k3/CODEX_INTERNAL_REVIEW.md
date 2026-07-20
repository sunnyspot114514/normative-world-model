# Codex internal review: Phase-5 common runtime plan v1

Date: 2026-07-20

Primary commit: `3f9c16a`

Reviewed repository state: `48ef084`

Decision: **PASS_WITH_FIXES FOR LOCAL ASSEMBLY; DO NOT FREEZE THE CLIENT AGAINST V1**

K3's attempted review is incomplete and supplies no verdict. Codex completed
the remaining attacks independently and retains final project authority.

## Supported parts

- The artifact, source/config bindings, write-once rule, self-hash, independent
  rebuild, exact two-checkpoint projection, 35-file/141,225,192,536-byte total,
  and upstream weight/termination bindings all pass.
- All emitted vLLM arguments exist in official tag `v0.25.1`; `triton` is an
  allowed MoE backend and `qwen3` is a registered reasoning parser.
- vLLM's native registry maps `Qwen3_5MoeForConditionalGeneration` to its local
  Qwen3.5 implementation. Both bound publisher configs declare that
  architecture, neither model config nor tokenizer config declares `auto_map`,
  and both tokenizer configs use the built-in `Qwen2Tokenizer`. Omitting
  `--trust-remote-code` is therefore correct and safer than the historical
  runner flag.
- The two launch vectors differ only in their reviewed snapshot path and served
  alias. Loopback host, shared port, sequential order, prior-server exit rule,
  vLLM-default generation config, explicit language-only mode, bfloat16, TP=1,
  8192-token limit, eager mode, Triton MoE, Qwen3 parser, and offline flags are
  represented honestly.
- Config-semantic binding rejects revision/path drift before a changed snapshot
  path can be constructed. Artifact tampering with or without a substituted
  self-hash fails closed.
- The module and wrappers contain no subprocess, HTTP client, model downloader,
  GPU entry point, retained-data reader, or confirmation path. All execution
  authorization remains false.
- The complete repository check passed 189 tests, isolation, all preserved
  result/source locks, and `confirmation_status=RESERVED_NOT_GENERATED`.

## Required fixes

### M1 — effective environment and runtime evidence are under-specified

Severity: **blocking before the reusable client contract freezes**

The v1 plan supplies required environment values but does not state how ambient
variables are inherited or rejected. In particular, official vLLM `v0.25.1`
defaults `VLLM_SERVER_DEV_MODE=0` and registers `/server_info` only when it is
set to `1`; v1 neither pins the variable nor binds an evidence alternative.
Other ambient Python/vLLM variables can also alter the executable closure.

Fix: v2 must pin development mode off, pin user-site loading off, state a
fail-closed Lock-A environment-inheritance policy, and choose the reviewed
evidence path: exact argv/required-environment capture, raw startup and model
list responses, plus a valid public multimodal request that must be rejected by
the language-only server. `/server_info` must be recorded as unavailable unless
development mode is explicitly enabled by a future reviewed amendment.

### M2 — actual-weight verification and snapshot containment are absent from the unresolved ledger

Severity: **blocking before Lock A; fix now to prevent contract omission**

The v1 artifact binds a metadata-only publisher weight plan, but its
`unresolved_before_lock_a` list omits the required post-download
publisher-versus-local byte verifier and canonical snapshot containment check.
Without those entries, a future checklist could mistake planned weight bytes
for verified local bytes.

Fix: v2 must explicitly require an exact post-download weight verifier, regular
file/no-link checks, canonical containment below the Lock-A remote root, and
publisher-versus-local digest/size equality before either serve command.

### M3 — lifecycle and evidence-capture obligations need machine-readable placeholders

Severity: **blocking before the reusable client contract freezes**

The booleans `serve_sequentially` and `prior_server_must_exit_before_next_launch`
are correct but do not yet bind readiness, shutdown timeout, process exit,
port-release verification, raw-before-parse capture, or fail-closed evidence
status. These belong to the client, but the runtime component should expose the
candidate contract that the client must consume rather than leaving it only in
prose.

Fix: v2 must add a candidate evidence/lifecycle contract marked unimplemented
and non-authorizing, and list its implementation and review as unresolved.

## Deferred, nonblocking at this slice

- The known basename-only metadata helper remains unreachable from the runtime
  module. It still blocks final Lock-A closure unless tightened with versioned
  upstream regeneration or formally excluded with no new caller.
- Wrapper scripts and the transitive import graph are not yet the final source
  closure. That is honestly listed as unresolved; Lock A must bind the complete
  executable/import/container closure.
- Checkpoint revisions remain `PENDING_LOCK_A`, provider/container identity and
  quote remain absent, and the plan is correctly not called Lock A.

## Decision

Preserve v1 as reviewed historical evidence. Build a write-once runtime plan v2
with M1–M3 fixed, rerun the full local checks, and perform a fresh review of v2.
Only then may the reusable public-synthetic client/orchestrator implementation
begin. Model download, rental, server start, HTTP/GPU execution, retained
population access, science, and confirmation remain unauthorized.
