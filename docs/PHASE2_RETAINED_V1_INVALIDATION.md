# Phase-2 retained v1 invalidation record

Status: **cross-environment result invalidated before any retained model
training**

The first retained Phase-2 run completed mechanically and passed its byte/hash
checks at Git commit
`741d5b4d5a9f876099007a527be4424f1f164e26`. Internal post-run review then
found that every Static prediction in A-to-B and B-to-A had
`parse_complete = 0`.

This was not evidence of failed abstract transfer. The Static predictor copied
the source environment's domain-native `physical_delta` object into a target
environment with a different exact field schema. The strict parser therefore
rejected the whole output before the otherwise shared `event_record` and
normative decision could be scored. The same missing destination-schema
contract would confound retained model comparisons.

No retained model output existed when this defect was found. Confirmation
remained `RESERVED_NOT_GENERATED`. Practical margins were not changed.

## Disposition

- The v1 files are preserved, not overwritten or relabelled as successful.
- V1 must not support a cross-environment capability claim or authorize model
  training.
- Its within-environment diagnostics remain historically reproducible but are
  superseded by the single retained-v2 execution.
- V2 adds only value-free destination physical field/type metadata, keeps the
  full within-environment joint estimand, and assigns the cross-environment
  bootstrap to the shared event-record-plus-N estimand.

## Preserved v1 evidence

| File | SHA-256 |
|---|---|
| `artifacts/phase2_retained/provenance_manifest.json` | `cd9b9b269dc683158d1c1df17bbd272feac6801dba835174c7a9ce97e003dcd3` |
| `artifacts/phase2_retained/static_baselines.json` | `a00d4ba7e66ff26caf45c33c4639c97598e26f13219b61f164d51c94a096f34f` |
| `artifacts/phase2_retained/evaluation_harness.json` | `0ba4303fab422cffb63f4a41b7cf6f9d933bb55084d054fa1a92a33dc73745ac` |
| `artifacts/phase2_retained/arm_data_manifest.json` | `a563989560208b3767d3cd27fcf043783f3fc2cdd1cc7c3f6bbea75b73ed7f84` |
| `artifacts/phase2_retained/transfer_manifest.json` | `a56bfade6708bf3f716c2ffcbd6f3abcd5ec620a3eeb0b93db09c36e6b9c415e` |
| `data/generated/phase2_retained/arms/joint_examples.jsonl.gz` | `2312013135ce6749fb563a37de9664bc03d1b14e18b542f23413fa4e095c9afe` |
| `data/generated/phase2_retained/arms/factorized_factual.jsonl.gz` | `4bcb90b35020b9732a1716836fd4839cadaaea29679eec80bc850e67b9419edf` |
| `data/generated/phase2_retained/arms/factorized_normative.jsonl.gz` | `9f348dbb352aa3b2e6f974fe571e3657513e544268eedccc00fced14ffca83b2` |
