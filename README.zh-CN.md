# Normative World Model：受泄漏控制的运行时遥测实验

[🇺🇸 English](README.md) | [🇨🇳 中文说明](README.zh-CN.md)

Normative World Model 是一个隔离研究项目，用于检验规范性预测何时能够成为 Agent 行动的可靠运行时遥测信号。

项目从一个狭窄且可证伪的问题出发：

**受政策和评价配置条件化的语言世界模型，能否在 evaluator-value 干预下保持事实转移预测稳定，同时正确改变规范判断？**

本项目不尝试训练通用的人类价值系统。它提供两个符号环境、确定性的物理与规范 oracle、成对反事实家族、泄漏审计，以及用于分离世界预测和评价过程的预注册门槛。

## 当前状态

- **隔离项目脚手架和 P0 合同已经完成。**
- 两个表面完全不同的环境共享同一套冻结规范谓词：
  - 叙事游戏状态机；
  - 组织内部 Agent 模拟器。
- Phase-1 revision-2 smoke 语料在每个环境中包含 300 个场景家族，并通过全部本地门槛。
- Gate C 已在两个环境中分别通过：

| 环境 | word/character 最大 macro AUC | 95% 聚类上界 | 冻结门槛 |
|---|---:|---:|---|
| game | `0.4743` | `0.5047` | **PASS** |
| organization | `0.5153` | `0.5699` | **PASS** |

- 两份原始 smoke JSONL 在相同 seed 重跑下保持逐字节稳定。
- 外部审计提出的条件已经落实；刷新后的 provenance manifest 正等待无条件重新接受，之后才会解锁 retained 生成。
- 完整 retained 语料、confirmation 语料、模型权重和训练运行尚未生成。
- 生成数据、模型、缓存、秘密 nonce 和实验产物均被 Git 明确忽略。

## 研究动机

Agent 的失败可能在最终输出提交前形成。一个运行时治理系统可能需要跨越以下阶段进行判断：

1. 转移前世界状态
2. 候选行动和适用政策
3. 预测的物理状态转移
4. 合成制度事件记录
5. 受 evaluator 条件化的规范判断
6. Runtime 的允许、拒绝或升级决定

本仓库研究世界模型预测能否充当 **Runtime 传感器**，同时避免评价条件改写事实预测。

核心区分是：

- `actor_values` 是世界中的因果变量，可以合法地改变物理转移；
- `evaluator_values` 定义评价视角，不得改变事实目标。

## 仓库内容

```text
configs/
  calibration_cases.json          # 端到端 oracle 可达性断言
  evaluator_profiles.toml         # 四个确定性 evaluator profile
  normative_predicates.toml       # A/B 共享本体与生成器门槛
  preregistration.toml            # 机器可读的阈值与停止规则

docs/
  NORMATIVE_PREDICATE_CONTRACT.md  # 跨环境谓词合同
  EVALUATOR_PROFILES.md            # 两层 N oracle 与精确语义
  LEAKAGE_AUDIT_SPEC.md            # 按环境执行的生成器出口审计
  METRIC_COMPARATOR_V2_1.md        # 正确性与不变性共享比较器
  EXTERNAL_SMOKE_ACCEPTANCE.md     # 哈希绑定的 retained 生成锁
  EXTERNAL_AUDIT_ADJUDICATION.md   # 接受的意见与事实纠正

src/normative_world_model/
  environments/game.py             # 叙事游戏动力学与渲染器
  environments/organization.py     # 组织 Agent 动力学与渲染器
  policy_oracle.py                  # 不可由 profile 推翻的硬政策层
  normative_oracle.py               # 受 profile 条件化的裁量 oracle
  generator.py                      # 成对家族与 rollout 生成器
  audits.py                         # 密度、泄漏、完整性与基线门槛
  comparators.py                    # v2.1 数值比较合同
  metrics.py                        # 成对事实与规范指标

scripts/
  setup.ps1                         # 项目本地 Python 环境初始化
  check.ps1                         # 单元测试与隔离审计
  check-phase1-smoke.ps1            # smoke provenance 验证器
  build-smoke-audit-bundle.py       # 紧凑外审包生成器

tests/
  test_*.py                         # 合同、oracle、审计、指标和锁测试
```

大型或敏感产物不会进入仓库，可在本地忽略目录中重新生成。

## 核心实验

主实验在保持转移前状态与候选行动不变的情况下改变 evaluator profile：

```text
T(source, actor_values) -> physical_delta, next_state, event_record
N(event_record, policy_result, evaluator_values) -> allow | reject | escalate
```

成功的联合模型必须同时满足：

```text
evaluator 干预下，事实预测保持正确且不变
确定性 oracle 要求翻转时，规范预测正确翻转
```

核心工程对照为：

| 实验臂 | 事实模型是否看到 evaluator values？ | 是否由架构直接禁止泄漏？ |
|---|:---:|:---:|
| `joint_naive` | 是 | 否 |
| `joint_consistency` | 是 | 否；使用反泄漏目标训练 |
| `factorized` | 否 | 是 |
| Static envelope | 取决于任务 | 仅作为基线 |

