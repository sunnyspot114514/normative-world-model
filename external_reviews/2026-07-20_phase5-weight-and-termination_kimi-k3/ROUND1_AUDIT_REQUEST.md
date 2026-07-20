# Kimi K3 round-1 audit request: Phase-5 public weight and termination closure

Date: 2026-07-20

Reviewer: `kimi-code/k3`

Requested audit commit: `251e045be072444e7f793f00142dfcca4280177f`

Perform a read-only adversarial audit. Do not modify any file, open the retained
project corpus, derive the real population, download or open model weights,
start a server, use a GPU, access confirmation, or run scientific requests.
Public metadata and public tokenizer cache artifacts listed below are in scope.

## Primary committed scope

- commit `a18026f` (`phase5: close public weight metadata plan`);
- commit `251e045` (`phase5: design common termination probe`);
- `src/normative_world_model/phase5_public_metadata.py`;
- `src/normative_world_model/phase5_serialization.py`;
- `src/normative_world_model/phase5_public_weight_plan.py`;
- `src/normative_world_model/phase5_termination_probe.py`;
- the corresponding configs, scripts, tests, and result documents.

## Ignored public artifacts to reproduce

- `.cache/phase5_public_metadata/v1-2a23d1973113/`;
- `.cache/phase5_public_tokenizer_probe/v2-2a23d1973113.json`;
- `.cache/phase5_public_weight_plan/v3-2a23d1973113.json`;
- `.cache/phase5_common_termination_probe_plan/v1-832c06e718b9.json`.

## Required attacks

1. Rebuild all four public artifacts and verify their source/config/input hash
   chain. Check for self-hash substitution, source drift, duplicate/extra paths,
   symlink/hard-link escape, stale revision, or a false PASS after tampering.
2. Attack inert JSON number handling, including bool, NaN/Infinity, exponent
   overflow/underflow, integer-valued floats, binary64 rounding around `2**53`,
   negative/zero totals, and semantic mismatch between index tensor bytes and
   publisher/LFS container bytes.
3. Recompute the real publisher plan: exact shard sets, sizes, LFS SHA-256,
   unreferenced weights, totals, and container overhead. Decide whether any code
   path can fetch `.safetensors` bytes or silently authorizes a future download.
4. Audit the common termination candidate against official vLLM 0.25.1 source.
   In particular verify `--generation-config vllm`, `ignore_eos`, explicit
   `stop_token_ids`, forced `allowed_token_ids`, `return_token_ids`, special-token
   handling, and whether integer `stop_reason` really distinguishes an explicit
   stop-token hit from checkpoint-default EOS.
5. Attack the future raw-response verifier: exact case set, request hashes,
   external Lock-A plan binding, response model/choice/token/usage fields,
   bool-as-int, duplicate JSON, repeat equality, and any way to fabricate PASS.
6. Verify the authorization boundary. No existing status or script may be read
   as permitting HTTP execution, model download, rental, GPU work, real prompts,
   population selection, confirmation, or science.
7. State whether the project may proceed to **local Lock-A package assembly
   only**, and enumerate every remaining blocker before any synthetic rental.

Run the full local test suite and any additional read-only probes you need.
Return `PASS`, `PASS_WITH_FIXES`, or `BLOCK`, with exact file/line evidence and
blocking versus nonblocking findings separated. Codex will independently
reproduce and adjudicate every claim before it has any effect.
