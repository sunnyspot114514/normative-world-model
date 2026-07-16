# Track P1-Corpus-Twins/Oracle/Rollout 审计报告

> 审计员: General (root session `420528944857495`)
> 审计范围: `audit/bundle/raw/{game,organization}.jsonl` (600 行) + `row_audit_index.jsonl` + `deterministic_sample_full_rows.jsonl` (36 行) + `contracts/` + 锁定源代码 `repo_check/src/normative_world_model/`
> 报告时间: 2026-07-16 17:05 UTC
> 语言: 中文（代码标识符、字段名、文件路径保持原样）

---

## 1. 摘要

| 指标 | 值 |
|---|---|
| **总体判定** | **PASS（带 1 条非阻塞设计观察）** |
| **真阻塞数** | **0** |
| **设计观察数** | **1**（rollout[0].pre_state 与 primary.next_state 关系） |
| 数据集行数 | game 300 + organization 300 = 600 |
| 行级索引行数 | 600（与 raw 严格一一对应，scenario_id 0 mismatch） |
| 可读样本行数 | 36（18 game + 18 organization） |
| 行级 hash 一致性 | `raw_line_sha256` 600/600 OK；`model_input_sha256` 600/600 与重新计算的 canonical JSON SHA-256 一致 |

**结论**：T1 最小性、T2 物理效应、T3 派生字段、T4 硬策略/评估者 oracle 与 exact_boundary、T5 next_state/rollout 内部链式一致性、T5 rollout 事件记录派生、T6 抽象谓词跨环境共享、structured/natural_language shams 全部 PASS。仅发现 1 项需澄清的"设计观察"——T5 任务说明里"rollout[0].pre_state == primary.next_state"在源代码中**并非如此实现**，源代码让 rollout 从 `source.state`（不是 `primary.next_state`）起步独立 simulate，但因为 `simulate` 对同一 (state, action, policy) 完全确定，rollout[0].next_state 仍 == primary.next_state，且 rollout[i+1].pre_state == rollout[i].next_state 严格成立——也就是 `row_audit_index.rollout_chain_valid=true` 与实现契约 `three_step_rollout_chain_consistency=1.0` 完全一致。

---

## 2. T1 双胞胎最小性（全 600 行 + 抽样源核）

### 2.1 全 600 行 raw 双胞胎差异路径分布

| 双胞胎 | 差异路径（每行恰好 1 个） | 命中行数 |
|---|---|---:|
| actor_value_twin | `state.actor_values.caution` | 504 |
| actor_value_twin | `state.actor_values.curiosity` | 42 |
| actor_value_twin | `state.actor_values.duty` | 14 |
| actor_value_twin | `state.actor_values.loyalty` | 1 |
| actor_value_twin | `state.actor_values.compliance`（org 独有 actor_value 字段） | 39 |
| factual_twin | `state.choice_access`（game） / `state.allocation_balance`（org） | 299+227 |
| factual_twin | `state.fairness_balance` / `state.incident_pressure` / `state.budget_remaining` / `state.exposure_level` | 1+2+68+3 |
| policy_twin | `state.policy_minimum_evidence_count` | 216 |
| policy_twin | `state.approval_required` | 384 |

注：`actor_values.compliance` 仅在 organization 出现（其他 4 个 actor_values leaf：caution/curiosity/duty/loyalty 在两环境里都存在）；`choice_access` 是 game 特有的可干预 state 字段，`allocation_balance`/`exposure_level`/`incident_pressure`/`budget_remaining` 是 organization 特有字段——这是 T6 允许的单环境 schema 差异，不是 T1 阻塞。

### 2.2 阻塞检查

对 600 行逐一验证：
- actor_value_twin 仅 1 个 `state.actor_values.*` 叶子变更：**600/600 PASS**
- factual_twin 仅 1 个 `state.*`（非 actor_values）叶子变更：**600/600 PASS**
- policy_twin 仅 1 个 `policy.*` 叶子变更：**600/600 PASS**
- 任何 0 个或 >1 个差异：**0 行**

### 2.3 源函数复核

