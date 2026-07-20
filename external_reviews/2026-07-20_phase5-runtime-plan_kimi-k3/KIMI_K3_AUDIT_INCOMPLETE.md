# Kimi K3 runtime-plan audit: incomplete evidence record

Date: 2026-07-20

Audited primary commit: `3f9c16a`

Repository HEAD at start: `48ef084`

Status: **INCOMPLETE — NO VERDICT — QUOTA EXHAUSTED**

The K3 process exhausted its usage quota during official vLLM CLI-source
inspection. It did not return `PASS`, `PASS_WITH_FIXES`, or `BLOCK`. This file
preserves useful reproduced evidence but must not be counted as an accepted
review round.

## Completed before interruption

- Runtime plan file SHA-256 reproduced:
  `803f39375b04b419f566bac1c12ea0fb347f45d348f69c760358a6f85fb5d33f`.
- Runtime plan self-hash reproduced:
  `e6b399934ccb433d850f355d65fa697ac4f8fd00a56add694eb8074310288a6c`.
- All six recorded implementation-source hashes matched current bytes.
- Independent in-memory rebuild equaled the stored artifact.
- The two checkpoint projections summed to 35 weight files and
  141,225,192,536 publisher bytes.
- The two argv vectors were identical after replacing the snapshot path and
  served alias; their environment maps were identical.
- `VLLM_SERVER_DEV_MODE` was confirmed absent from the v1 environment.
- Write-once behavior raised `FileExistsError`, preserved the artifact bytes,
  and left no `.part` residue.
- Unrehashable mutations of authorization, port, order, alias, snapshot path,
  language-only flag, trust-remote-code flag, status, revision state, weight
  projection, source hashes, format, and sequencing were rejected by the
  self-hash check.
- Rehashed substitutions of HTTP authorization, trust-remote-code, alias, and
  Lock-A status were rejected by the independent rebuild comparison.
- Duplicate-key, non-finite, trailing-data, and double-document JSON attacks
  were rejected. Non-object JSON was accepted only by the generic inert loader
  and then rejected by the runtime-plan reader's object requirement.
- Stage-2 and termination semantic hashes recomputed exactly; mutations of
  authorization, revisions, engine version, generation mode, dtype, MoE
  backend, eager mode, language-only status, sampler mode, totals, checkpoint
  count, and termination status failed closed.
- Official tag `v0.25.1` was re-resolved to
  `752a3a504485790a2e8491cacbb35c137339ad34`.

## Not completed

- the full official-source check for every CLI value;
- the `--trust-remote-code` omission decision;
- the complete environment/network/path/sequence attack;
- the final authorization-boundary decision;
- the full local test/check run;
- a verdict on whether the reusable client/orchestrator may begin.

Those items were completed independently by Codex in
`CODEX_INTERNAL_REVIEW.md`; that does not retroactively turn this interrupted K3
run into a completed external review.

