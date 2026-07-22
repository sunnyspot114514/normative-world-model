# Phase-5 public-synthetic preflight result — 2026-07-22

Decision: **FAIL AS PRECOMMITTED; PRESERVE THE RUN; DO NOT UNLOCK SCIENCE**

## What succeeded

- Both frozen checkpoints were fully rehashed before launch: 35 weight files
  and 16 public metadata files.
- Both vLLM servers reached readiness, completed 10/10 requests, exited with
  code 0 after graceful SIGTERM, required no forced termination, and released
  loopback port 8000 before the next lifecycle step.
- All 20 request byte strings, raw-response hashes, generated-text hashes, and
  ordered attempt traces independently reverified.
- Runtime identity and text-only negative probes passed for both checkpoints.
- All eight explicit termination-token cases passed the frozen termination
  verifier.
- Each of the four checkpoint × serialization repeat cells was byte-stable at
  the generated-text level.

## The actual failure

AgentWorld passed the native `/v1/chat/completions` path twice: reasoning was
separated into the response's reasoning field and final content was the exact
JSON oracle. It failed the common `/v1/completions` path twice in exactly the
same way: the `text` field was

```text
<think>...reasoning...</think>{"checksum":"PUBLIC-17-5","difference":12,"sum":22}
```

The tail after `</think>` is semantically correct, but the frozen gate requires
the raw final field itself to be valid JSON. Base returned strict JSON on both
native and common paths. The independent verifier therefore stopped at
`agentworld-common_base_serialization-toy-repeat-1` with the preserved error
`invalid inert JSON content`.

This is not an arithmetic failure, sampling noise, transport failure, or
verifier false positive. It is deterministic reasoning-envelope leakage on the
raw text-completion path. Stripping `<think>` after seeing the result would
retroactively weaken the gate and is not allowed for this run.

## Residual runtime observations

The server logs contain non-fatal warnings that SM 12.x capability inspection
prefers CUDA 12.9 or newer, that the RTX PRO 6000 lacks a tuned vLLM MoE config,
and that first-request Triton kernels were JIT compiled. Both models nevertheless
loaded and served correctly. These warnings preclude throughput claims from
this preflight but do not explain the semantic failure.

## Decision boundary

The preserved failure answers the narrow V10 question: native structured output
works, while a supposedly common raw completion serialization is not output-
equivalent for AgentWorld. No retained corpus, project prompt, formal arm
comparison, Lock B, or confirmation data was used.

Before another GPU run, a new version must explicitly choose one of two
estimands:

1. application-level compatibility through native chat structured output; or
2. raw common-prompt compatibility, with reasoning-envelope leakage retained as
   a first-class failure rather than silently normalized.

Any version that adds a documented envelope extractor must report both raw
strict-JSON success and extracted-tail semantic success. It cannot relabel this
V10 run as passing.

The evidence archive is retained locally at
`artifacts/phase5-lock-a/v10-newhost-attempt1-evidence.tar.gz`, SHA-256
`f20870e26c40f9b073576542047c45ce54650ae32b2167ed892db9be7370e9f6`.
The replacement AutoDL instance was confirmed shut down after evidence transfer.