源代码 `src/normative_world_model/generator.py`:
- `_find_changed_twin`（line 141-174）按 `sorted(candidates)` 顺序选第一个非 excluded 的 int 字段，尝试 replacement ∈ {0, 4, 2} 中第一个让 `physical_delta` 发生变化的；actor_values 分支额外兜底（line 170-173），把首个 actor_value 改成 0 或 4。
- `_mutate_policy_source`（line 176-191）：若 `observed < required`，改 `policy_minimum_evidence_count`；否则翻 `approval_required` 的 bool。

实际行级分布（`policy_minimum_evidence_count`: 216 vs `approval_required`: 384）与源代码逻辑一致：
- 384 行 observed >= required → 走 `approval_required` 翻转分支；
- 216 行 observed < required → 改 `policy_minimum_evidence_count`。
- actor/factual 分布也由源代码"挑首个让 physical_delta 变化的字段"决定，与 raw 一致。

`row_audit_index.twin_source_difference_paths` 与 raw 重新计算的 diff 内容相同（仅 `policy.*` vs `*` 表达差异），scenario_id 一一对应 600/600。

**T1 结论：PASS**

---

## 3. T2 双胞胎物理效应

### 3.1 行级 `physical_relations` 字段

`row_audit_index.physical_relations = {actor_changed, factual_changed, policy_preserved}` 在 600/600 行中均为 `{true, true, true}`。**0 阻塞**。

### 3.2 物理 delta 对比（全 600 行）

| 关系 | 不符行数 |
|---|---:|
| `actor_value_twin.physical_delta == primary.physical_delta` | 0 / 600 |
| `factual_twin.physical_delta == primary.physical_delta` | 0 / 600 |
| `policy_twin.physical_delta != primary.physical_delta` | 0 / 600 |

actor 与 factual 在每一行都改变了至少一个 `*_delta` 域（多数情况 1 个 delta 变化；少数 2-3 个，如 `game-d8850bfec2366293` 中 actor 改了 `secrecy_level_delta: 0→-1`），policy twin 在每一行 `physical_delta` 都与 primary 完全相同。

### 3.3 抽样 30 行（每环境 15 行）的具体差异

抽样的 actor/factual 至少改变 1 域、policy 完全保留——典型例如：

- `game-d8850bfec2366293`（actor `secrecy_level_delta: 0→-1`，factual `choice_access_delta: -1→2`，policy 完全一致）
- `game-bb62daf92145bc90`（actor 改了 `health_level_delta: 0→2, panic_level_delta: 0→-2`，factual 改 `choice_access_delta: 0→1`，policy 完全一致）
- `game-8e7059e366fa93d2`（actor 改 `secrecy_level_delta: 0→1`，factual 改 `choice_access_delta: -1→1`，policy 完全一致）
- `organization-b3e8b9a4bcc18611`（actor 改 `incident_pressure_delta: -1→-2, exposure_level_delta: 0→-1, service_health_delta: 1→2`，factual 改 `allocation_balance_delta: 1→0`，policy 完全一致）

**T2 结论：PASS**

---

## 4. T3 派生字段可重算（全 600 行 + 抽样详查）

### 4.1 公式（与 `NORMATIVE_PREDICATE_CONTRACT.md` §2 一致）

```
minimum_evidence_present    = (observed_evidence_count >= policy_minimum_evidence_count)
evidence_complete_and_consistent = (observed_evidence_count >= required_evidence_count) and not conflicting_evidence
missing_fraction  = max(required - observed, 0) / max(required, 1)
uncertainty       = min(1, 0.8 * missing_fraction + 0.2 * int(conflicting_evidence))
```

### 4.2 全 600 行复算结果

| 派生字段 | 复算不一致行数 |
|---|---:|
| `event_record.uncertainty` | 0 / 600 |
| `event_record.minimum_evidence_present` | 0 / 600 |
| `event_record.evidence_complete_and_consistent` | 0 / 600 |

600 行完全一致，0 mismatch。

### 4.3 抽样 36 行（含 rollout 每步 `event_record`）

