# Codex V3 internal review: public-synthetic client plan

Date: 2026-07-20

Verdict: **PASS AS A LOCAL, NON-EXECUTING V3 CANDIDATE; NOT LOCK A**

## Delta from preserved V2

V3 changes only the public 1-by-1 PNG fixture, format/status/path versioning,
and the test that proves the media bytes are structurally valid. The new PNG is
constructed as signature + IHDR + IDAT + IEND and the test independently checks
every chunk length and CRC, exact chunk order, terminal length, and 1-by-1
dimensions. It prevents malformed-media rejection from masquerading as the
language-only boundary.

## Rechecked V3 properties

- 20 public requests remain symmetric: ten per sequential checkpoint;
- all request identities, canonical UTF-8 body hashes, seeds, headers, and
  retry predicates recompute;
- native chat and common completions fields exist in vLLM 0.25.1, and the
  structured-output engine receives reasoning-end state for chat while common
  serialization disables thinking in the rendered prompt;
- the language-only semantic gate requires the source-derived 400
  `BadRequestError` zero-modality signature, not an arbitrary 4xx;
- raw envelope bytes precede envelope parsing and verbatim generated text
  precedes generated-JSON parsing;
- startup-log capture follows process start, and health/shutdown/exit/port
  events are all retained;
- V1 and V2 artifacts remain present and unmodified;
- V3 independently rebuilds with plan SHA-256
  `37ca3afaf8b2b6d465d695ecbc324f7ee0f78b14439a4876c10c76ff099efdf8`
  and file SHA-256
  `e0307cc074135d99c4585d91bf0ff11e1d2fd5dbe8818c9a89e066c53686b7bb`.

## Authorization and review status

No network/process/download/GPU/rental/retained/scientific execution surface is
present or authorized. Runtime evidence remains necessary, and K3 has completed
zero review rounds because the configured K3 endpoint returned quota 403 before
producing any audit content.
