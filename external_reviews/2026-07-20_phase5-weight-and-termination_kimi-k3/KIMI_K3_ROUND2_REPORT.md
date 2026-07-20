# Kimi K3 round-2 audit report: Phase-5 termination v2 and counter-review

Date: 2026-07-20

Reviewer: `kimi-code/k3` (fresh, independent run; `KIMI_K3_ROUND1_INCOMPLETE.md` treated as incomplete evidence, never as a verdict)

Fix commit audited: `e04e022`; repository state audited: clean worktree at `d2c5b38` (HEAD includes `3f9c16a` runtime plan, noted below)

Boundary kept: read-only throughout. No file modified/created/deleted/staged. No retained corpus, no population derivation, no weights, no server, no GPU, no confirmation, no scientific requests. Network used only to read official vLLM `v0.25.1` source.

## Verdict: PASS_WITH_FIXES (local Lock-A package assembly only)

All blocking-class concerns from round 1 are resolved and independently reproduced. Two nonblocking debts remain (N1, N2 below), both already recorded by the project. No blocking finding.

---

## 1. v2 plan rebuild and hash chain (attack 1) — PASS

Independent in-memory rebuild and byte-level checks of the ignored artifact `.cache/phase5_common_termination_probe_plan/v2-1a8cdbf5f807.json`:

- Plan-file SHA-256 `9d663e7d7f707bf51a66061bf79ff873e7977f1002985a946365723e9f2e8855` — matches Codex's recorded value.
- Self-hash recomputed over the document minus `plan_sha256`: `b752a05215d735a5d33e4fb3a70e740876afe2a695759d78ded5828468610002` — matches the field.
- Config semantic SHA-256 recomputed from `configs/phase5_common_termination_probe_candidate.toml`: `1a8cdbf5f8071c27f31c1e04ec026655d922703c8aa8c4b30bfcc1a8a485018c` — matches `TERMINATION_CONFIG_SEMANTIC_SHA256` (`src/normative_world_model/phase5_termination_probe.py:25-27`) and the plan field.
- All five `implementation_sources` records match live file bytes/SHA-256.
- All eight `request_body_sha256` values recompute exactly; the case set is exactly `{agentworld,base} × {248044,248046} × {repeat 1,2}`.
- The plan binds the live tokenizer probe artifact hash `57aa5fe28faab15d…c4ceee86970`.
- Write-once: `default_common_termination_probe_plan_path()` resolves to the v2 path; calling `_write_plan_once` against the existing artifact raises `FileExistsError` before any write (artifact SHA-256 unchanged afterward, no `.part` residue).
- Preservation: `v1-832c06e718b9.json` still present, its own self-hash `d76811eb…` still valid, still `phase5-common-termination-plan-v1` bound to the old config hash `832c06e7…` — superseded, not rewritten.
- `scripts/verify-phase5-common-termination-plan.py` → `PASS_PLAN_ONLY_EXECUTION_NOT_AUTHORIZED`, `http_execution: false`.

## 2. Official vLLM v0.25.1 adjudication (attack 2) — all seven claims CONFIRMED

Tag `v0.25.1` resolves to commit `752a3a504485790a2e8491cacbb35c137339ad34` (GitHub ref API), matching Codex's claim. I read the raw files at that tag and confirm each claim independently:

1. **`--generation-config vllm` suppresses checkpoint generation defaults** — `vllm/config/model.py:1501`: `config = {} if src == "vllm" else self.try_get_generation_config()`, plus docstring at `model.py:290-296`. Caveat I verified: `try_get_generation_config()` (`model.py:1463-1470`) still reads the checkpoint's `generation_config.json` for EOS bookkeeping, but with `ignore_eos=true` that path only feeds `_all_stop_token_ids` (min-tokens machinery, inactive at `min_tokens=0`) and never `stop_token_ids` or `_eos_token_id` (`vllm/sampling_params.py:633-655`). No sampling default leaks.
2. **`ignore_eos=true` + explicit `stop_token_ids=[248044, 248046]` makes both tokens take the explicit-stop branch** — `sampling_params.py:633-634` sets `_eos_token_id` only when `not ignore_eos`, so the primary-EOS comparison in `check_stop` (`vllm/v1/core/sched/utils.py`, `last_token_id == sampling_params.eos_token_id`) compares against `None` and can never fire; both tokens are in the request's `stop_token_ids` and hit the explicit branch.
3. **Explicit branch reports the integer token ID; default EOS reports `None`** — `check_stop` sets `request.stop_reason = last_token_id` only on the explicit `stop_token_ids` branch; the EOS branch returns without setting it. `vllm/entrypoints/openai/completion/protocol.py:525-531` documents `stop_reason` as "None if the completion finished for some other reason including encountering the EOS token".
4. **`allowed_token_ids=[forced_id]` forces the one permitted token** — `vllm/v1/worker/gpu_input_batch.py:427-448` builds a per-request vocab mask with only the allowed IDs unmasked; `vllm/v1/sample/sampler.py:396-397` applies `logits.masked_fill_(mask, float("-inf"))`. Only the forced token is samplable.
5. **`return_token_ids=true` returns generated and prompt token IDs** — non-streaming path `vllm/entrypoints/openai/completion/serving.py:576-583`: `prompt_token_ids` and `token_ids` are populated iff `request.return_token_ids`.
6. **`include_stop_str_in_output=false` makes the first forced stop token's completion text exactly empty, even with `skip_special_tokens=false`** — `vllm/v1/engine/output_processor.py:639-641` passes `stop_terminated = (finish_reason == FinishReason.STOP)`; `vllm/v1/engine/detokenizer.py:107-113` drops the final token from detokenization before decoding (then re-appends it to `token_ids`, lines 124-126). Exclusion happens at token-ID level, so `skip_special_tokens=false` cannot resurrect the text. One-token generation ⇒ `text=""`. K3 round-1's tentative literal-text fix was indeed not source-correct; Codex's C2 empty-string adjudication is right.
7. **`/v1/completions` reports `object="text_completion"` and `total_tokens=prompt+completion`** — `protocol.py:550` (`object: Literal["text_completion"]`), `serving.py:601-605` (`total_tokens=num_prompt_tokens + num_generated_tokens`).

Corollary design check: with `ignore_eos=false`, a forced token equal to the checkpoint's default EOS would hit the primary branch first and report `stop_reason=None` — indistinguishable. The plan's `ignore_eos=true` is therefore necessary, not cosmetic. `min_tokens=0` keeps the stop check live at one token; `max_tokens=4` means a failed `allowed_token_ids` clamp yields `finish_reason="length"`/`stop_reason=None`, which the verifier rejects — fail-closed.

## 3. Adversarial probes against the v2 evidence verifier (attack 3) — no false pass found

Loaded the stored v2 plan, built a valid synthetic eight-row evidence set in memory (baseline: `PASS`, 8 cases, 4 checkpoint/stop cells), then ran 56 mutations. All rejected with the expected fail-closed errors:

- Response object: wrong value, missing, bool, case-variant — rejected (`phase5_termination_probe.py:435-436`).
- Text: `<|endoftext|>`, `<|im_end|>`, null, single space — rejected (exact `""` binding, line 447).
- Usage: missing/bool/32/34/float `33.0` `total_tokens`; `completion_tokens=2`; `prompt_tokens=31` — rejected (lines 456-469).
- Stop semantics: null/string/bool/wrong-token `stop_reason`; extra/wrong/empty `token_ids`; truncated/extended `prompt_token_ids`; `finish_reason="length"`; `index=1` — rejected (lines 443-455).
- Binding: wrong model alias, HTTP 201, `seed` drift, `allowed_token_ids` drift, wrong/uppercase/non-hex external plan hash, tampered plan body/self-hash/prompt-count/missing-case/extra-case — all rejected (self-hash at lines 400-402, external binding at 393-399, request-body hash at 406-408).
- Structure: missing/extra/duplicate evidence case, extra/missing row key, two/empty choices, missing usage, repeat drift, oversized raw (>2 MiB) — rejected.
- Inert JSON: duplicate keys, `NaN`, `Infinity`, trailing garbage, double document, non-string raw — rejected before semantics (`_load_inert_json`).

