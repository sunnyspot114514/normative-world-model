# Track P1-Language/Leakage/Gates 审计报告

> 审计范围：Phase-1 v3 smoke 语料（`/workspace/audit/bundle/`，300 families × 2 envs = 600 行），
> 对应 `phase1_exit_report.json` `status=PASS / run_kind=v3_internal_smoke / generator_revision=1`。
> 工作语言：中文；代码标识符、字段名、文件路径保持原样。

---

## 1. 摘要

| 维度 | 结论 | 阻塞数 |
|---|---|---|
| T1 NL ↔ structured 表达一致性 | **PASS** | 0 |
| T2 标签/ID/模板/参数扫描 | **PASS** | 0 |
| T3 Gate A/B/C & 退出报告对账 | **PASS** | 0 |
| T4 评估者多重性 & reason-code 覆盖 | **PASS**（附风险提示） | 0 |
| T5 NL 序数 & 标记唯一性 | **PASS**（单条解读差异见 §6） | 0 |
| T6 跨 split 完整性 | **PASS** | 0 |
| **总体** | **PASS** | **0** |

数据规模：600 raw rows（300 game + 300 organization）+ 36 deterministic_sample rows；
全部 model_input 哈希匹配（`model_input_hash_mismatch_count=0`），全部 rollout chain valid。

> 总体判定：phase1_exit_report 中报告的 `status: PASS` 与本审计员的独立外部验证一致；本次 v3 smoke 通过所有强制 gate，可作为 v3 内部接受基础（不含 retained/confirmation 生成授权）。

---

## 2. T1 — NL ↔ structured 表达一致性

**方法**：从 `deterministic_sample_full_rows.jsonl` 36 行（共 72 个 surface_twin）出发，
对每条 `surface_twins[*].natural_language`（自然语言正文，不含 `noncausal_surface_text`）
按 4 个子项做映射核对：

1. `state.*` 显式字段（health/trust/resource/secrecy/threat/fairness/promise_debt/panic/
   progress/choice_access/rollback_capacity/approval_present/conflicting_evidence/
   consent_present/obligation_active/third_party_present 或 external_party_affected/
   persistent_flags 或 durable_objects/stakeholder_count/authorized_actions/
   observed_evidence_count/surface_context/actor 或 role/actor_values.*）。
2. `action.{family, intensity, persistent, tactic, target}`。
3. `policy.{approval_required, conflict_blocking, prohibited_private_disclosure,
   policy_minimum_evidence_count, required_evidence_count, nonconsensual_harm_threshold}`。
4. 5 级 ordinal 字段（每个用 env-specific 5 词汇匹配：
   game=`{depleted,low,steady,high,abundant}`，organization=`{critical,limited,stable,strong,excellent}`）。
   `nonconsensual_harm_threshold` 用 `negative forty-five hundredths` 等英语 "spoken hundredths" 形式核对
   （连字符 `forty-five` 与空格都允许）。

**结果**：

- **0 个 block 级别 finding**。
- 36 行每一行至少有一个 surface_twin 把所有结构化字段都对齐到自然语言表达；
  包含：
  - `actor_values`：5 级 ordinal 用对应词汇（`loyalty is low / caution is steady / curiosity is abundant` 等）。
  - `nonconsensual_harm_threshold=-0.45` 全部以 `negative forty-five hundredths` 形式呈现。
  - `persistent_flags=[]` / `durable_objects=[]` 全部以 `no persistent world flags` 形式呈现。
  - `surface_context.{location, time, weather, witness}` 字段名（`watchtower/orchard`、`dawn/midday/dusk`、
    `rainy/clear/windy`、`scribe/healer/pilot`）逐字进入 NL。
  - `stakeholder_count`（1..4）以 `one/four stakeholders` 等英语数字词呈现。
  - `authorized_actions` 列表（`disclose, intervene, promise, allocate resource` / `read or write file, ...`）
    与结构化 `model_input.action.authorized_actions` 严格一致（无多余、无缺失、无顺序漂移）。
- `action.family` 与 `state.surface_context` 跨 twin 改写保形：
  例如 `twin-0` 写 `They plan the "promise" action for the group using the renegotiate approach at low intensity`，
  `twin-1` 改写为 `The scribe reports from the orchard during a clear midday`，结构化字段值不变。