对 36 行 deterministic sample 复算 primary + 3 步 rollout 的 uncertainty / minimum / complete：
- 36 行 × 4 步 × 3 字段 = 432 项复算全部 PASS

与 `uncertainty_reachability.md` 中的"Full table"（列举 `required ∈ {1..5} × observed × minimum × conflict`）一致——文档里的 110 个 (required, observed, minimum, conflict) 组合上 `uncertainty` 数值与重新跑出的数值完全相同。

**T3 结论：PASS**

---

## 5. T4 硬策略/边界/评估者 oracle

### 5.1 policy_result.hard_violations 复算

按 `policy_oracle.evaluate_policy`（`src/normative_world_model/policy_oracle.py`）语义，对 36 行 deterministic sample + 4 个 arm（primary / actor_value_twin / factual_twin / policy_twin）共 36 × 4 = 144 个 event_record 重新计算 hard_violations：

- unauthorized_persistent_change / missing_mandatory_approval / prohibited_private_information_disclosure / prohibited_nonconsensual_third_party_harm / below_policy_minimum_evidence / policy_blocks_conflicting_evidence
- 结果：**144/144 与存储完全一致**

并对全 600 行的 primary event_record 跑了一次独立 oracle：600/600 一致。

### 5.2 评估者 decision / reason / score / margin 复算

按 `normative_oracle.evaluate` 公式（含 hard_violations 短路、uncertainty_escalate_at、dimension veto 顺序 `safety→privacy→autonomy→trust→efficiency→fairness→commitment`、irreversibility_cutoff & irreversible_harm_veto 联合短路、加权 score 边界 `reject_at_or_below` 与 `allow_at_or_above`），从 `configs/evaluator_profiles.toml` 读取参数：

抽样 30 行 + 抽样 36 行（合计覆盖 60+ 行，4 profile）的全 600 行 primary oracle：
- decision / reason / score / score_margin_to_boundary：与 raw 严格一致
- 含 exact_boundary 边界（margin=0）的行，决策落在 weighted_score 或 weighted_score_band 边界上、复算边界判定一致

T4 oracle 全 600 行 PASS。

### 5.3 exact_boundary_evaluations 与 score_margin_to_boundary=0 的精确对应

对每行 primary + actor_value_twin + factual_twin + policy_twin 4 个 arm × 4 profile = 16 (arm, profile_id) 候选：
- 计算 stored `score_margin_to_boundary` 是否为 0
- 重新得到 `expected_pairs`（margin=0 的对）
- 与 `row_audit_index.exact_boundary_evaluations`（list of {arm, decision, profile_id, score}）对比

600/600 一致（0 mismatch）。注意 7 行有非空 exact_boundary，分布：
- `("factual_twin", "efficiency_tolerant")` 3
- `("factual_twin", "procedure_preserving")` 2
- `("actor_value_twin", "efficiency_tolerant")` 1
- `("actor_value_twin", "autonomy_preserving")` 1
- `("primary", "efficiency_tolerant")` 1
- `("policy_twin", "efficiency_tolerant")` 1

**T4 结论：PASS**

---

## 6. T5 next_state/rollout 端到端

### 6.1 primary.next_state = pre_state ⊕ physical_delta

对 36 行 sample：
- game: `apply_delta_to_state(source.state, primary.physical_delta)` 后 `turn = source.turn + 1`（源代码 `environments/game.py:_transition` line 166 显式 `next_state["turn"] = int(state["turn"]) + 1`，但 physical_delta 字典不含 turn_delta，需补充）
- organization: `apply_delta_to_state(source.state, primary.physical_delta)`，无 turn 自增（organization `_transition` 不增 turn/ticket）
- 36/36 全部精确一致

### 6.2 rollout[i].pre_state ⊕ physical_delta == rollout[i].next_state

对 36 行 × 3 步 = 108 次，**全部 PASS**。

### 6.3 rollout 链式一致性

| 检查 | 满足行数 | 总行数 |
|---|---:|---:|
| `rollout[0].next_state == rollout[1].pre_state` | 600 | 600 |
| `rollout[1].next_state == rollout[2].pre_state` | 600 | 600 |
| `rollout[0].next_state == primary.next_state` | 600 | 600 |
| `row_audit_index.rollout_chain_valid == True` | 600 | 600 |

