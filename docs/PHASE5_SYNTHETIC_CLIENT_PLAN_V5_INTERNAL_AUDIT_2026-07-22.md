# Phase-5 public-synthetic client plan V5 internal audit

Date: 2026-07-22
Status: **LOCAL MOCK AUDIT PASS; ALL EXECUTION CLOSED; NOT LOCK A**

## Outcome

V5 binds the previously separate exact weight-snapshot verifier and the new
Linux-only loopback/process adapter into the public-synthetic client plan. The
adapter is execution-capable source code but has no command-line entry point,
and neither this review nor plan generation made a network call, started a
process, accessed a GPU, downloaded weights, or interacted with AutoDL.

The immutable local artifact is:

`.cache/phase5_synthetic_client_plan/v5-b2887ba90d81-b752a05215d7.json`

- client-plan field SHA-256:
  `34f7a44dddd24c9fa6d8c1ac69f51ed204a264c454b6daf9d039183c759cd844`;
- plan-file SHA-256:
  `2d1118da10bb4e9361689200646ace9f340deaf26c4ade4ea607ebd9cd6ecfb9`;
- file bytes: `49,153`;
- requests: `20`;
- every download, rental, process, HTTP, GPU, retained-population, project
  prompt, and scientific-execution authorization remains `false`.

V1--V4 remain preserved. V5 does not rewrite their status or evidence.

## Internal audit round 1

The first pass found a real download-to-launch gap: the post-download verifier
proved the checkpoint at one time, but the adapter had no mandatory byte-level
recheck immediately before launch. The repair adds:

- external self-hash validation for each exact checkpoint manifest;
- exact regular, single-link file-set enumeration;
- streaming size and SHA-256 re-verification before launch;
- a cheap device/inode/size/mtime seal checked again at launch;
- rejection of mutation after initial download verification.

## Internal audit round 2

The adapter and runner were attacked with mocked process, socket, and HTTP
faults. Repairs made during this pass include:

- only `127.0.0.1:8000` can be probed or contacted;
- only connection refusal counts as a free port; timeout and other errors are
  ambiguous failures;
- an absolute, regular executable is required and `shell=False` is fixed;
- `Popen` receives only the externally bound environment, never `os.environ`;
- the bound snapshot root must appear exactly once in argv;
- `--host 127.0.0.1` and `--port 8000` are mandatory;
- HTTP calls require this adapter's live child process and must match one
  frozen request contract;
- response bodies, response headers, and startup logs are independently
  bounded;
- the log path cannot be inside the exact snapshot root;
- launch failure reaps a child that was already created;
- emergency cleanup escalates from SIGTERM to SIGKILL and returns evidence
  without masking the original failure;
- a second or concurrent launch is refused;
- the runner now uses the frozen 30-second port-release window instead of a
  one-shot post-exit probe.

The tests use only temporary files and mocks. They never open a real socket or
start a real subprocess.

## Deliberate remaining boundary

V5 is not sufficient for Lock A. The following must be externally frozen and
then reviewed before any paid-machine action:

1. absolute remote argv and snapshot paths;
2. container/image identity plus the executable and installed-package
   attestation (hashing the small console-script alone is not enough);
3. exact authorized weight-download procedure and resulting snapshot
   manifests; ordinary Hugging Face cache snapshots use symlinks, so the
   served roots must be explicitly materialized as regular single-link files;
4. source-bound language-only error semantics on both checkpoints;
5. provider quote, storage policy, and whole-rental spend cap;
6. mock throughput and memory-envelope qualification;
7. final Lock-A record binding V5 and the two runtime-spec rows.

The launch-time stat seal is a local race detector, not a defense against a
privileged adversary able to replace bytes and forge filesystem metadata. The
remote workspace must therefore be single-purpose and access-controlled.

## Decision

The local implementation may proceed to a no-GPU, no-network remote-spec and
environment-attestation design. It may not start AutoDL, download the 141 GB
publisher weight set, launch vLLM, or send HTTP requests. Confirmation remains
`RESERVED_NOT_GENERATED`.