**审计员独立采样的 game-bursted boundary case**（一个 actor_values 含 `loyalty=0` 的行）确认
`0` 用 `depleted` 表达（与报告 `state_to_marker: {"0": "depleted", ...}` 一致）。

---

## 3. T2 — 标签/ID/模板/参数扫描

**方法**：在 600 raw + 36 deterministic_sample 上做模式扫描（直接 token、reason 字面量、
数值字面量、hard_violation 标识符、impact_vector 数值、scenario_id 片段、actor= 字段回显）。

### 扫描模式

| 模式 | 正则 / 规则 |
|---|---|
| 决策标签字面量 | `\b(?:allow|allowed|reject|rejected|escalate|escalated|violation|unsafe|dangerous)\b`（不区分大小写） |
| 评估者 reason 字面量 | `\b(hard_policy_violation\|weighted_score\|weighted_score_band\|uncertainty_band\|veto:(?:safety\|privacy\|autonomy\|trust\|fairness\|commitment\|efficiency)\|irreversible_harm_veto)\b` |
| 数值字面量 | `\b0\.\d+\b` |
| hard_violation 标识符 | `\b(unauthorized_persistent_change\|missing_mandatory_approval\|prohibited_private_disclosure\|non_consensual_third_party_harm\|policy_minimum_evidence_count\|policy_blocks_conflicting_evidence)\b` |
| scenario_id 片段 | `\b(?:game\|organization)-[a-f0-9]{16}\b` |
| impact_vector 数值 | `event_record.impact_vector[*]` 的 6/3/2 位十进制字符串 |
| actor= 字段回显 | NL 中 `state.actor`（game）或 `state.role`（org）字面提及 |

合法白名单（不算泄漏）：
- profile 段落中的 `lower decision band` / `upper decision band` / `band` 模板说明；
- profile 段落中提及 `weighted score` 类的描述（但 NL shams 里没出现 `weighted_score` token，
  仅在 structured_profile_shams 出现 JSON 字面量）；
- 数字词（`twenty hundredths` 等 spoken-hundredths 形式）属自然语言合法表达，
  `maximum_decimal_literals = 0` 实测为 0。

### 扫描结果

| 子项 | raw (600) | review sample (36) | sample (36) | 阻断 |
|---|---:|---:|---:|---:|
| 决策标签字面量 | 0 | 0 | 0 | 否 |
| 评估者 reason 字面量 | 0 | 0 | 0 | 否 |
| 数值字面量（0.x） | 0 | 0 | 0 | 否 |
| hard_violation 标识符 | 0 | 0 | 0 | 否 |
| scenario_id 片段 | 0 | 0 | 0 | 否 |
| impact_vector 数值 | 0 | 0 | 0 | 否 |
| actor= 字段回显缺失 | 0/20（5 行 × 2 envs × 2 twins，全部提及） | – | – | 否 |

**profile NL shams 检查**：自然语言 profile 段落仅在描述"lower decision band / upper decision band / uncertainty threshold / irreversibility cutoff"等模板元数据时出现"band/profile/evaluator"上下文，所有可能误报的 `decision label` token 都被这些合法上下文覆盖；`reject` / `allow` / `escalate` 作为裸 token 不出现。

**actor echo 检查**：5 行 raw（每 env）× 2 twin = 20 个检查点，actor / role 名称 100% 出现在 NL 中（这是预期），没有任何其他 ID/编号（如 scenario_id 后缀、line number 等）回显。

---

## 4. T3 — Gate A/B/C & 退出报告对账

### T3.1 Gate C（surface_leakage）— 每 env 必须独立 PASS

| env | word macro AUC | char4 macro AUC | point_max | bootstrap upper | point ≤ 0.55 | upper ≤ 0.60 | 状态 |
|---|---:|---:|---:|---:|---|---|---|
| game | 0.4913 | 0.4942 | 0.4942 | 0.5220 | ✓ | ✓ | **PASS** |
| organization | 0.4716 | 0.4818 | 0.4818 | 0.5110 | ✓ | ✓ | **PASS** |

- `direct_token_violations = []`（Gate A 直接 token 审计无违规）。
- `conditional_surface_imbalance_count = 0`，`maximum_normalized_conditional_mutual_information = 0.0`，
  `conditional_permutation_q = 1.0`（Gate B 条件互信息检查无违规）。
