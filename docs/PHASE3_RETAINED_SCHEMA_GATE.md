# Phase-3 retained schema-convergence gate

Status: **frozen before any retained model update**

This is a narrow retained-discovery engineering experiment, not the retained
joint-versus-factorized comparison. It asks whether adding the value-free
destination physical schema is enough for the cached 1.7B base model and LoRA
path to begin emitting strictly parseable one-step outputs.

## Frozen run

- model: `Qwen/Qwen3-1.7B-Base` at revision
  `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`;
- arm: `joint_naive` only;
- data: the retained Phase-1 discovery families rendered through the
  hash-locked Phase-2 v2 one-step interface;
- 64 balanced unique training pairs and 64 optimizer updates;
- 16 deterministic structured development generations from 16 unique
  scenario families, balanced over both environments and all four profiles;
- no rollout target beyond the required empty one-step `rollout` list;
- no confirmation content;
- no server rental.

The run passes only if:

1. training loss remains finite;
2. peak allocated GPU memory remains at or below 95%;
3. all 16 frozen development attempts execute;
4. at least 25% pass the exact output parser.

The threshold is an engineering gate, not an effect-size estimate. Failure
stops the generative path before any retained arm comparison and sends the
project to constrained decoding or schema-native prediction heads.

## Claim boundary

Passing would show only that strict structured generation is viable enough to
implement the preregistered slot-level consistency objective. It would not
show factual correctness, normative transfer, leakage control, model
superiority, or confirmation performance.

The existing gold-token consistency proxy is not used: this gate trains only
`joint_naive`. Formal `joint_consistency` remains blocked until the
JS/Huber-by-slot objective is implemented and separately frozen.
