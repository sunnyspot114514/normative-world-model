# Codex counter-review of the Kimi K3 AgentWorld preflight audit

Date: 2026-07-19

## Disposition

**ACCEPT_WITH_CLARIFICATIONS.** K3 independently reconstructed the evidence chain and found no blocking defect in the narrow infrastructure/API preflight claim. Its `PASS_WITH_FINDINGS` verdict is supported.

This disposition does not authorize the Phase-5 scientific population, confirmation access, training, or another rental.

## Findings accepted

1. The outer archive and transfer-manifest chain verifies: the reported archive hash, manifest hash, and 48/48 bound evidence files are consistent.
2. The four final attempt exit codes and root causes reconstruct as `20`, `20`, `1`, `0`. The attempt-1 log also contains an earlier incomplete-download execution; this is a chronology/documentation nuance, not a contradiction in the stored final exit code.
3. No false-PASS path was found in the final runner/client chain for HTTP, exception, timeout, or any of the five checks in the `required` list.
4. `toy_semantics_correct` is computed and true in the retained run but is not included in the PASS gate. This is a real hardening defect. It does not invalidate the historical PASS because the retained value independently recomputes true, but any reused preflight client must gate it explicitly.
5. The README wording "two guided Chat responses byte-identical" is too broad. The enforced equality is final-content equality. Reasoning also happens to match in this run, but complete response envelopes do not because request IDs/timestamps differ.
6. Attempt 3 did not retain its raw non-JSON completion text. The error classification remains recoverable, but future clients must store the raw API envelope/text before parsing.
7. The base checkpoint, base-template serialization, cross-checkpoint token-ID equality, and protocol-scale throughput remain untested.

## Clarifications to K3

### Publisher anchoring

K3 correctly found that this **audit package** contains internally recorded per-shard hashes but does not contain the official Hugging Face/LFS reference hash set needed to independently anchor them to the publisher. Earlier operational checks reportedly compared the 21 downloaded shards with official LFS SHA-256 values, but those reference records are not in the retained package and therefore are not independently auditable here.

The correct conclusion is an evidence-scope gap, not evidence of a bad download. The Phase-5 source manifest must include the publisher-resolved revision, official per-file identifiers/hashes, downloaded-file hashes, and the comparison result in the same bound package.

### Runtime estimate

K3's performance warning is valid, but a worst-case estimate based on 2,048 generated tokens for every request is not a budget forecast. Actual output lengths, batching, concurrency, and the final science runner are not measured. Cost/time must be established by a separately authorized, non-scientific throughput smoke using the frozen serving configuration before the maximum-spend gate closes.

### Claim wording

Until publisher anchoring is packaged, the strongest precise wording is: "the revision-addressed snapshot bytes recorded by the evidence loaded and served successfully." Avoid using "publisher-authenticated exact checkpoint" based on this package alone.

## Required remediation before the next execution lock

1. Preserve the historical evidence unchanged; do not rewrite attempt logs or manifests.
2. In any future preflight/science client, add `toy_semantics_correct` (or the relevant semantic oracle check) to the required PASS list.
3. Change the evidence summary wording to "guided final contents byte-identical" and explicitly distinguish content/reasoning equality from whole-envelope equality.
4. Store raw response envelopes and raw generated text before parsing.
5. Bind official publisher provenance and the complete frozen runtime: container digest, vLLM/PyTorch/CUDA versions, server flags, environment variables, tokenizer/template files, decoding parameters, seeds, hardware, and request order.
6. Preflight the base checkpoint and prove base-rendered common serialization produces byte-identical token IDs under both frozen server tokenizers.
7. Measure throughput/cost separately before rental authorization; do not infer it from the current toy requests.

## Audit sequencing

No further review of the unchanged AgentWorld evidence bundle is necessary now. A second K3 round would have little value before remediation. The next meaningful audit target is the combined Phase-5 execution-lock package after the base preflight, serialization proof, source manifest, runner, verifier, and cost ceiling exist. That package should receive the usual two-round Codex/K3 review before any scientific request is sent.
