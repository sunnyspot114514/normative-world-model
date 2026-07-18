# Kimi K3 review request: Phase-5 execution sequence and authorization gates

Date: 2026-07-19

## Reviewer role

Act as an independent, read-only protocol and execution-governance reviewer. Do not modify any repository file. Inspect primary repository files and recompute/check claims where useful. This request asks for a prospective sequencing decision, not approval of scientific execution.

Repository HEAD before this request was created:

`7653fcb27017d484b8d0118277dedc2dbde99bd7`

The current worktree contains only the uncommitted review-request/report directory from the completed AgentWorld preflight audit. Treat those files as review records, not as frozen project inputs.

## Required reading

Read completely:

1. `docs/PHASE5_SCALE_INFERENCE_PROTOCOL_DRAFT.md`
2. `configs/phase5_scale_inference_draft.toml`
3. `artifacts/phase5_agentworld_preflight_20260718/README.md`
4. `artifacts/phase5_agentworld_preflight_20260718/summary.json`
5. `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/KIMI_K3_AUDIT_REPORT.md`
6. `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/CODEX_COUNTER_REVIEW.md`

Inspect other source, test, evidence, or governance files when needed. Do not inspect or open confirmation data.

## Current proposed order to review

1. Commit the completed K3 audit request/report and Codex counter-review, while leaving the historical AgentWorld evidence immutable.
2. Revise the Phase-5 protocol so it freezes the observed AgentWorld compatibility settings, narrows replay wording to final content, adds publisher-anchored source hashes and a throughput/cost gate, and explicitly states that AgentWorld feasibility does not establish Base feasibility.
3. Implement locally, without GPU:
   - the deterministic 96-family selector and population lock;
   - executable input/prompt/schema lock;
   - common-base-serialization renderer and cross-tokenizer token-ID equality checker;
   - a reusable synthetic preflight client that gates its semantic check and stores raw responses before parsing;
   - the future scientific runner and independent verifier;
   - full project-local import-closure hashing and source-cleanliness verification.
4. Run local tests and non-GPU smoke checks.
5. Conduct Codex/K3 two-round review.
6. Only after that review, authorize a GPU rental for:
   - a Base-checkpoint synthetic preflight;
   - the base-template/common-serialization proof on the served checkpoints;
   - a small non-scientific throughput/cost smoke;
   - no project scenarios and no scientific population.
7. Ingest and bind the Base-preflight evidence, freeze the final runtime/cost ceiling, close the scientific execution lock, and audit it before any 1,536-request-per-checkpoint scientific run.

## Questions requiring an explicit decision

1. Is the order internally consistent, or does it incorrectly attempt to freeze/audit the final science runner before Base preflight can reveal required runtime changes?
2. Should governance use two distinct locks?
   - a **synthetic-preflight authorization lock** before the next GPU rental; and
   - a **scientific execution lock** after Base evidence and cost measurements are available.
3. Exactly which files/artifacts must exist for each lock? Give a concrete minimum deliverable list, not general principles.
4. Which items may be implemented before the selector opens the retained-discovery source, and which operation first constitutes opening/deriving the planned 96-family scientific population?
5. Can tokenizer/config files be downloaded and compared without GPU before the Base weight download? If so, what must be recorded and what does that prove or not prove?
6. Must the Base synthetic preflight reuse precisely the AgentWorld runtime flags, or may a checkpoint-specific flag differ? Define the rule for justified exceptions and how a difference affects the later matched comparison.
7. What minimum throughput smoke is informative without leaking scientific outputs or turning into an undeclared pilot? Specify prompts, request count/concurrency, measured quantities, and stop conditions.
8. At what exact points are Codex/K3 two-round reviews required? Avoid review loops that would add no new evidence.
9. Which current K3 findings require code/doc changes now, which should remain immutable historical notes, and which are only final-freeze requirements?
10. Give explicit go/no-go exit criteria for:
    - committing the current audit disposition;
    - authorizing the Base GPU preflight;
    - accepting Base feasibility;
    - freezing the scientific execution lock;
    - authorizing the scientific run.

## Constraints

- Do not authorize or inspect confirmation data.
- Do not run or request any project scenario before the final scientific execution lock.
- The next GPU use, if approved later, must be synthetic/infrastructure-only.
- Historical attempts and their manifests remain immutable.
- Distinguish publisher authenticity, internal byte integrity, serving feasibility, serialization equality, throughput feasibility, and scientific validity.
- Treat the Phase-5 study as exploratory retained-discovery work, never confirmation.
- Challenge the proposal. Do not accept it merely because it is cautious.

## Required output

Return one Markdown report with exactly these sections:

1. `Verdict`: ACCEPT, ACCEPT_WITH_RESEQUENCING, or REJECT.
2. `Critical sequencing findings`: ordered by severity.
3. `Corrected stage plan`: numbered stages with allowed actions, forbidden actions, deliverables, and exit criteria.
4. `Two-lock specification`: exact minimum contents of the preflight authorization lock and scientific execution lock.
5. `Runtime and serialization rules`: checkpoint-common versus checkpoint-specific settings and exception handling.
6. `Throughput smoke specification`: smallest defensible design and what it may claim.
7. `Audit schedule`: exact Codex/K3 review points and what new evidence each review consumes.
8. `Immediate next action`: the single next repository action after this report.

Do not propose running the scientific population now. Do not modify files.
