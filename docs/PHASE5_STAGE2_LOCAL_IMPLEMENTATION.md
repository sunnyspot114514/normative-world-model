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
4. Base history rendering with `add_generation_prompt=false`, followed by the frozen shared assistant prefix and a ban on reserved control literals; the full-prompt token-ID proof binds the inspected snapshot hashes, retains every compared ID locally, and stops on one mismatch.

Tests use temporary synthetic tokenizer packages and fake tokenizer objects. No official snapshot has been downloaded by this slice.

The payload verifier rejects hard links as well as symlinks and path escapes. Its two content-class labels remain attestations: the future payload builder must cross-check them against a separately hash-bound source/provenance closure, and the post-transfer verifier must rehash the received bytes.

The selector API is intentionally named `select_phase5_fixture_population`. No real-export entry point exists. A future real selector must verify the separately committed population-selection authorization before it opens the retained export.

## K3 review and counter-adjudication

K3 returned `PASS_WITH_FIXES` for commit `164228d`; its exact report and the Codex counter-review are preserved under `external_reviews/2026-07-20_phase5-stage2-local-primitives_kimi-k3/`. A later public-snapshot probe corrected one premise in the Codex counter-review: the effective Base package also registers the four control tokens through `tokenizer_config.json`. The exact erratum is preserved next to the review. The manual assistant-prefix rule remains because it removes an empty reasoning envelope, not because the old package would necessarily tokenize the tags differently.

## Restricted public-metadata downloader

After the review fixes passed the full local check, the TOML gained the distinct authorization `public_metadata_download=true`; `model_download=false` remains unchanged. `phase5_public_metadata.py` and `scripts/fetch-phase5-public-metadata.py` implement this one bounded network action:

- the two repository IDs and full 40-hex revisions come only from the semantic-hash-bound TOML;
- the initial host is exactly `https://huggingface.co`; HTTPS redirects are limited to boundary-checked Hugging Face/CDN/Xet hosts and every redirect is retained;
- a frozen root-filename allowlist is intersected with the pinned publisher response; four tokenizer/config/index files are mandatory and `.safetensors` bytes are never requested;
- the API response, each file, each checkpoint, and the two-checkpoint bundle have predeclared byte caps; downloads use identity encoding, bounded attempts, bounded redirects, certificate-verified HTTPS, exact publisher-size checks, publisher LFS SHA-256 checks for LFS bytes, and locally recomputed Git blob IDs for non-LFS bytes;
- JSON is parsed inertly with duplicate-key rejection, non-JSON metadata must be UTF-8, and no template or downloaded code is executed;
- exact API bytes, exact downloaded bytes, redirect evidence, publisher identities, and SHA-256 manifests are written once under `.cache/phase5_public_metadata/`; any failure removes the newly created partial root and an existing root is never overwritten.

The tests use only injected fixture fetchers and do not open the network. The first real execution is permitted only from a clean commit containing this implementation and its passing tests. It remains a public-metadata probe, not a model download or Lock A.

The verifier independently rebuilds the manifest hash, snapshot hashes, exact file set, source identities, URL boundaries, byte counts, local SHA-256s, publisher LFS/Git hashes, inert JSON checks, and aggregate caps before a tokenizer loader can see the files. It rejects symlinks, junctions, hard links, empty directories, extra files, and a cache bound to an older TOML semantic hash.

`phase5_tokenizer_probe.py` then loads only the verified local files with `local_files_only=true`, `trust_remote_code=false`, and `use_fast=true`. Its fixed public prompts include ASCII, Unicode, punctuation, multi-turn, and long-context witnesses. The proof binds every prompt token ID to the exact snapshot hashes. A successful input-tokenization probe still reports `PASS_WITH_LOCK_A_EOS_ACTION`, because the checkpoint-default EOS tokens differ and the matched serving termination rule is not yet frozen.
