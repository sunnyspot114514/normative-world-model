# Independent Read-Only Audit Report — Phase-3 Role-Query Representation Gateway V4

Reviewer: `kimi-code/k3` · Audited commit: `e9ef49c` (working tree also contains `610b07f`, which adds only this audit request; `git diff e9ef49c..HEAD` = +71 lines, one file) · Work performed read-only; working tree verified clean before and after (`git status --porcelain` empty).

## 1. Verdict

**PASS_WITH_FINDINGS.** The preserved V4 result is internally consistent, hash-anchored, and reproducible from primary files; `BLOCKED` follows mechanically from raw `result.json` rows and frozen thresholds; the evaluation binding is exactly the V3 fallback reservation, scenario-disjoint from all prior populations, with 48 balanced buckets; confirmation was never generated and no formal/fifth-population route was opened. No defect invalidating the frozen V4 result was found. Non-blocking findings are listed in §3.

## 2. Blocking findings

None.

## 3. Non-blocking findings

1. **Low — transitive executable imports are not hash-bound in the V4 input lock.** `configs/phase3_representation_gateway_v4_input_lock.json:2-29` (`bound_hashes`) binds the directly referenced modules but not the full import closure that actually executes during the run: `src/normative_world_model/local_pilot.py` (provides `ConsistencyPair` and `build_consistency_pairs`, load-bearing for population selection via `phase3_comparison.py:11`), `transfer_matrix.py` (imported by `local_pilot.py:9`), `comparators.py` and `contracts.py` (imported by `model_output.py:10-11` and `phase2_metrics.py:12-19`), and `result_lock.py` (imported by the V1 runner at `scripts/run-phase3-anti-collapse-smoke.py:40`). The runner's cleanliness gate is path-scoped to `bound_hashes` plus the input lock (`scripts/run-phase3-representation-gateway-v4.py:185-196`), so an uncommitted edit to one of these five files at execution time would not have been caught. Mitigations verified: the execution commit `0602260` is recorded in the result (`result.json` → `git_head_before_execution`), `git diff 0602260..HEAD` shows zero changes under `src/` or `scripts/`, and the tree is clean — so these files are byte-identical between the execution commit and the audited state. The residual exposure is theoretical, not evidentiary.
2. **Low — `deterministic_training_contract` is asserted, not recomputed.** The runner hardcodes it (`scripts/run-phase3-representation-gateway-v4.py:764`), and the result verifier only checks the boolean flows into the gate (`src/normative_world_model/gateway_v4_result_lock.py:57-69`). The assertion is genuinely backed by fail-fast equality checks before report writing — rebuilt statistics/weights must equal the selection lock or the run raises (`scripts/run-phase3-representation-gateway-v4.py:718-721`), and the marker audit is re-executed and compared in validation (`:324-326`) — but a future verifier should derive the flag from those recomputations rather than trusting it.
3. **Informational — the result verifier does not re-derive summary metrics from `rows`.** `gateway_v4_result_lock.py:57-66` recomputes checks from the `evaluation` summary block and `thresholds`, not from the 48 raw rows; a result whose summary disagreed with its rows would still verify. This audit re-derived every summary metric from raw rows independently: no mismatch at 1e-9 (§4).
4. **Informational — `strict_schema_coverage` is 1.0 by construction for V4's head-based decode.** `decode_slot_predictions_v4` (`src/normative_world_model/phase3_gateway_v4.py:478-519`) emits argmax over frozen categorical support, thresholded frozen set members, and clipped/rounded scalars, so the strict parse at `scripts/run-phase3-representation-gateway-v4.py:596` cannot fail. The check is honestly reported and was frozen in advance, but it carries little discriminative information for this architecture.
5. **Informational — commitment secrets exist in gitignored `.tmp/`.** `.tmp/confirmation_v2_secret.json` and `.tmp/confirmation_v3_secret.json` are the nonces referenced by the reservation's commitment scheme (`data/generated/phase1_discovery_v3/confirmation_reservation.json:139-140`); `.tmp` is gitignored, no confirmation population file exists anywhere, and the reservation hashes match the input lock. Expected state, noted for completeness.
6. **Informational — HEAD differs from the audited commit.** HEAD is `610b07f` (adds only `external_reviews/2026-07-18_phase3-v4_kimi-k3/AUDIT_REQUEST.md`); the audited content is identical to `e9ef49c`, and the recorded execution commit `0602260` matches `result.json` → `git_head_before_execution` and the result lock.

