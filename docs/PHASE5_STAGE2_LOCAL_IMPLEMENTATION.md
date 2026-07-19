# Phase-5 Stage-2 local implementation

Date: 2026-07-19

Status: **IN PROGRESS — LOCAL SYNTHETIC FIXTURES ONLY**

Stage-1 closed at commit `0b1a2c0` after K3 review and Codex counter-adjudication. Stage 2 implements local primitives without opening a new data boundary.

## Authorized in this stage

- parse and validate the committed two-lock TOML;
- implement the deterministic selector against synthetic in-memory fixtures;
- implement exact-set, symlink-free, fail-closed remote-payload manifests against temporary synthetic directories;
- implement renderer, tokenizer-checker, preflight-client, runner/verifier, and source-closure components with public synthetic fixtures;
- download only public tokenizer/config metadata after its dedicated code path and manifest tests exist.

## Still forbidden

- the selector's first execution over `joint_examples.jsonl.gz` or any other real retained-discovery export;
- changing `population_selection` without a separate committed local-derivation gate;
- model-weight download, GPU rental, server execution, project-scenario inference, confirmation access, or scientific metrics;
- copying project prompt text, token IDs, caches, embeddings, request bodies, or reversible prompt-derived artifacts into any synthetic preflight payload.

## First implementation slice

`phase5_preflight.py` provides three deliberately local primitives:

1. a contract validator that binds the complete parsed TOML semantics, while retaining targeted diagnostics for authorization, confirmation, remote-payload, token-budget, concurrency, and cap failures;
2. a balanced 72/24 selector implementation whose tests use only synthetic records and which stops rather than relaxing a short stratum;
3. an exact remote-payload verifier that rejects undeclared files, symlinks, path escapes, and content classes outside the two-class synthetic allowlist.

This slice is not a population lock and creates no Lock A or Lock B artifact.

The selector's target-pair order, SHA-256 ranking preimages, canonical NL scenario-surface choice, and canonical/sham profile variants are mirrored in the TOML. The Stage-2 contract test fails if code and configuration drift.

## Second implementation slice

`phase5_serialization.py` adds local proof primitives without adding a network or weight-download path:

1. an exact public-metadata filename allowlist that rejects weights and path traversal;
2. a reviewed normalizer for realistic Hugging Face `blobs=true` sibling metadata and a publisher weight-plan resolver driven by the checkpoint's own index and nested publisher LFS SHA-256 metadata, never by a hard-coded shard count;
3. every-present-metadata byte hashing plus exact core-vocabulary, preprocessing, truncation/padding, and full shared-added-token comparison;
4. Base history rendering with `add_generation_prompt=false`, followed by the frozen shared assistant prefix and a ban on AgentWorld-only control literals; the full-prompt token-ID proof binds the inspected snapshot hashes, retains every compared ID locally, and stops on one mismatch.

Tests use temporary synthetic tokenizer packages and fake tokenizer objects. No official snapshot has been downloaded by this slice.

The payload verifier rejects hard links as well as symlinks and path escapes. Its two content-class labels remain attestations: the future payload builder must cross-check them against a separately hash-bound source/provenance closure, and the post-transfer verifier must rehash the received bytes.

The selector API is intentionally named `select_phase5_fixture_population`. No real-export entry point exists. A future real selector must verify the separately committed population-selection authorization before it opens the retained export.

## K3 review and counter-adjudication

K3 returned `PASS_WITH_FIXES` for commit `164228d`; its exact report and the Codex counter-review are preserved under `external_reviews/2026-07-20_phase5-stage2-local-primitives_kimi-k3/`. The bounded fixes also close a Codex-identified empty-`<think>` serialization risk that K3 did not report. Restricted downloader implementation remains downstream of a clean full local check.