Expected boundary (not a false pass): a fully fabricated but internally consistent eight-row set passes this offline schema verifier — it has no network client by design. Remote authenticity must come from the Lock-A capture chain (runner, raw-before-parse capture, transfer manifest, external plan hash). This matches Codex's C4. Note also that replaying one repetition's response into its sibling repetition passes by design — the repetitions exist to prove semantic equality, and their request bodies are byte-identical.

## 4. Deferred `subdir/tokenizer.json` observation (attack 4) — adjudicated: unreachable, nonblocking, pre-Lock-A debt

- Weakness confirmed: `validate_public_metadata_path` (`src/normative_world_model/phase5_serialization.py:72-89`) allowlists `path.name`, so `validate_public_metadata_path("subdir/tokenizer.json")` returns `'subdir/tokenizer.json'`.
- Every current caller fails closed, demonstrated in memory:
  - `_publisher_file_plan` (`phase5_public_metadata.py:332-341`) intersects siblings against the fixed flat `REQUESTED_METADATA_FILENAMES` (`:42-54`); a crafted publisher body containing `subdir/tokenizer.json` and `evil.safetensors` yields a flat-only plan.
  - `_download_checkpoint` (`:398-415`) fetches/writes only flat plan paths.
  - `_verify_public_metadata_bundle` (`:663`, `:713-718`) rejects any downloaded row not equal to the flat publisher plan and enforces the exact on-disk set — an added nested file fails `actual_paths != expected_paths`.
  - `inspect_tokenizer_packages` (`phase5_serialization.py:127`) runs only after `verify_public_metadata_bundle` passes (`phase5_tokenizer_probe.py:236-240`); a nested file would also change the package report → probe hash → independent-rebuild mismatch.
- Disposition: does **not** block local Lock-A assembly. Before the Lock-A executable closure freezes, the project must either repair the helper to exact-flat matching with versioned regeneration of all dependent public artifacts, or explicitly record the helper as excluded from the closure and add no new caller that could trust a nested path. Codex's C3 stands.

## 5. Language-only serving vs vLLM 0.25.1 (attack 5)

Both public checkpoint `config.json` files (ignored public cache, previously reviewed) declare `Qwen3_5MoeForConditionalGeneration` with `vision_config`, `image_token_id`, `video_token_id` — multimodal.

- Exact server argument Lock A must bind for **both** checkpoints: **`--language-model-only`** on both `vllm serve` commands. Verified in official source: `vllm/engine/arg_utils.py:553,1240-1242` (CLI → `EngineArgs.language_model_only` → `MultiModalConfig`), `vllm/config/multimodal.py:77-79` ("If True, disables all multimodal inputs by setting all modality limits to 0"). `vllm/config/model.py:425-431` includes `language_model_only` in the model-config hash factors because it can change the language-model compute graph — so a divergent setting between the two servers is a divergent effective runtime, and Lock A must fail on it.
- Returned runtime evidence Lock A must bind per server: the resolved effective config from vLLM 0.25.1's dev **`/server_info`** endpoint (`vllm/entrypoints/serve/dev/server_info/api_router.py:43-57`, text or JSON dump of `VllmConfig`, which exposes `multimodal_config.language_model_only=true`), captured raw-before-parse; the served alias from `/v1/models`; and the startup log lines. The Lock-A runtime manifest must compare both captures against the plan and against each other and fail closed on any difference. A negative multimodal preflight (mm request rejected at limit 0) is a valid additional check but belongs to the authorized preflight phase, not to local assembly.
- Context note: HEAD's `phase5_runtime_plan.py:124,288` (commit `3f9c16a`, queued for its own separate review) already encodes `--language-model-only` and `language_model_only: True`. I audited the requirement, not that module; its consistency with the official argument is noted without rendering a verdict on it here.

