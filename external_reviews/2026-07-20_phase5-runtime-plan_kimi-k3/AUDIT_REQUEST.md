# Kimi K3 audit request: Phase-5 common runtime launch plan

Date: 2026-07-20

Reviewer: `kimi-code/k3`

Primary commit: `3f9c16a`

Termination v2 dependency: `e04e022`

Status: **QUEUED — K3 QUOTA UNAVAILABLE AT CREATION**

Perform a read-only adversarial audit. Do not modify files, open the retained
corpus, derive the real population, download/open weights, start a server, use a
GPU, access confirmation, or send HTTP/scientific requests.

## Scope

- `src/normative_world_model/phase5_runtime_plan.py`;
- `tests/test_phase5_runtime_plan.py`;
- both runtime-plan scripts and the Stage-2 documentation update;
- ignored artifact
  `.cache/phase5_runtime_plan/v1-2a23d1973113-1a8cdbf5f807.json`;
- the verified public weight and termination-v2 artifacts on which it depends.

## Required attacks

1. Independently rebuild the runtime artifact and verify its self-hash,
   source/config bindings, transitive public-artifact bindings, exact two-
   checkpoint identity, 35-file/141,225,192,536-byte projection, write-once
   behavior, and rejection after tampering or rehash substitution.
2. Check official vLLM tag `v0.25.1` for every emitted CLI argument and decide
   whether the two vectors are valid and equivalent apart from the snapshot
   path and served alias. In particular audit `--language-model-only`,
   `--generation-config vllm`, `--moe-backend triton`, `--reasoning-parser
   qwen3`, eager mode, dtype, TP, model length, max sequences, GPU memory, host,
   and served-model-name.
3. Decide whether omitting `--trust-remote-code` is correct for both pinned
   `Qwen3_5MoeForConditionalGeneration` packages under vLLM 0.25.1. A claim that
   it is required must cite exact publisher bytes or official vLLM source, not
   the historical runner's flag alone.
4. Attack the offline boundary: environment drift, network fallback, absolute
   or escaping snapshot paths, alias drift, shared-port sequencing, failure to
   stop the prior server, checkpoint order, and a way to read the plan as
   authorizing execution.
5. Verify that `PENDING_LOCK_A` revisions, missing container/quote/client/
   throughput/source-closure/review components, and all false authorization
   flags are represented honestly. The artifact must not be called Lock A.
6. Search for any subprocess, HTTP, download, GPU, retained-data, or
   confirmation entry point in the new scope. Run the full local check and any
   additional read-only tamper probes.

Return `PASS`, `PASS_WITH_FIXES`, or `BLOCK`, separating blocking and
nonblocking findings with exact file/line evidence. State whether the runtime
plan may remain a component of **local Lock-A assembly only** and list any
required fixes before the reusable client/orchestrator slice begins.
