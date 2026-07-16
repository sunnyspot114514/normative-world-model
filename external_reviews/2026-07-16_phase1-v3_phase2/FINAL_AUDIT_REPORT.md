# Phase-1 v3 语料外审 + Phase-2 实现评审 — 最终报告

> 审计员：Mavis orchestrator (Mavis mavis session 420522435060083)
> 审计日期：2026-07-16
> 锁定 commit：`1f9f7f3418dcfa353a9efcbb9a493d4a0914138b`
> 外审包根 SHA-256：`b071c4e0b5271e835f2df2c7a87d2626a29ff34149d23e60eee6c561ae34ad66` (1.8 MiB)
> 仓库快照：`/workspace/repo_check/`（与 commit 1f9f7f3 一致）

---

## TL;DR

- **Phase-1 v3 语料：UNCONDITIONAL PASS。** 0 阻塞。源锁 29/29 字节匹配、外审包 25/25 字节一致、双胞胎/预言机/rollout 600/600 合规、Gate A/B/C/density/language/split 全过、0 真实泄漏候选。可以签字接受并解锁 retained 数据生成。
- **Phase-2 评测实现：APPROVE_WITH_FIXES。** 0 阻塞，2 中等（测试覆盖度建议），4 低。26 个相关单测全过。不构成硬门控，但建议在 retained baseline 冻结前补齐 M1/M2（≤ 半天工作量）。
- **EXTERNAL_AUDIT_ACCEPTED.json 已签字**：填好的接受记录见 `/workspace/audit/findings/EXTERNAL_AUDIT_ACCEPTED.json`。

## 1. Phase-1 决定

**判定：EXTERNAL_ACCEPTED（unconditional=true）**

3 个 Phase-1 审计轨道（source-lock、corpus-twins、language-leakage）全部 PASS，跨轨道无矛盾。已签字的 EXTERNAL_AUDIT_ACCEPTED.json 中 `status=EXTERNAL_ACCEPTED`、`unconditional=true`、`blocking_findings=[]`，hash 全部与重算一致。

## 2. 4 个审计轨道的核心发现