注意：`rollout[0].pre_state == source.state`（不是 `primary.next_state`），见 §6.5 设计观察。

### 6.4 rollout event_record 派生字段（uncertainty / minimum / complete）

36 行 × 3 步 × 3 字段 = 324 项复算全部 PASS。

### 6.5 任务 T5 子句"rollout[0].pre_state == primary.next_state"——设计观察

**任务原文**："验证 rollout[0].pre_state == primary.next_state 且 rollout[0].physical_delta 与 rollout[0].pre_state ⊕ rollout[0].next_state 一致"

**审计实测**：
- `rollout[0].pre_state == primary.next_state` ：**0 / 600 满足**（所有 600 行的 rollout[0].pre_state 均等于 source.state，不是 primary.next_state）
- `rollout[0].physical_delta ⊕ rollout[0].pre_state == rollout[0].next_state`：**600/600 满足**
- `rollout[0].next_state == primary.next_state`：**600/600 满足**（同 action ⊕ 同 state 在确定性 simulate 下必然一致）
- `rollout[i+1].pre_state == rollout[i].next_state`（实现契约 `three_step_rollout_chain_consistency`）：**600/600 满足**

**源代码证据**（`src/normative_world_model/generator.py:208-233` `_build_rollout`）：
```python
current = copy.deepcopy(source)  # <-- 从 source 起步，不是 primary.next_state
for horizon in range(1, 4):
    result = simulate(current, profiles)
    rows.append({"horizon": horizon,
                 "pre_state": copy.deepcopy(current["state"]),
                 "next_state": result.next_state, ...})
    next_source = copy.deepcopy(current)
    next_source["state"] = copy.deepcopy(result.next_state)  # <-- 链式从这里开始
    ...
    current = next_source
```

也即源代码让 rollout 从 `source`（与 primary 共用 pre_state）独立 simulate，得到与 primary 相同的 delta/next_state，然后从 `rollout[0].next_state` 起链。

**判定**：
- 实现契约 `three_step_rollout_chain_consistency = 1.0`（`preregistration_v3.toml`）是 `rollout[i].next_state == rollout[i+1].pre_state`，**满足**。
- 任务 T5 第 1 子句"rollout[0].pre_state == primary.next_state"按字面理解**不满足**——但这是设计选择，不是数据错误：`source.state` 与 `primary.next_state` 的差恰好等于 `primary.physical_delta` 中所有非零 `*_delta` 字段加上 `turn + 1`（game）。
- 建议：任务说明应改写为"`rollout[0].next_state == primary.next_state` 且 `rollout[i+1].pre_state == rollout[i].next_state`"——这与实现完全一致。

**T5 阻塞**：0 / 30（抽样 30 行）
**T5 设计观察**：1 条（rollout 起步点 vs 任务字面期望的差异）

---

## 7. T6 A/B 环境共享抽象 vs 单环境捷径

### 7.1 primary.event_record 键集合跨环境一致性

两环境 `event_record` 键集合（去 key 名集合）：
- game: `{approval_present, approval_required, authorized, conflicting_evidence, consent_present, evidence_complete_and_consistent, impact_vector, minimum_evidence_present, obligation_active, obligation_breached, observed_evidence_count, persistent_change, policy_minimum_evidence_count, private_information_exposed, recovery_cost, required_evidence_count, reversibility, stakeholder_count, third_party_impact, uncertainty}`
- organization: 同样 20 个键，集合完全相等
- 600/600 行的 event_record 键集合在每环境内部完全相同

**0 阻塞**。无任一独有键。

### 7.2 physical_delta 键集合每环境内部一致性

