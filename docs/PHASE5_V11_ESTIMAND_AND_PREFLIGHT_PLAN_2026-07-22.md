# Phase-5 V11 estimand and public preflight plan — 2026-07-22

Status: **LOCAL PLAN FROZEN; EXECUTION NOT AUTHORIZED**

## Decision

V11 adopts an application-level deployment-package estimand. Both checkpoints
receive the same OpenAI `messages`, JSON schema, and decoding fields through
`/v1/chat/completions`, apart from the unavoidable model alias and request
identity. Each checkpoint's tokenizer, chat template, and reasoning packaging
remain part of the package under test. Results cannot be attributed to weights
alone.

The raw `/v1/completions` common-base serialization is retained only as a
public-synthetic diagnostic. Its raw generated text is always preserved. A
verifier may report strict JSON or one exactly bounded Qwen reasoning envelope
with an exact JSON tail, but that tail is never substituted into the formal
gate and never enters scientific requests or metrics.

## Protection against outcome-dependent repair

- V10 remains `FAIL_PRECOMMITTED_SEMANTIC_GATE`; its result record and evidence
  archive are unchanged.
- V11 uses unseen public integers `23` and `7`, checksum `PUBLIC-23-7`, and seed
  `2026072204` rather than rescoring the V10 response.
- Native final content must be strict duplicate-key-rejecting JSON, match the
  exact arithmetic oracle, and replay exactly within checkpoint.
- Raw-common classification and repeat equality are reported but are not pass
  predicates. No trimming, code-fence removal, arbitrary prose recovery, or
  last-brace search is allowed.
- The scientific protocol now reports only a deployment-package contrast. The
  prior weights-oriented matched-common claim is withdrawn prospectively, not
  reinterpreted retroactively.

## Frozen local object

- Client-plan semantic SHA-256:
  `242a1aa2e044d04301772cf53c892b5671191a4a29b887a1af308f2ac94256dd`
- Client-plan file SHA-256:
  `bcbbd77fe94e9bcb6a74d789533758f8980a6fd488b4fefaddd7beb72200aafa`
- Ignored local path:
  `.cache/phase5_synthetic_client_plan/v11-b2887ba90d81-b752a05215d7.json`
- Request count: 20 public-synthetic requests.

The plan independently rebuilds from the source closure. It authorizes no
download, rental, server process, HTTP request, GPU work, retained-population
access, project-prompt access, or scientific execution.

## Next gate

The old V10 acceptance cannot authorize V11. The deployment registry is reset
to `None`. Before any GPU action, V11 requires a new source commit, two-review
Lock-A disposition, a fresh provider/runtime binding, a new time-limited
acceptance, and an action-time user confirmation. A V11 public preflight still
does not authorize retained-data or scientific execution.
