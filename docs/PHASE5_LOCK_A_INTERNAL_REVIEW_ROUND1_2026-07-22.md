# Phase-5 Lock-A internal review — round 1

Date: 2026-07-22

Decision: **PASS AFTER BLOCKING FIXES; PUBLIC-SYNTHETIC SCOPE ONLY**

## Blocking finding

The V6 trust-root registry was inside `phase5_lock_a.py`, while that same file
was included in the client-plan implementation-source hash. Registering an
acceptance digest therefore changed the client plan bound by the acceptance,
which changed the acceptance digest again. The proposed deployment had no
stable fixed point. Launching by monkey-patch or caller-supplied digest would
have reopened the self-authorization flaw that V6 was intended to close.

## Resolution

- The fixed acceptance verifier remains inside the plan-hashed execution
  closure.
- The literal trust root moved to
  `phase5_lock_a_registry.py`, which is not a client-plan input and cannot be
  supplied by a caller.
- The concrete Linux entry point is now plan-hashed.
- It requires a clean two-commit deployment: the accepted source commit must
  be the deployment commit's parent, and the deployment delta must contain
  exactly the acceptance JSON and registry source.
- The entry point rechecks the environment-manifest self-hash, Python and vLLM
  executable hashes, hostname, kernel, GPU identity, and disk headroom before
  entering the model runner.

The source closure produces client-plan V9:

- client-plan SHA-256:
  `ba5e4ac433916b40ba5054fb854c542a9875c986e7b51e57069efee46e4a4cbd`;
- path:
  `.cache/phase5_synthetic_client_plan/v9-b2887ba90d81-b752a05215d7.json`;
- requests: 20 public synthetic requests, 10 per checkpoint;
- retained data, project prompts, scientific execution, and confirmation
  generation remain closed.

## Adversarial checks

- caller-supplied or absent trust roots fail before output creation;
- source, runtime-binding, request-byte, and plan drift fail before launch;
- a dirty deployment worktree or a deployment delta wider than two files is
  rejected;
- output roots are fresh and restricted to the remote Phase-5 run directory;
- the adapter remains loopback-only and sequential, with bounded raw evidence,
  emergency cleanup, and port-release checks.

No unresolved blocking finding remains in the authorization architecture.
The repository-wide check passed 248 tests plus compile and isolation audits.
