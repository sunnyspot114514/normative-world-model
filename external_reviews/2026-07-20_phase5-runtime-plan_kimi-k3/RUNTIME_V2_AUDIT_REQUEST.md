# Kimi K3 audit request: Phase-5 common runtime plan v2

Date: 2026-07-20

Primary fix commit: `c9152f6`

Superseded runtime-plan commit: `3f9c16a`

Status: **QUEUED — K3 QUOTA EXHAUSTED DURING V1 REVIEW**

Perform a fresh read-only audit. Treat `KIMI_K3_AUDIT_INCOMPLETE.md` only as an
incomplete evidence record; it is not a verdict. Do not modify files, open the
retained corpus, derive the real population, download/open weights, start a
server, use a GPU, access confirmation, or send HTTP/scientific requests.

## Required inputs

- `AUDIT_REQUEST.md` and `CODEX_PRE_REVIEW_ADDENDUM.md`;
- `KIMI_K3_AUDIT_INCOMPLETE.md` and `CODEX_INTERNAL_REVIEW.md`;
- commit `c9152f6` and parent `48ef084`;
- ignored v2 artifact
  `.cache/phase5_runtime_plan/v2-2a23d1973113-1a8cdbf5f807.json`;
- preserved v1 artifact and the verified public weight/termination artifacts.

## Required attacks

1. Rebuild v2 and verify source/config/upstream bindings, write-once path,
   self-hash, file SHA-256, exact two launch vectors, totals, and v1
   preservation.
2. Recheck every CLI value against official vLLM tag `v0.25.1`, including the
   native `Qwen3_5MoeForConditionalGeneration` registry and the omission of
   `--trust-remote-code`.
3. Attack the new environment contract. Confirm development mode and user-site
   loading are pinned off, `/server_info` is not claimed reachable, the future
   ambient allowlist remains pending rather than falsely frozen, and any
   rehashed environment substitution fails the independent rebuild.
4. Attack the evidence/lifecycle contract. It must remain unimplemented and
   non-authorizing while requiring raw-before-parse launch/environment/log/model
   capture, a valid public language-only behavioral rejection probe, readiness,
   shutdown timeout, process exit, and port release before the second launch.
5. Confirm the unresolved ledger now includes post-download exact weight
   verification, regular-file/link-safe canonical snapshot containment,
   environment closure, lifecycle enforcement, the nested-path helper debt,
   source closure, cost/container/revision gates, and two-round review.
6. Search for any execution or network entry point, rerun the complete local
   check, and state whether local candidate-only client/orchestrator design may
   begin. Nothing may authorize model download, rental, HTTP/GPU execution,
   retained-population access, science, or confirmation.

Return `PASS`, `PASS_WITH_FIXES`, or `BLOCK`, with blocking and nonblocking
findings separated. This review may be counted only if it completes with a
verdict.

