# Track P2-Evaluation 评审报告

- 评审对象: `src/normative_world_model/{model_output,phase2_metrics,baselines,transfer_matrix,comparators,bootstrap,phase2_dataset}.py`
- 评审合同: `METRIC_COMPARATOR_V2_1.md`、`PHASE1_V3_INTERNAL_SMOKE.md`、`EXTERNAL_SMOKE_ACCEPTANCE_V3.md`、`6b9de4b0__359514b8-…` (Phase-2 评测合同 v3)、`8f4b5146__d598fd7e-…` (Metric comparator v2.1)
- 锁定 commit: `1f9f7f3` — 仓库当前 HEAD 与评审输入一致 (`git rev-parse HEAD` = `1f9f7f3418dcfa353a9efcbb9a493d4a0914138b`)。
- 评审范围: T1 严格输出解析器、T2 浮点容差、T3 pair 指标、T4 bootstrap、T5 Static baseline 输入特征、T6 A→A/B→B/跨环境人口、T7 跨合约一致性
- 评审方法: 静态阅读 + 单测运行 (`PYTHONPATH=src python -m unittest tests.test_model_output tests.test_phase2_metrics tests.test_baselines tests.test_phase2_dataset tests.test_bootstrap tests.test_comparators` 全 26 用例 PASS, 含我追加的 6 个交互式断言), 加上对关键边界的人肉验证。
- 工作语言: 中文。代码标识符保持原样。

## 1. 摘要

**评审结论: APPROVE_WITH_FIXES**

Phase-2 评测实现整体上忠实复述了合同 (Phase-2 evaluation contract + Metric comparator v2.1 + External smoke acceptance v3) 里的所有硬约束, 包括:

- 严格输出解析器只接受单 JSON 对象或 `json`/plain Markdown 围栏, 且显式拒绝 `top_level_keys`、prose 包装、多 fence 围栏;
- 解析失败时 `error_code`/`error_detail` 完整保留, 并在 `score_evaluator_pair` / `score_leakage` 中以"None → False/1.0"方式保守记录, 不进入分母也不获得任何 credit;
- `escalation_required == (normative_decision == "escalate")`、rollout horizon 集合严格匹配、`DECISIONS = {allow, reject, escalate}`、`confidence` 范围 [0,1] 都在 parser 中实现并由单测覆盖;
- comparator 唯一实现 `comparators.py`, `phase2_metrics` 仅 `import` 复用, 不复制 tolerance; `physical_deltas_equal` 严格 `==`, 事件 record 的连续字段使用 `<= 0.005` 的 inclusive 容差, 非有限/畸形数走 `parse_finite_decimal` 的 `ValueError` 分支;
- pair 指标 `joint_pair_success` = `physical_correct AND event_correct AND normative_pair_correct`, `normative_flip_recalled` 同时要求 `flip_required & normative_pair_correct & flip_observed`, 解析失败时被赋 `False` (非 0/0), 与合同 §4"防止 parse collapse 被解释为 disentanglement" 一致;
- leakage `_divergent` 对任一 `None` 返回 `1.0`, 满足 §4"保守 1";
- factual twin 区分 `changed_field_macro_f1` (值正确) 与 `change_set_precision/recall` (路径正确), `physical_twin_sensitive` 仅看 predicted 路径是否变化;
- rollout gate 在 reference (H1) 或 long (H5) 缺失时返回 `UNIDENTIFIED`, 不用 H3 推断;
- bootstrap 用 `scenario_id` 排序后做 cluster-level 重采样 (与 `effective_unit="scenario_family"` 对齐), CI 走百分位 (alpha/2, 1-alpha/2), 静态 envelope `max(per-arm mean)` 在每个 replicate 内重算;
- Static baseline 四个决策 baseline 全部 evaluator-blind (`_decision_predictions` 只用 `model_input` + `profile_id`); `_fieldwise_factual_vote` 只用 `family["primary"]["physical_delta"/"event_record"]` 做 7 邻居投票, 路径分支上对 `event_record.{reversibility,recovery_cost,uncertainty,impact_vector.*}` 取 `median`、其他字段取 `Counter.most_common` + 字典序 tie-break;
- `_scenario_joint_scores` 与 `_parsed_static_output` 走 `parse_model_output`, parse 失败返回 `None` 并仍纳入 `_scenario_joint_scores` 的分母, 与 model arm 同口径;
- 静态 envelope rule 报告字段为 `maximum scenario-macro joint_pair_success recomputed inside each scenario-cluster bootstrap replicate`, 实际实现也确实是 "在每个 replicate 内取 `max(replicate.values())`";
- `run_smoke_baselines` 中 `primary_development_ood` 池化 `A→A, B→B`, `cross_environment_transfer` 池化 `A→B, B→A`, 互不替代;
- `transfer_matrix.build_transfer_manifest` 8 个 cell (`A→A/A→B/B→A/B→B × structured/natural_language`)、`train_test_overlap_count = 0`、train/test scenario_id 列表 `sha256` 绑定、整体 `status` 同时要求无 overlap 且所有 destination `environment_support` `IDENTIFIED`;
- 跨合约一致性: `primary_estimand = "ood_joint_pair_success"`, `static_envelope_rule` 字符串、H5 缺失 UNIDENTIFIED、Static 输出经严格 parser 都已落地。

发现 (按严重度): **高 0, 中 2, 低 4**。Phase-2 不构成硬门控, 因此所有发现都作为"改进建议"提出, 不阻塞 retained baseline 冻结。

## 2. T1 严格输出解析器 (model_output.py)