科学问题是联合模型能否学会内部解耦；factorized 实验臂回答的是另一个工程问题：模块化架构是否足以可靠地保证不变性。

## Phase-1 Smoke 结果

revision-2 smoke 共包含 600 个场景家族，不生成任何 confirmation 样本。

本地复现检查包括：

- 确定性重放；
- 场景家族切分完整性；
- `physical_delta` 与 `next_state` 精确一致；
- 三步 rollout 链式连接；
- 单叶 factual、actor-value 和 policy 干预；
- 自然语言语法和信息等价检查；
- 逐字段序数标记基数；
- 仿射与深度三非平凡性基线；
- 按环境执行的 word/character TF-IDF 泄漏门；
- 精确 Decimal oracle 边界测试；
- 源码、语料、报告和外审包 provenance 哈希。

原始语料保留在本地。仓库记录协议和哈希，不提交生成的 JSONL 内容。

参见：

- [Phase-1 revision-2 smoke 记录](docs/PHASE1_REVISION2_SMOKE.md)
- [外部审计裁决](docs/EXTERNAL_AUDIT_ADJUDICATION.md)
- [外部 smoke 接受合同](docs/EXTERNAL_SMOKE_ACCEPTANCE.md)

## 快速开始

项目目前面向 Windows PowerShell 和 Python `>=3.12,<3.13`。

克隆并建立隔离环境：

```powershell
git clone https://github.com/sunnyspot114514/normative-world-model.git
cd normative-world-model
.\scripts\setup.ps1
. .\scripts\enter.ps1
```

运行仓库检查：

```powershell
.\scripts\check.ps1
```

生成本地 revision-2 smoke 语料：

```powershell
. .\scripts\project-env.ps1
.\.venv\Scripts\python.exe -m normative_world_model phase1-smoke --families 300
.\.venv\Scripts\python.exe .\scripts\build-smoke-audit-bundle.py
.\scripts\check-phase1-smoke.ps1
```

生成内容写入：

```text
data/generated/
artifacts/
runs/
models/
.cache/
.tmp/
```

这些路径均位于项目内部，并被 Git 忽略。

## 复现范围

仓库当前提供：

- 两个独立的确定性环境
- 一套共享且冻结的规范谓词合同
- 四个确定性 evaluator profile
- 硬政策层与裁量规范层
- factual、policy、actor-value、evaluator 和 surface 反事实
- 三步链式 rollout
- 精确边界 oracle calibration
- 按环境执行的泄漏和非平凡性门槛
- 共享的 v2.1 数值比较器
- retained 生成前的哈希绑定外部接受
- 标准库单元测试和 Windows 隔离脚本

当前尚不提供：

- 已提交的训练或 confirmation 生成语料
- 已训练的语言模型 checkpoint
- joint 与 factorized 模型结果
- 模型层面的跨环境迁移结果
- Runtime 干预结果
- 关于通用价值或一般道德推理的主张

## 实验阶段

- [x] 隔离项目脚手架
- [x] A/B 共享谓词合同
- [x] actor/evaluator value 分离
- [x] 确定性 policy 与 normative oracle
- [x] uncertainty 可达性分析
- [x] revision-2 成对家族生成器
- [x] 自然语言与 structured 输入审计
- [x] 因果 twin 与 rollout 完整性门槛
- [x] 按环境执行 Gate C
- [x] 外部全语料条件审计
- [x] 解决外部审计条件
- [ ] 对刷新 provenance manifest 的无条件接受
- [ ] retained Phase-1 语料
- [ ] 冻结 Phase-2 baseline 表
- [ ] 本地小模型 pilot
- [ ] 锁定 confirmation
- [ ] 可选服务器规模实验
- [ ] proposal/commit Runtime 评估

## 项目隔离

本仓库不会污染相邻项目：

- `.venv/` 是项目唯一使用的 Python 环境；
- `.cache/` 保存包、Hugging Face、Torch 和工具缓存；
- `.tmp/` 保存进程临时文件和秘密 nonce；
- `data/`、`models/`、`runs/` 和 `artifacts/` 仅保存本项目输入输出；
- `PYTHONNOUSERSITE=1` 防止 Windows 用户级 Python 包进入环境；
- 未来外部输入必须以带哈希、只读、版本化快照的方式导入。

## 研究合同

- [设计说明](DESIGN_NOTE.md)
- [执行计划](EXECUTION_PLAN.md)
- [预注册](PREREGISTRATION.md)
- [规范谓词合同](docs/NORMATIVE_PREDICATE_CONTRACT.md)
- [Evaluator profiles](docs/EVALUATOR_PROFILES.md)
- [联合一致性目标](docs/JOINT_CONSISTENCY_OBJECTIVE.md)
- [泄漏审计规格](docs/LEAKAGE_AUDIT_SPEC.md)
- [v2.1 指标比较器](docs/METRIC_COMPARATOR_V2_1.md)

## 许可证

本项目采用 Apache License 2.0。详见 [LICENSE](LICENSE)。
