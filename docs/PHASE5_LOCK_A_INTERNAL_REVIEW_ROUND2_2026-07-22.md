# Phase-5 Lock-A internal review — round 2

Date: 2026-07-22

Decision: **PASS FOR ONE PUBLIC-SYNTHETIC PREFLIGHT; SCIENCE REMAINS CLOSED**

## Independent checks

1. The cloned snapshot was rehashed from disk against the previously accepted
   post-verification result. All 35 weight files and 16 public metadata files
   passed size and SHA-256 checks, and the exact file set had no additions or
   omissions. Clone result SHA-256:
   `8b637956cfb11758da3d822d916c4ca8b2e0680714396ec3b7a6763764fb358d`.
2. The remote environment manifest binds the AutoDL clone, RTX PRO 6000
   Blackwell GPU, 120 GiB cgroup memory limit, driver 595.58.03, vLLM 0.25.1,
   PyTorch 2.11.0, Transformers 5.14.1, executable hashes, and aggregate
   fingerprints for eight runtime distributions. Manifest SHA-256:
   `a8716d101011d7251cb12cae2a5c82c422d3b1d82b00a36cc935843f9fbae816`.
3. The runtime bundle uses one absolute executable, two absolute regular-file
   snapshot roots, identical runtime flags and environment for both
   checkpoints, offline Hugging Face settings, data-disk cache paths, and
   loopback port 8000. Bundle SHA-256:
   `23bc5c115561682ab56c9ba430474746ab5bcd549ae2f04c8f47eb4996d2cb0e`.
4. Runtime-bindings SHA-256:
   `04f66ef99f081a1c139d772a187dfdb97eda65435ffe7d8c254702ddd3e17af5`.
5. The provider quote is CNY 5.98 per GPU-hour plus CNY 1.58 per day of
   storage. The operator created and started the clone and separately approved
   GPU execution. The acceptance cap is limited to this public-synthetic
   preflight; no retained corpus is copied to the server.

## Residual risks and disposition

- Distribution fingerprints are capture-time attestations; launch-time checks
  rehash the Python and vLLM executables and rely on the clean, single-purpose
  clone for the remaining installed files. No package installation is allowed
  between capture and execution.
- Snapshot bytes receive a complete second rehash immediately before each
  checkpoint launch, so weight mutation after clone verification still fails
  closed.
- This pass authorizes interface, loadability, termination, deterministic
  replay, memory, and lifecycle evidence only. It does not authorize the real
  selector, retained-discovery prompts, throughput claims, Lock B, or any
  scientific result.

No unresolved blocking finding remains for the bounded public-synthetic run.
The repository-wide check passed 249 tests plus compile and isolation audits.
