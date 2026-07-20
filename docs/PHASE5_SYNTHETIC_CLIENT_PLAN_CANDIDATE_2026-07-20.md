# Phase-5 public-synthetic client/orchestrator plan candidate

Date: 2026-07-20

Status: **LOCAL V3 PLAN PASS; CLIENT, ORCHESTRATOR, AND EVIDENCE VERIFIER NOT BUILT; EXECUTION NOT AUTHORIZED**

This candidate closes the paper design for the reusable Lock-A client before
any networking code exists. It does not download a model, launch a server,
send HTTP, access retained project prompts, rent a GPU, or authorize scientific
execution.

## Bound inputs

The write-once plan binds:

- runtime-plan v2 SHA-256
  `b2887ba90d81cc32f9b49993853df5c97a8676341e7bf3d76de2bb1b44ac7c6f`;
- common termination-plan v2 SHA-256
  `b752a05215d7689335813546500916648413863f2e6faeaa215d7120313218a9`;
- the complete Stage-2 and termination configuration semantic hashes;
- the implementation source bytes;
- one 64-token public common-serialization prompt whose Base and AgentWorld
  token-ID sequences are exactly equal and leave 8,128 tokens of context
  headroom;
- exact request bodies, canonical UTF-8 body hashes, logical request IDs,
  headers, endpoints, methods, seeds, request order, retry rules, evidence
  event order, and server lifecycle order.

## Public request battery

There are 20 future requests, ten per sequential checkpoint server:

- one `GET /v1/models` identity capture;
- one valid public one-pixel-PNG request that must be rejected by the
  language-only server boundary;
- four exact termination-v2 cases;
- two deterministic native-chat arithmetic/schema cases;
- two deterministic common-completions arithmetic/schema cases.

The arithmetic oracle is deliberately non-subjective and non-project:
`sum=22`, `difference=12`, and `checksum="PUBLIC-17-5"`. A structural JSON pass
without this exact semantic result is a failure. Repeated final content must be
byte-identical within checkpoint and mode; reasoning and whole-envelope
equality are retained as separate diagnostics and are not replay predicates.

Both OpenAI-compatible paths use vLLM 0.25.1's reviewed
`response_format.type=json_schema` interface. The native request preserves
reasoning capture. The common request uses the verified client-rendered Base
prompt, disables implicit special-token insertion, and applies the explicit
two-token termination candidate.

## Raw-before-parse and retry contract

The future evidence state machine must first persist and fsync the complete
HTTP envelope and response bytes. Only then may it parse the envelope. After it
extracts generated text, it must persist and fsync the exact text before
attempting to parse the generated JSON. Invalid UTF-8 retains the raw bytes and
fails text parsing.

Exactly one retry is permitted only for a transport failure or HTTP 5xx. The
method, endpoint, logical `X-Request-ID`, complete headers, canonical UTF-8
request bytes, and seed must remain identical; both attempts are evidence. A
second failure is `TECHNICALLY_BLOCKED`. The frozen termination-v2 bodies are
not silently modified to add a new body field; their logical request IDs live
in the bound request header. New toy bodies use the same ID in both the header
and vLLM's supported body `request_id` field.

## Lifecycle contract

AgentWorld and Base must be served sequentially. For each checkpoint the future
orchestrator must prove the port is free, verify the snapshot and effective
environment, capture argv/environment/startup logs, reach bounded readiness,
run only that checkpoint's public battery, perform bounded shutdown, capture
the exit and final logs, and prove port release. Starting Base before the
AgentWorld port-release proof is forbidden.

## Local artifact and checks

Ignored write-once artifact:

`.cache/phase5_synthetic_client_plan/v3-b2887ba90d81-b752a05215d7.json`

- plan-field SHA-256:
  `37ca3afaf8b2b6d465d695ecbc324f7ee0f78b14439a4876c10c76ff099efdf8`;
- file SHA-256:
  `e0307cc074135d99c4585d91bf0ff11e1d2fd5dbe8818c9a89e066c53686b7bb`;
- bytes: 48,071;
- independent rebuild: PASS;
- repository checks: 197 tests PASS, isolation PASS, retained locks PASS,
  confirmation remains `RESERVED_NOT_GENERATED`.

Commands:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe scripts/run-phase5-synthetic-client-plan.py
.\.venv\Scripts\python.exe scripts/verify-phase5-synthetic-client-plan.py
powershell -ExecutionPolicy Bypass -File scripts/check.ps1
```

## Remaining boundary

The preserved v1 artifact has plan SHA-256
`a8d892819d6dc416f810a5749485b4b6968c5ba5237299416927d939dcd317ac`
and file SHA-256
`22586f3e3dc4be0a10107896dacce143b268d2c0bb92a98bc85678ef823e2787`.
It is superseded, not deleted: a second internal pass found that its generic
4xx language-only gate could falsely accept 401/404 responses and that its
lifecycle wording placed startup-log capture before process launch. V2 requires
the source-derived 400 `BadRequestError` with an image/vision-chunk zero-limit
signature, fixes the executable event order, and retains every health,
shutdown, exit, and port-release event.

The preserved V2 artifact has plan SHA-256
`807b07d39b06fe800c444b90ad91fd3a3d2e7f7ecb403cedecfc869ac2174ba4`
and file SHA-256
`d156a4dd612996c2f833ad482c1a9a282459732f238f9b77aacb9cadcb7d423a`.
It is also superseded: its PNG had a valid signature and 1-by-1 IHDR but a
chunk CRC mismatch, so a strict parser could reject malformed media before
testing the language-only boundary. V3 uses a fully CRC-validated 1-by-1 RGBA
PNG and freezes an exact standard-library structural test.

V3 is not Lock A. The network client, process orchestrator, and
independent evidence verifier remain `NOT_BUILT`. The exact language-only error
text still requires both-checkpoint runtime confirmation, but unrelated 4xx
responses can no longer pass the source-bound semantic gate.
Container/provider/cost bindings, the effective environment allowlist,
post-download weight verification, throughput runner, and two accepted review
rounds also remain unresolved.