## 4. Independent recomputations

All hashes recomputed with SHA-256 over raw bytes; all metrics recomputed from primary files with my own code, then cross-checked against the project's verifiers.

**Hash chain (all match, no exceptions):**

- `artifacts/phase3_representation_gateway_v4/result.json` = `8471c46a636f28102afe78d0d7f5376c1e03f4abdcca8647ca98b4235b50aa68` = result lock `result_sha256`.
- `configs/phase3_representation_gateway_v4_input_lock.json` = `56ce02b4ee07355f81e2eff97b0bda71ffe671e8ca840030e8a2e7de922db677` = result lock `input_lock_sha256`; identical bytes already at freeze commit `0602260`.
- `configs/phase3_representation_gateway_v4_selection_lock.json` = `0df787815cc2f16a4d77bc93515c6b934849b5d22369a3ee69f1cd9cf6e89903` = input lock `selection_lock_sha256`.
- All 24 `bound_hashes` entries (configs, locks, scripts, source modules, `requirements-model.txt`, `joint_one_step.jsonl.gz` = `37d86044…`, confirmation reservation = `f26e5b70…`, model manifest = `54c4b1d4…`) — 24/24 exact.
- All 5 preserved run files match result lock `run_files`: adapter `README.md` `9110cba9…`, `adapter_config.json` `06f5da54…`, `adapter_model.safetensors` `0cc20256…`, `role_query_heads.safetensors` `3c19a5db…`, `training_contract.json` `3dff8daf…` (content of the last equals the selection-lock statistics and weights).
- Base model: `models/qwen3-1.7b-base-ea980cb0/model.safetensors` = `6df85b39330e5a425ee36253d0f894e4387e4f0a15b9c53cb467d668e6b3a841` and `tokenizer.json` = `c0382117…`, both matching the bound snapshot manifest (`artifacts/phase3_internal/model_snapshot_manifest.json:30-39`, status PASS, revision `ea980cb0…`).
- Marker/token audit recomputed with the real tokenizer over all 2,096 presentations: `length_and_query_position_sha256` = `06d3ac0aaeec6b10faa1b88a436a9f1a1911259389b8633e3259ef03d8a25845`, lengths 572–692 tokens, 0 source-marker collisions, 0 truncations — identical to the frozen input lock.

**Gate recomputation from raw `result.json` rows vs frozen thresholds** (`configs/phase3_representation_gateway_v4.toml:97-114`; byte-equal to the repaired V3 gate, verified against `configs/phase3_diversity_gateway_v3.toml:73-87` on all 13 numeric keys):

| Check | Recomputed | Threshold | Frozen result |
|---|---:|---:|:---:|
| fixed_probe_loss_improvement | 0.168761 (3.540221→2.942770) | ≥ 0.20 | **FAIL** |
| normative_accuracy | 0.4375 (21/48) | ≥ 0.40 | PASS |
| normative_recall_per_class (min) | 0.0000 (allow 0/16, escalate 8/16, reject 13/16) | ≥ 0.20 | **FAIL** |
| decision_not_collapsed | 0.604167 (29/48 reject) | ≤ 0.85 | PASS |
| impact_not_collapsed | 1.0000 | ≥ 0.50 | PASS |
| physical_not_empty | 1.0000 | ≥ 0.50 | PASS |
| event_mae_beats_training_constant | −0.004446 (model 0.329273 vs constant 0.324826) | ≥ 0.02 | **FAIL** |
| physical_f1_beats_training_constant | +0.002083 (0.387500 vs 0.385417) | ≥ 0.02 | **FAIL** |
| event_f1_beats_training_constant | −0.056891 (0.439904 vs 0.496795) | ≥ 0.02 | **FAIL** |
| strict_schema_coverage | 1.0000 | ≥ 1.00 | PASS |
| resource_status | peak fraction 0.315565 (4,065,856,512 / 12,884,377,600 B) | ≤ 0.95 | PASS |
| deterministic_training_contract | True (backed; see §3.2) | required | PASS |