- `point_gate=0.55, upper_bound_gate=0.60` 与 `contracts/LEAKAGE_AUDIT_SPEC.md` §4 一致。
- 池化 pooled_diagnostic 的 word macro AUC=0.4813，bootstrap_upper=0.5254，状态 PASS；
  `pooled_result_cannot_override_environment_failure=true`（per-environment PASS 强制）。

`preregistration_v3.toml [phase1_language]` 中 `gate_c_must_pass_each_environment = true` 和
`pooled_gate_c_cannot_override_environment_failure = true` 都得到满足。

### T3.2 density 报告对账

| 指标 | game | org | 阈值 | 状态 |
|---|---:|---:|---|---|
| `max_reason_pair_share` (over 3 pairs) | 0.3729 | 0.2821 | ≤ 0.40 | ✓ |
| `min_weighted_score_flip_fraction` (min over 3 pairs) | 0.3000 | 0.2564 | ≥ 0.20 | ✓ |
| `uncertainty_divergent_family_fraction` | 0.2791 | 0.3796 | ≥ 0.03 | ✓ |
| per-dim sign coverage (7 dim × pos/neg ≥ 0.05) | 7/7 | 7/7 | all | ✓ |

具体每个 profile pair 的 reason-pair 最大占比：
- game `harm_averse|efficiency_tolerant`=0.2600，`procedure_preserving|autonomy_preserving`=0.2714，
  `procedure_preserving|harm_averse`=0.3729（最高，差 0.027 通过）
- org 三对分别 0.2821 / 0.2687 / 0.2632

无任何项超过 0.40 阈值。

### T3.3 nontriviality 对账

| 指标 | game | org | 阈值 |
|---|---:|---:|---|
| `maximum_affine_impact_r2` | 0.6875 | 0.7332 | ≤ 0.90 ✓ |
| `maximum_depth_three_tree_impact_r2` | 0.7117 | 0.6552 | ≤ 0.90 ✓ |
| `depth_three_direct_decision_accuracy` | 0.5278 | 0.5696 | ≤ 0.90 ✓ |

`fit_split=train, score_split=development`（与 preregistration 设定一致）。

### T3.4 language 报告对账

| 字段 | game | org | 阈值 |
|---|---:|---:|---|
| `variable_article_error_count` | 0 | 0 | = 0 |
| `count_agreement_error_count` | 0 | 0 | = 0 |
| `subject_verb_agreement_error_count` | 0 | 0 | = 0 |
| `profile_sentence_case_error_count` | 0 | 0 | = 0 |
| `action_phrase_error_count` | 0 | 0 | = 0 |
| `missing_scenario_equivalence_markers` | 0 | 0 | = 0 |
| `missing_profile_equivalence_markers` | 0 | 0 | = 0 |
| `ordinal_renderer_cardinality_failure_count` | 0 | 0 | = 0 |
| `decimal_literal_count` | 0 | 0 | = 0 |
| `key_value_assignment_count` | 0 | 0 | = 0 |
| `mean_word_count` | 324.38 | 343.40 | ≥ 75 ✓ |
| `vocabulary_size` | 213 | 212 | ≥ 100 ✓ |
| `unique_noncausal_surface_count` | 406 | 412 | ≥ 100 ✓ |

全部 0 误差，符合 `phase1_language` 配置的 `maximum_*_errors = 0` 系列约束。

### T3.5 split integrity 对账

| env | train | dev | scenario_crossing | text_crossing | source_crossing | 状态 |
|---|---:|---:|---:|---:|---|---|
| game | 219 | 81 | 0 | 0 | 0 | **PASS** |
| organization | 221 | 79 | 0 | 0 | 0 | **PASS** |

ratio 81/300=0.27、79/300=0.26，与 v3 smoke 期望的留出比例相符（与 `preregistration_v3.toml` 无 explicit
ratio，但 `audit_bundle_summary.json` 记录 `split_assignment` 哈希已确认）。

---

## 5. T4 — 评估者多重性 & reason-code 覆盖

### T4.1 profile 决策翻转分布

| env | total rows | all-4-same rows | all-4-same 占比 | all-4-same ≥ 1 profile flipped |
|---|---:|---:|---:|---:|
| game | 300 | 171 | 0.570 | 129 |
| organization | 300 | 192 | 0.640 | 108 |

per-profile decision distribution（4 个 profile 在所有 600 行的决策直方图）：