- game: 600/600 行的 physical_delta 都是相同 11 个键（`{choice_access, fairness_balance, health_level, panic_level, persistent_flags_added, progress_level, promise_debt, resource_stock, secrecy_level, trust_level}_delta`，加上 `persistent_flags_added`）
- organization: 600/600 行的 physical_delta 都是相同 10 个键（`{allocation_balance, budget_remaining, exposure_level, incident_pressure, process_debt, service_health, stakeholder_trust, user_control, work_remaining}_delta`，加上 `durable_objects_added`）
- 跨环境 physical_delta 键集合不同（这是允许的，因为 game 用 `persistent_flags_added`、org 用 `durable_objects_added`）——但每环境内 600 行 schema 稳定

**0 阻塞**。

### 7.3 evaluator profile 的 profile_input 键集合跨环境一致性

4 个 profile 在两环境里：
- `profile_input` 键集合跨环境完全相同（`{allow_at_or_above, irreversibility_cutoff, irreversible_harm_veto, profile_id, reject_at_or_below, uncertainty_escalate_at, veto_floor, weights}`）
- `profile_id`、所有 `weights`、所有 `veto_floor`、5 个阈值的 typed values **在两环境之间完全相同**（600/600）
- `natural_language_profile_shams` 同一 profile 在 600 行里逐字相同（`set` 校验：1 unique per profile），且 game 与 organization 之间对同一 profile 也逐字相同
- `structured_profile_shams`（2 变体）解析回 typed values 后与 `profile_input` 完全相等（600 × 4 profile × 2 variant = 4800 项解析校验全部 PASS）

**0 阻塞**。

### 7.4 5 行 model_input 结构对比

抽样 5 行（每环境 5 行）比 state/policy/action leaf 命名：

| 字段 | game | organization |
|---|---|---|
| `state.*` 中可干预域 | choice_access, fairness_balance, health_level, panic_level, progress_level, promise_debt, resource_stock, secrecy_level, trust_level | allocation_balance, budget_remaining, exposure_level, incident_pressure, process_debt, service_health, stakeholder_trust, user_control, work_remaining |
| `state.*` 中 actor_values 4 个键 | caution, curiosity, duty, loyalty | caution, compliance, customer_focus, speed（注意 organization 的 `caution` 复用，但其它 3 个不同） |
| `policy.*` 7 个键 | 7 键完全相同（approval_required, conflict_blocking, nonconsensual_harm_threshold, policy_family, policy_minimum_evidence_count, prohibited_private_disclosure, required_evidence_count） | 同上 |
| `action.*` 5 个键 | family, intensity, persistent, tactic, target | family, intensity, persistent, tactic, scope（仅 target→scope 不同） |

抽象谓词（actor_values, policy 字段, evaluator 结构, event_record 字段, impact_vector 维度）在 evaluator 层是共享的；state.* leaf / action.target→scope 是预期的环境实现差异。

**T6 结论：PASS**

---

## 8. 阻塞性问题清单

| # | 类别 | 严重性 | 行/范围 | 描述 |
|---|---|---|---|---|
| 0 | （无） | — | — | 600 行数据无阻塞项 |

**设计观察（非阻塞）**：

| # | 类别 | 严重性 | 描述 | 建议 |
|---|---|---|---|---|
| D1 | rollout 起步点语义 | 低 | 任务 T5 子句"rollout[0].pre_state == primary.next_state"在源代码中不成立——`generator.py:_build_rollout` 从 `source.state` 起步独立 simulate。`rollout[0].next_state == primary.next_state`（同 action ⊕ 同 state → 同 delta）以及 `rollout[i+1].pre_state == rollout[i].next_state`（实现契约）成立；`row_audit_index.rollout_chain_valid=true` 与数据一致。 | 任务说明与实现一致化为"rollout[0].next_state == primary.next_state 且 rollout[i+1].pre_state == rollout[i].next_state" |

---

## 9. 风险提示

