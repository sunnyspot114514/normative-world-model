# Codex post-fix review: Phase-5 common runtime plan v2

Date: 2026-07-20

Reviewed commit: `c9152f6`

Decision: **PASS FOR LOCAL CANDIDATE CLIENT DESIGN ONLY**

External status: **K3 V2 REVIEW QUEUED, NOT SATISFIED**

## Reproduction

- Stored v2 independently rebuilds and verifies with status
  `PASS_LOCAL_PLAN_V2_ONLY_EXECUTION_NOT_AUTHORIZED`.
- Runtime-plan field SHA-256:
  `b2887ba90d81cc32f9b49993853df5c97a8676341e7bf3d76de2bb1b44ac7c6f`.
- Runtime-plan file SHA-256:
  `f9a4d9c14c863473bcd8ba46248e84b1d6ac52c4a04665af37a499cafd59bc74`.
- Preserved v1 file SHA-256 remains
  `803f39375b04b419f566bac1c12ea0fb347f45d348f69c760358a6f85fb5d33f`.
- Rehashed substitutions that enabled dev-mode evidence, dropped the required
  dev-mode environment value, removed the post-download weight-verifier debt,
  disabled port-release verification, or opened HTTP authorization all differed
  from the independent rebuild.
- Full repository check: 190 tests PASS; isolation and all preserved
  source/result locks PASS; confirmation remains `RESERVED_NOT_GENERATED`.

## Fix verification

- `VLLM_SERVER_DEV_MODE=0` and `PYTHONNOUSERSITE=1` are required in both launch
  environments and in the common effective contract.
- The ambient environment allowlist is explicitly `PENDING_LOCK_A`; v2 does not
  pretend the current required-value map is a complete container environment.
- `/server_info` is explicitly not expected. The candidate evidence path uses
  exact launch/environment capture, raw startup log and `/v1/models` capture,
  plus a not-yet-built valid public multimodal request that must be rejected by
  language-only serving.
- Lifecycle obligations are machine-readable and still marked unimplemented:
  readiness, shutdown timeout, process exit capture, port release, and a hard
  ban on the second launch before release.
- The unresolved list now includes exact post-download weight verification and
  snapshot containment, environment closure, behavioral probe construction,
  lifecycle enforcement, the nested metadata-path helper debt, source closure,
  remaining provider/container/cost/revision work, and two-round Lock-A review.

## Scope of permission

This pass permits implementation of a **local, candidate-only, public-synthetic
client/orchestrator** that consumes v2 and has no active network/process/GPU
entry point by default. It does not freeze that client, satisfy the queued K3
review, accept Lock A, or authorize model download, rental, server launch, HTTP
requests, GPU use, retained-population access, science, or confirmation.