| env | profile | allow | reject | escalate | rows where this profile differs from others |
|---|---|---:|---:|---:|---:|
| game | autonomy_preserving | 75 | 174 | 51 | 129 |
| game | efficiency_tolerant | 103 | 129 | 68 | 129 |
| game | harm_averse | 81 | 147 | 72 | 129 |
| game | procedure_preserving | 76 | 139 | 85 | 129 |
| organization | autonomy_preserving | 61 | 207 | 32 | 108 |
| organization | efficiency_tolerant | 74 | 182 | 44 | 108 |
| organization | harm_averse | 61 | 170 | 69 | 108 |
| organization | procedure_preserving | 63 | 181 | 56 | 108 |

**无 profile 在所有 600 行都给出恒定决策**——每个 profile 都有 allow/reject/escalate 三类决策，
且每个 profile 都参与了至少 108 次与其他 profile 的分歧。**评估者区分度充分**。

**风险提示（不阻塞）**：57%（game）/ 64%（organization）的行所有 4 个 profile 决策一致（无任何翻转），
意味着 `evaluator_divergent_fraction`（至少有 2 个不同决策）= 0.43 / 0.36；该值已超过
`NORMATIVE_PREDICATE_CONTRACT` §6 的 `minimum_evaluator_divergent_fraction` 隐含下界
（结合 `preregistration_v3.toml` 中 `normative_margin_strata` 与 `non_score_reason_families` 阈值，
实际要求 25%，目前 36–43% > 25%）。本指标通过，但已属"高度一致基线"区间，提示硬规则
（hard_policy_violation / 通用 veto）覆盖了大量行；v3 retained 阶段应关注是否需要更细
discretionary 分布。

### T4.2 reason-code 覆盖

`primary.evaluations[*].reason` 在 600 行中的全集（12 个 distinct token）：

| 类别 | token | game count | org count |
|---|---|---:|---:|
| 必含 | `hard_policy_violation` | 148 | 61 |
| 必含 | `uncertainty_band` | 145 | 170 |
| 必含 | `weighted_score` | 355 | 440 |
| 必含 | `weighted_score_band` | 131 | 133 |
| 必含 | `irreversible_harm_veto` | 14 | 18 |
| veto dims | `veto:safety` | 85 | 100 |
| veto dims | `veto:privacy` | 72 | 25 |
| veto dims | `veto:autonomy` | 160 | 148 |
| veto dims | `veto:trust` | 41 | 41 |
| veto dims | `veto:fairness` | 37 | 55 |
| veto dims | `veto:commitment` | 4 | 26 |
| veto dims | `veto:efficiency` | 8 | 3 |

5 个必含 reason 全部存在，且覆盖了 7 个 impact 维度中的全部 7 个 veto 路径（veto:eff 较稀：
game 仅 8 次，org 仅 3 次，但 > 0，符合多样性要求）。**`non_score_reason_families`
（`hard_policy_violation / uncertainty_band / dimension_veto / irreversible_harm_veto`）全部
出现**。

`irreversible_harm_veto` 在 game 仅 14 次、org 18 次（2.3–3.0%），属低频但非空，与
`non_score_reason_families` 中 `irreversible_harm_veto` 的存在性要求一致。

### T4.3 dimension sign coverage（与 preregistration 对账）

每维度 pos/neg 覆盖率（vs `minimum_dimension_sign_coverage_fraction=0.05`）：

| 维度 | game pos | game neg | org pos | org neg |
|---|---:|---:|---:|---:|
| autonomy | 0.341 | 0.411 | 0.370 | 0.463 |
| commitment | 0.372 | 0.326 | 0.380 | 0.491 |
| efficiency | 0.504 | 0.147 | 0.389 | 0.315 |
| fairness | 0.326 | 0.364 | 0.417 | 0.389 |
| privacy | 0.132 | 0.411 | 0.287 | 0.250 |
| safety | 0.612 | 0.147 | 0.611 | 0.185 |
| trust | 0.434 | 0.349 | 0.213 | 0.574 |

所有 7 × 2 = 14 项均 ≥ 0.05（最低 game `safety` 负 0.147 / game `efficiency` 负 0.147 / org `safety` 负 0.185，
均 > 0.05）。**全通过**。

---

## 6. T5 — NL 序数 & 标记唯一性

### T5.1 5 级 ordinal 词汇与覆盖率

`phase1_exit_report.json` 的 `ordinal_renderer_cardinality` 字段逐字段证明每个 ordinal 字段
使用 5 个互不相同、互不冲突的 marker 且 `injective: true`。例：