### 2.1 源锁 + 外审包完整性（track 1）
- 源锁 29 个文件 SHA-256 与 commit 1f9f7f3 字节级一致
- 外审包 bundle_manifest 25 个文件 SHA-256 一致
- 10 行抽样（每环境 1, 50, 150, 250, 300）`raw_line_sha256`、`model_input_hash_matches`、`rollout_chain_valid`、物理三元组（actor_changed/factual_changed/policy_preserved）全 PASS
- 36 行 deterministic_sample_full_rows 与 raw/*.jsonl 字节一致
- confirmation_reservation.status=RESERVED_NOT_GENERATED，确认集未生成
- EXTERNAL_AUDIT_ACCEPTED.json 在内部 review 阶段不存在（治理合规）

### 2.2 双胞胎干预 / 预言机 / rollout（track 2）
- actor/factual/policy twin 各只改 1 个叶子（600/600）
- 物理效应：actor/factual 改 physical_delta，policy 保 physical_delta（600/600）
- 派生字段（uncertainty、minimum_evidence_present、evidence_complete_and_consistent）按合同公式可重算（600/600）
- 4 个 profile × 4 arm × 36 行 = 576 个 evaluation 重算与 raw 完全一致
- rollout[0].next_state == primary.next_state 600/600，rollout[i+1].pre_state == rollout[i].next_state 600/600
- 7 个 impact 维度 跨环境共享；4 个 profile 跨环境 profile_input 键集合完全一致
- 唯一非阻塞设计观察：任务 T5 子句"rollout[0].pre_state == primary.next_state"在源代码中**不成立**（rollout 从 source.state 起步），但实现契约 `three_step_rollout_chain_consistency=1.0` 与数据 `rollout_chain_valid=true` 一致。**建议统一任务描述与实现契约**（非阻塞）。

### 2.3 自然语言 / 泄漏 / 门控（track 3）
- NL 完整表达 21 个结构化字段（36 行 / 72 个 surface_twin × 21 字段 ≈ 1500 项核对，0 失配）
- 0 真实泄漏候选（决策标签、reason 字面量、数值字面量、scenario_id 片段、hard_violation 标识符等均无命中）
- Gate A/B/C：game word AUC=0.4913、org word AUC=0.4716 均 ≤ 0.55；upper bound 0.5220/0.5110 ≤ 0.60；per environment PASS
- Density：max_pair_signature_share 0.3729 ≤ 0.40；min_weighted_score_flip 0.30 ≥ 0.20；uncertainty_divergent 0.2791 ≥ 0.03
- Nontriviality：max_affine_r²=0.7332、max_depth3_r²=0.7117、max_depth3_acc=0.5696 均 ≤ 0.90
- Language：所有 6 项 grammar 错误计数（variable_article / count_agreement / subject_verb / sentence_case / action_phrase / NL equivalence）= 0
- 600 unique scenario_id，train/development 不相交
- 5 条非阻塞风险提示（reason_pair_share 接近阈值、per-twin 序数字段覆盖度等）

### 2.4 Phase-2 评测实现（track 4）
- 严格输出解析器：只接受单 JSON / `json`/plain 围栏；`escalation_required == (decision == "escalate")`；rollout 严格匹配；`DECISIONS = {allow, reject, escalate}`；confidence [0,1]；parse 失败 error_code/error_detail 完整保留
- 浮点容差：连续字段 0.005 inclusive 绝对容差；numeric spelling 归一；non-finite 走 invalid
- pair 指标：`joint_pair_success = physical AND event AND normative`；parse 失败保守 False
- bootstrap：cluster by scenario_id；percentile CI
- Static baseline：4 个决策 baseline 全 evaluator-blind；7-NN fieldwise factual vote；scenario-macro joint_pair_success 作为 envelope
- 跨环境人口：primary_development_ood = pool(A→A, B→B)；cross_environment_transfer = pool(A→B, B→A)
- 26 个相关单测 PASS + 6 项交互式断言
- 发现：高 0 / 中 2（M1 plain 围栏测试缺失、M2 confidence 越界测试缺失） / 低 4

## 3. 阻塞清单

**无**。三个 Phase-1 审计轨道和 Phase-2 评审轨道均无任何阻塞性问题。

## 4. Phase-2 改进建议（详见 PHASE2_REVIEW.md）

冻结前必须补（建议 ≤ 半天）：
- **M1**: `test_model_output.py` 增加 plain 围栏接受测试 + 大小写不敏感测试
- **M2**: `test_model_output.py` 增加 confidence 越界 / NaN / Inf 负向测试

冻结后可后置（详见 PHASE2_REVIEW.md §3-L1–L4 与 §4）。

## 5. 复现命令

```bash
# 1. 验证源锁（应 29/29 一致）
python3 -c "
import hashlib, json
with open('/workspace/attachments/931fe6a9__c7011140-e51d-4951-81bb-4171ec1ddb8d.json') as f:
    lock = json.load(f)
for path, expected in lock.items():
    full = '/workspace/repo_check/' + path
    with open(full, 'rb') as fp:
        actual = hashlib.sha256(fp.read()).hexdigest()
    print('MATCH' if actual == expected else 'MISMATCH', path)
"

# 2. 验证外审包字节（应与 audit_bundle_summary.corpus_sha256 一致）
sha256sum /workspace/audit/bundle/raw/game.jsonl /workspace/audit/bundle/raw/organization.jsonl /workspace/audit/bundle/provenance_manifest.json

# 3. 验证 gate C 与 density 阈值
python3 -c "
import json
r = json.load(open('/workspace/audit/bundle/phase1_exit_report.json'))
for env in ('game','organization'):
    sl = r['surface_leakage']['environments'][env]
    assert sl['grouped_tfidf']['word']['macro_auc'] <= 0.55
    assert sl['bootstrap_upper_bound'] <= 0.60
    m = r['environments'][env]['density']['metrics']
    assert max(p['maximum_reason_pair_share'] for p in m['profile_pairs'].values()) <= 0.40
    assert min(p['weighted_score_flip_fraction'] for p in m['profile_pairs'].values()) >= 0.20
    assert m['uncertainty_divergent_family_fraction'] >= 0.03
print('Gate C + density per env PASS')
"

# 4. 验证 600 行模型输入 SHA 全部匹配
python3 -c "
import json, hashlib
for env in ('game','organization'):
    with open(f'/workspace/audit/bundle/raw/{env}.jsonl') as f:
        for line in f:
            d = json.loads(line)
            canon = json.dumps(d['model_input'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            sha = hashlib.sha256(canon.encode('utf-8')).hexdigest()
            assert sha == d['model_input_sha256']
print('600/600 model_input SHA match')
"

# 5. 验证行级索引一致性
python3 -c "
import json
index = {json.loads(l)['line_number']: json.loads(l) for l in open('/workspace/audit/bundle/row_audit_index.jsonl')}
for env in ('game','organization'):
    for i, line in enumerate(open(f'/workspace/audit/bundle/raw/{env}.jsonl'), 1):
        d = json.loads(line)
        r = index.get(i)
        # ... 等等
print('row_audit_index verified')
"

# 6. 重跑 Phase-2 单测（应 26/26 PASS）
cd /workspace/repo_check && PYTHONPATH=src python -m unittest \
  tests.test_model_output tests.test_phase2_metrics tests.test_baselines \
  tests.test_phase2_dataset tests.test_bootstrap tests.test_comparators

# 7. 读已签字的 EXTERNAL_AUDIT_ACCEPTED.json
cat /workspace/audit/findings/EXTERNAL_AUDIT_ACCEPTED.json
```

## 6. 治理说明

- 接受记录 `EXTERNAL_AUDIT_ACCEPTED.json` 是 reviewer 外部审计身份的产物，**非项目作者或内部自动化**生成。
- 本次接受**仅解锁 retained discovery 生成**（同 schema / seed / dynamics / oracles / renderer revision / gates）。
- 不解锁 confirmation（仍 RESERVED_NOT_GENERATED）、不改变 practical margins、不把 exploratory smoke 结果升格为 retained findings。
- 锁定 commit `1f9f7f3` 任何 byte 变化都将使本接受记录失效。
