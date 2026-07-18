# Codex counter-review: Phase-5 two-lock protocol

Date: 2026-07-19

Reviewed K3 report: `KIMI_K3_AUDIT_REPORT.md`  
Reviewed commit: `e9da3e3`

## Decision

**ACCEPT_WITH_BOUNDED_FIXES.** K3's `PASS_WITH_FIXES` verdict is supported after independent inspection. The two-lock architecture, closed authorization state, exact-revision metadata checks, request arithmetic, token budget, and Stage-2 boundary all reproduce. No weight download, rental, population derivation, confirmation access, or science is authorized.

## Findings accepted and closed

1. **Prompt-derived remote artifacts.** The old allowlist named raw prompt text and request bodies but did not unambiguously cover token-ID sequences, rendered caches, embeddings, base64, or other prompt-derived encodings. The stricter resolution is adopted: none of these may enter the synthetic rental. K3's alternative of explicitly allowing a token-ID-only payload is rejected because it is unnecessary and reversible. Served-snapshot tokenizer/config files return under transfer hashes; the all-prompt proof is rerun locally.
2. **Stability semantics.** The Markdown wording is corrected to eight requests per checkpoint-by-mode-by-candidate cell. A pass now requires eight final 2xx responses after the frozen retry allowance, synthetic-schema validity, no truncation, at least 8,192 generated tokens in the cell, continued server health, and no crash/restart/OOM/KV-allocation failure. Latency is diagnostic, not a pass threshold.
3. **Time-cap scope.** The 30-minute condition cap and one-GPU-hour checkpoint cap apply only to post-warm-up decode measurement windows. Grid probes, one defined warm-up block, and the protocol-shaped component are excluded from those statistical caps but included in a separate whole-rental wall-clock cap and maximum-spend cap that Lock A must bind. Cap exhaustion before minimum evidence is an insufficient preflight, never a partial PASS.
4. **Attribution accuracy.** The disposition no longer claims that K3 proposed `max-num-seqs=32`, and it replaces the overstated AgentWorld-only characterization with K3's actual hedged wording. The earlier Codex phrase `96 requests or 20 minutes` is also not supported by the stored K3 review; only the substantive minimum-evidence correction is retained. The historical counter-review file remains unchanged as an audit record.
5. **Local derivation trigger.** K3 treated the missing trigger for `population_selection` as non-blocking. It is nevertheless closed now: a separate committed post-Stage-2 local-derivation gate must flip the flag before the selector first touches the real retained-discovery export. That gate permits one deterministic local selection run and no remote action.

## K3 claims independently corrected or bounded

- The metadata conclusions are observations at exact public revisions, not Lock-A source bindings. They remain provisional until the publisher manifest is rebuilt.
- Both configs declaring vision components supports a common `--language-model-only` candidate; it does not prove Base serving compatibility. A forced difference still stops the attempt and requires a Lock-A delta review.
- Three CV windows are a predeclared engineering stability screen, not a strong estimator of long-run variance and not a scientific result.
- Empty-string placeholders are not treated as authority because neighboring status fields and all authorization booleans remain closed. Explicit revision statuses were added; replacing all placeholders is not required for Stage 2.

## Entry decision

With the protocol and TOML fixes in this review applied and the repository checks passing, the K3 blocking findings are closed. Stage 2 may then begin only as local, non-deriving implementation against synthetic fixtures. The first real-source selector execution remains separately gated. Model weights, GPU rental, project-scenario inference, confirmation, and scientific execution remain forbidden.
