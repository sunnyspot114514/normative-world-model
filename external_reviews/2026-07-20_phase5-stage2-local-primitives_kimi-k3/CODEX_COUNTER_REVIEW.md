# Codex counter-review

Date: 2026-07-20

Reviewed commit: `164228d841715d17221d620e441c67fbdb991f26`

K3 session: `session_8b24765d-8327-43e1-8d68-5d75a17a4fb1`

Normalized K3 report SHA-256: `604d624044b60a204b601f4b628e1f363a6b958cafb108028da3cbb5c1e15fe3`

## Decision

K3's `PASS_WITH_FIXES` verdict is accepted, but downloader execution remains blocked until the accepted findings and the additional serialization finding below are fixed and the complete local check passes.

## Accepted findings

1. **B1 accepted.** The Stage-2 validator has vacuous-success paths and does not bind all frozen semantics. The fix will bind the complete parsed TOML semantics, in addition to retaining useful field-specific diagnostics.
2. **B2 accepted.** Publisher weight planning must consume a committed normalization of realistic Hugging Face sibling metadata, including nested LFS digests, rather than relying on an undocumented flat adapter.
3. **B3 accepted.** Tokenizer inspection must include truncation, padding, full shared added-token attributes, and every allowlisted metadata byte present in the inspected snapshot.
4. **Non-blocking findings 1 and 2 are promoted into this fix set.** Payload hard links will be rejected, content-class provenance will be documented as an attestation that later builders must cross-check, and prompt token proofs will bind the inspected tokenizer snapshot hashes.
5. The synthetic selector remains fixture-only. Its public name will state that boundary, while the future real-data entry point must verify a separately committed authorization before opening the retained export.

## Additional blocking finding from Codex

The current common renderer calls the Base template with `add_generation_prompt=true` and `enable_thinking=false`. Qwen's Base template can still append an empty `<think>...</think>` block in that mode. AgentWorld has additional registered `<think>` and `</think>` tokens that Base does not share, so the same rendered text can tokenize differently even though the core vocabulary matches. This can make the common token-ID proof fail by construction.

The common renderer will instead render the message history with `add_generation_prompt=false`, then append the frozen shared assistant prefix `<|im_start|>assistant\n` itself. It will fail closed if any AgentWorld-only control literal (`<tool_response>`, `</tool_response>`, `<think>`, or `</think>`) appears in the common prompt. The authoritative real-snapshot token-ID proof remains required after public metadata is downloaded.

## Downloader correction

K3's proposed `huggingface.co only` redirect rule is too strict for files served through Hugging Face LFS/Xet infrastructure. The downloader must require the initial HTTPS host to be exactly `huggingface.co`, but may follow only an explicit, boundary-checked set of official Hugging Face CDN/Xet HTTPS hosts. It must record the full redirect chain and reject every other host. This correction does not authorize any weight download.

## Authorization after adjudication

Authorized now: local code, tests, documentation, and synthetic fixtures for the bounded fixes.

Still unauthorized: real retained-population selection, model weights, GPU rental, server execution, project-scenario inference, confirmation access, and scientific metrics.

Restricted public tokenizer/config metadata download may be implemented only after these fixes pass. Its first execution requires committed host/revision/path/size/redirect/hash/manifest controls and may write only to an ignored project-local cache.
