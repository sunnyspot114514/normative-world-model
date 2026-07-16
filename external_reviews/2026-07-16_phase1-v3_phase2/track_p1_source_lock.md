# Track P1-Source-Lock & Bundle 审计报告

审计员: General (root session 420529783723400)
日期: 2026-07-16
对象: Phase-1 v3 revision-1 外部 smoke 审计包
来源: /workspace/audit/bundle/  (根 SHA-256: b071c4e0b5271e835f2df2c7a87d2626a29ff34149d23e60eee6c561ae34ad66, 1.8 MiB)
源锁文件: /workspace/attachments/931fe6a9__c7011140-e51d-4951-81bb-4171ec1ddb8d.json (configs/phase1_v3_source_lock.json)
锁定 commit: 1f9f7f3418dcfa353a9efcbb9a493d4a0914138b (位于 /workspace/repo_check/)

---

## 1. 摘要

- **总体结论: PASS**
- **阻塞性问题数量: 0**

所有 29 项源锁 SHA-256 与 repo_check @ 1f9f7f3418dcfa353a9efcbb9a493d4a0914138b 的对应文件字节级一致；外审包 bundle_manifest.json 列出 25 个文件全部 SHA-256 一致；raw/*.jsonl 与 audit_bundle_summary.corpus_sha256 一致；confirmation_reservation.status="RESERVED_NOT_GENERATED" 且无任何确认集行级内容；行级 row_audit_index 在 10 个抽样行（每环境 1, 50, 150, 250, 300）上全部满足 `raw_line_sha256`、`model_input_hash_matches=true`、`rollout_chain_valid=true`、物理三元组 `actor_changed/factual_changed/policy_preserved` 真值；36 行 deterministic_sample_full_rows 与 raw/*.jsonl 对应记录 canonical-JSON 字节一致；治理侧 `EXTERNAL_AUDIT_ACCEPTED.json` 不存在、`independent_internal_audit.json` 中 `imports_project_package=false` 且 `governance.authorizes_retained_generation=false`、确认集未生成。

---

## 2. 源锁字节核对 (T1)

源锁列出 29 个文件路径 → 仓库 `/workspace/repo_check/` 对应路径全部存在，SHA-256 完全一致。

| 文件路径 | 期望 SHA-256 前 16 位 | 实际 SHA-256 前 16 位 | 状态 | 字节数 |
|---|---|---|---|---:|
| configs/calibration_cases.json | f8e8a602f91e65b8 | f8e8a602f91e65b8 | MATCH | 6018 |
| configs/evaluator_profiles.toml | 5b66d8b1e2a1562a | 5b66d8b1e2a1562a | MATCH | 2030 |
| configs/normative_predicates.toml | 60895564d1b70ad7 | 60895564d1b70ad7 | MATCH | 7770 |
| configs/preregistration_v3.toml | 62532313df6a902d | 62532313df6a902d | MATCH | 4237 |
| docs/EVALUATOR_PROFILES.md | 58263e9a5e67d0c4 | 58263e9a5e67d0c4 | MATCH | 5198 |
| docs/EXTERNAL_SMOKE_ACCEPTANCE_V3.md | 955daa18842e36a7 | 955daa18842e36a7 | MATCH | 1505 |
| docs/INTERNAL_REVIEW_PROTOCOL.md | 4f2d2f1f795ceba7 | 4f2d2f1f795ceba7 | MATCH | 2516 |
| docs/LEAKAGE_AUDIT_SPEC.md | 3d4caf112825005e | 3d4caf112825005e | MATCH | 6724 |
| docs/METRIC_COMPARATOR_V2_1.md | 00f5d7e3666757b4 | 00f5d7e3666757b4 | MATCH | 1355 |
| docs/NORMATIVE_PREDICATE_CONTRACT.md | f8e80172b8c77271 | f8e80172b8c77271 | MATCH | 11361 |
| docs/PHASE1_V2_INTERNAL_REVIEW.md | d64302b8ed9cce42 | d64302b8ed9cce42 | MATCH | 2981 |
| docs/PHASE1_V3_REVISION0_INTERNAL_REVIEW.md | 2820329aa8461f32 | 2820329aa8461f32 | MATCH | 1678 |
| PREREGISTRATION_V3.md | 9b91375bbf4040dc | 9b91375bbf4040dc | MATCH | 4220 |
| scripts/check-phase1-v3-smoke.ps1 | 1e4b4bb56929886c | 1e4b4bb56929886c | MATCH | 3959 |
| scripts/independent-smoke-audit.py | 9b8c5c27a2379c96 | 9b8c5c27a2379c96 | MATCH | 26910 |
| scripts/run-phase1-v3-smoke.py | a1b1a8c5fd510856 | a1b1a8c5fd510856 | MATCH | 921 |
| src/normative_world_model/__init__.py | 482ba1b06eb39637 | 482ba1b06eb39637 | MATCH | 367 |
| src/normative_world_model/audits.py | 44365b13ebc4024b | 44365b13ebc4024b | MATCH | 47234 |
| src/normative_world_model/calibration.py | 1d93e325d583ebeb | 1d93e325d583ebeb | MATCH | 4414 |
| src/normative_world_model/environments/__init__.py | 5a723a9396940553 | 5a723a9396940553 | MATCH | 319 |
| src/normative_world_model/environments/game.py | 75cce92f9eb72290 | 75cce92f9eb72290 | MATCH | 14631 |
| src/normative_world_model/environments/organization.py | dfea9bfee20811be | dfea9bfee20811be | MATCH | 14912 |
| src/normative_world_model/generator.py | e8d9786a46b1ea47 | e8d9786a46b1ea47 | MATCH | 30794 |
| src/normative_world_model/normative_oracle.py | 9ca64e4924ba0023 | 9ca64e4924ba0023 | MATCH | 6873 |
| src/normative_world_model/ontology.py | 7ba6c22acb15a29f | 7ba6c22acb15a29f | MATCH | 1587 |
| src/normative_world_model/phase1_v3.py | a0a5fb894f1b681a | a0a5fb894f1b681a | MATCH | 24581 |
| src/normative_world_model/policy_oracle.py | 70d32efae5db5128 | 70d32efae5db5128 | MATCH | 2399 |
| src/normative_world_model/reachability.py | 871c0f67d2f23916 | 871c0f67d2f23916 | MATCH | 4178 |
| src/normative_world_model/simulation.py | 76161a79c74b35c5 | 76161a79c74b35c5 | MATCH | 6316 |

29/29 MATCH，无 missing，无 mismatch。

---

## 3. 外审包字节核对 (T2)

### 3.1 raw/*.jsonl ↔ audit_bundle_summary.corpus_sha256

| 文件 | bundle_manifest 期望 | 实际 sha256sum | 状态 | 字节数 |
|---|---|---|---|---:|
| raw/game.jsonl | afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768 | afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768 | MATCH | 12,616,226 |
| raw/organization.jsonl | ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92 | ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92 | MATCH | 13,158,196 |

### 3.2 bundle_manifest.json 全文件 SHA-256

25/25 全部 MATCH，列出如下：

| 文件 | 期望 SHA-256 前 16 位 | 实际 SHA-256 前 16 位 | 状态 | 字节数 |
|---|---|---|---|---:|
| AUDIT_README.md | 4905c3c457d0ffdf | 4905c3c457d0ffdf | MATCH | 567 |
| DATASET_CARD.md | 559ede628ae95c0a | 559ede628ae95c0a | MATCH | 995 |
| EXTERNAL_AUDIT_ACCEPTED.template.json | 9b388eee637922e1 | 9b388eee637922e1 | MATCH | 618 |
| audit_bundle_summary.json | 816863b61a574638 | 816863b61a574638 | MATCH | 797 |
| confirmation_reservation.json | f26e5b70338e7a8e | f26e5b70338e7a8e | MATCH | 5,516 |
| contracts/EVALUATOR_PROFILES.md | 58263e9a5e67d0c4 | 58263e9a5e67d0c4 | MATCH | 5,198 |
| contracts/EXTERNAL_SMOKE_ACCEPTANCE_V3.md | 955daa18842e36a7 | 955daa18842e36a7 | MATCH | 1,505 |
| contracts/INTERNAL_REVIEW_PROTOCOL.md | 4f2d2f1f795ceba7 | 4f2d2f1f795ceba7 | MATCH | 2,516 |
| contracts/LEAKAGE_AUDIT_SPEC.md | 3d4caf112825005e | 3d4caf112825005e | MATCH | 6,724 |
| contracts/METRIC_COMPARATOR_V2_1.md | 00f5d7e3666757b4 | 00f5d7e3666757b4 | MATCH | 1,355 |
| contracts/NORMATIVE_PREDICATE_CONTRACT.md | f8e80172b8c77271 | f8e80172b8c77271 | MATCH | 11,361 |
| contracts/PHASE1_V2_INTERNAL_REVIEW.md | d64302b8ed9cce42 | d64302b8ed9cce42 | MATCH | 2,981 |
| contracts/PHASE1_V3_INTERNAL_SMOKE.md | a52a6414e61136a7 | a52a6414e61136a7 | MATCH | 4,267 |
| contracts/PHASE1_V3_REVISION0_INTERNAL_REVIEW.md | 2820329aa8461f32 | 2820329aa8461f32 | MATCH | 1,678 |
| contracts/PREREGISTRATION_V3.md | 9b91375bbf4040dc | 9b91375bbf4040dc | MATCH | 4,220 |
| contracts/preregistration_v3.toml | 62532313df6a902d | 62532313df6a902d | MATCH | 4,237 |
| deterministic_review_sample.json | 56578482b19755b4 | 56578482b19755b4 | MATCH | 426,754 |
| deterministic_sample_full_rows.jsonl | 8496db8d5add185a | 8496db8d5add185a | MATCH | 1,545,976 |
| independent_internal_audit.json | feccfc72c07dbb24 | feccfc72c07dbb24 | MATCH | 789 |
| phase1_exit_report.json | 843f0d0e89e93a3d | 843f0d0e89e93a3d | MATCH | 40,332 |
| provenance_manifest.json | caa9beb623666382 | caa9beb623666382 | MATCH | 4,645 |
| raw/game.jsonl | afbe64f9b4a66ab6 | afbe64f9b4a66ab6 | MATCH | 12,616,226 |
| raw/organization.jsonl | ef2633bba4c9fece | ef2633bba4c9fece | MATCH | 13,158,196 |
| row_audit_index.jsonl | 3718d8bf91660289 | 3718d8bf91660289 | MATCH | 461,955 |
| uncertainty_reachability.md | 3310123eae8d3396 | 3310123eae8d3396 | MATCH | 10,034 |

### 3.3 confirmation_reservation.json 状态

- `status = "RESERVED_NOT_GENERATED"` ✅
- 不含 `scenarios` / `scenario_id` / 行级目标等任何确认集内容 ✅
- `seed_commitment`、`commitment_inputs_sha256`、`commitment_input_manifest` 完整但均为元数据级别，不暴露具体确认场景 ✅
- `note: "No confirmation scenarios or targets were generated."` ✅

---

## 4. 合同一致性 (T3)

### 4.1 EXTERNAL_AUDIT_ACCEPTED.template.json 字段契约

合同 `contracts/EXTERNAL_SMOKE_ACCEPTANCE_V3.md` 规定的接受记录必须字段：

| 字段 | 模板字段 | 模板类型/示例 | 合同要求 | 结论 |
|---|---|---|---|---|
| status | "REVIEW_REQUIRED" | str | 接受后必须为 "EXTERNAL_ACCEPTED" | OK（模板占位） |
| unconditional | false | bool | 接受后必须为 true | OK（模板占位） |
| preregistration_version | 3 | int | 必须为 3 | OK |
| generator_revision | 1 | int | 必须为 1 | OK |
| run_kind | "v3_internal_smoke" | str | 合同明示该值 | OK |
| reviewer | "" | str | "external reviewer identity" | OK（模板空待填） |
| reviewed_at | "" | str | "ISO-8601 timestamp" | OK（模板空待填） |
| provenance_manifest_sha256 | "caa9beb..." | hex64 | "exact sha256" | OK（与 manifest 字节哈希一致） |
| corpus_sha256 | {game: afbe64..., org: ef2633...} | dict | exact sha256 对应两个文件 | OK（与 raw/*.jsonl 字节哈希一致） |
| blocking_findings | [] | list | 接受后必须为 [] | OK（模板占位） |

合同另有"额外禁止条款"，本模板未引入 reviewer/conditions/reservation 字段冲突 — 模板与合同契约完全一致。

### 4.2 preregistration_v3.toml 与 run_kind 一致性

`configs/preregistration_v3.toml`:
- `preregistration_version=3`（schema_version 字段） → 与 EXTERNAL 模板 `preregistration_version: 3` 一致 ✅
- `must_freeze_before_discovery = true` → 合同对 v3_renderer_reset_frozen 状态要求冻结 ✅
- `internal_review_may_authorize_retained = false` → 与模板 unconditional=false 方向一致 ✅
- `external_acceptance_required_before_retained = true` → 接受记录绑定后才允许 retained 路径 ✅
- `status = "v3_renderer_reset_frozen"` 与 `run_kind = "v3_internal_smoke"` 内部一致 ✅
- 模板中 `generator_revision: 1` 与 `[stopping].generator_schema_revisions_used = 1` 一致 ✅

### 4.3 contracts/PHASE1_V3_INTERNAL_SMOKE.md 与 raw/*.jsonl

合同内"Fixed corpus hashes"段：
- game JSONL: `afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768` ↔ raw/game.jsonl `afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768` ✅
- organization JSONL: `ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92` ↔ raw/organization.jsonl `ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92` ✅
- confirmation reservation: `f26e5b70338e7a8ee45d5ec4329221de5cb4b199cab40dd547c3b9f4753c5d27` ↔ bundle confirmation_reservation.json `f26e5b70338e7a8e...` ✅
- provenance manifest: `caa9beb6236663823b5126c94c318ca20e59aca2e99efa0c735b72f68f91e88a` ↔ bundle provenance_manifest.json `caa9beb...` ✅
- deterministic readable-review sample: `56578482b19755b4342150aab8eea74fd2be16da70c149be304f35c4ab69cf89` ↔ bundle deterministic_review_sample.json `56578482b19755b4...` ✅

### 4.4 contracts/PHASE1_V2_INTERNAL_REVIEW.md / PHASE1_V3_REVISION0_INTERNAL_REVIEW.md 与本包哈希隔离

| 版本 | game hash | organization hash | provenance hash | 与本外审包关系 |
|---|---|---|---|---|
| v2（已废弃） | 631d5cdc725cb2011382b630d05417eadaf6d5531db933307656eb20faa7b48c | 9277eb9aaa3634a3a3e5363e4f9451b29d70b0688469649c07721a04d02fbc2b | 72786321f920a5427291c4fd82d7fd5a9e8a904f6dcaaeea5cc69de5fd63a431 | 不冲突（不同值） ✅ |
| v3 revision-0（已废弃） | 83555e8f6b3634b703635d010c15598c1ccc92542e13fed33462738ba5c4776b | 6f85adf999bbea0e4d1a27150f60d5c802faa63c8ffb25a6be518f91fce23557 | 2694c009e77dc4796258324b9af7c2932ea7c38daf8b6e20ff20deb343469bf4 | 不冲突（不同值） ✅ |
| v3 revision-1（本包） | afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768 | ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92 | caa9beb6236663823b5126c94c318ca20e59aca2e99efa0c735b72f68f91e88a | 现役 |

三组哈希彼此正交 → 不存在错误复用旧版 corpus / provenance 的可能。

---

## 5. 行级索引与原始字节 (T4)

### 5.1 抽样 10 行的 raw_line_sha256 比对

抽样的 `raw_line_sha256` 期望值 = `sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',',':')))`。
说明：原始 JSONL 文件每行末尾有 `\n`，但行级 `raw_line_sha256` 在 row_audit_index 中按"规范 JSON"（sort_keys, 紧凑分隔符）计算；这是 deterministic_sample_full_rows.jsonl 与 raw 记录能完全字节匹配的同一规范。

| env | line | 索引 raw_line_sha256 前 16 | 独立重算 前 16 | 匹配 | 字节数 |
|---|---|---|---|---|---:|
| game | 1 | 9122a5aa0e75444a | 9122a5aa0e75444a | ✅ | 42,039 |
| game | 50 | 56651a3dd405a9b4 | 56651a3dd405a9b4 | ✅ | 41,329 |
| game | 150 | 338c437e1011e147 | 338c437e1011e147 | ✅ | 41,930 |
| game | 250 | af13447a4dad2f08 | af13447a4dad2f08 | ✅ | 42,026 |
| game | 300 | a4127af482c063e6 | a4127af482c063e6 | ✅ | 42,029 |
| organization | 1 | 8cbb450e967c1e04 | 8cbb450e967c1e04 | ✅ | 44,223 |
| organization | 50 | 60138cac32af48ff | 60138cac32af48ff | ✅ | 43,586 |
| organization | 150 | 3dec13972c533fb4 | 3dec13972c533fb4 | ✅ | 44,390 |
| organization | 250 | 8e6933e2efa14a9d | 8e6933e2efa14a9d | ✅ | 43,583 |
| organization | 300 | f04ab9421f881d83 | f04ab9421f881d83 | ✅ | 43,857 |

10/10 MATCH。

### 5.2 抽样 10 行的 model_input canonical SHA-256

| env | line | 存储 stored_model_input_sha256 前 16 | 独立重算 model_input canonical 前 16 | 匹配 | model_input_hash_matches | rollout_chain_valid |
|---|---|---|---|---|---|---|
| game | 1 | 67a0b320f337378b | 67a0b320f337378b | ✅ | true | true |
| game | 50 | f8d7a7cf2d03ec69 | f8d7a7cf2d03ec69 | ✅ | true | true |
| game | 150 | b6e6ba3fb68a6c9d | b6e6ba3fb68a6c9d | ✅ | true | true |
| game | 250 | 553613a98c51a6e1 | 553613a98c51a6e1 | ✅ | true | true |
| game | 300 | 2ebc5d5533b52c86 | 2ebc5d5533b52c86 | ✅ | true | true |
| organization | 1 | 1fa15464c92c4fc8 | 1fa15464c92c4fc8 | ✅ | true | true |
| organization | 50 | e8d9f47ed9741528 | e8d9f47ed9741528 | ✅ | true | true |
| organization | 150 | 0f82e999c83b13d7 | 0f82e999c83b13d7 | ✅ | true | true |
| organization | 250 | f6fa4c0c68e16394 | f6fa4c0c68e16394 | ✅ | true | true |
| organization | 300 | f23db00a23c1fbc1 | f23db00a23c1fbc1 | ✅ | true | true |

10/10 全部 model_input hash 匹配 + rollout chain 有效。

### 5.3 抽样 10 行的 physical_relations

| env | line | actor_changed | factual_changed | policy_preserved |
|---|---|---|---|---|
| game | 1 | true | true | true |
| game | 50 | true | true | true |
| game | 150 | true | true | true |
| game | 250 | true | true | true |
| game | 300 | true | true | true |
| organization | 1 | true | true | true |
| organization | 50 | true | true | true |
| organization | 150 | true | true | true |
| organization | 250 | true | true | true |
| organization | 300 | true | true | true |

10/10 全部满足三元组（actor_changed ∧ factual_changed ∧ policy_preserved）。

### 5.4 deterministic_sample_full_rows.jsonl (36 行) 与 raw/*.jsonl 对应记录 canonical-JSON 字节一致

将 36 条记录通过 `scenario_id` 映射到 raw/*.jsonl，再以 `sort_keys=True, separators=(',',':')` 序列化后逐字符比较：
- 36/36 全部 MATCH（无任何字节差异）
- game 抽样 + organization 抽样都覆盖了

### 5.5 index_checks 总量（与 audit_bundle_summary 对账）

| 指标 | summary 报告 | 独立全量重算 | 一致 |
|---|---:|---:|---|
| total_rows | 600 | 600 | ✅ |
| model_input_hash_mismatch_count | 0 | 0 | ✅ |
| invalid_rollout_chain_count | 0 | 0 | ✅ |
| actor_physical_unchanged_count | 0 | 0 | ✅ |
| factual_physical_unchanged_count | 0 | 0 | ✅ |
| policy_physical_changed_count | 0 | 0 | ✅ |
| exact_boundary_row_count | 7 | 7 | ✅ |

---

## 6. 治理与独立性 (T5)

### 6.1 EXTERNAL_AUDIT_ACCEPTED.json 不存在

`contracts/INTERNAL_REVIEW_PROTOCOL.md` 显式禁止"create or imitate EXTERNAL_AUDIT_ACCEPTED.json"。
- 当前 `/workspace/audit/bundle/` 下没有 `EXTERNAL_AUDIT_ACCEPTED.json` ✅
- 仅有 `EXTERNAL_AUDIT_ACCEPTED.template.json`（占位模板，status="REVIEW_REQUIRED", unconditional=false, reviewer/reviewed_at 空），用于外部 reviewer 后续填写 ✅
- 治理合规：内部 review 未冒充外部接受 ✅

### 6.2 independent_internal_audit.json 三项必查

| 字段 | 期望 | 实际 | 状态 |
|---|---|---|---|
| imports_project_package | false | false | ✅ |
| governance.authorizes_retained_generation | false | false | ✅ |
| governance.creates_external_acceptance | false | false | ✅ |
| raw_corpus_sha256.game | afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768 | 一致 | ✅ |
| raw_corpus_sha256.organization | ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92 | 一致 | ✅ |
| independent_implementation | true | true | ✅ |
| status | PASS | PASS | ✅ |

### 6.3 confirmation_reservation 与 raw/*.jsonl 无 scenario_id 共享

- `confirmation_reservation.json` 不含 `scenarios`/`scenario_id`/`scenario_families` 等任何具体条目 ✅
- raw/game.jsonl 300 个 scenario_id、raw/organization.jsonl 300 个 scenario_id 彼此完全无交集（0 overlap）✅
- 在 500 个预期 unique_scenario_families × 2 environments 配置下，确认集为"占位未生成"状态，与合同对齐 ✅

---

## 7. 阻塞性问题清单

| # | 严重度 | 描述 | 证据 | 修复建议 |
|---|---|---|---|---|
| — | — | （无） | — | — |

**阻塞性问题数量: 0**

---

## 8. 风险提示（非阻断）

| # | 严重度 | 描述 | 备注 |
|---|---|---|---|
| R1 | 低 | `row_audit_index.jsonl` 的 `raw_line_sha256` 使用"规范 JSON"（sort_keys=True, 紧凑分隔符）计算，并非原始 JSONL 字节（含换行符）的 SHA-256。如果未来 reviewer 期望"行字节哈希"，需要事先在 contract 中明示口径。 | 本审计口径与 `deterministic_sample_full_rows.jsonl` 内部序列化一致；摘要 `index_checks` 报告的 `model_input_hash_mismatch_count=0` 已由独立重算确认。 |
| R2 | 低 | `audit_bundle_summary.json` / `bundle_manifest.json` 中 "raw/*.jsonl" 路径使用 POSIX 前缀斜杠，而 `provenance_manifest.json` 中使用反斜杠（`data\generated\phase1_v3_smoke\game.jsonl`）。两套路径表示等价，但建议统一为 POSIX 以减少人工核查混淆。 | 哈希值无歧义，已逐项核对。 |
| R3 | 低 | `EXTERNAL_AUDIT_ACCEPTED.template.json` 当前 `status="REVIEW_REQUIRED"`、`unconditional=false`、`reviewer=""`、`reviewed_at=""`，是合法占位状态。Reviewer 在签字前应保持 `unconditional=true` 才会触发接受。 | 合同 `EXTERNAL_SMOKE_ACCEPTANCE_V3.md` 已显式禁止"conditions/reservations"，模板与合同契约一致。 |

---

## 9. 附：复现命令清单

```bash
# === T1 ===
# 比对源锁 29 项
python3 - <<'PY'
import json, hashlib, os
src_lock = json.load(open('/workspace/attachments/931fe6a9__c7011140-e51d-4951-81bb-4171ec1ddb8d.json'))
mismatches=missing=0
for p, exp in src_lock.items():
    full = f'/workspace/repo_check/{p}'
    if not os.path.exists(full):
        missing+=1; print('MISSING', p); continue
    act = hashlib.sha256(open(full,'rb').read()).hexdigest()
    if act != exp:
        mismatches+=1
        print('MISMATCH', p, exp, act)
print(f'T1: missing={missing} mismatches={mismatches} (expect 0/0)')
PY

# === T2 ===
# raw/*.jsonl 字节哈希
sha256sum /workspace/audit/bundle/raw/game.jsonl /workspace/audit/bundle/raw/organization.jsonl
# bundle_manifest 全文件哈希
python3 - <<'PY'
import json, hashlib
bm = json.load(open('/workspace/audit/bundle/bundle_manifest.json'))
miss=mis=0
for p, exp in bm['files'].items():
    full = f'/workspace/audit/bundle/{p}'
    try:
        act = hashlib.sha256(open(full,'rb').read()).hexdigest()
    except FileNotFoundError:
        miss+=1; print('MISSING', p); continue
    if act != exp: mis+=1; print('MISMATCH', p)
print(f'T2: missing={miss} mismatches={mis} (expect 0/0)')
PY
# confirmation_reservation 状态
python3 -c "import json; d=json.load(open('/workspace/audit/bundle/confirmation_reservation.json')); assert d['status']=='RESERVED_NOT_GENERATED'; print('OK')"

# === T3 ===
# 模板字段对齐
python3 -c "import json; t=json.load(open('/workspace/audit/bundle/EXTERNAL_AUDIT_ACCEPTED.template.json')); print(json.dumps(t, indent=2))"
# preregistration_v3.toml
grep -E "schema_version|must_freeze_before_discovery|internal_review_may_authorize_retained|external_acceptance_required_before_retained|generator_schema_revisions_used" /workspace/audit/bundle/contracts/preregistration_v3.toml

# === T4 ===
python3 - <<'PY'
import json, hashlib
def canon(d): return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',',':'))
def get_raw(p, n):
    with open(p,'rb') as f:
        for i, line in enumerate(f, 1):
            if i==n: return json.loads(line)
idx={}
with open('/workspace/audit/bundle/row_audit_index.jsonl') as f:
    for line in f:
        r=json.loads(line)
        idx.setdefault(r['environment'], {})[r['line_number']]=r
ok=True
for env in ['game','organization']:
    for n in [1,50,150,250,300]:
        raw=get_raw(f'/workspace/audit/bundle/raw/{env}.jsonl', n)
        r=idx[env][n]
        c1=hashlib.sha256(canon(raw).encode()).hexdigest()
        c2=hashlib.sha256(canon(raw['model_input']).encode()).hexdigest()
        if c1!=r['raw_line_sha256']: print('RAW_SHA_MISMATCH', env, n); ok=False
        if c2!=r['stored_model_input_sha256']: print('MI_SHA_MISMATCH', env, n); ok=False
        if not r['model_input_hash_matches']: print('MI_HASH_FLAG', env, n); ok=False
        if not r['rollout_chain_valid']: print('ROLLOUT_INVALID', env, n); ok=False
        p=r['physical_relations']
        if not (p['actor_changed'] and p['factual_changed'] and p['policy_preserved']):
            print('PHYS_TUPLE_FAIL', env, n, p); ok=False
print('T4 sample 10:', 'OK' if ok else 'FAIL')
PY
# 36 行 deterministic_sample 与 raw 对账
python3 - <<'PY'
import json
def canon(d): return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(',',':'))
def load(p): return [json.loads(l) for l in open(p)]
rg=load('/workspace/audit/bundle/raw/game.jsonl')
ro=load('/workspace/audit/bundle/raw/organization.jsonl')
m={r['scenario_id']:r for r in rg+ro}
ok=0
for r in load('/workspace/audit/bundle/deterministic_sample_full_rows.jsonl'):
    raw=m.get(r['scenario_id'])
    if raw and canon(raw)==canon(r): ok+=1
print('T4 DSFR:', ok, '/', 36)
PY

# === T5 ===
# 外部接受文件不存在
test ! -e /workspace/audit/bundle/EXTERNAL_AUDIT_ACCEPTED.json && echo "T5.1 OK"
# 独立审计三项
python3 -c "import json; a=json.load(open('/workspace/audit/bundle/independent_internal_audit.json')); print(a['imports_project_package'], a['governance']['authorizes_retained_generation'], a['raw_corpus_sha256'])"
# 确认集与 raw 无 scenario_id 共享
python3 - <<'PY'
import json
c=json.load(open('/workspace/audit/bundle/confirmation_reservation.json'))
assert c['status']=='RESERVED_NOT_GENERATED'
assert 'scenarios' not in c and 'scenario_id' not in c
g={json.loads(l)['scenario_id'] for l in open('/workspace/audit/bundle/raw/game.jsonl')}
o={json.loads(l)['scenario_id'] for l in open('/workspace/audit/bundle/raw/organization.jsonl')}
print('T5.3 raw cross-overlap:', len(g&o))  # expect 0
PY
```

---

**审计结论**: 该外审包在源锁、字节完整性、行级索引、规范 JSON 哈希、合同一致性、治理与独立性方面全部通过 T1–T5 检查；无阻塞性问题；可以进入下一阶段的契约/语义审计（track_p1_corpus_twins、track_p1_language_leakage 等）。