My independent 12-boolean map equals `result.json` → `gate_checks` and the result lock exactly; `all()` is false → **BLOCKED follows mechanically**, as do `status` and `next_action = terminate_local_qwen3_1_7b_path_as_engineering_null`. Every summary metric (accuracy, recalls, shares, MAE, F1 means, improvements, coverage) re-derived from raw rows matches the `evaluation` block with zero mismatches at 1e-9; training-constant baselines rebuilt from the 1,024 training pairs only (environment-conditioned; categorical typed mode, set ≥½ frequency, continuous median) score to exactly the stored constants.

**Population binding (rebuilt from raw data via the frozen selectors):**

- Training: 1,024 pairs, 1,024 unique scenario families (left/right of each pair share one `scenario_id`), binding byte-equal to `formal_training` in the base lock, V3 lock, and V4 lock (`order_sha256` `64bc85b6…`, buckets 28 × 36–37).
- Evaluation: 48 records, `order_sha256` `0ee7e5d0…`, `bucket_counts_sha256` `c6e756d3…` — byte-equal to the V3 selection lock's `fallback_reservation`, which I confirmed was already committed with identical hashes at `bd1a383`, the V3 execution commit (i.e., reserved before V3 ran, never opened since). Result rows are exactly these 48 records in order.
- Disjointness: 0 scenario overlap between training and evaluation; the selection cumulatively excludes schema-gate development, V1, formal-reserved, V2, and V3 scenario ids (`scripts/build-phase3-representation-gateway-v4-selection-lock.py:64-112`).
- Buckets: 48 unique (environment × input_condition × decision × profile) cells = 2×2×3×4, exactly one record each; targets balanced 16/16/16.
- Continuous statistics (10 slots × 2,048 presentations, ddof=0, floor 1e-6) and normative class weights (counts allow 488 / reject 1,168 / escalate 392 → 1.2187960037 / 0.7878064118 / 1.3598715847, exposure-weighted mean exactly 1.0) rebuild byte-equal to the selection lock.
- Selection lock rebuilds byte-identical end-to-end; project verifiers `verify_phase3_representation_gateway_v4_result` and `verify_phase3_diversity_gateway_v3_result` each return zero failures; 16/16 V4 unit/contract/result-lock tests pass.

## 5. Implementation and governance audit

