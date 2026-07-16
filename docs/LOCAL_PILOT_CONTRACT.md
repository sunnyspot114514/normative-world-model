# Local small-model pilot contract

Status: **exploratory smoke preparation; external Phase-1 acceptance pending**

## Checkpoint lock

The local pilot uses the same base checkpoint for every trained arm:

```text
model: Qwen/Qwen3-1.7B-Base
revision: ea980cb0a6c2ae4b936e82123acc929f1cec04c1
license: Apache-2.0
```

The checkpoint is a 1.7B dense causal language model. It is loaded without remote code and in
float16 on the local RTX 3060. No quantization is used in the first smoke because the checkpoint
fits in 12 GiB at inference precision and avoiding a quantization backend removes a Windows-specific
confound.

## Dependency lock

`requirements-model.txt` records the exact smoke stack. `scripts/setup-model.ps1` installs the
CUDA 12.6 PyTorch wheel from the official PyTorch index and installs the remaining packages into the
project-local `.venv`. All caches remain under this repository through `scripts/project-env.ps1`.

The first smoke must record:

- installed package versions;
- model ID and exact Hub revision;
- hashes of downloaded checkpoint files;
- GPU name, driver-visible CUDA version, peak allocated/reserved memory, and wall time;
- prompt, target, and total token counts;
- trainable and total parameter counts;
- forward loss and whether one LoRA optimizer step completed.

The first trained view is explicitly one-step: it retains the required `rollout` key but uses an
empty list in the target. Stored H1/H2/H3 targets remain available for the later rollout stage and
are not mixed into the initial one-step optimization budget.

## Permitted work before external acceptance

Permitted:

- tokenizer-length audits over the v3 smoke exports;
- checkpoint download and hash verification;
- model load, forward, backward, one-step LoRA, strict-parser, and latency plumbing checks;
- repair of Phase-2/3 code that does not change any frozen Phase-1 input or artifact.

Not permitted:

- retained-data generation or retained training;
- opening or generating confirmation data;
- tuning preregistered practical margins from smoke results;
- presenting smoke model behavior as a scientific result.

## Arm invariants

- `joint_naive` and `joint_consistency` receive byte-identical prompts and targets.
- Their only training difference is the factual consistency term.
- `factorized_factual` never receives evaluator values.
- `factorized_normative` may use gold factual context during training only. Evaluation must use the
  factual component prediction and recompute policy results with the deterministic policy oracle.
- Every arm uses the same base checkpoint revision, tokenizer revision, family split, and declared
  primary scenario/target-token budgets.

## Smoke exit criterion

The local stack is ready for an exploratory multi-record pilot only if:

1. the checkpoint revision and local file hashes are recorded;
2. CUDA loading succeeds without falling back to CPU;
3. one masked-causal-LM LoRA optimizer step completes without non-finite loss;
4. the longest audited smoke record fits the declared token limit, or truncation is explicitly
   rejected and the limit is revised before training;
5. peak allocated CUDA memory stays at or below 95% of device memory; a step that succeeds only by
   WDDM shared-memory oversubscription is a resource failure;
6. the standard repository checks and both frozen Phase-1 verifiers still pass.

## Current infrastructure result

- Snapshot revision resolution: PASS.
- `model.safetensors`: 3,441,185,608 bytes,
  SHA-256 `6df85b39330e5a425ee36253d0f894e4387e4f0a15b9c53cb467d668e6b3a841`.
- One-step joint token range: 726 to 868; no record exceeds the 3,072-token cap.
- One-step LoRA smoke: 726 tokens, finite loss, one optimizer step, 8,619,154,432 peak allocated
  bytes out of 12,884,377,600 device bytes (`0.6690`), PASS.
- Full stored-rollout diagnostic: 1,521 tokens and 16,359,308,800 peak allocated bytes, exceeding
  physical device memory through WDDM shared-memory behavior, RESOURCE FAIL.

These values establish local feasibility for one-step plumbing only. They are not model-quality
results and do not authorize a retained pilot.