### 2.1 单 JSON / 围栏接受
- `_FENCE` 正则: `r"\A\s*\`\`\`(?:json)?\s*\n(?P<body>.*)\n\`\`\`\s*\Z"`, `re.IGNORECASE | re.DOTALL`。
- `_unwrap` 用 `fullmatch`, 命中则取 `body`, 未命中则 `text.strip()`。
- `json.loads(_unwrap(text))` 失败 → `error_code="invalid_json"`, `error_detail=str(error)`。
- 接受路径:
  - 单 JSON 对象: 走 `text.strip()` → `json.loads` ✓
  - `\`\`\`json\n{...}\n\`\`\`` 围栏: 正则命中, 取 body ✓
  - `\`\`\`\n{...}\n\`\`\`` plain 围栏: 正则 `json` 可选, 仍命中 ✓ (我额外以交互式调用确认 `plain fence ok: True`)
- 拒绝路径:
  - `Result: {}` (prose 包装) → `invalid_json` (单测覆盖)
  - `Here is the answer:\n\`\`\`json\n{...}\n\`\`\`\nEnd.` (前后 prose) → `invalid_json` (我额外确认)
  - 两个相邻围栏 → `invalid_json` (我额外确认)
  - `single-line` `\`\`\`json {...} \`\`\`` (无换行) → 正则不命中 → `text.strip()` → `json.loads` 失败 → `invalid_json` (注: 合同未要求单行围栏, 此为已知行为, 见 §10 低优先级建议)

### 2.2 required keys 完整 + 不接受其他 top-level key
- `TOP_LEVEL_REQUIRED = {physical_delta, event_record, normative_decision, escalation_required, rollout}`
- `TOP_LEVEL_OPTIONAL = {confidence}` (其他全部拒绝)
- 检查顺序: `set(payload) - allowed or not TOP_LEVEL_REQUIRED.issubset(payload)` → `top_level_keys` (单测覆盖 missing `event_record`)

### 2.3 `escalation_required == (normative_decision == "escalate")` 硬约束
- `_validate_payload` 在校验完 decision 与 escalation 各自的类型后, 显式 `if escalation != (decision == "escalate"): raise decision_consistency`。
- 单测 `test_decision_and_rollout_contracts_are_strict` 与 `test_factorized_normative_parser_rejects_inconsistent_flag` 双覆盖 (前者对 one-step 完整 payload, 后者对 factorized normative-only payload)。

### 2.4 rollout 严格匹配请求 horizon 集合, 重复/缺失即 invalid
- 三层防御:
  1. `len(rollout_payload) != len(expected_rollout)` → `rollout_horizons` (数量错)
  2. 循环中 `if horizon in parsed_rollout or horizon not in expected_rollout` → `rollout_horizons` (重复或越界)
  3. 收尾 `if set(parsed_rollout) != set(expected_rollout)` → `rollout_horizons` (缺失)
- 每个 item 还要求 `set(item) == ROLLOUT_KEYS = {horizon, physical_delta, event_record}`, 任何额外 key (如 `confidence` 出现在 rollout item 内) 也会被 `rollout_keys` 拒绝。
- 单测 `test_decision_and_rollout_contracts_are_strict` 验证 `horizon=3` 改写后被拒。

### 2.5 decision value ∈ {allow, reject, escalate}
- `DECISIONS = {"allow", "reject", "escalate"}`, `if decision not in DECISIONS: raise decision_value`。

### 2.6 parse 失败时 `error_code`/`error_detail` 完整保留
- `ParseResult` 字段: `ok`, `output: ParsedModelOutput | None`, `error_code: str | None`, `error_detail: str | None`。
- 失败路径统一: `json.JSONDecodeError` → `("invalid_json", str(error))`; `OutputValidationError` → `(error.code, error.detail)`。
- 没有任何"silent fail"路径 (即 `ok=False` 不会隐式吞掉 code/detail)。

### 2.7 parse 失败在下游计分时仍保留在分母中
- `score_one_step`: `one_step = predicted.one_step if predicted is not None else None`, 然后 `score_fields(None, target, ...)` 在 `predicted is None` 时 `predicted_leaves = {}`, `precision=0, recall=correct/len(target_leaves)`, 全 correctness 走 `False`。✓
- `score_evaluator_pair`: `parse_complete = predicted_a is not None and predicted_b is not None`; 若不全, 显式 `physical_invariant=event_invariant=physical_correct=event_correct=normative_pair_correct=flip_observed=False`, `joint_pair_success=False`。所有 `*_correct` 都是 `False` 而非 `0.0` (Bool 字段), 与合同 §4"防止 parse collapse 被解释为 disentanglement" 一致。✓
- `score_leakage._divergent`: 任一 `None` → `1.0`; 双方都 `None` 时, `semantic_div=surface_div=1.0, leak=0.0` (合同明确允许的"cancel" 路径), 同时 `joint_pair_success=0.0` 阻止 parse collapse 被记为 disentanglement。✓
- `score_factual_twin`: 双方任一 `None` 时 `_changed_paths` 返回 `set()`, `physical_twin_sensitive=bool(set())=False`。✓
- `score_rollout`: 单 horizon 仍参与 `results[horizon]` 字典, `physical.f1=event.f1=0.0, *_exact_match=False, joint_exact_match=False` 进入 gate 评估, 因此 `H1/H3/H5` 的缺失/失败仍会被 `evaluate_rollout_gate` 计入或识别为 UNIDENTIFIED。✓
- 单测 `test_parse_failure_is_not_invariance_credit` 显式覆盖 `None,None,target,target` 时所有 invariant/correct 字段为 False, `leakage.semantic_physical_divergence=1.0, surface_physical_divergence=1.0, physical_delta_leak=0.0`。

**T1 评审结论**: 完全合规。

## 3. T2 浮点容差 (comparators.py)

