# Kimi K3 audit request: implemented Phase-5 two-lock protocol

Date: 2026-07-19

## Role and scope

Perform an independent, read-only audit of the **implemented Stage-1 protocol state**, not the earlier proposal. Do not modify any repository file. Do not open confirmation data, run a selector over the real retained-discovery export, download model weights, or perform inference.

Audited repository commit:

`e9da3e3` (`phase5: correct base package assumptions`)

The only expected uncommitted path is this audit-request directory. Verify that statement.

## Required reading

Read completely:

1. `docs/PHASE5_SCALE_INFERENCE_PROTOCOL_DRAFT.md`
2. `configs/phase5_scale_inference_draft.toml`
3. `docs/PHASE5_AGENTWORLD_PREFLIGHT_AUDIT_DISPOSITION.md`
4. `docs/PHASE5_TWO_LOCK_INTERNAL_REVIEW_2026-07-19.md`
5. `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/KIMI_K3_ROUND2_SEQUENCE_REVIEW.md`
6. `external_reviews/2026-07-19_phase5-agentworld-preflight_kimi-k3/CODEX_ROUND2_SEQUENCE_COUNTER_REVIEW.md`
7. `artifacts/phase5_agentworld_preflight_20260718/README.md`
8. `artifacts/phase5_agentworld_preflight_20260718/summary.json`

Inspect related primary files as needed. You may read official Hugging Face metadata at the exact revisions below to verify the internal-review claims, but do not treat `main` as equivalent to the pinned revisions:

- Base: `Qwen/Qwen3.5-35B-A3B-Base` at `0f0813072d2358973511097385626f21fcb6d422`
- AgentWorld: `Qwen/Qwen-AgentWorld-35B-A3B` at `60d2b0434a53d2e62a7c00a489586815d94ebffb`

## Audit questions

1. Does the two-lock split remove the previous contradiction between pre-rental authorization and post-smoke runtime/cost knowledge?
2. Can any current status/boolean/wording be misread as authorizing model download, rental, population inference, science, or confirmation?
3. Are the Markdown protocol, TOML, disposition, and internal review mutually consistent?
4. Recheck the exact-revision metadata claims:
   - both configs declare `Qwen3_5MoeForConditionalGeneration` and `vision_config`;
   - both tokenizer configs contain thinking-enabled native chat templates;
   - both tokenizer JSON files have the same 248,044-entry core vocabulary and identical shared token IDs;
   - AgentWorld alone adds IDs 248066–248069 for tool-response/think markers.
5. Is setting `native_base_reasoning_enabled = true` the correct package-level interpretation? Is treating `--language-model-only` as a common candidate for both checkpoints better supported than the prior AgentWorld-only example?
6. Is the common-serialization proof adequate: synthetic checker probe before derivation, all locked common prompts after derivation, and served-snapshot repetition before Lock B?
7. Does Lock A safely bind scientific hashes locally while guaranteeing that no project prompt text or scientific request body enters the synthetic remote payload? Identify any missing fail-closed contract.
8. Audit the throughput design:
   - protocol-shaped versus decode-ceiling separation;
   - total rendered prompt-token targets and the 8,192/2,048 budget;
   - candidate grid `[1, 8, 16, 32]` and all-checkpoint/all-mode selection rule;
   - three 8,192-token windows and CV ≤ 0.20;
   - fixed plus variable cost formula and 1.5 multiplier;
   - whether the evidence minimum can still pass with an unmeasured cell or unstable condition.
9. Does the delta-review rule prevent an on-rental compatibility fix from silently entering Lock B?
10. Are K3's earlier recommendations correctly categorized as accepted, modified, or rejected? Point out any Codex counter-review correction that is itself wrong or unsupported.
11. What exact missing Stage-2 artifacts should be implemented next? Is Stage 2 safe to begin locally without deriving the real population or authorizing external execution?

## Required verification

At minimum:

- verify HEAD and worktree scope;
- parse the TOML;
- verify all authorization and confirmation fields remain closed;
- inspect the exact committed diff from `7653fcb` through `e9da3e3`;
- recompute/check the internal metadata observations where feasible;
- check the 6,000 + 2,048 token arithmetic and clarify that 6,000 means the total rendered prompt;
- find contradictions, false-PASS states, ambiguous field types, and unbound decisions;
- do not rely on stored summaries when primary files are available.

## Decision standard

- `PASS`: no unresolved blocker; Stage 2 local implementation may begin.
- `PASS_WITH_FIXES`: Stage 2 may begin only after listed bounded fixes land and are counter-reviewed.
- `FAIL`: the lock design or authorization boundary remains materially unsound.

No verdict may authorize real population derivation, model weights, GPU rental, project-scenario inference, confirmation, or science.

## Required output

Return one Markdown report with exactly these sections:

1. `Verdict`
2. `Blocking findings`
3. `Non-blocking findings`
4. `Independent verification`
5. `Cross-file consistency`
6. `Throughput and serialization adjudication`
7. `Authorization boundary`
8. `Stage-2 entry decision`

Do not modify files. Return only the report.
