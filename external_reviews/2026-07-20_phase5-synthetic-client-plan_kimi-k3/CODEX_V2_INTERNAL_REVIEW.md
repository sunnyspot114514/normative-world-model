# Codex V2 internal review: public-synthetic client plan

Date: 2026-07-20

Verdict: **SUPERSEDED AFTER PNG CRC ATTACK; V2 IS NOT ACCEPTED**

V2 preserves all V1 request bodies and upstream bindings while fixing the two
superseding findings recorded in `CODEX_ROUND1_INTERNAL_REVIEW.md`.

## V2-specific checks

- the language-only path was traced in vLLM v0.25.1 from
  `MultiModalConfig.language_model_only` to a zero per-prompt modality limit,
  `validate_num_items`, `VLLMValidationError`, and the API's 400
  `BadRequestError` mapping;
- 401, 404, unrelated 400, 2xx, and persistent 5xx outcomes cannot satisfy the
  declared language-only semantic gate;
- prelaunch argv/environment persistence precedes process launch, while log
  capture begins only after the process exists;
- every readiness poll, shutdown branch, process exit/final log, and
  port-release probe has an ordered raw-evidence obligation;
- V1 remains untouched at its old write-once path and V2 uses a new versioned
  path;
- V2 independently rebuilds with plan SHA-256
  `807b07d39b06fe800c444b90ad91fd3a3d2e7f7ecb403cedecfc869ac2174ba4`
  and file SHA-256
  `d156a4dd612996c2f833ad482c1a9a282459732f238f9b77aacb9cadcb7d423a`.

## Remaining limits

This is still only a data/contract planner. The source-derived language-only
error signature must be confirmed on both live checkpoints. No HTTP client,
server launcher, runtime evidence verifier, model download, rental, GPU action,
retained prompt, or science execution is authorized. K3 has completed zero
rounds on V2.

## Superseding finding

The initial V2 test checked the PNG signature, dimensions, and content-part
shape but not every PNG chunk CRC. A full standard-library parse found a CRC
mismatch in the embedded 1-by-1 fixture. That could cause a strict media parser
to reject malformed bytes before reaching the language-only zero-modality
boundary, making the negative probe causally ambiguous. V3 replaces the bytes
with a freshly constructed 1-by-1 RGBA PNG and validates the exact chunk order,
lengths, CRCs, IEND, and dimensions. The V2 artifact remains preserved.

The exact V2 module source is identified by byte count 30,504 and SHA-256
`ef04c4e752e0dc739c1e52faf0bbf33595965041fe012e1800a22b62b8733fb7`
inside the preserved artifact. It is deterministically reconstructible from
V3 module source SHA-256
`f39ede5d87f7fc7ede6f94debe660a4af9aad131891478040bc620123c8339d5`
by changing the four V3 format/status/path literals to V2 and restoring the V2
data-URI string recorded by the preserved plan. No other module byte differs.
