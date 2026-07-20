# Codex round-1 internal review: public-synthetic client plan

Date: 2026-07-20

Verdict: **PASS AS A LOCAL, NON-EXECUTING CANDIDATE; NOT LOCK A**

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
