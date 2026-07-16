# Phase-2 评测实现评审建议

> 评审对象：`src/normative_world_model/{model_output, phase2_metrics, baselines, transfer_matrix, comparators, bootstrap, phase2_dataset}.py`
> 锁定 commit：`1f9f7f3418dcfa353a9efcbb9a493d4a0914138b`
> 评审合同：METRIC_COMPARATOR_V2_1 + Phase-2 evaluation contract + EXTERNAL_SMOKE_ACCEPTANCE_V3 §7 + PHASE1_V3_INTERNAL_SMOKE §9
> 单测运行：26/26 PASS（含评审员追加 6 项交互式断言）

---

## 1. 评审结论

**APPROVE_WITH_FIXES** — 不构成硬门控，可在补齐 M1/M2 后冻结 retained baseline。

| 严重度 | 数量 | 是否阻塞 retained 冻结 |
|---|---:|:---:|
| 高 | 0 | — |
| 中 | 2 | 推荐在冻结前补齐（≤ 半天工作量） |
| 低 | 4 | 可后置到 retained baseline 之后再修 |

## 2. 中等建议（建议在 retained baseline 冻结前补齐）

### M1 — `test_model_output.py` 缺 plain 围栏与大小写敏感测试
- 当前 `_FENCE` 正则接受 ```` ```json ```` 与 ```` ``` ```` 两种围栏（`json` 可选、`re.IGNORECASE`），但 tests 只显式覆盖 ```` ```json ```` 一种。
- 补两个用例即可：
  - `test_plain_fence_is_accepted`：直接喂 ```` ```\n{...}\n``` ````，断言 `ok=True`。
  - `test_plain_fence_case_insensitive`：喂 ```` ```JSON\n{...}\n``` ````，断言 `ok=True`。
- 这两个 case 现在由评审员交互式验证过，但没在仓库 tests 里。

### M2 — `test_model_output.py` 缺 confidence 越界 / 非有限 / 多带字段负向测试
- 当前 confidence 校验在 `_validate_payload` 中已实现（`float(parse_finite_decimal(...))` + `[0, 1]` 区间），但仓库 tests 没显式覆盖越界。
- 建议补：
  - `payload["confidence"] = 1.5` → `error_code = "invalid_confidence"`
  - `payload["confidence"] = float("nan")` → `error_code = "invalid_confidence"`
  - `payload["confidence"] = float("inf")` → `error_code = "invalid_confidence"`
- 同样地，`parse_factual_output` 当前只测 happy path；建议补多带 `confidence` 字段时 `error_code = "top_level_keys"` 的负向测试。

## 3. 低优先级改进（可后置）

### L1 — 单行围栏 ```` ```json {...} ``` ````（无换行）当前不接受
- `_FENCE` 显式要求 `\n` 在 opening 之后、closing 之前。
- 合同未明确要求单行围栏；如要支持，调整 `_FENCE` 即可。
- 建议在合同里**显式锁定**"围栏必须多行"或"允许单行"，避免后续模型输出习惯变化时静默改语义。

### L2 — `parse_finite_decimal` 接受带 `+` 号的字符串（如 `"+0.5"`），合同未显式说明
- `_DECIMAL_PATTERN = r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$"`，`+`/`-` 都接受；Python `Decimal("+0.5")` 也支持。
- 当前实现与合同 §3"0.1/0.10/.1 are identical" 严格一致（`+0.5 == 0.5`）。
- 建议在合同 §3 末尾补一句"带显式 `+`/`-` 符号的连续数字与无符号等价"。

### L3 — `score_evaluator_pair` 在 `parse_complete=False` 时 `flip_observed` 重置
- 当前实现：在失败分支显式 `flip_observed=False`，与 oracle 翻转率解耦。
- 合同期望的"保守 False"行为，但代码没有显式注释。
- 建议加一行注释："任何 flip 都不能在 parse 失败时被计为 recalled，否则 0.0 准确率会被记为 false recall"。

### L4 — `baselines._run_cell` 的 `eligible_arms` vs `eligible_joint_arms` 命名
- `eligible_arms` 只列 4 个决策 baseline，`eligible_joint_arms` 列出 8 个（4 决策 × 2 factual mode）。
- 命名上不够显眼地表达"eligible_joint_arms 是 baseline + fieldwise 7-NN factual mode 强化的合集"。
- 建议在 `_run_cell` docstring 或 report 字段注释里加一句。

## 4. 可选改进（不阻塞）

- `bootstrap.scenario_cluster_bootstrap` 入口或 docstring 加一句"CI 走 percentile，不做 BCa / t-bootstrap / normal approximation"，防止后续被"优化"成 normal approximation 时悄悄改语义。
- `phase2_metrics.information_diagnostics` 在 `attempt_count == 0` 时早 raise，与 `scenario_cluster_bootstrap` 的"空 cluster"错误处理风格保持一致。

## 5. 跨合约一致性核对

| 合同条款 | 实现位置 | 状态 |
|---|---|---|
| 解析器只接受单 JSON / `json`/plain 围栏 | `model_output._FENCE` + `_unwrap` | ✓ |
| `escalation_required == (decision == "escalate")` | `_validate_payload` | ✓ |
| rollout horizon 集合严格匹配 | `_validate_payload` 三层防御 | ✓ |
| `DECISIONS = {allow, reject, escalate}` | `model_output.DECISIONS` | ✓ |
| 连续字段 0.005 inclusive 绝对容差 | `comparators.continuous_equal` | ✓ |
| numeric spelling 归一（"0.1"=="0.10"==".1"） | `comparators.parse_finite_decimal` | ✓ |
| non-finite / malformed 数字 invalid | `comparators.parse_finite_decimal` ValueError | ✓ |
| `joint_pair_success = physical AND event AND normative` | `phase2_metrics.score_evaluator_pair` | ✓ |
| `normative_flip_recalled` = flip_required & pair_correct & flip_observed | `score_evaluator_pair` | ✓ |
| leakage D_semantic - D_surface，None 保守记 1 | `score_leakage._divergent` | ✓ |
| H5 缺失 → UNIDENTIFIED（不默默用 H3 推断） | `evaluate_rollout_gate` | ✓ |
| bootstrap cluster by `scenario_id` | `scenario_cluster_bootstrap` | ✓ |
| Static baseline evaluator-blind | `_decision_predictions` / `_fieldwise_factual_vote` | ✓ |
| `primary_development_ood` = pool(A→A, B→B) | `run_smoke_baselines` | ✓ |
| `cross_environment_transfer` = pool(A→B, B→A) | `run_smoke_baselines` | ✓ |
| 8 cells, train_test_overlap=0, status=READY | `build_transfer_manifest` | ✓ |
| destination `environment_support` IDENTIFIED | `_environment_support` | ✓ |
| `_classification_summary` 仅作 diagnostics | `baselines._run_cell` | ✓ |

## 6. 优先级建议

冻结前（必须做）：
- M1（plain 围栏 + 大小写）
- M2（confidence 越界 / 非有限 / 多带字段）

冻结后可后置：
- L1（围栏合同明确）
- L2（`+` 号合同明确）
- L3（注释 flip_observed reset）
- L4（`eligible_arms` 命名注释）
- 2 项可选改进
