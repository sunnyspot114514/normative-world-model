# Phase-5 public-synthetic evidence verifier candidate

Date: 2026-07-22

Status: **LOCAL VERIFIER CANDIDATE PASS; NOT BOUND BY CLIENT PLAN V3; LOCK A REMAINS CLOSED**

`phase5_synthetic_evidence.py` is the first independent consumer of the future
public-synthetic preflight evidence. It has no HTTP, socket, subprocess,
model-download, GPU, or retained-data entry point. It accepts already captured
evidence and fails closed against an externally supplied client-plan SHA-256
and per-checkpoint runtime bindings.

## Verified boundary

The candidate verifies:

- the exact closed V3 client plan and its termination-plan binding;
- the externally supplied snapshot, effective-environment, and argv/environment
  hashes for both checkpoints;
- AgentWorld-before-Base process/port lifecycle ordering;
- exact request set and request order, canonical request bytes, headers, seed,
  logical request ID, and the one-retry predicate;
- strict monotonic raw-before-parse and generated-text-before-JSON-parse event
  traces, including cross-request non-overlap and placement between readiness
  and battery completion;
- raw-body base64 and SHA-256 integrity;
- exact `/v1/models` alias identity;
- the source-bound 400 `BadRequestError` language-only rejection rather than a
  generic 4xx;
- duplicate-key-rejecting toy JSON, exact arithmetic semantics, strict scalar
  types, and exact final-content replay;
- all eight termination cases through the existing independent termination
  evidence verifier;
- separate, non-gating diagnostics for reasoning equality and whole-response
  byte equality.

## Two-pass internal attack review

Pass 1 found a real lifecycle gap in the initial implementation: request-list
order was checked, but request timestamps were not tied to readiness and battery
completion, so a self-consistent list could claim that the battery completed
before the requests ran. The verifier now requires strictly sequential attempt
traces after readiness and before the fsynced battery-completion event. The same
pass added plan-level closure checks, per-request identity-hash recomputation,
health-poll window checks, strict attempt-index typing, and explicit 5xx output
rules.

Pass 2 attacked retry gaming, non-semantic 400 acceptance, arithmetic drift,
duplicate JSON keys, request-byte substitution, runtime-binding substitution,
cross-checkpoint overlap, and reasoning/envelope drift. Nine focused tests pass.
The latter drift remains diagnostic by design; exact final content remains the
replay predicate.

## Remaining before Lock A

This candidate does not retroactively change or re-hash client plan V3, whose
own immutable status still says that the verifier is not built. A later V4 plan
must bind this exact verifier source after the client/orchestrator evidence
producer and concrete runtime bindings are complete. The following remain
open:

1. client raw-capture/fsync implementation and concrete HTTP adapter;
2. process/port orchestrator and bounded shutdown implementation;
3. post-download exact-weight verifier;
4. effective environment, container, provider quote, and whole-rental cap;
5. throughput runner;
6. two accepted review rounds over the complete Lock-A candidate.

No model was downloaded, no server was started, no AutoDL instance was powered
on, and no authorization flag was changed by this slice.