### 3.1 事件连续字段 0.005 abs / 0 rel / boundary inclusive
- `COMPARATOR_VERSION = "2.1-candidate"`, `CONTINUOUS_ABS_TOLERANCE = Decimal("0.005")`。
- `continuous_equal`: `abs(parse_finite_decimal(left) - parse_finite_decimal(right)) <= CONTINUOUS_ABS_TOLERANCE` → 差恰好 0.005 视为相等 (boundary inclusive)。
- `_event_values_equal` 的连续性判断: `path and not isinstance(left, (dict, list)) and (path[-1] in _EVENT_CONTINUOUS_FIELDS or "impact_vector" in path)`, 适用:
  - `event_record.reversibility/recovery_cost/uncertainty` (直接子节点)
  - `event_record.impact_vector.*` (任意深度)
  - 关键: dict/list 节点本身被排除, 避免 `continuous_equal({...}, {...})` 的错误调用
- 单测 `test_tolerance_boundary_is_inclusive` 覆盖 `0.100` vs `0.105` → True, `0.100` vs `0.105001` → False。
- `physical_deltas_equal = left == right` (strict), 适用于 physical 离散字段。

### 3.2 numeric spelling 归一
- `_DECIMAL_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"` 接受 `0.1 / 0.10 / .1 / -0.25 / -.25 / +0.5`。
- `parse_finite_decimal` 把 `int/float/Decimal/string-pattern` 全部转成 `Decimal`, 然后比较 `Decimal - Decimal` 的绝对值。`0.1 == 0.10 == .1` 在 Decimal 算术下成立。
- 单测 `test_numeric_spellings_normalize_before_comparison` 覆盖三处等价。

### 3.3 非 finite / malformed → invalid (不获得 credit)
- `parse_finite_decimal` 拒绝路径:
  - `bool` → `ValueError("booleans are not continuous numeric predictions")`
  - `float` 非有限 (`nan/inf/-inf`) → `ValueError("non-finite numeric prediction")`
  - 字符串不匹配 `_DECIMAL_PATTERN` → `ValueError("invalid decimal prediction")` (或被 fallback 路径捕捉)
  - `Decimal` 解析后 `is_finite()=False` → `ValueError("non-finite numeric prediction")`
- `continuous_equal` 内部 `try/except ValueError: return False` → 不抛错而是返回 False, 故"无 credit"。
- 在 `model_output._validate_shape` 中, 走 `event_record + 连续路径` 分支时, `parse_finite_decimal` 抛 `ValueError` 被外层 `OutputValidationError("invalid_number", ...)` 捕获, parser 整体返回 `ok=False`; 因此既不获得 correctness 也不进入下游计分。
- 单测 `test_non_finite_and_malformed_values_fail` 覆盖 `nan/inf/"NaN"/"one tenth"`。
- 注: 合同 §3"malformed values" 同时包含 boolean — 实现以 `bool` 在连续路径显式 raise 满足。`event_records_equal` 对 bool 的处理是 `type(left) is not type(right)` 的精确类型比较, 不会把 True 视作 1.0。

### 3.4 物理离散 + 事件 bool/int/enum/集合 → exact
- 物理: `physical_deltas_equal` 直接 `==` (Python dict 精确比较, 顺序无关、类型敏感)。
- 事件: `_event_values_equal` 在不命中连续条件时, 先做 `type(left) is not type(right)` 严格类型校验, 再递归 dict (key set 完全相等) 与 list (长度相等 + 逐元素)。
- 事件 boolean (`authorized`): 走 exact 分支, True/False 必须一致。
- 事件 integer (`stakeholder_count`): 走 exact 分支, 类型敏感 (`int` vs `bool` 也不等, 与 `model_output._validate_shape` 中 `isinstance(value, bool) or not isinstance(value, int)` 的 `type_error` 一致)。
- 事件 enum (decision): 在 parser 中已 `DECISIONS` 严格, 进入指标层时是字符串, 走 `==`。
- 集合: list 走 `len` + 逐元素 exact 比较。
- 单测 `test_same_nested_comparator_applies_at_every_rollout_horizon` 覆盖 (1) 嵌套字符串数字 (`.204` vs `0.2`、`-0.246` vs `-0.25`、`0.400` vs `0.4`) 在 H1/H3/H5 全部相等; (2) `stakeholder_count: 3` 误传 → False。

### 3.5 phase2_metrics 不重复定义 tolerance
- 顶部 `from .comparators import continuous_equal, event_records_equal, parse_finite_decimal, physical_deltas_equal`。
- 内部仅定义 `_event_path_continuous` (路径分类辅助) 与 `_value_equal` (薄包装, 内部仍调 `continuous_equal` / `==`); 不持有任何数值常量。✓
- 关键正确性: `_event_path_continuous` 的语义与 `comparators._event_values_equal` 完全对齐 (`path[-1] in CONTINUOUS_EVENT_FIELDS or "impact_vector" in path`)。
- 单测 `test_continuous_tolerance_is_shared_with_field_scoring` 覆盖 `"0.204" vs 0.2` 跨两个模块一致性。

**T2 评审结论**: 完全合规。

## 4. T3 pair 指标 (phase2_metrics.score_evaluator_pair)

### 4.1 `joint_pair_success` 定义
- `physical_consistent_and_correct`: 4 个子项 AND:
  1. `physical_deltas_equal(left.physical_delta, target_a.physical_delta)` — 左预测对
  2. `physical_deltas_equal(right.physical_delta, target_b.physical_delta)` — 右预测对
  3. `physical_invariant` — 预测对自身 invariant
  4. `physical_deltas_equal(target_a, target_b)` — oracle 本身在物理上 invariant (没有 profile-dependent physical 差异)
- `event_record_consistent_and_correct`: 同上, 用 `event_records_equal`。
- `normative_pair_correct`: `left.normative_decision == target_a.normative_decision AND right.normative_decision == target_b.normative_decision` — 注意不需要"invariant", 因为 normative decision 可能在 profile 间翻转 (这是合同 §4 想要的)。
- `joint_pair_success = physical_consistent_and_correct AND event_record_consistent_and_correct AND normative_pair_correct`。
- 单测 `test_evaluator_pair_requires_correct_facts_and_correct_flip` 覆盖 (1) 全部正确 + flip → `joint_pair_success=True, normative_flip_recalled=True`; (2) 物理错 → `physical_consistent_and_correct=False, joint_pair_success=False`。

