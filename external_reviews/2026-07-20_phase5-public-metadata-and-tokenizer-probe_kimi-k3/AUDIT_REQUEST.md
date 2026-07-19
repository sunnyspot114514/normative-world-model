# Phase-5 public metadata and tokenizer-probe audit request

Date: 2026-07-20

Repository: `normative-world-model`

Review HEAD: `1cb7c90`

Relevant commits:

- `275f068`: accepted Stage-2 source-contract fixes;
- `2dc000d`: restricted public-metadata downloader and fixture tests;
- `1cb7c90`: public-probe erratum, independent bundle verifier, effective tokenizer-package inspection, and public tokenizer proof.

## Scope and authorization

This is a read-only adversarial audit. Do not modify repository or cache files, do not access retained project corpora or confirmation, do not open the network, do not download model weights, and do not run GPU/server inference.

You may inspect the ignored public-only cache `.cache/phase5_public_metadata/v1-d46462f4f4c2/` solely to verify the numerical claims in the committed probe/erratum. It contains public Hugging Face API responses and allowlisted tokenizer/config/index metadata only. It is bound to the superseded pre-erratum TOML semantic hash and is not the pending repeat bundle.

## Required verification

1. Reproduce HEAD, worktree state, targeted tests, full project tests, and isolation audit.
2. Audit `phase5_public_metadata.py` against the minimum controls in your previous Stage-2 report:
   - exact initial host and bounded official redirects;
   - exact repo IDs, 40-hex revisions, and root filename allowlist;
   - no weight-byte request path;
   - per-response, per-file, per-checkpoint, and bundle caps;
   - bounded attempts, redirects, timeouts, identity encoding, TLS defaults;
   - exact publisher size plus LFS SHA-256 or recomputed Git blob verification;
   - inert parsing, duplicate-key rejection, atomic write-once behavior, partial cleanup;
   - exact manifest/source/config binding and independent local rebuild.
3. Attack URL parsing and redirect evidence: userinfo, ports, fragments, host-suffix confusion, missing/forged redirect chains, final-URL mismatch, and CDN/Xet boundaries.
4. Attack filesystem handling on Windows: symlink, junction, hard link, path escape, extra/missing files, empty directories, TOCTOU, existing-output preservation, and cleanup scope.
5. Attack realistic Hugging Face API shapes, including non-LFS Git blobs, LFS `sha256`/`oid`, missing sizes, duplicate siblings, and branch/revision ambiguity.
6. Audit the first public probe claims against the ignored cache without writing it. Recompute the manifest/file counts/bytes/hashes, redirect hosts, and absence of `.safetensors` payloads.
7. Audit the erratum. Determine whether effective added tokens must merge `tokenizer.json.added_tokens` with `tokenizer_config.json.added_tokens_decoder`, and whether the four control-token bindings actually agree in the loaded local packages.
8. Attack the narrow `model.ignore_merges` absent-equals-false normalization. Confirm it is the only normalized difference and that the official BPE default is false; reject any broader silent normalization.
9. Audit the tokenizer config split between input-tokenization-critical fields and diagnostics. In particular, assess whether differing `eos_token` and `model_max_length` are correctly excluded from the raw `add_special_tokens=false` token-ID proof but kept as a Lock-A runtime action.
10. Audit `phase5_tokenizer_probe.py`: fixed public-only prompts, local-only/trust-remote-code-false loading, snapshot binding, control-token checks, long-context witness, full token-ID retention, output write-once, and proof preimage.
11. Check documentation and TOML claims against the code. Confirm the current semantic hash is exact and the old ignored cache cannot pass the current verifier.
12. Identify any missing tests or false PASS path. Distinguish blockers before a repeat public-metadata download/probe from Lock-A-only issues.

## Mandatory questions

1. Is the restricted downloader safe to execute again at the current exact sources?
2. If the repeat bundle verifies, is the public tokenizer probe safe to execute locally?
3. Does a successful input-token-ID proof close only input serialization, while EOS remains a real Lock-A serving blocker?
4. Does any code path authorize weights, real project prompts, population selection, rental, confirmation, or science?

## Output format

Return one Markdown report with exactly these top-level sections:

1. `# Verdict`
2. `# Blocking findings`
3. `# Non-blocking findings`
4. `# Independent verification`
5. `# Downloader and bundle-verifier adjudication`
6. `# Tokenizer erratum and probe adjudication`
7. `# Contract and authorization adjudication`
8. `# Repeat-execution decision`

Use `PASS`, `PASS_WITH_FIXES`, or `FAIL`. Give exact file/line evidence, commands, and numbers. A `PASS_WITH_FIXES` must say whether the fixes block the repeat public download, the tokenizer probe, Lock A only, or later science only.
