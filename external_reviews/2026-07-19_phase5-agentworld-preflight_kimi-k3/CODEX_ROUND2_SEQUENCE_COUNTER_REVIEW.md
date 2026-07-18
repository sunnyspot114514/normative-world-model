# Codex counter-review: Phase-5 sequence review

Date: 2026-07-19

## Disposition

**ACCEPT_WITH_AMENDMENTS.** K3's two-lock staging and corrected order are the right governance structure. The plan should be adopted with the following implementation-level amendments.

## Amendments

1. **Remote synthetic-preflight allowlist.** Lock A may locally bind the selected population and scientific request hashes, but the Stage-5 remote payload must have a separate, independently verified allowlist containing only source/runtime files and synthetic prompts. No selected project prompt, presentation text, or model-ready scientific request body may be copied to the preflight rental. The remote transfer verifier must fail on any undeclared file.
2. **Token-ID proof coverage.** A synthetic probe proves only the checker works. After population derivation, the CPU proof must compare token IDs for every locked `common_base_serialization` prompt, not only a probe subset. Lock B must repeat the comparison using tokenizer files rehashed from the served snapshots. Any single mismatch blocks the common mode.
3. **Manifest-driven weights.** Do not hardcode AgentWorld's 21-shard layout as a rule for Base. For each checkpoint, derive the exact required-file set from the publisher's index/metadata and bind every referenced file.
4. **Cost model includes fixed overhead.** The ceiling must cover download, publisher-hash verification, model load/unload, JIT/warm-up, evidence packaging/transfer, retry allowance, and inference time. A `1.5×` multiplier is only a candidate engineering choice until Stage 1 predeclares the formula; it is not accepted here as a frozen number.
5. **Minimum valid throughput evidence.** A "96 requests or 20 minutes" window needs a minimum valid generated-token count per condition; otherwise the slowest condition can time out with too little evidence. Freeze request count, concurrency, minimum measured tokens, time cap, and validity rule before rental.
6. **Delta review exception.** K3's statement that no review occurs between R2 and R3 applies only when Stage 5 follows Lock A unchanged. A forced runtime/client/source change during Stage 5 is new evidence and requires a Lock-A amendment plus delta review before another attempt. It may not be improvised on the same rental and silently carried into Lock B.
7. **Candidate science code is not Lock-A authority.** The science runner/verifier may exist and receive structural review in Lock A, but their hashes become execution-authoritative only in Lock B. Lock A must label them `candidate_only` and must not imply scientific authorization.

## Final accepted order

1. Preserve and commit the review records only.
2. Revise the protocol into explicit Lock-A/Lock-B governance.
3. Implement and test locally; obtain official tokenizer/config evidence.
4. Derive the discovery population locally and build Lock A, including a strict synthetic-only remote allowlist.
5. Complete R2 two-round review.
6. Rent one GPU instance for synthetic preflight and throughput measurement of both checkpoints.
7. Bind the new evidence, fixed/variable cost model, full-prompt serialization proof, and final runner/verifier into Lock B.
8. Complete R3 two-round review.
9. Only then consider the exploratory scientific run; verify and review its result lock before reporting.

No GPU rental, project-scenario inference, confirmation access, or scientific execution is authorized by this disposition.