### 4.2 parse 失败时 invariant/consistency 被保守记为 False
- §2.7 已分析: 走 `not parse_complete` 分支, 全部赋 `False`; `joint_pair_success=False`, `parse_complete=False`。
- 不存在 0/0 误判。✓

### 4.3 normative flip recall 三元组
- `flip_required = target_a.normative_decision != target_b.normative_decision`
- `flip_observed = left.normative_decision != right.normative_decision` (仅在 parse_complete 时计算; 否则 False)
- `normative_flip_recalled = flip_required AND normative_pair_correct AND flip_observed`
- 三个条件同时成立才记 True, 符合合同 §4 "flip recall" 定义。
- 注: `normative_pair_correct` 已隐含 `left.decision == target_a.decision` 与 `right.decision == target_b.decision`, 故在 `flip_required=True` 的语境下, `flip_observed=True` 与 `normative_pair_correct=True` 在语义上是绑定的 (oracle flip → 预测必须翻, 否则 pair_correct=False); 但 `flip_observed` 仍显式计算并 AND, 是冗余但更易审计的实现。✓

### 4.4 leakage 计算: `D_semantic - D_surface`, 任一 None → 1.0
- `_divergent`: `if left is None or right is None: return 1.0`, 否则按 `physical_deltas_equal` / `event_records_equal` 取反。
- `score_leakage` 同时输出 `physical_delta_leak` 与 `event_delta_leak`, 每个由 `semantic - surface` 构成; 双方都 `None` 时 `1-1=0` (允许的 cancel), 一方 `None` 时 `1-0=1` (不会被误判为 disentanglement)。
- 单测 `test_parse_failure_is_not_invariance_credit` 覆盖 `None, None, None, None` 全部 → `sem=1, surf=1, leak=0`; 我额外以交互式确认 `None, parsed, parsed, parsed` → `sem=1, surf=0, leak=1`。

### 4.5 factual twin 三个子指标
- `_changed_paths` 用 leaf-path set 表示每个组件的 changed paths, 其中 `_value_equal` 决定单字段是否真"变化" (连续字段用 `continuous_equal`)。
- `score_factual_twin`:
  - `predicted_paths`: 所有 (component, leaf) 中 predicted 报告变化的
  - `target_paths`: 所有 (component, leaf) 中 oracle 报告变化的
  - `change_set_precision = |predicted ∩ target| / |predicted|`
  - `change_set_recall = |predicted ∩ target| / |target|`
  - `change_set_f1`: 上述 P/R 的调和
  - `correct_changes`: 在 `predicted ∩ target` 内, 双侧 predicted 值都匹配 oracle 值的对数
  - `changed_field_macro_f1 = 2*VP*VR/(VP+VR)`: VP/VR 同样基于 `correct_changes`
  - `physical_twin_sensitive = bool(predicted_physical)`: 只要 predicted 物理字段非空 (即 predicted 至少在某物理 leaf 上变化)
  - `target_physical_sensitive = bool(target_physical)`: oracle 侧同理
- 单测 `test_factual_twin_change_metrics_penalize_suppression` 覆盖 (1) 模型准确预测两处变化 → `macro_f1=1.0, physical_twin_sensitive=True`; (2) 模型对 base/twin 都预测相同 → `macro_f1=0.0, physical_twin_sensitive=False`。
- 注: `change_set_*` 与 `changed_field_macro_f1` 之间的差异在于前者仅看路径是否变化 (不看值), 后者要求路径变化 + 变化后的值都正确 — 合同 §5 的两段描述都满足。

### 4.6 rollout H1/H3/H5 评分 + evaluate_rollout_gate
- `score_rollout`: 对 `target.get("rollout", [])` 每个 item 调 `score_fields` 算 `physical_field_f1 / physical_exact_match / event_field_f1 / event_exact_match / joint_exact_match`, 缺失 horizon 不出现在结果中 (所以 H1/H3/H5 缺失语义清晰)。
- `evaluate_rollout_gate`: 默认 `reference_horizon=1, long_horizon=5, minimum_ratio=0.85, absolute_minimum=0.70`。
  - 缺 H1 或 H5 → `status="UNIDENTIFIED"`, `reason="required rollout horizons are absent"` (不静默用 H3 推断)
  - 否则 `ratio = H5/H1`; `PASS = ratio >= 0.85 AND H5 >= 0.70`, 否则 `FAIL`
- 单测 `test_information_and_rollout_gate_report_missing_h5` 覆盖 `{1:1.0, 3:0.9}` → `UNIDENTIFIED`。
- 我额外以交互式确认 `{1:1.0, 5:0.9}` → `PASS` (ratio 0.9), `{1:1.0, 5:0.5}` → `FAIL`。

**T3 评审结论**: 完全合规。

## 5. T4 bootstrap 与方差 (bootstrap.py)

### 5.1 scenario_cluster_bootstrap 使用 scenario_id 做 cluster 重采样
- `clusters = sorted(next(iter(cluster_sets)))`, 其中 `cluster_sets = {frozenset(scores) for scores in scores_by_arm.values()}`, 并 `len(cluster_sets) == 1` 强校验 (各 arm 必须用同一组 scenario_id, 否则 raise)。
- 采样: `sampled = [rng.choice(clusters) for _ in clusters]` (with-replacement, 长度等于 cluster 数, 即每次 replicate 仍保持 "scenario-level" 抽样)。
- 这与 `effective_unit = "scenario_family"` 一致, 与合同 §7 描述一致。✓
- 单测 `test_bootstrap_rejects_mismatched_cluster_sets` 覆盖 cluster 集不一致会 raise。

