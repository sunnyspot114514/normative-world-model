# Phase-5 public-synthetic client plan V6 authorization audit

Date: 2026-07-22

Scope: local code, public synthetic preflight only

Decision: **PASS AS A CLOSED PLAN; EXECUTION REMAINS UNAUTHORIZED**

## Why V6 exists

V5 bound the reviewed loopback adapter and exact weight-snapshot verifier, but
its runner accepted a caller-supplied authorization mapping. A caller could
construct that mapping in memory, so the gate checked shape rather than
provenance. The first V6 draft replaced it with a self-hashed certificate and
an expected hash argument. A second internal pass found that a caller could
still construct both the certificate and the expected hash. That design
prevented accidental mutation but did not prevent self-authorization.

V6 therefore separates three properties:

1. the certificate is strict, self-hashed, time-limited, budget-limited, and
   synthetic-only;
2. the evidence bundle records the accepted certificate digest;
3. the runner obtains its trust root from the reviewed execution source, not
   from a caller argument.

The source-registered digest is deliberately `None` in this candidate. A
well-formed certificate therefore cannot start a process, create an evidence
directory, issue HTTP, or use a GPU. Registering a future digest changes an
execution source, requires a new source-bound client plan, and is an explicit
review event rather than a runtime parameter.

## New machine-enforced boundaries

- `phase5_lock_a.py` validates an exact certificate schema and exact
  synthetic-only authorization set.
- The certificate binds the client plan, runtime bindings, remote environment,
  weight-download plan, provider quote, two distinct review records, operator
  approval, validity window, maximum spend, wall-clock cap, download cap, and
  post-download disk headroom.
- Certificate validity is at most seven days; the spend hard ceiling is
  CNY 1,000 and the rental wall-clock hard ceiling is 24 hours.
- The runner has no `expected_lock_a_acceptance_sha256` parameter. It reads the
  only acceptable digest from the reviewed source registry and fails closed
  while that registry is empty.
- The runner exposes no caller-controlled wall-clock override; certificate
  validity is checked against system UTC at the execution boundary.
- Before any output directory, adapter call, process launch, or HTTP request,
  the runner re-hashes every execution source recorded by the client plan.
- Evidence format V2 binds the accepted Lock-A digest independently of its own
  self-hash.

These checks do not make the local Python process secure against an attacker
who can rewrite or monkey-patch the running program. The threat model is
governance error and accidental self-authorization in the reviewed workflow,
not a hostile machine administrator.

## Two-pass internal review

Pass 1 found that the V5 flat authorization mapping was self-asserted. It added
the strict certificate verifier, validity and resource bounds, two-review and
operator bindings, and evidence provenance.

Pass 2 rejected the first fix because its expected certificate digest remained
a caller argument. It replaced that parameter with a source-registered trust
root and added a test proving that an otherwise valid certificate is rejected
before all side effects while the registry is empty.

The targeted suite covers certificate self-hash substitution, expiry,
over-long validity, authorization expansion, review drift, quote and disk
bounds, evidence substitution, execution-source drift, and no-registry
failure. The repository-wide check result and generated V6 artifact hashes are
recorded after generation below.

## V6 artifact

- Path: `.cache/phase5_synthetic_client_plan/v6-b2887ba90d81-b752a05215d7.json`
- Client-plan SHA-256: `854b1fceb893d112cde3e382cc5a5d61cb8c558700faa5908b138057fc5073f2`
- File SHA-256: `4cead49f4c49907511cb956a8bfac989307613a750fa062b8cd821d8389b6aab`
- Bytes: `49,642`
- Confirmation status: `RESERVED_NOT_GENERATED`
- Lock-A trust root: `UNREGISTERED_FAIL_CLOSED`

V1--V5 remain preserved. V6 does not authorize AutoDL startup, model download,
server rental, process launch, HTTP execution, GPU use, retained-corpus access,
confirmation generation, or formal scientific execution.

## Remaining Lock-A work

Before any paid or remote action, the workflow still needs exact remote
runtime specs and package/container attestation, exact weight-download and
post-download snapshot plans, a current provider quote and storage policy,
memory/throughput qualification, two review records, explicit operator
approval, and a time-limited certificate. Its exact digest must then be
registered in the execution source and the resulting plan reviewed again.
