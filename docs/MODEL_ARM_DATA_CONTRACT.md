# Model-arm data contract

Status: **exploratory smoke exports implemented; no model has been trained**

The three scientific arms share the same scenario families, splits, presentation surfaces, output
schema, and evaluation harness. The exports are deterministic gzip JSONL files under ignored
project-local paths.

## Joint arms

`joint_naive` and `joint_consistency` use the same `joint_examples.jsonl.gz` records. Each record
contains:

- one structured or natural-language input;
- one full physical/event/normative target;
- a semantic evaluator-pair group;
- a profile surface-sham group;
- preregistered target-pair memberships.

The difference between the arms is training loss, not data access:

- `joint_naive`: supervised physical, event-record, and normative losses only;
- `joint_consistency`: the same losses plus factual invariance over semantic evaluator and
  profile-surface groups.

The consistency objective applies only to `physical_delta` and `event_record`. It explicitly
excludes `normative_decision` and `escalation_required`.

Model targets preserve the declared schema order rather than alphabetically sorting keys. In the
one-step joint view, `physical_delta` and `event_record` therefore form one shared gold factual
prefix before the normative fields. Canonical source JSON remains key-sorted; only target ordering
is specialized for the decoder consistency objective.

Each joint record also carries `factual_prefix_text` and `normative_suffix_text`. Their exact
concatenation must equal `target_text`; the tokenizer encodes them separately so factual logit
positions are defined without substring search or BPE boundary guessing.

## Factorized arm

The factorized pipeline has two components.

### Factual component

`factorized_factual.jsonl.gz` contains only the pre-transition source and requests:

```text
physical_delta
event_record
rollout
```

The evaluator profile is absent from every factual input. The export gate searches every factual
prompt for evaluator-profile headings, weight/veto terminology, thresholds, and structured profile
keys. Any hit fails the export.

### Normative component

`factorized_normative.jsonl.gz` receives:

- a structured event record;
- the deterministic policy-oracle output object;
- a structured or natural-language evaluator profile.

It predicts only:

```text
normative_decision
escalation_required
```

Teacher-forced training may use the gold event record and policy result. Evaluation may not: it must
use the factorized factual prediction and recompute the policy result through the deterministic
policy oracle before invoking the normative component.

## Current smoke export

The deterministic export contains:

| file | records | SHA-256 |
|---|---:|---|
| `joint_examples.jsonl.gz` | 14,400 | `b74c008be1bf493d7685cb3fca86f9c8a3f5d35f7f728f35d4ad09248fb17c9e` |
| `factorized_factual.jsonl.gz` | 1,800 | `771b4335e3e8fc30404df7875331865303055ee84743d5e16f65ed38d4f9c328` |
| `factorized_normative.jsonl.gz` | 9,600 | `3fb50aec9ebcd6f9d0f63fb1b4258b80c7b536a61ea30b5cfd3f5f949cf956a9` |

The factorized factual evaluator-visibility failure count is zero. These files are smoke-scale
infrastructure artifacts, not retained training data.

## Local one-step view

The initial local pilot follows the execution-plan rule to pass one-step gates before adding
rollouts. It therefore exports a separate ignored view whose required `rollout` target is an empty
list:

| file | records | SHA-256 |
|---|---:|---|
| `joint_one_step.jsonl.gz` | 14,400 | `fe6d3383516a5d054c816111de676b5e81e3cc6096064afa7fddbe6ed7a1300c` |
| `factorized_factual_one_step.jsonl.gz` | 1,800 | `e1b307974135a61d7444317fc8a2864ee9043f2c922373f16f13b6194396f03b` |
| `factorized_normative.jsonl.gz` | 9,600 | `3fb50aec9ebcd6f9d0f63fb1b4258b80c7b536a61ea30b5cfd3f5f949cf956a9` |

This view is derived from the exact v3 smoke hashes and does not alter the stored Phase-1 rows.
Full H1/H2/H3 targets remain in the Phase-2 export for later rollout work.

## Budget matching

Later training configurations must report:

- unique scenario-family count;
- presentation count;
- target-token count;
- optimizer-update count;
- maximum input/output tokens;
- trainable parameter count;
- wall-clock time and peak memory.

Matching only row counts is insufficient because the factorized arm has two components and the joint
arms emit a larger schema. Primary comparisons match unique scenario families and total target-token
budget; update-count and compute-matched analyses are secondary diagnostics.