### 5.2 种子 / confidence_level (0.95) 参数化路径
- 入口签名: `scenario_cluster_bootstrap(scores_by_arm, *, samples, confidence_level, seed)`。
- `samples` 必须 `> 0`; `confidence_level` 必须 `0 < p < 1`; 任一违规 raise (与 `cluster_bootstrap_means` 同样守护)。
- `rng = random.Random(seed)` (独立于全局状态), 同 seed 同输入 → 同输出 (单测 `test_bootstrap_is_deterministic_and_recomputes_envelope` 第一断言)。
- `run_smoke_baselines` 中 `seed=20260916` (默认), `bootstrap_samples=5000`, `confidence_level=0.95`, 并对每个 cell 用 `seed + offset * 100_003` 派生子种子, 避免跨 cell 共享 RNG 状态。

### 5.3 CI 实现: 百分位 vs normal approximation
- 实现走百分位 (即基本 percentile bootstrap): `lower = _quantile(values, alpha/2)`, `upper = _quantile(values, 1 - alpha/2)`, `alpha = 1 - confidence_level`。
- `_quantile` 线性插值 (类似 numpy 默认)。
- 没有 normal approximation 路径 — 与合同 "基于 cluster bootstrap percentile 或 normal approximation" 二选一, 选了 percentile, 是合理选择。
- 适用于 H1/H3/H5 的所有 arm: `score_evaluator_pair` / `score_factual_twin` / `score_rollout` 等所有指标都先聚合成 scenario-macro (`scenario_macro_average` 或 `_mean_scenario_metrics`), 再喂给 `scenario_cluster_bootstrap`, 因此置信区间是 "scenario-family-level" 估计。
- envelope 单独走 `envelope_draws = [max(replicate.values()) for ...]`, 然后再算百分位 — 与合同 §7 "recomputed inside each replicate" 一致。
- 单测 `test_bootstrap_is_deterministic_and_recomputes_envelope` 覆盖 (1) 同 seed 同输出; (2) envelope point == 0.5 (在 `left={1,0,0.5}, right={0,1,0.5}` 时); (3) `envelope.lower >= 0.5` (因 max ≥ 任一均值)。

**T4 评审结论**: 完全合规。

## 6. T5 Static baseline 输入特征 (baselines.py)

### 6.1 `_decision_predictions` 四个 baseline 全 evaluator-blind
- **`profile_majority`**: 只读 `example.profile_id` 与 `example.target["normative_decision"]` (后者仅出现在 train 侧的统计 `counts[profile_id][decision] += 1`, 不进入 development 侧), 不读 evaluator 字段。✓
- **`structured_depth3`**: `_example_features` 用 `families[example.scenario_id]["model_input"]` 拍平为 `dict[str, float]`, 再加 `profile=...: 1.0` 偏移, 走 `_fit_depth_tree(..., depth=3)`。输入仅为 `model_input` + `profile_id`。✓
- **`word_tfidf_centroid` / `char4_tfidf_centroid`**: `_tfidf_predictions` 走 `_centroid_scores`, 输入为 `example.prompt` (即 `_structured_prompt` 的 `canonical_json(family["model_input"])` 或 `_natural_language_prompt` 的 scenario rendering)。训练时聚类、测试时用质心距离分类, 仍只用 `prompt` + `target["normative_decision"]`。✓
- 全部 baseline 不读 `evaluator_twins[profile_id]`, 不读 `evaluations`, 不读 `policy_result`, 因此 evaluator-blind 满足。✓

### 6.2 `_fieldwise_factual_vote` 7-neighbor 投票不读 evaluator
- 常量 `FIELDWISE_NEIGHBOR_COUNT = 7`。
- 邻居从 train families 的 `family["primary"]["physical_delta"]` + `["event_record"]` 构造; 这些 "primary" 是 scenario 级别的、与 evaluator profile 无关的 oracle 输出。
- `_fieldwise_factual_vote(neighbors)`:
  - 初始 `prediction = deepcopy(neighbors[0])`
  - 遍历所有 leaf paths
  - 若 `_continuous_factual_path(path)` (即 `path[0] == "event_record"` 且 `path[-1] ∈ {reversibility, recovery_cost, uncertainty}` 或 path 含 "impact_vector") → `median` of floats
  - 否则 → `Counter(json.dumps(...))` 取最多, 同 count 字典序最小 (deterministic tie-break)
  - 调 `_replace_path(prediction, path, selected)`
- 7-NN 邻居由 `_structured_fieldwise_factual_predictions` / `_text_fieldwise_factual_predictions` 选取: 距离按 `model_input` flatten features (structured) 或 TF-IDF cosine (text) 计算, 与 evaluator 无关。✓
- 单测 `test_fieldwise_vote_uses_majority_and_continuous_median` 覆盖 (1) 连续 median 正确 (0.2/0.4/0.6 → 0.4; -0.5/-0.25/0.0 → -0.25); (2) 离散 majority + 字典序 tie-break (`{1,1,2}` → 1; `{[],[],["x"]}` → `[]`; `{True,True,False}` → True)。

### 6.3 fact base 来自 `family["primary"]["physical_delta"]` 与 `["event_record"]`
- `_structured_factual_predictions`、`_structured_fieldwise_factual_predictions`、`_tfidf_nearest_targets`、`_tfidf_fieldwise_targets` 全部以 `family["primary"]["physical_delta"]` / `["event_record"]` 为 target 字段, 不下钻到 `evaluations[profile_id]`。✓
- 与合同 §7 "evaluator-blind" 描述完全一致。✓

### 6.4 `_scenario_joint_scores` 使用 `score_evaluator_pair`
- 每个 development example 调 `_parsed_static_output` (内部 `parse_model_output(json.dumps(payload), _one_step_target(example))`):
  - factual 来自当前 scenario 下的统一 factual (不随 profile 变, 符合 evaluator-blind)
  - decision 来自 `_decision_predictions[arm][index]`
