# Kimi K3 audit request: Phase-5 public weight-plan metadata closure

Date: 2026-07-20

Requested baseline HEAD: `1f230c2335b51a029006e6740ec7b0fc34cbf7b8`

Reviewer: `kimi-code/k3`

The requested review was read-only and limited to the working-tree delta in
`phase5_serialization.py` and `phase5_public_metadata.py`, plus the proposed next
step of producing a local publisher weight-plan artifact from the already
verified public API response and `model.safetensors.index.json`.

The reviewer was asked to:

1. attack the proposed normalization of an integer-valued JSON float in
   `metadata.total_size`, including bool, zero, fractional, non-finite,
   precision, and mismatch cases;
2. verify that inert JSON rejects all non-finite numbers;
3. name the blocking tests;
4. specify the exact fail-closed bindings required in a metadata-only plan and
   independent verifier; and
5. confirm that no path authorizes or fetches `.safetensors` bytes.

The reviewer was explicitly forbidden to edit files, open project corpus data,
download model weights, or run GPU/inference work. K3 was advisory; Codex would
independently reproduce and adjudicate every finding.
