# 文档集索引

这套文档的作用是**约束边界**：任何"要不要做"的分歧，先在设计合同和实现规格里找答案，找不到再讨论。
仓库只含文档，不含实现代码；文档描述的是实现必须满足的契约（代码按它写，冲突时代码算错）。

| 文档 | 一句话职责 | 什么时候看 | 优先级 |
| --- | --- | --- | --- |
| [DESIGN.md](DESIGN.md) | 边界契约：什么算这个项目、什么不算 | 提需求、评审、架构有分歧时 | 最高，冲突以它为准 |
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | 可编码规格：类型、六工具、8 条订单与分支矩阵、提示词契约、事务、回放、API 与 AC01–AC21 | 写代码和设计验收时 | 设计合同之下，开发计划之上 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 工作计划与评估操作手册 | 安排工作、追踪产物时 | 执行计划 |
| [INTERVIEW_READINESS.md](INTERVIEW_READINESS.md) | 面试可用性、证据缺口与讲解边界 | 投递、演示、写简历前 | 评审参考 |
| [BADCASE.md](BADCASE.md) | 迭代台账：失败怎么归因、修了怎么验证 | 每轮评估之后 | 记录性，不得与上两份矛盾 |

## 阅读顺序

```
第一次接触        → README.md（项目 3 分钟概览）
要判断"能不能做"  → DESIGN.md 第 2 章（非目标）+ 2.2 边界三问
要动手写代码      → IMPLEMENTATION.md（接口与验收）+ DEVELOPMENT.md第3章（工作包）
要改 prompt/工具  → DEVELOPMENT.md 第 6 章（评估 SOP）+ DESIGN.md 第 10 章（口径）
要解释某个失败    → BADCASE.md 归因表 + 对应 run 的 trace
```

## 文档边界

| 文档 | 只写 | 不写 |
| --- | --- | --- |
| DESIGN.md | 契约、非目标、判定条件、ADR、验收标准 | 具体代码、逐日计划、历史失败记录 |
| DEVELOPMENT.md | 命令、目录、任务分解、编码规范、测试与评估流程 | 架构理由的完整论证（指回 DESIGN） |
| BADCASE.md | 每条失败的现象、归因、修复、回放结果；缺附件的历史叙述标记未核验 | 通用方法论 |
| IMPLEMENTATION.md | 数据、接口、事务、执行和验收的具体规格 | 实测效果与虚构运行记录 |
| INTERVIEW_READINESS.md | 当前可证明的能力、证据缺口与讲解建议 | 无依据的个人经历与保证录用 |

## 一条元规则

**实测效果必须有原始产物和复现入口。** 阈值、排期、数据规模和目标值明确标注性质；没有实测数据就写待实测。
真实模型重跑不保证输出完全一致，需保存实验条件和波动；历史参考实现未附证据的主张不作当前项目结论。

## 当前状态

截至2026-11-04，W1–W3 的实现与离线验收已完成，W4 文档与演示产物随本次提交同步。

- 代码：`app/`（六组件：config / schemas / store / tools / core / llm + api / cli / eval）、`scripts/`（数据集、评估、泄漏检查、证据收集、演示）、`tests/test_acceptance.py`（AC01–AC21 共 22 个测试）。
- 验收：`python -m pytest tests -q` → 22 passed；证据索引见 `reports/evidence-index.md`（每条 AC 附 run_id）。
- 数据集：`data/eval_cases.jsonl` 24 条、`data/holdout.jsonl` 12 条、`data/drafts_50.jsonl` 50 条；题干泄漏检查 `scripts/check_leakage.py` → ok。
- 指标口径见 [DESIGN.md](DESIGN.md) 第 10 章。两份报告分列：`provider=scripted`（离线桩，证明链路可跑，**不代表模型能力**）与 `provider=openai`（真实模型 deepseek-v4.1-flash-1017，intent 0.958 / tools 0.958 / args 1.000 / escalation 0.917、degraded 0、P95 9062 ms，跑间波动见 README 指标表）。
- 阻塞：真实模型（`OPENAI_API_KEY` / `OPENAI_BASE_URL`）未提供，真实模型基线与单位成本待实测；`drafts_50` 的人工 A/B/C 档评分无人复核，人工采纳率写“待实测”。