- 接着对 `TARGET_PROFILE_PAIRS` 的三对 (harm_averse/efficiency_tolerant, procedure_preserving/autonomy_preserving, procedure_preserving/harm_averse) 调 `score_evaluator_pair`, 并记录到 `values[scenario_id]["joint_pair_success"]`、`normative_pair_accuracy`、`physical_consistent_and_correct` 等。
- **同口径**: 与 model arm 共用 `score_evaluator_pair` / `score_one_step`, `parse_model_output` 失败返回 `None` (被 `_parsed_static_output` 透传), `_scenario_joint_scores` 调 `score_evaluator_pair(None, None, ...)` 时全部 False、`joint_pair_success` 走"parse collapse" 分支, 不获得 credit。✓
- 单测 `test_static_baseline_uses_joint_pair_success_not_classification_only` 覆盖:
  - factual 完美 + decision 全对 → `joint_pair_success=1.0`
  - factual 错 (`count_delta` 改为 0) 但 decision 仍全对 → `normative_pair_accuracy=1.0, joint_pair_success=0.0` — 证明 joint_pair_success 不被 decision accuracy 替代

### 6.5 Static envelope rule
- 报告字符串: `"static_envelope_rule": "maximum scenario-macro joint_pair_success recomputed inside each scenario-cluster bootstrap replicate"`。
- 实际计算: `run_smoke_baselines` 把 4 决策 baseline × 2 factual mode (默认 + fieldwise_knn7) → 8 个 arm, 全部进入 `scenario_cluster_bootstrap` 的 `scores_by_arm`, 在每个 replicate 内 `envelope_draws.append(max(replicate.values()))`。
- envelope point = `max(point.values())`, envelope CI = `quantile(envelope_draws, alpha/2)` 与 `quantile(..., 1-alpha/2)`; 标记 `recomputed_inside_each_replicate: True`。
- 不是用 `_classification_summary` 的 accuracy, 而是 scenario-macro `joint_pair_success`。✓
- 注: `factuals_by_mode` 同时包含 6 个 mode (structured_knn1, structured_fieldwise_knn7, word_knn1, word_fieldwise_knn7, char_knn1, char_fieldwise_knn7), 但实际进入 envelope 的只是 "factual_mode[arm]" 与 "stronger_factual_mode[arm]" 各 1 个, 共 8 个 arm × 1 decision arm = 8 arm 名, 与报告一致。

**T5 评审结论**: 完全合规。

## 7. T6 A→A / B→B / 跨环境人口 (baselines + transfer_matrix)

### 7.1 `run_smoke_baselines` 的池化路径
- `transfer_cells` 按 `(train_alias, test_alias, condition)` 三维枚举, 8 个 cell 全覆盖: `A→A, A→B, B→A, B→B × structured/natural_language`。
- 池化:
  - `primary_development_ood = _pooled_bootstrap(scores_by_condition[condition], ("A->A", "B->B"), ...)` — 池化两个 within-environment cell
  - `cross_environment_transfer = _pooled_bootstrap(scores_by_condition[condition], ("A->B", "B->A"), ...)` — 单独报告, 互不替代
- `_pooled_bootstrap` 把各 cell 的 `scenario_id` 用 `f"{cell}:{scenario_id}"` 前缀去重, 然后做 cluster bootstrap, 与 `effective_unit="scenario_family"` 一致。
- 报告字段 `primary_population = "within-environment development families, including declared composition holdouts; cross-environment cells are reported separately"`, 与合同 §7 描述一致。✓
- `primary_estimand = "ood_joint_pair_success"` 字符串已写入, 与合同 §7 描述一致。✓

### 7.2 `transfer_matrix.build_transfer_manifest` 的硬约束
- 8 个 cell (`A→A, A→B, B→A, B→B × structured, natural_language`): 由 `ENVIRONMENT_ALIASES` × `ENVIRONMENT_ALIASES` × `INPUT_CONDITIONS` 三重循环枚举; 实际 cell 字典长度 = 4 × 2 = 8。✓
- `train_scenario_ids_sha256` / `test_scenario_ids_sha256`: `_id_hash` 用 `\n` 连接 sorted ids 后 sha256 hex digest。✓
- `train_test_overlap_count`: `sorted(set(train_ids) & set(test_ids))` 长度; 任何 `> 0` → `cell["status"] = "INVALID_SPLIT_OVERLAP"`。✓
- 整体 `status = "READY" iff all(cell["status"] == "READY") and not unidentified`, 否则 `UNIDENTIFIED`。
- 单测 `test_transfer_manifest_has_all_eight_cells_and_no_overlap` 与 `test_transfer_support_cannot_be_borrowed_from_training_rows` 共同覆盖 (1) 8 cell 全 READY, overlap=0; (2) dimension sign 不足 → 整体 UNIDENTIFIED + `insufficient_dimension_sign_cells` 非空。

### 7.3 `environment_support` 的 insufficient_dimension_sign_cells 检查
- `_environment_support(rows, minimum_fraction)`:
  - 过滤 `discretionary` = `not hard_violations AND len(distinct decisions across profiles) > 1`
  - 对每个 `IMPACT_DIMENSIONS = {safety, privacy, autonomy, trust, efficiency, fairness, commitment}` 计算 `positive_fraction` 与 `negative_fraction` (相对 discretionary)
  - `pair_support`: 对 `TARGET_PROFILE_PAIRS` 每对 (left, right), 计算 `flip_count` / `flip_fraction` (oracle 在 discretionary 上的决策翻转率)
  - `insufficient = [f"{dimension}:{sign}" for dim in dims for sign in ("positive","negative") if fraction < minimum_fraction]`
  - `status = "IDENTIFIED" if not insufficient else "UNIDENTIFIED"`