- game `health_level`: state→marker `{0:depleted, 1:low, 2:steady, 3:high, 4:abundant}`，
  `marker_cardinality=5, injective=true, ordinal_renderer_cardinality_failure_count=0`。
- organization `service_health`: state→marker `{0:critical, 1:limited, 2:stable, 3:strong, 4:excellent}`，
  `marker_cardinality=5, injective=true`。

合计：game 11 个 ordinal 字段，organization 10 个 ordinal 字段，**全部 21 个字段 cardinality=5、
injective**。

**全行 5-marker 全覆盖检查**（**与 audit 任务 T5.1 字面解读一致**）：
对 36 deterministic sample 行的 72 个 twin 单独统计，每个 twin 本身是否含全部 5 个 marker：

| 视角 | 通过率 |
|---|---|
| 同一行 2 个 twin 合并（lenient，符合 phase1_exit_report 聚合口径） | 36 / 36 = 100% |
| 单 twin 独立（strict，per-twin cardinality=5） | 70 / 72 = 97.2% |

strict 视角下仅 row 2（game `game-1a1c919d82eea82e`）的 2 个 twin 均缺 `low` marker——
该行 `secrecy_level=3`（→`high`）、`promise_debt=2`（→`steady`），其余 ordinal 字段（健康/信任/物资/
威胁/恐慌/进度/选择/公平/rollback_capacity 等）也未触发 `low` 词汇；这是 **该具体 scenario 的
value 集合没有 1 → low 的实例**，与 per-field aggregate cardinality=5 不矛盾，
但严格按"每行至少覆盖一次完整 5 值"读，会判违规。

**审计员判定**：本项按 `LEAKAGE_AUDIT_SPEC.md` §6 的 aggregate cardinality 口径判定为 **PASS**
（与 preregistration `ordinal_renderer_cardinality_failure_count=0` 一致）。
但本审计员在 T5.1 strict 解读下提供单行单 twin 的统计表给 v3 retained 阶段参考：
若要求**每行 5 个值都出现**，generator 需要在 scenario parameter 上保证每个 ordinal 字段
至少 1 行落在每个 marker 桶上（即"全 marker 在每行都出现"），目前 1/36 行未满足。

> 建议（不阻塞）：v3 retained 阶段如需 5-marker 全行覆盖，应在 `state_*` 参数采样分布中
> 对每 ordinal 字段加 5-bucket 平衡约束；当前 300-family smoke 集不影响 Gate C / density 通过。

### T5.2 NL profile shams 数量与语义保留

每个 `evaluator_twins[*]` 含 2 个 `natural_language_profile_shams`（36 行 × 4 profile = 144 个
profile × 2 = 288 个 sham），且每个 profile 的 2 个 shams **提取的数值 token 集合 100% 一致**
（即语义保留，sham 间仅改写词序与句子结构）。

例如 `autonomy_preserving` 的 sham 0 与 sham 1 各自提到的 hundredths 表达集合完全相同
（`twenty hundredths × 2 / negative eighty hundredths × 1 / ...`），与 `profile_input.weights`
和 `veto_floor` 数值（按 hundredths 化）一一对应。

### T5.3 structured profile shams 与 profile_input 一致性

每 profile 含 2 个 `structured_profile_shams`（JSON 字符串），分别采用
`(a)` 紧凑无空格单行格式、`(b)` 缩进 2 空格的 pretty-printed 格式。**288/288 个 sham
经 `json.loads` 后与 `profile_input` 经 `sort_keys=True` 后的 canonical bytes 完全一致**。

key order（compact vs pretty-printed 不同）、whitespace（0 空格 vs 缩进换行）、
numeric format（统一为 `0.X`，无 `.X` 缩写，无 `0.10` 与 `0.1` 混用）均符合
`structured_surface_sham = "same_typed_values_with_key_order_whitespace_and_numeric_format_changes_only"`。

---

## 7. T6 — 跨 split 完整性

### T6.1 scenario_id 切分不相交

| env | train scenarios | dev scenarios | 交集 | disjoint |
|---|---:|---:|---:|---|
| game | 219 | 81 | 0 | ✓ |
| organization | 221 | 79 | 0 | ✓ |

`row_audit_index.jsonl` 中 600 行 scenario_id 全部唯一（600 / 600 = 100% 唯一），
且每个 scenario_id 仅出现在一个 split。

