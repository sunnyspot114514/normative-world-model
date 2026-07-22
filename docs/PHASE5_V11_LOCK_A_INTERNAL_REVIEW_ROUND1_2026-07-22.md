# Phase-5 V11 Lock-A internal review — round 1 — 2026-07-22

Decision: **PASS SOURCE CANDIDATE; PUBLIC-SYNTHETIC SCOPE ONLY**

This review covers the V11 source candidate after the failed V10 result and
before any V11 GPU process or HTTP request. V10 remains
`FAIL_PRECOMMITTED_SEMANTIC_GATE`; no V10 evidence was relabelled or replaced.

## Finding and repair

The first pass found that `client_plan_file_sha256` was present in the Lock-A
acceptance schema but was not consumed by the concrete Linux entry point. The
semantic client-plan self-hash still failed closed on semantic drift, but the
declared whole-file byte commitment was not enforced. The entry point now
hashes the single-link regular plan file and compares it with the accepted
digest before reading the plan. A negative test mutates the file after the
accepted digest is computed and requires rejection.

Because the entry point is in the transitive implementation closure, the V11
plan was rebuilt rather than patched in place:

- semantic client-plan SHA-256:
  `d85104f01375d18a772d25e3ef5b81f26503f09c39a62eb028c73be1a4d7a3d9`;
- whole-file client-plan SHA-256:
  `c8f0554485f9821fbade122eb9e9cb6bab1d862521130431487040bf7f6e0091`;
- V11 freeze self-hash:
  `55bd8f3d47a3b66411124b2856975571b64a967b52837ba6b380aba8691c81c3`;
- Lock-A runtime-bundle self-hash:
  `bf6c648c8c54ef4373ea872b7339f80c481b349f68ece0d89d81ec82f90d5c42`.

The runtime-binding hash remains
`04f66ef99f081a1c139d772a187dfdb97eda65435ffe7d8c254702ddd3e17af5`:
the change affects the accepted client-plan bytes, not either checkpoint's
model snapshot, argv, or effective environment.

## No-GPU environment evidence

The AutoDL clone was inspected read-only in no-card mode. It reported hostname
`autodl-container-vyjukdwhue-05db523c`, kernel `5.15.0-78-generic`, data-disk
total `375809638400` bytes and free space `149134827520` bytes. No GPU was
visible and no vLLM or Phase-5 process was running. The Python and vLLM
executable hashes exactly matched the existing host manifest.

The preserved source and clone post-verification records independently bind
35 weight files / `141225192536` bytes and 16 public metadata files /
`46074242` bytes, with result hashes
`52c7fffb1ff8209b8b86cdfa675bf09cd816e5dd9439bedc641bd4f0f0906061`
and
`8b637956cfb11758da3d822d916c4ca8b2e0680714396ec3b7a6763764fb358d`.
The launch adapter will re-hash the exact file set again immediately before
each checkpoint launch.

After the repair, the complete repository check passed: 255 unit tests,
project-isolation audit, V11 independent plan rebuild, and all preserved
Phase-1/Phase-3 result locks were green.

No retained corpus, project prompt, confirmation content, model service, GPU
execution, or scientific experiment was accessed during this review.