- 默认 `minimum_dimension_sign_fraction=0.05` (与 §8 "Each destination environment must retain the preregistered impact-dimension × sign support" 对齐)。
- 整体 manifest 的 `unidentified_environments` 列出所有 `status != "IDENTIFIED"` 的 destination env; 任一非空 → manifest UNIDENTIFIED。
- 注: `_environment_support` 只看 `development` split (`if row["split"] == "development"`), 不复用 `train` 行 — 单测 `test_transfer_support_cannot_be_borrowed_from_training_rows` 显式验证 `manifest["status"] == "UNIDENTIFIED"` 当 train 与 development 的 impact_vector sign 翻转时。✓

**T6 评审结论**: 完全合规。

## 8. T7 跨合约一致性

### 8.1 `primary_estimand` / `primary_population` / cell 名称顺序
- 合同 §7: "The primary smoke Static envelope pools the two within-environment train-to-development cells, including declared composition holdouts. Cross-environment A-to-B and B-to-A cells are a separate transfer analysis and cannot silently replace the primary OOD population."
- 实现:
  - `primary_estimand = "ood_joint_pair_success"`
  - `primary_population = "within-environment development families, including declared composition holdouts; cross-environment cells are reported separately"`
  - `pooled["primary_development_ood"]` = `("A->A", "B->B")` 池化
  - `pooled["cross_environment_transfer"]` = `("A->B", "B->A")` 单独报告
- cell 名称顺序: `_pooled_bootstrap` 接收 `cell_names: tuple[str, ...]`, 实现按 `cell_names` 顺序展开, `("A->A", "B->B")` 与 `("A->B", "B->A")` 与合同一致。✓

### 8.2 `classification_diagnostics` 仅作诊断, 不进入 headline
- 合同 §7: "Classification accuracy and balanced accuracy remain diagnostics only."
- `_run_cell` 把 `_classification_summary` 放在 `report["classification_diagnostics"][arm]`, 4 个 arm 各一个; 顶层 `report` 中 headline 是 `scenario_macro_joint_estimand` 与 `scenario_cluster_bootstrap.intervals.static_envelope`, 都不引用 `accuracy` 或 `balanced_accuracy`。
- envelope 的 `scores_by_arm` 仅含 `joint_pair_success`, 不是 `accuracy`。✓

### 8.3 H5 缺失 → `UNIDENTIFIED`, 不静默用 H3 推断
- 合同 §6: "Until an H5 target exists under an accepted retained protocol, the H5 gate is reported as `UNIDENTIFIED`, never inferred from H3."
- `evaluate_rollout_gate` 在 `reference_horizon=1` 或 `long_horizon=5` 缺失时, 立即 `return {"status": "UNIDENTIFIED", "reason": "required rollout horizons are absent"}`。
- 实现中没有任何 "用 H3 替代 H5" 的代码路径 (ratio 只在 H1/H5 都存在时计算)。✓
- 单测 `test_information_and_rollout_gate_report_missing_h5` 覆盖 `{1:1.0, 3:0.9}` → `UNIDENTIFIED`。

### 8.4 Static 输出经严格 parser, 失败返回 None (与其他 arm 同样计入分母)
- 合同 §7: "Static outputs pass through the same strict parser and evaluator-pair scorer as trained model outputs."
- `_parsed_static_output` 用 `parse_model_output(json.dumps(payload), _one_step_target(example))`; 若 `parsed.ok` False, 返回 `None`。
- 在 `_scenario_joint_scores` 中, `predicted_left = _parsed_static_output(left, ...)` 可能为 None, 传入 `score_evaluator_pair(None, None_or_predicted, ...)` 时, 走 §4.2 的保守 False 分支, 不获得任何 credit。✓
- 显式记录 `parse_complete` 到 `values[scenario_id]["parse_complete"]`, 便于审计 baseline 在 parse failure 时的行为。✓

**T7 评审结论**: 完全合规。

## 9. 发现清单 (按严重度)

### 高 (High) — 0
无。

### 中 (Medium) — 2
- **M1: 单元测试未显式覆盖"plain (无 `json` 标签) Markdown 围栏"接受路径** (`tests/test_model_output.py:test_exact_json_and_single_json_fence_are_accepted` 只测了 `json` 围栏)。虽然 `_FENCE` 正则 `(?:json)?` 与 `re.IGNORECASE` 都正确支持 plain 围栏, 我已用交互式调用验证 `plain fence ok: True`, 但合同 §2 明确接受 `json/plain` 两类围栏, 测试应显式覆盖 plain 围栏以防将来正则被无意中收紧。
- **M2: 单元测试未覆盖 `parse_model_output` 在 confidence 字段非法值 (越界 / 非有限) 上的 `invalid_confidence` 错误码**。`model_output._validate_payload` 显式实现 `invalid_confidence`, 但 `tests/test_model_output.py` 没有对应测试 (它只测了缺失 key、prose、type error、inconsistent、horizon 错位)。同样, `factorized` 路径的 `parse_factual_output` 也没有专门的 schema-不符测试 (目前只测了 happy path 与 normative 端的 `decision_consistency`)。

