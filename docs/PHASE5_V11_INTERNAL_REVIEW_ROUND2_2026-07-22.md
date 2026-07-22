# Phase-5 V11 internal review — round 2 — 2026-07-22

Decision: **PASS LOCAL FREEZE; REMOTE EXECUTION REMAINS UNAUTHORIZED**

## Independent attack checklist

- Native output with an exact JSON tail inside `<think>...</think>` fails.
- Duplicate keys in native JSON fail before semantic scoring.
- A bounded reasoning envelope in raw common output is classified, retained,
  and cannot affect the application gate.
- Raw-common repeat inequality is reported and does not affect the application
  gate.
- V11 contains no `PUBLIC-17-5` toy content and uses a new fixed seed.
- The two native request bodies are identical across checkpoints after removing
  only `model` and `request_id`.
- V10's result file is unchanged and hash-bound by the V11 freeze record.
- Every V11 execution authorization is false and the Lock-A registry is
  unregistered.

## Verification

- Full repository check: 255 tests passed, compile and isolation audits passed.
- Client-plan independent rebuild: PASS.
- Client-plan semantic SHA-256:
  `242a1aa2e044d04301772cf53c892b5671191a4a29b887a1af308f2ac94256dd`.
- Client-plan file SHA-256:
  `bcbbd77fe94e9bcb6a74d789533758f8980a6fd488b4fefaddd7beb72200aafa`.

## Claim boundary

This review accepts only the local V11 contract. It does not claim that native
package differences identify a weights-only treatment effect, does not accept a
new Lock A, and does not authorize a rental or any scientific request.