- **Marker uniqueness / no truncation:** markers are distinct, order-frozen, required 0× in source and 1× in suffix; violations and any over-length prompt raise rather than truncate (`phase3_gateway_v4.py:141-199`), and the recomputed audit (§4) confirms 0 collisions / 0 truncations across all 2,096 presentations.
- **Role-hidden-state routing:** last token of each manually tokenized marker segment feeds only that role's `LayerNorm→Linear→GELU` trunk and its heads (`phase3_gateway_v4.py:202-264`); cross-role isolation is regression-tested (`tests/test_phase3_gateway_v4.py:139-153`).
- **Continuous statistics / decode:** population mean/std over all 2,048 training presentations only, z-score Smooth-L1 (β=0.25), decode `mean + std·raw` clipped to the frozen slot range (`phase3_gateway_v4.py:79-102`, `:510-514`).
- **Per-example normative weighting at batch size one:** unreduced CE × per-example class weight, then arithmetic mean (`phase3_gateway_v4.py:281-292`) — the batch-size-one cancellation trap is explicitly avoided and locked by a ratio test (`tests/test_phase3_gateway_v4.py:127-137`); training used batch_pairs = 1 with one optimizer step per unique pair (`scripts/run-phase3-representation-gateway-v4.py:446-480`).
- **Factual consistency loss:** implemented as frozen (symmetric JS categorical, mean symmetric Bernoulli JS sets, z-space Smooth-L1 continuous) in `phase3_gateway_v4.py:377-416`; the V4 gateway ran with `consistency_lambda = 0.0` as frozen.
- **Strict output decoding and atomic promotion:** decoded JSON round-trips through the strict parser before scoring; outputs are staged under `.tmp` and promoted with `os.replace` plus rollback on failure (`scripts/run-phase3-representation-gateway-v4.py:677-690`), and validation refuses to run if outputs already exist (`:314-317`).
- **Governance:** no `runs/` or `artifacts/` formal-comparison directories exist; no formal runner script exists in `scripts/`; V1/V2/V3 remain `BLOCKED` (V3 result re-verified independently); confirmation is `RESERVED_NOT_GENERATED` with no confirmation data anywhere; no fifth diagnostic population exists in `runs/`, `artifacts/`, or `data/generated/`. No target leakage route was found: evaluation targets are never read during training, statistics/weights/baselines derive from training pairs only, and decode consumes only model predictions plus training statistics. No metric gaming: failures are reported as failures, including negative improvements and a single `allow` prediction retained in the rows.

## 6. Claim boundary

The data support **only an engineering null for this checkpoint, budget, and path** — nothing more. Grounds: one checkpoint (`Qwen3-1.7B-Base@ea980cb0`), one budget (1,024 pairs/steps, one epoch), one representation package whose three mechanisms were changed jointly (so no per-mechanism attribution is possible, as the design doc itself states, `docs/PHASE3_REPRESENTATION_GATEWAY_V4_DESIGN.md:19-25`), `consistency_lambda = 0` (not a joint-consistency test), no factorized arm run, and an n=48 precommitted-unopened-not-blind evaluation. The result document's own interpretation boundary (`docs/PHASE3_REPRESENTATION_GATEWAY_V4_RESULT.md:44-59`) states exactly this and does not overclaim; its V3-vs-V4 comparison is correctly flagged as cross-population and non-causal. Terminating the local Qwen3-1.7B path **follows directly from the frozen contract**: the decision rule was frozen before execution (`configs/phase3_representation_gateway_v4.toml:133-138`; `docs/PHASE3_REPRESENTATION_GATEWAY_V4_DESIGN.md:113-123`), five blocking checks failed, and the failure margins are not boundary artifacts (0.1688 vs 0.20; recall 0.0 vs 0.20; −0.057 and −0.004 vs +0.02). The contract forbids, as continuations: threshold reinterpretation, extra epochs or LR search, a fifth diagnostic population, formal opening, and confirmation. `EXECUTION_PLAN.md:115-117` and `:201-211` already enact this termination correctly.

## 7. Recommended next action

Stand by the frozen outcome exactly as executed: keep `e9ef49c`'s preserved artifacts (result, result lock, run files, result document) as the terminal record of the local Qwen3-1.7B path, with Phase-3 status V1–V4 `BLOCKED`, confirmation `RESERVED_NOT_GENERATED`, H5 `UNIDENTIFIED`, and no server rental. Do not reopen thresholds, epochs, populations, formal evaluation, or confirmation under this protocol — no defect invalidating the frozen V4 result was found, so none of those continuations is warranted. Any future scale study must arrive as a separately authorized protocol per `EXECUTION_PLAN.md:211`. Optional hardening for future locks (not required by this result): bind the full transitive import closure in execution input locks, have result verifiers derive flags like `deterministic_training_contract` and re-derive summary metrics from raw rows instead of trusting the summary block.
