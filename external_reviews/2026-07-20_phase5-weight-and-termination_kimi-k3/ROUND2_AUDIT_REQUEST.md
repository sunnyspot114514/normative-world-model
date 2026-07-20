# Kimi K3 round-2 audit request: Phase-5 termination v2 and counter-review

Date: 2026-07-20

Reviewer: `kimi-code/k3`

Primary fix commit: `e04e022`

Baseline commits: `a18026f`, `251e045`, `10ecdaa`

Status: **QUEUED — K3 QUOTA UNAVAILABLE AT CREATION**

Perform a fresh read-only adversarial audit. Do not treat
`KIMI_K3_ROUND1_INCOMPLETE.md` as a verdict. Reproduce its claims and the Codex
counter-review independently. Do not modify files, open the retained project
corpus, derive the real population, download or open weights, start a server,
use a GPU, access confirmation, or send scientific requests.

## Required inputs

- `ROUND1_AUDIT_REQUEST.md`;
- `KIMI_K3_ROUND1_INCOMPLETE.md`;
- `CODEX_ROUND1_COUNTER_REVIEW.md`;
- commit `e04e022` and its parent chain;
- ignored v2 artifact
  `.cache/phase5_common_termination_probe_plan/v2-1a8cdbf5f807.json`;
- the previously reviewed public metadata, tokenizer, and weight-plan artifacts.

## Required attacks

1. Rebuild the v2 plan and verify the complete source/config/tokenizer hash
   chain, write-once path, self-hash, eight exact request hashes, and preservation
   of v1.
2. Check official vLLM **tag v0.25.1** and independently decide whether:
   - `--generation-config vllm` suppresses checkpoint generation defaults;
   - `ignore_eos=true` plus explicit `[248044, 248046]` makes both tokens take
     the explicit-stop branch;
   - the explicit branch reports the integer token ID while default EOS reports
     `None`;
   - `allowed_token_ids=[forced_id]` forces the one permitted token;
   - `return_token_ids=true` returns both generated and prompt token IDs;
   - `include_stop_str_in_output=false` makes the first forced stop token's
     completion text exactly empty, even with `skip_special_tokens=false`;
   - `/v1/completions` reports `object="text_completion"` and
     `total_tokens=prompt_tokens+completion_tokens`.
3. Attack v2 with wrong/missing/bool response object, text, total-token fields,
   stop reason, token IDs, prompt IDs, request bodies, external plan hash,
   duplicate/non-finite JSON, missing/extra cases, and repeat drift. Look for a
   false pass that survives exact request and plan binding.
4. Adjudicate the deferred `subdir/tokenizer.json` observation. Demonstrate a
   reachable current false pass or confirm that every current caller fails
   closed. State whether it blocks local Lock-A assembly.
5. Audit the language-only serving requirement against vLLM 0.25.1. Decide what
   exact server argument and returned runtime evidence Lock A must bind for both
   multimodal-declared checkpoint packages.
6. Recheck the authorization boundary. Nothing in this scope may authorize
   retained-population access, model download, rental, HTTP/GPU execution,
   science, or confirmation.
7. Run the full local check. State whether work may continue to **local Lock-A
   package assembly only**, and list all blockers before any rental.

Return `PASS`, `PASS_WITH_FIXES`, or `BLOCK`, separating blocking and
nonblocking findings with exact file/line and official-source evidence. State
explicitly whether this completed run may count as the first accepted external
round; the interrupted earlier run may not be counted automatically.