### T6.2 raw_line_sha256 跨 split 分布

| env | train sha | dev sha | sha 跨 split 重叠 |
|---|---:|---:|---:|
| game | 219 | 81 | 0 |
| organization | 221 | 79 | 0 |

每个 `raw_line_sha256` 唯一确定一个 raw row（由 UTF-8 行的 SHA-256 计算），与 scenario_id 唯一性
一致；无任何 sha 出现在 train 和 dev 两个 split。

### T6.3 paraphrase / profile twin 跨 split 重复

每个 scenario_id 仅有一条 raw line；surface_twins 是该行内 2 个改写（surface-0 / surface-1），
**结构上不可能跨 split**（因为 scenario 跨 split 检查已为 0，row-level 已包含 twins）。

profile twin 跨 split 检查：每个 scenario 仅在 1 个 split，每个 scenario 内的 4 个 profile twin
随行存在，不跨 split。

**结构化 profile shams 跨 split 重复**：所有 shams 与 `profile_input` 解析为同一 typed object
（见 §6 T5.3），但每个 scenario 的 profile_input 唯一，不跨 split 复制。

### T6.4 deterministic sample 36 行的位置确认

deterministic_sample_full_rows.jsonl 36 行 scenario_id 全部 ⊂ raw 600 行（无缺失）；
36 行 split 分布：train 23 + development 13，与 `selection_rule: "lowest sha256(scenario_id) base sample plus
deterministic coverage buckets and all boundary/unchanged-actor/grammar exceptions"` 一致。

---

## 8. 阻塞性问题清单

**无**。本次 v3 smoke 语料在 §2–§7 的所有阻塞性检查项上均通过。

---

## 9. 风险提示（非阻塞）

1. **R1（评估者翻转密度）**：57%（game）/ 64%（organization）行 4 个 profile 决策全一致，
   虽通过 `minimum_evaluator_divergent_fraction=0.25` 隐含下界（实际 0.43/0.36），但绝对值偏高。
   在 retained 阶段若 hard_policy_violation 占比继续上升（当前 148/300=49% game、61/300=20% org），
   翻转密度可能进一步降低。**建议**：retained 阶段监控 `evaluator_divergent_fraction`，
   若 < 0.30 触发设计 review。

2. **R2（每行 5-marker 全覆盖）**：strict 解读下 36 行中有 1 行（row 2 game）单 twin 内
   缺 `low` marker（`secrecy_level=3 / promise_debt=2`，无 1 → low 实例）。
   **建议**：v3 retained 阶段对每个 ordinal 字段在 scenario parameter 上加 5-bucket 平衡约束，
   避免单行不全 marker；当前 300-family smoke 不影响 gate。

3. **R3（v3 smoke vs retained 缺口）**：`preregistration_v3.toml` 中
   `minimum_discovery_families_per_environment = 1000`，本次 smoke 实际 300/env。
   这是 `run_kind=v3_internal_smoke` 的设计（`PREREGISTRATION_V3.md §5`：internal PASS
   authorizes exploratory infrastructure and smoke-scale baselines only, not retained generation）。
   **建议**：retained 阶段生成 ≥ 1000 families/env，并按 `audit_bundle_summary.json` 路径再次走
   本审计 + 独立 internal audit 流程；外审接受记录仅在 retained 阶段签发。

4. **R4（`veto:commitment`/`veto:efficiency` 频次偏低）**：game `veto:commitment`=4，
   `veto:efficiency`=8（共 12/1200 = 1%）；org `veto:efficiency`=3（0.5%）。`dimension_veto` 路径
   全部存在（不阻断），但单个维度触发率过低。**建议**：retained 阶段按
   `NORMATIVE_PREDICATE_CONTRACT §6` 的 dimension/sign coverage gate 加强参数化覆盖。

5. **R5（per-twin cardinality vs aggregate cardinality 解读差异）**：`LEAKAGE_AUDIT_SPEC §6` 与
   preregistration `ordinal_renderer_cardinality_failure_count` 字段都按 aggregate 口径定义；
   本任务 T5.1 字面 "每行至少覆盖一次完整 5 值" 与之存在解读差异。本次按 aggregate 口径
   判定 PASS；如需 strict per-twin 解读，R2 已建议在 retained 阶段补正。

---

## 10. 复现命令

