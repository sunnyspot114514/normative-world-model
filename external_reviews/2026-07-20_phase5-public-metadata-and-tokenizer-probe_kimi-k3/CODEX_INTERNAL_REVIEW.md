# Codex internal review

Date: 2026-07-20

Reviewed HEAD: `1cb7c90`

External status: K3 attempt incomplete because of provider quota; no external verdict exists.

## Verdict

**PASS FOR REPEAT PUBLIC-METADATA DOWNLOAD AND LOCAL PUBLIC-SYNTHETIC TOKENIZER PROBE.**

This is not Lock A acceptance. Model weights, retained project prompts, real population selection, GPU rental, confirmation, and scientific execution remain unauthorized.

## Reproduced evidence

- Current parsed TOML semantic SHA-256 equals the code binding: `2a23d1973113694468cd25be92e8932b52f8c4f3d56deda78ea2b5421e7abb76`.
- `validate_stage2_contract` returns no violations.
- The full project check passes with 172 tests after adding the final verifier hard-link/extra/empty-directory attack.
- The initial public-cache manifest canonical hash recomputes to `90045b75a1d01588a83c3df539c21f310f8d94324bf00b57015aebf1360151a7`.
- Initial snapshots recompute as AgentWorld 9 files / 22,982,918 bytes and Base 7 files / 23,091,324 bytes, total 46,074,242 bytes. Every local file matches its recorded byte count and SHA-256. Redirect hosts are exactly `huggingface.co` and `us.aws.cdn.hf.co`. No `.safetensors` payload exists.
- The old cache binds semantic hash `d46462f4...` and the current verifier rejects it with `public metadata bundle constant differs: stage2_config_semantic_sha256`, as required.

## Adjudication

1. URL validation rejects non-HTTPS, credentials, non-443 ports, fragments, initial subdomains, and suffix-confusion hosts. Redirects are limited to domain-boundary Hugging Face hosts, capped, and the recorded final URL must equal the last redirect.
2. Repository IDs, revisions, paths, destination, and network limits are not caller-controlled in the production entry point. Only two TOML-bound repos at full 40-hex revisions are accepted. The filename intersection is frozen and never includes weight bytes.
3. API/file/bundle byte caps, identity encoding, two attempts, five redirects, TLS defaults, exact publisher sizes, LFS SHA-256, non-LFS Git blob recomputation, inert parsing, duplicate-key rejection, and write-once cleanup are enforced before a passing manifest exists.
4. The independent verifier scans links before reading payload files, rejects symlinks/junctions/hard links/empty directories/extra files, then rebuilds source, manifest, snapshot, publisher, URL, Content-Length, file, and total bindings.
5. The effective-token correction is valid: the union of `tokenizer.json.added_tokens` and `tokenizer_config.json.added_tokens_decoder` is identical across the two real packages (33 tokens); the four control literals share IDs 248066–248069.
6. The only normalized tokenizer JSON difference is BPE `ignore_merges` absent versus explicit `false`. Hugging Face's official Tokenizers API documents `false` as the BPE default. No other field receives default normalization.
7. Differing `eos_token` and `model_max_length` are correctly excluded from the raw `add_special_tokens=false` input-ID equivalence claim and explicitly retained in the probe diagnostics. EOS remains a Lock-A serving blocker until one common termination policy passes the synthetic serving probe.
8. The public tokenizer probe loads only locally verified files with `local_files_only=true`, `trust_remote_code=false`, and `use_fast=true`; it binds package hashes, effective control IDs, five fixed public prompt classes, all compared token IDs, and the installed tokenizer-library versions.

## Residual limits

- A local concurrent writer could still race between a verifier read and a later tokenizer load. The project workflow bounds this by a write-once ignored bundle, exact verification immediately before loading, clean single-user execution, and proof binding to the pre-load hashes. Lock A must rehash the served snapshots again; this is not a reason to claim hostile-filesystem security.
- `transformers` and `tokenizers` are runtime tools already present in the isolated environment rather than declared project dependencies. The probe records exact versions; Lock A must bind them in the source closure/container rather than treating the current workstation installation as portable.
- Domain-boundary CDN permission trusts Hugging Face-controlled DNS and platform TLS. Publisher hash verification protects file bytes; the API identity itself remains HTTPS-authenticated and is re-resolved again at Lock A.

## Execution decision

After committing this review and final test, it is safe to rerun the restricted public downloader into the new semantic-hash-derived, nonexisting ignored root. If the independent bundle verifier passes, it is safe to run the local public tokenizer probe once. Any mismatch stops. No downstream execution is implied.
