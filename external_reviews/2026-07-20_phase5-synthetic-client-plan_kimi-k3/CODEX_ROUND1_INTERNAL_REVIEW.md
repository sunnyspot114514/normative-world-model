# Codex round-1 internal review: public-synthetic client plan

Date: 2026-07-20

Verdict: **SUPERSEDED AFTER SECOND INTERNAL PASS; V1 IS NOT ACCEPTED**

This file records the first pass against commit `c3d9f13`. Before any K3 audit
actually began, Codex performed another source-level attack and invalidated the
V1 disposition below. It is preserved rather than rewritten as though V1 had
always passed the stronger checks.

## Independently checked

- vLLM v0.25.1 declares `response_format`, `seed`, `request_id`, and
  `return_token_ids` on both reviewed request paths; chat also declares
  `include_reasoning`, while completions declares `add_special_tokens`,
  `stop_token_ids`, and the other common-termination fields used here.
- `response_format.type=json_schema` is converted to structured-output JSON in
  the v0.25.1 protocol implementation.
- the embedded image decodes as a PNG signature with a 1-by-1 IHDR and contains
  only public synthetic bytes;
- the generated common prompt is 64 tokens under both bound tokenizer
  snapshots with identical token IDs;
- all 20 request identities and canonical UTF-8 request hashes recompute;
- the frozen termination cases are referenced without body mutation;
- every execution authorization remains false and the new module imports no
  subprocess, socket, URL, HTTP-client, retained-corpus, or scientific runner;
- the write-once artifact independently rebuilds byte-for-byte;
- all 196 repository tests, isolation, retained locks, and confirmation
  reservation pass.

## Attacks exercised

- runtime and termination mutation without a matching trusted verification;
- common prompt token mismatch;
- authorization opening;
- request-identity recomputation over method, endpoint, ID, headers, body, and
  seed;
- event-order checks for both envelope parsing and generated-text JSON parsing;
- omission of the semantic oracle from a schema-only success definition;
- accidental conflation of final-content replay with reasoning or response
  envelope equality;
- a second-server launch before exit/port-release evidence.

## Review finding resolved before this disposition

The first draft said only that raw capture preceded "parse". That was
insufficiently typed: parsing the HTTP response envelope is different from
parsing the model-generated JSON. The contract now requires raw envelope bytes
to be fsynced before envelope parsing, then generated text to be extracted,
persisted verbatim, and fsynced before generated-text JSON parsing.

The first draft also constrained semantic request equality but did not bind the
actual serialized bytes. It now specifies a canonical UTF-8 JSON encoding,
stores its SHA-256 for every body, and requires identical request bytes on the
single permitted retry.

## Open, non-accepted items

1. The exact error-object semantics of the language-only negative probe require
   live evidence from both checkpoints. Only the 4xx class gate is a candidate
   today; a 2xx is failure and a persistent 5xx is technically blocked.
2. No executable HTTP client, server process controller, or evidence verifier
   exists. This review accepts the plan shape only.
3. Runtime-plan v2 still lacks a completed second external review because the
   earlier K3 attempt exhausted quota before verdict. The client plan cannot
   upgrade that status.
4. Container, provider, environment-allowlist, weight-verification, cost, and
   throughput obligations remain outside this slice.

K3 review is requested next. Codex retains final adjudication and will not
convert an incomplete or unsupported K3 response into an accepted round.

## Superseding findings

1. **Generic 4xx false pass.** V1 accepted any 4xx for the language-only
   negative probe. A 401 authentication failure or 404 route error could
   therefore masquerade as proof that multimodality was disabled. vLLM 0.25.1
   source traces the intended path through a zero multimodal item limit,
   `VLLMValidationError`, and a 400 `BadRequestError`. V2 requires that code,
   type, an image/vision-chunk parameter, and the zero-limit message fragments.
2. **Impossible lifecycle wording.** V1's composite order placed startup-log
   capture before server launch. V2 persists intended argv/environment before
   launch, starts the process, then captures the log stream from process start.
   It also adds explicit raw evidence for every health poll, shutdown path,
   process exit, final log, and port-release check.

These are contract changes, so the write-once V1 artifact remains on disk and
V2 receives a new format version and path.
