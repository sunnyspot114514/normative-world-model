# Independent audit request: Phase-5 Stage-2 local primitives

Date: 2026-07-20

## Authority and scope

Audit the committed repository at `164228d841715d17221d620e441c67fbdb991f26` read-only. Do not modify any file. K3 is advisory: Codex will independently reproduce and adjudicate every finding.

The only expected uncommitted path is this audit-request directory. Verify HEAD and worktree scope before analysis.

This review covers two local-only Stage-2 slices:

- `9abb4b3 phase5: start local stage2 infrastructure`
- `164228d phase5: add serialization proof primitives`

The governing Stage-1 audit closure is `0b1a2c0`.

## Required reading

Read completely:

- `AGENTS.md`
- `docs/PHASE5_SCALE_INFERENCE_PROTOCOL_DRAFT.md`
- `configs/phase5_scale_inference_draft.toml`
- `docs/PHASE5_STAGE2_LOCAL_IMPLEMENTATION.md`
- `src/normative_world_model/phase5_preflight.py`
- `src/normative_world_model/phase5_serialization.py`
- `tests/test_phase5_preflight.py`
- `tests/test_phase5_serialization.py`
- `external_reviews/2026-07-19_phase5-two-lock-protocol_kimi-k3/KIMI_K3_AUDIT_REPORT.md`
- `external_reviews/2026-07-19_phase5-two-lock-protocol_kimi-k3/CODEX_COUNTER_REVIEW.md`

Inspect the exact committed diffs `0b1a2c0..9abb4b3` and `9abb4b3..164228d`.

## Mandatory verification

1. Verify HEAD, worktree scope, TOML parsing, and that every authorization/confirmation/lock field remains closed.
2. Run the two Stage-2 test modules and, if useful, the full repository check. Report commands and exact counts.
3. Confirm that neither implementation module has a network, model-download, GPU, server-execution, confirmation-access, or automatic real-corpus entry point.
4. Attack `validate_stage2_contract`: find false-PASS states, missing closed fields, mutable or ambiguous status semantics, and mismatches between Markdown/TOML/code.
5. Attack the synthetic selector against the actual `joint_examples` schema by code inspection only; do not open or execute against the real retained JSONL. Check:
   - deterministic behavior under row-order changes;
   - exact 36/12 per-environment strata and 96-family/768-presentation semantics;
   - target-pair eligibility and hash preimages;
   - hard-policy recomputation rather than all-reject inference;
   - exact presentation choice and target/source invariance;
   - exclusion behavior and STOP_WITHOUT_RELAXATION;
   - whether the API can bypass the future separate real-source derivation gate.
6. Attack `verify_remote_payload`: path normalization, undeclared files, missing files, symlinks including symlinked directories, root/path escape, duplicate normalization, empty directories, hard links, race windows, and whether a caller can falsely label project-derived content as public synthetic content.
7. Attack tokenizer-package inspection and the full-prompt equality proof:
   - whether all tokenization-relevant tokenizer JSON sections and added-token attributes are covered;
   - whether chat-template/config differences are correctly scoped;
   - whether proof rows bind the exact tokenizer snapshots used;
   - empty/duplicate prompts, token type/range, ordering, and mismatch handling;
   - local-only retention of reversible prompt token IDs.
8. Attack `resolve_publisher_weight_plan` against realistic Hugging Face metadata shapes and safetensors indexes. Check duplicate siblings, absent/extra shards, nested paths, byte counts, SHA-256 semantics, and hard-coded-count avoidance.
9. Decide whether it is safe to implement and then execute a restricted public tokenizer/config metadata downloader. Specify the minimum source/host/revision/path/size/redirect/hash controls required before any network write.
10. Point out any claim in the Stage-2 document that is stronger than the code or tests establish.

Do not treat tests as proof when direct code inspection contradicts them. Do not rely on stored reports where committed primary code is available.

## Decision standard

- `PASS`: no unresolved blocker; restricted public metadata downloader work may begin.
- `PASS_WITH_FIXES`: downloader work may begin only after bounded fixes land and Codex counter-review confirms them.
- `FAIL`: Stage-2 primitives are materially unsound or cross an authorization/data boundary.

## Required output

Return only one Markdown report with exactly these top-level sections:

1. `Verdict`
2. `Blocking findings`
3. `Non-blocking findings`
4. `Independent verification`
5. `Contract and authorization adjudication`
6. `Selector adjudication`
7. `Payload and serialization adjudication`
8. `Downloader entry decision`

For each finding, give file/line evidence, explain impact, and state the smallest correct fix. Explicitly state that your verdict authorizes neither real-source selection, model weights, GPU rental, project-scenario inference, confirmation, nor science.
