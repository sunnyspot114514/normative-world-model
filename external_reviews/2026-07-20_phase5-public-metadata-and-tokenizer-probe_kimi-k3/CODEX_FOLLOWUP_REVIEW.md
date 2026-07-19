# Codex follow-up review

Date: 2026-07-20

Status: **V1 TOKENIZER PROBE PARTIALLY INVALIDATED; V2 FIX ACCEPTED LOCALLY**

After the repeat public bundle passed, the first actual tokenizer artifact exposed a gap that the fixture tests and prior internal review missed: `long-public` encoded to 8,019 input tokens. Adding the frozen 2,048 generated-token allowance exceeds the 8,192 context. The artifact's exact Base/AgentWorld token-ID equality remains true, but it cannot serve as the protocol-shaped long-context witness.

The V1 ignored artifact is preserved at its original write-once path with SHA-256 `56984cf880b4102766e1d2ab3f1475cc236667aa074c6c2cfb19c42a932f007e`. It is not relabeled as a full pass.

The accepted V2 repair is prospective and machine-enforced:

- reduce only the fixed public repetition count from 1,000 to 750;
- require the named long row to be between 5,900 and 6,144 tokens;
- require the same row plus 2,048 generated tokens to be at most 8,192;
- increment the probe format/path to V2 rather than overwrite V1;
- independently reload verified local tokenizer packages and rebuild the stored V2 document byte-semantically before accepting it.

This change touches only public synthetic text and local proof logic. It does not authorize weights, project prompts, population selection, rental, confirmation, or science. A clean committed V2 implementation and passing full check are required before the one-time V2 run.
