# Phase-5 public-synthetic client plan V4 candidate

Date: 2026-07-22

Status: **LOCAL V4 CORE/VERIFIER PASS; CONCRETE REMOTE ADAPTER NOT BUILT; EXECUTION NOT AUTHORIZED**

V4 binds the adapter-driven client/orchestrator core and the independent
evidence verifier added after the immutable V3 plan. It remains a local plan:
no HTTP request, process launch, model download, GPU action, rental, retained
prompt access, or scientific execution occurred.

## Artifact

Ignored write-once path:

`.cache/phase5_synthetic_client_plan/v4-b2887ba90d81-b752a05215d7.json`

- client-plan SHA-256:
  `5f5b8b60726e71f5af65e027a73bbef1ca2c8eeb45927b24dc3d619f3eb7a770`;
- file SHA-256:
  `fa85a2f8dd49402388e5d3b6be3a8f754adccb1727cc07692cffc7aca577f800`;
- bytes: 48,606;
- request count: 20;
- independent rebuild: PASS;
- all execution authorization fields: false.

V1, V2, and V3 remain present and unmodified. V4 does not retroactively alter
their findings or review history.

## Core producer and verifier

The core now:

- requires a separate exact Lock-A acceptance record before creating an output
  directory or calling an adapter;
- recomputes the complete V4 and termination-plan hashes before any side effect;
- requires externally supplied runtime hashes and a Lock-A record binding those
  hashes, instead of deriving and accepting them from the same runtime object;
- sends only the frozen request sequence through a narrow injected adapter;
- writes and fsyncs raw response bytes before response parsing and verbatim
  generated text before generated-JSON parsing;
- permits one identical retry only after a transport error or 5xx and stops on
  a second failure;
- sequences readiness, all request attempts, battery completion, shutdown, exit,
  final logs, and port release on one monotonic trace;
- preserves partial raw evidence and invokes the adapter's emergency cleanup on
  a live-path exception;
- refuses an existing output root and linked ancestors;
- independently verifies the completed bundle before writing the final PASS
  files.

## Two-pass internal attack review

The first pass found three blocking flaws in the initial core: plan integrity
was checked only after execution, runtime hashes were self-asserted, and an
unexpected live exception had no mandatory cleanup path. All three were moved
in front of execution or into the adapter contract.

The second pass added exact retry-exhaustion stopping, expected-status stopping,
per-event write-once lifecycle files, immutable normalized runtime inputs,
launch-time log capture evidence, raw-size caps, and linked-output rejection.
Nine runner tests plus the nine independent-verifier tests pass. The full local
suite at the V4 source commit passed 215 tests with isolation and retained locks
unchanged.

## Post-V4 weight-verifier slice

After the immutable V4 artifact was written, a separate read-only
`phase5_weight_snapshot.py` slice was implemented. It combines the publisher
weight plan and metadata manifest, requires an exact two-snapshot file set,
rejects symlinks/junctions/hard links/path escapes, and verifies size and SHA-256
through stable open file descriptors. It has no downloader or execution path.
Because this source post-dates V4, it is intentionally not claimed as V4-bound;
the next complete plan revision must bind it.

## Remaining before Lock A

1. concrete loopback HTTP/process adapter with emergency cleanup;
2. exact effective-environment/container/provider bindings;
3. whole-rental time and spend cap;
4. reviewed weight-download mechanism constrained to the frozen publisher plan;
5. throughput runner;
6. a new complete plan revision binding the adapter and weight verifier;
7. two accepted review rounds over that complete candidate.

AutoDL remains powered off. V4 is not Lock A.
