# Phase-5 V11 Lock-A internal review — round 2 — 2026-07-22

Decision: **PASS FOR SOURCE FREEZE; NO UNRESOLVED BLOCKING FINDINGS**

Round 2 attacked the repaired candidate as a deployment boundary rather than
assuming that a passing local plan authorizes execution.

## Adversarial checks

- The V10 acceptance cannot authorize V11. The source registry is `None`, the
  V10 accepted client-plan digest differs, and execution therefore fails
  before adapter, output-directory, HTTP, or process side effects.
- Whole-file client-plan drift is now rejected independently of the semantic
  self-hash. The plan rebuild also verifies the complete transitive local
  source closure, including the concrete entry point.
- The V11 native `/v1/chat/completions` path remains the sole formal gate. The
  raw common-base `/v1/completions` path is retained as a non-gating diagnostic
  and cannot promote an arbitrary or recovered tail into pass status.
- The runtime bundle changes only its client-plan and bundle self-hashes.
  Checkpoint snapshots, runtime argv/environment, termination plan, publisher
  weight plan, and runtime-binding hash are byte-identical to the reviewed
  host binding.
- Reusing the environment manifest is acceptable only because hostname,
  kernel, disk total, Python executable hash, and vLLM executable hash were
  re-observed exactly on the same clone. The no-card session does not assert a
  live GPU. The concrete entry point must still match the previously captured
  exact GPU/driver line after GPU startup or fail closed before model launch.
- Both snapshot roots must contain exactly the bound single-link regular files.
  All 35 weight files and 16 metadata files are streamed through SHA-256 again
  before launch, followed by a stat-fingerprint check immediately before the
  subprocess starts.
- A deployment commit is still required to change exactly the acceptance JSON
  and registry literal. The source commit alone retains no execution authority.

The V11 probe remains a 20-request public-synthetic application-interface
preflight. It authorizes neither retained-population access nor a scientific
arm comparison, Lock B, confirmation generation, or any claim that isolates
checkpoint weights from the deployment package.
