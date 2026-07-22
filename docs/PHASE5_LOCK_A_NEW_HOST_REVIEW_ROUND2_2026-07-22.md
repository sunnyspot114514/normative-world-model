# Phase-5 Lock-A new-host internal review — round 2

Date: 2026-07-22

Decision: **PASS FOR ONE REPLACEMENT-HOST PUBLIC-SYNTHETIC PREFLIGHT**

## Adversarial checks

- Reusing the previous acceptance was rejected because its hostname binding is
  stale, even though GPU and executable hashes match.
- The AutoDL UI independently identifies instance `vyjukdwhue-05db523c` as a
  running, pay-as-you-go RTX PRO 6000 one-GPU clone. The rate remains bound to
  the original provider quote for the same cloned configuration; credentials
  are not recorded.
- The new source-lock commit must carry the environment/runtime rebinding,
  remove the old acceptance, and reset the registry. A following deployment
  commit must again contain exactly the acceptance JSON and registry literal.
- The client plan's implementation hashes and runtime bindings must remain
  byte-identical. Any change would require a new client-plan version instead of
  this host-only rebind.
- The runner must perform the full 35-weight/16-metadata snapshot rehash before
  each checkpoint launch. Until then no snapshot claim is promoted from the
  preserved clone post-verification evidence.

The run remains an interface/loadability/termination/lifecycle preflight over
20 public synthetic requests. It does not unlock retained data, the real
selector, formal arm comparison, Lock B, or confirmation generation.