## 6. Authorization boundary (attack 6) — intact

- `configs/phase5_common_termination_probe_candidate.toml:4-10`: all six execution flags false; v2 plan copies them; verifier output `http_execution: false`.
- `configs/phase5_scale_inference_draft.toml:6-18,21,27,54`: `model_download/server_rental/synthetic_preflight_lock_accepted/synthetic_preflight_rental/scientific_execution_lock_accepted/scientific_run/performance_inference/confirmation_generation/independent_confirmation/population_selection` all false; `confirmation_status = "RESERVED_NOT_GENERATED"` (confirmed live by check.ps1 output).
- Only network import in Phase-5 source is the previously reviewed restricted public-metadata fetcher (`phase5_public_metadata.py:21`), building huggingface.co URLs solely from frozen public identities; `phase5_public_weight_plan.py` and `phase5_termination_probe.py` have no network client. No launcher, rental, GPU, population, confirmation, or science path is authorized anywhere in this scope.

## 7. Full local check (attack 7)

`scripts/check.ps1` (PowerShell, project-local env): compileall OK, isolation audit OK, all preserved phase-1/phase-3 result/source-lock verifiers PASS, `confirmation_status: RESERVED_NOT_GENERATED` in every report. Unit tests: **189 ran, OK** (Codex reported 185 at `e04e022`; the delta is the four runtime-plan tests added by `3f9c16a` — explained, not a discrepancy). Additional read-only verifiers: tokenizer probe PASS, weight plan PASS (35 files, 141,225,192,536 publisher bytes, `weight_bytes_present: false`), runtime plan PASS with all execution flags false.

## Findings

Blocking: **none.**

Nonblocking:

- N1 (pre-Lock-A debt): `validate_public_metadata_path` basename allowlist (`phase5_serialization.py:83`) — unreachable today (section 4); must be repaired with versioned regeneration or explicitly excluded from the Lock-A executable closure before it freezes.
- N2 (recorded boundary, C4): the offline evidence verifier cannot prove remote provenance; Lock A must bind the authorized runner, raw-before-parse capture, request order, transfer manifest, and external plan hash before any evidence row is authoritative.
- Note (informational): the `"NONE"` TOML sentinel for `truncate_prompt_tokens` maps to JSON `null` in request bodies (`phase5_termination_probe.py:244`); internally consistent with vLLM's `None` default, no action needed.

## Disposition

Work may continue to **local Lock-A package assembly only**. Before any rental, all of the following remain open: (1) separate committed authorization gate before retained-population derivation plus source/exclusion/selection/request-order hashes; (2) exact checkpoint revisions, the accepted public weight plan, and a post-download publisher-vs-local hash verifier; (3) exact common launch commands including `--language-model-only`, served aliases, vLLM 0.25.1, container digest, environment manifest, runtime-exception register; (4) the public synthetic runner/orchestrator, raw capture, transfer manifest, v2 termination verifier, and fail-closed remote-payload allowlist; (5) throughput-smoke runner/verifier and deterministic concurrency selection; (6) provider quote, whole-rental wall-clock cap, and nonzero preflight-only spend ceiling; (7) two completed review rounds with no unresolved blocking findings.

**External-round adjudication:** this run is a complete, fresh audit that reproduced every claim from primary sources and returns a signed verdict. It may count as the **first accepted external round**. The interrupted round-1 run may not be counted automatically — and is not counted here. The two-round gate still requires one further completed independent round (e.g., Codex counter-review of this report) with no unresolved blocking findings.
