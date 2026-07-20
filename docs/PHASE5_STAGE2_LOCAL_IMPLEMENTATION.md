# Phase-5 Stage-2 local implementation

Date: 2026-07-19

Status: **IN PROGRESS — PUBLIC SOURCE/INPUT/WEIGHT-METADATA PASS; TERMINATION PLAN PASS, EXECUTION OPEN**

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

`phase5_tokenizer_probe.py` then loads only the verified local files with `local_files_only=true`, `trust_remote_code=false`, and `use_fast=true`. Its fixed public prompts include ASCII, Unicode, punctuation, multi-turn, and long-context witnesses. The V2 long witness must contain 5,900–6,144 input tokens and must also satisfy `input + 2,048 <= 8,192`; V1 was preserved and invalidated for missing this headroom check. The proof binds every prompt token ID to the exact snapshot hashes, and a separate verifier reloads the packages and rebuilds the whole artifact. A successful input-tokenization probe still reports `PASS_WITH_LOCK_A_EOS_ACTION`, because the checkpoint-default EOS tokens differ and the matched serving termination rule is not yet frozen.

## Metadata-only publisher weight plan

`phase5_public_weight_plan.py` consumes only the verified local public bundle.
It separates index-declared tensor storage bytes from full publisher/LFS
safetensors container bytes, resolves every index-referenced shard without a
hard-coded count, and binds repo/revision, API/index hashes, LFS hashes, Stage-2
configuration, and implementation source bytes. Its independent verifier
rebuilds the complete write-once artifact. The accepted v3 plan covers 35 files
and 141,225,192,536 prospective publisher bytes; it contains no weight bytes and
does not alter `authorization.model_download=false`. Full evidence and the v1
source-binding invalidation are recorded in
`docs/PHASE5_PUBLIC_WEIGHT_PLAN_2026-07-20.md`.

## Common termination probe candidate

The standalone candidate TOML and `phase5_termination_probe.py` define a
local-only eight-case probe for the remaining default-EOS difference. Both
checkpoint servers would receive the same explicit stop-token list with default
EOS ignored; each default token is separately forced on both checkpoints and
must return its integer `stop_reason`. The request planner binds the verified
public tokenizer proof and exact source bytes. The raw-response verifier also
requires the future Lock-A plan hash, so a recomputed self-hash cannot authorize
changed requests. The candidate plan passes locally, but contains no HTTP client
and leaves the main TOML's termination status pending until an accepted Lock A
authorizes the public synthetic serving probe. See
`docs/PHASE5_COMMON_TERMINATION_PROBE_CANDIDATE_2026-07-20.md`.

The source-reviewed v2 evidence contract additionally binds the completion
response object, the empty detokenized text required when the first forced stop
token is excluded from output, and exact total-token accounting. The v1 plan is
preserved but superseded; neither version authorizes HTTP or GPU execution.

## Common runtime launch plan

`phase5_runtime_plan.py` projects the reviewed Stage-2 config, public weight
plan, and termination v2 proof into two exact future `vllm serve` argument
vectors. AgentWorld and Base use the same offline environment and every runtime
flag except the pinned snapshot path and served alias. In particular, both use
vLLM 0.25.1, `--generation-config vllm`, `--language-model-only`, bfloat16,
TP=1, max model length 8192, eager mode, Triton MoE, the Qwen3 reasoning parser,
loopback-only port 8000, and FlashInfer sampling disabled. `trust_remote_code`
is explicitly false and is absent from both launch vectors.

The preserved v1 write-once artifact is
`.cache/phase5_runtime_plan/v1-2a23d1973113-1a8cdbf5f807.json`:

- runtime-plan field SHA-256:
  `e6b399934ccb433d850f355d65fa697ac4f8fd00a56add694eb8074310288a6c`;
- plan-file SHA-256:
  `803f39375b04b419f566bac1c12ea0fb347f45d348f69c760358a6f85fb5d33f`;
- checkpoints: 2; weight files: 35; prospective publisher bytes:
  141,225,192,536;
- `model_download=false`, `server_rental=false`, `http_execution=false`, and
  `gpu_execution=false`.

The independent verifier rebuilds the full plan and both launch vectors from
the current source-bound public artifacts. This is a local Lock-A component,
not Lock A itself: revisions are still observed rather than frozen, container
identity and provider quote are unset, and no reusable client/orchestrator,
throughput runner, source closure, or two-round Lock-A disposition exists yet.

The v1 artifact is preserved as the first launch-vector design. Internal review
found that it did not make the ambient-environment policy, resolved-runtime
evidence path, post-download weight verification, or process/port lifecycle
obligations machine-readable. Runtime-plan v2 fixes those omissions without
opening authorization: it pins `VLLM_SERVER_DEV_MODE=0` and
`PYTHONNOUSERSITE=1`, declares a future fail-closed environment allowlist,
chooses exact launch/environment/log/model-list capture plus a public
language-only behavioral rejection probe instead of the disabled development
`/server_info` endpoint, and records post-download snapshot containment and
server shutdown/port release as mandatory unresolved work.

The current local write-once artifact is
`.cache/phase5_runtime_plan/v2-2a23d1973113-1a8cdbf5f807.json`:

- runtime-plan field SHA-256:
  `b2887ba90d81cc32f9b49993853df5c97a8676341e7bf3d76de2bb1b44ac7c6f`;
- plan-file SHA-256:
  `f9a4d9c14c863473bcd8ba46248e84b1d6ac52c4a04665af37a499cafd59bc74`;
- status:
  `PASS_LOCAL_PLAN_V2_ONLY_EXECUTION_NOT_AUTHORIZED`;
- checkpoints: 2; weight files: 35; prospective publisher bytes:
  141,225,192,536;
- every download, rental, HTTP, GPU, retained-population, and science
  authorization remains false.

## Public-synthetic client/orchestrator plan

`phase5_synthetic_client_plan.py` consumes the independently rebuilt runtime
v2 and termination v2 plans plus a fresh two-tokenizer proof for a public toy
prompt. It freezes 20 future public-only requests, exact canonical request-byte
hashes, a one-retry identity contract, two-stage raw-before-parse persistence,
the arithmetic semantic oracle, deterministic final-content replay, and the
sequential server/port lifecycle. The module has no subprocess or network
client surface; the client, orchestrator, and evidence verifier are explicitly
`NOT_BUILT`.

The local write-once artifact is
`.cache/phase5_synthetic_client_plan/v1-b2887ba90d81-b752a05215d7.json`:

- client-plan field SHA-256:
  `a8d892819d6dc416f810a5749485b4b6968c5ba5237299416927d939dcd317ac`;
- plan-file SHA-256:
  `22586f3e3dc4be0a10107896dacce143b268d2c0bb92a98bc85678ef823e2787`;
- requests: 20; common public prompt: 64 tokens;
- every process, HTTP, GPU, retained-population, and science authorization
  remains false.

See `docs/PHASE5_SYNTHETIC_CLIENT_PLAN_CANDIDATE_2026-07-20.md` for the exact
battery, evidence sequence, lifecycle contract, and remaining Lock-A debts.