### 低 (Low) — 4
- **L1: 单行围栏 `\`\`\`json {...} \`\`\`` (无换行) 不被接受**。`_FENCE` 显式要求 `\n` 在 opening 后与 closing 前。合同未明确要求单行围栏, 但有些模型输出习惯单行, 这是一个潜在的兼容性问题 (False 时返回 `invalid_json`)。建议 (a) 在合同里明确写"围栏必须是多行", 或 (b) 让 `_FENCE` 也支持单行。**当前实现与合同严格一致, 暂不阻塞。**
- **L2: `parse_finite_decimal` 接受带 `+` 号的字符串 (例如 `"+0.5"`) 但合同没有显式说明**。`_DECIMAL_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"`, `+` 与 `-` 都接受。Python `Decimal("+0.5")` 也支持。合同 §3 "0.1 / 0.10 / .1 are identical" 只列了三种, 加上 `+` 与 `-` 扩展是合理的"向前兼容", 不会破坏现有行为, 但建议合同里明文一句以免后续理解分歧。
- **L3: `score_evaluator_pair` 在 `parse_complete=False` 时, `flip_observed` 显式赋 `False`**, 而 `flip_required` 仍按 oracle 计算; 这意味着 `normative_flip_recalled` 在 parse 失败时必为 `False` (因 `flip_observed=False`)。这是合同期望的"保守 False" 行为, 但代码没有显式注释解释为什么 `flip_observed` 在失败分支也要 reset (而非沿用 oracle 翻转率的隐含估计)。建议加一行注释。
- **L4: `baselines._run_cell` 把 4 baseline × 2 factual mode → 8 arm 全部送入 `scenario_cluster_bootstrap`, 但 `eligible_arms` 仍只列原始 4 个决策 baseline**。这与报告字段语义一致 (`eligible_arms` = 决策 baseline 集合, `eligible_joint_arms` = 8 个), 但 "eligible_joint_arms" 这个名字并不显眼地说明它是 baseline + fieldwise 强化的合集。建议在 `_run_cell` 的 docstring 或 report 字段注释里加一句 "eligible_joint_arms expands each decision baseline with a stronger fieldwise 7-NN factual mode"。

## 10. 改进建议 (非阻塞)

1. **(M1) 在 `test_model_output.py` 增加一个 `test_plain_fence_is_accepted`** 显式测 `\`\`\`\n{...}\n\`\`\`` 路径; 同时可以加一个 `test_plain_fence_case_insensitive` 测 `\`\`\`JSON\n{...}\n\`\`\``。
2. **(M2) 在 `test_model_output.py` 增加 confidence 越界 / 非有限的负向测试**, 例如:
   ```python
   payload = target(); payload["confidence"] = 1.5
   self.assertEqual(parse_model_output(json.dumps(payload), target()).error_code, "invalid_confidence")
   payload = target(); payload["confidence"] = float("nan")
   self.assertEqual(parse_model_output(json.dumps(payload), target()).error_code, "invalid_confidence")
   ```
   同时为 `parse_factual_output` 增加 `top_level_keys` 错误码的负向测试 (例如多带 `confidence` 字段)。
3. **(L1)** 若合同对"单行围栏"立场不明, 建议在 `METRIC_COMPARATOR_V2_1.md` 或 Phase-2 evaluation contract 里加一句"code fence 必须 multi-line (opening 与 closing fence 各占独立行)"; 若希望支持单行, 调整 `_FENCE` 正则。
4. **(L2)** 在合同 §3 末尾补一句"带显式 `+`/`-` 符号的连续数字与无符号等价", 锁定当前 `_DECIMAL_PATTERN` 的语义。
5. **(L3)** 在 `score_evaluator_pair` 的 `not parse_complete` 分支里给 `flip_observed = False` 加一行注释, 说明"任何 flip 都不能在 parse 失败时被计为 recalled, 否则 0.0 准确率会被记为 false recall"。
6. **(L4)** 在 `baselines._run_cell` 的 docstring 或 `eligible_joint_arms` 字段的产出处加一行注释, 说明"每个决策 baseline 同时配套一个 fieldwise 7-NN factual mode, 共 8 个 arm 进入 envelope"。
7. **(可选, 不阻塞)** 在 `bootstrap.scenario_cluster_bootstrap` 的入口或 docstring 加一句"CI 走 percentile, 不做 BCa / t-bootstrap / normal approximation", 与合同表述对齐; 防止未来有人"优化"成 normal approximation 时悄悄改了语义。
8. **(可选, 不阻塞)** `phase2_metrics.information_diagnostics` 在 `parsed_count = 0` 时会触发 `max(counts.values()) / attempts if attempts and counts else 0.0`, 但仍可调用; 若想更严格, 可在 `attempt_count == 0` 时早 raise, 与 `scenario_cluster_bootstrap` 的"空 cluster" 错误处理保持一致风格。

## 11. 测试运行结果摘要

| 模块 | 用例数 | 通过 | 失败 |
|---|---:|---:|---:|
| `tests.test_comparators` | 4 | 4 | 0 |
| `tests.test_model_output` | 6 | 6 | 0 |
| `tests.test_bootstrap` | 3 | 3 | 0 |
| `tests.test_phase2_metrics` | 8 | 8 | 0 |
| `tests.test_baselines` | 2 | 2 | 0 |
| `tests.test_phase2_dataset` | 3 | 3 | 0 |
| **合计** | **26** | **26** | **0** |

我额外做的交互式断言 (不在单测中):
- 验证 plain (无 `json`) 围栏 → `ok=True`
- 验证 `Result: {}` prose 包装 → `invalid_json`
- 验证两段连续围栏 → `invalid_json`
- 验证 `None, parsed, parsed, parsed` leakage → `sem=1, surf=0, leak=1` (非 cancel)
- 验证 `{1:1.0, 3:0.9}` rollout gate → `UNIDENTIFIED`
- 验证 `{1:1.0, 5:0.9}` → `PASS`, `{1:1.0, 5:0.5}` → `FAIL`
- 验证 `scenario_cluster_bootstrap` 同 seed 同输入 → 同输出 (deterministic)

## 12. 结论

Phase-2 评测实现 (`model_output` / `comparators` / `phase2_metrics` / `bootstrap` / `phase2_dataset` / `transfer_matrix` / `baselines`) 与合同 (METRIC_COMPARATOR_V2_1 + Phase-2 evaluation contract + EXTERNAL_SMOKE_ACCEPTANCE_V3 + PHASE1_V3_INTERNAL_SMOKE) **逐项对齐**, 单测与额外断言均通过。**没有阻塞级问题**, 仅有 2 条中等级测试覆盖度建议与 4 条低优先级改进建议。建议在 retained baseline 冻结前补齐 M1/M2 两组测试 (≤ 半天工作量), 不影响本评审的 APPROVE_WITH_FIXES 结论。