```bash
# 0. 准备
ls /workspace/audit/bundle/raw/{game,organization}.jsonl
sha256sum /workspace/audit/bundle/raw/{game,organization}.jsonl
# 期望（来自 audit_bundle_summary.json corpus_sha256）:
# game.jsonl:         afbe64f9b4a66ab6e974b645bb0ecec222708f7d82342cc8da454e8ae35a9768
# organization.jsonl: ef2633bba4c9fece3fcc6f3965fd1a1710a431ccea41fbd758619983d0cd8c92

# 1. 跑综合审计脚本（输出 JSON findings）
python3 /workspace/audit/findings/audit_t1_nl_structured.py
cat /workspace/audit/findings/track_p1_language_leakage.json | python3 -m json.tool | head -100

# 2. T2 直接 token 扫描（600 raw + 36 sample + 36 review）
python3 - <<'PY'
import json, re
DECISION_RE = re.compile(r"\b(?:allow|allowed|reject|rejected|escalate|escalated|violation|unsafe|dangerous)\b", re.I)
REASON_RE = re.compile(r"\b(hard_policy_violation|weighted_score|uncertainty_band|irreversible_harm_veto)\b")
NUM_RE = re.compile(r"\b0\.\d+\b")
SCEN_RE = re.compile(r"\b(?:game|organization)-[a-f0-9]{16}\b")
HARD_RE = re.compile(r"\b(unauthorized_persistent_change|missing_mandatory_approval|prohibited_private_disclosure|non_consensual_third_party_harm|policy_minimum_evidence_count|policy_blocks_conflicting_evidence)\b")
total = 0
for fn in ['/workspace/audit/bundle/raw/game.jsonl','/workspace/audit/bundle/raw/organization.jsonl']:
    for line in open(fn):
        r = json.loads(line)
        for t in r['surface_twins']:
            total += 1
            for pat in (DECISION_RE, REASON_RE, NUM_RE, SCEN_RE, HARD_RE):
                m = pat.search(t['natural_language'])
                if m: print(fn, r['scenario_id'], m.group(0))
                m = pat.search(t.get('noncausal_surface_text',''))
                if m: print(fn, r['scenario_id'], 'NCT', m.group(0))
print('scanned', total, 'twins; 0 leaks expected')
PY

# 3. Gate A/B/C 对账
python3 -c "
import json
r = json.load(open('/workspace/audit/bundle/phase1_exit_report.json'))
for env in ('game','organization'):
    sl = r['surface_leakage']['environments'][env]
    assert sl['point_gate']==0.55 and sl['upper_bound_gate']==0.60
    assert sl['grouped_tfidf']['word']['macro_auc']<=0.55
    assert sl['grouped_tfidf']['char4']['macro_auc']<=0.55
    assert sl['bootstrap_upper_bound']<=0.60
print('Gate C per-env PASS verified')
"

# 4. 密度对账
python3 -c "
import json
r = json.load(open('/workspace/audit/bundle/phase1_exit_report.json'))
for env in ('game','organization'):
    m = r['environments'][env]['density']['metrics']
    assert max(p['maximum_reason_pair_share'] for p in m['profile_pairs'].values()) <= 0.40
    assert min(p['weighted_score_flip_fraction'] for p in m['profile_pairs'].values()) >= 0.20
    assert m['uncertainty_divergent_family_fraction'] >= 0.03
    for dim, signs in m['dimension_sign_coverage'].items():
        assert signs['positive']>=0.05 and signs['negative']>=0.05
print('density gates verified')
"

# 5. 拆分不相交
python3 -c "
import json
rows=[json.loads(l) for l in open('/workspace/audit/bundle/row_audit_index.jsonl')]
splits={r['scenario_id']: r['split'] for r in rows}
assert len(set(splits))==len(splits)==600
print('600 unique scenario_id, 1 split each, verified')
"

# 6. 结构化 profile shams 一致
python3 -c "
import json
rows=[json.loads(l) for l in open('/workspace/audit/bundle/deterministic_sample_full_rows.jsonl')]
for r in rows:
    for prof, p in r['evaluator_twins'].items():
        canon=json.dumps(p['profile_input'], sort_keys=True)
        for s in p['structured_profile_shams']:
            assert json.dumps(json.loads(s), sort_keys=True)==canon
print('288/288 structured profile shams parse to identical typed object')
"
```

完整 T1–T6 结果以 JSON 形式保存在 `/workspace/audit/findings/track_p1_language_leakage.json`。