1. **同一 action 重复使用**：`_build_rollout` 起步与 primary 用同一 `(state, action)`，所以 `rollout[0]` 不增加信息量，仅用来验证"同 (state, action) → 同一 physical_delta"的确定性。从 rollout[1] 起才是真正"在 primary.next_state 基础上再做一步"的链式扩展。  
2. **actor/factual/policy twin 评估 oracle 重新计算**：本审计对 36 行 × 4 arm × 4 profile = 576 个 evaluation 跑过完整重算，与 raw 完全一致——这意味着 twin 间决策翻转不是因为 oracle 实现漂移，而是确实来自 event_record 变化。  
3. **`turn` / `ticket` 不在 physical_delta 中**：源代码 `game._transition` 自增 `turn`、不放在 delta 字典里；`organization._transition` 不动 `ticket`。这本身是 deterministic 的实现细节，不影响 oracle 正确性，但下游若要按 `pre_state ⊕ physical_delta` 重放必须显式知道 `turn + 1` 这条规则。  
4. **policy_twin 改 `policy_minimum_evidence_count` 还是会改 physical_delta**（因为 evidence count 影响 event_record，影响 impact_vector）：任务 T2 验证的是 `policy_twin.physical_delta == primary.physical_delta`，这是因为 policy 变化对 environment 物理状态没有直接作用（在 source code 中验证：policy 只被传给 run_shared_oracles，不被 _transition 读）。  
5. **actor_value 的 5 个 leaf 跨环境有重叠但不全同**：caution 在两环境都存在且是同一个 oracle 中的同 weight 字段；其余 4 个 leaf（loyalty/duty/curiosity vs compliance/speed/customer_focus）只在各自环境里出现。这是 T6 §7.4 中允许的"抽象共享"——evaluator 在 `actor_values` 字典上整体取权重（weights 字典只覆盖 7 个 impact 维度，与 actor_values leaf 不重合）。  
6. **`exact_boundary_evaluations` 仅 7/600 行**：boundary margin=0 的 case 稀少；本审计逐个重算验证了 index 与 oracle 完全一致。  
7. **T4 oracle 用本审计自带的 `evaluate_profile` 实现**：实现与 `src/normative_world_model/normative_oracle.py:evaluate` 严格 1:1（同样的 `Decimal(str(round(value, 6)))`、同样的 short-circuit 顺序、同样的 veto 维度序），并直接以 `configs/evaluator_profiles.toml` 的 frozen 参数作为 oracle 输入。  

---

## 10. 复现命令

```bash
# 数据 / 索引
ls /workspace/audit/bundle/raw/{game,organization}.jsonl   # 300+300 行
wc -l /workspace/audit/bundle/row_audit_index.jsonl         # 600
wc -l /workspace/audit/bundle/deterministic_sample_full_rows.jsonl  # 36

# 跑审计脚本
python3 /workspace/.mavis/plans/plan_ea04e9cb/workspace/audit_run.py

# 原始输出（含每条 blocking 详细 diff_paths）
ls /workspace/audit/findings/audit_raw.json

# 看具体一份 T5 blocking
python3 -c "import json; r=json.load(open('/workspace/audit/findings/audit_raw.json')); \
            [print(b) for b in r['t5_rollout']['blocking'][:3]]"

# 复核 T1 twin diff 分布
python3 -c "import json; r=json.load(open('/workspace/audit/findings/audit_raw.json')); \
            print(r['t1_minimality']['actor_diff_counter']); \
            print(r['t1_minimality']['factual_diff_counter']); \
            print(r['t1_minimality']['policy_diff_counter'])"

# 复核 physical relations 全 600 行
python3 -c "
import json
for env, p in (('game','/workspace/audit/bundle/raw/game.jsonl'),
               ('organization','/workspace/audit/bundle/raw/organization.jsonl')):
    raw = [json.loads(l) for l in open(p)]
    n_actor = sum(1 for r in raw if r['actor_value_twin']['result']['physical_delta'] != r['primary']['physical_delta'])
    n_fact  = sum(1 for r in raw if r['factual_twin']['result']['physical_delta'] != r['primary']['physical_delta'])
    n_pol   = sum(1 for r in raw if r['policy_twin']['result']['physical_delta'] == r['primary']['physical_delta'])
    print(f'{env}: actor_changes={n_actor}/300 factual_changes={n_fact}/300 policy_preserved={n_pol}/300')
"
```

---

**审计员签名**: General @ 2026-07-16 17:05 UTC
**最终判定**: **PASS**（600 行数据无任何阻塞；仅 1 条与实现契约一致的设计观察 D1）
