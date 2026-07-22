# Phase-5 Lock-A new-host internal review — round 1

Date: 2026-07-22

Decision: **PASS AFTER REBINDING; PUBLIC-SYNTHETIC SCOPE ONLY**

The replacement AutoDL clone has hostname
`autodl-container-vyjukdwhue-05db523c`; the prior accepted hostname was
different. The old acceptance therefore fails closed at the live-environment
check and is superseded rather than edited in place.

The replacement host was captured from scratch before model launch. For each
of the eight pinned runtime distributions, every `importlib.metadata` file was
required to be a single-link regular file, hashed with SHA-256, and represented
as the canonical sorted list `{path, bytes, sha256}` before producing the
package fingerprint. Package versions, file counts, and aggregate byte counts
match the prior clone. Python, vLLM, GPU, driver, kernel, cgroup memory, and
data-disk identities also match; only the host identity and expected free-space
observation changed.

The V10 public-synthetic client plan, its 24-source transitive closure, the two
checkpoint snapshot manifests, termination plan, and runtime bindings remain
unchanged. The runtime bundle is re-self-hashed only to bind the replacement
environment manifest. Retained data, project prompts, scientific execution,
and confirmation generation remain closed.

No model process was started during this review.
