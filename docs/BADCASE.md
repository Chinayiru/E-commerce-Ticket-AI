# Bad Case 归因与迭代记录

> 本文件是评估闭环的账本：每个失败用例都要落到四类归因之一，修复后必须回放验证。
> 规则：没有trace的失败仍计入失败总数并标记evidence_missing；没有回放证据的修复不能标记已验证。

## 1. 四类归因（判定口径）

| 归因 | 判定依据 | 典型 trace 特征 |
| --- | --- | --- |
| A 意图识别错 | `intent_pred != intent_gold`，且工具调用随意图一起跑偏 | `expected_tools` 与 `called_tools` 成组缺失 |
| B 工具选错 | 意图对，但工具集合多一个/少一个 | `missing_tools` / `extra_tools` 非空，`intent_ok=True` |
| C 参数提取错 | 工具调了，但 `args` 与 `expected_args` 不一致 | `arg_errors` 非空（如 `order_id=O1002 期望 O1001`） |
| D 草稿质量差 | 意图与工具都对，草稿缺要素或含越权承诺 | 草稿档位 B/C，`DRAFT_RISK` 命中（赔付/承诺/一定…） |

排序原则：按影响面（受影响条数 × 后果严重度）排序，**参考顺序 A → C → B → D**，越权、安全和基础设施故障优先：
A 影响整条链路，修一条顶三条；C 会让结论指向错误事实（查到别人的订单），风险高于缺工具；
B 只影响信息完整度；D 不改变业务动作，但直接影响采纳率与合规，必须在下一版前修完。

## 2. 历史记录：参考实现的一轮运行（provider = scripted，2026-11-03）

> 本节与第3节保留原文所述参考实现的历史叙述。本包没有对应代码、数据库或原始报告，本轮未核验其真实性和作者归属。
> 因此这些数字在当前仓库内不可复现，保留的目的是示范"如何从 trace 落到归因"，而不是充当效果结论。
> 真实模型的效果数据必须等实现完成、Key 到位后按 DEVELOPMENT.md 第 6 章重新产出。

命令：

```bash
python -m app.cli eval --prompt v3 --tag final --provider scripted
```

结果（原文数字，无可复现附件，不得引用为本项目成绩）：24 条中 3 条失败（分类 87.5%、工具 87.5%、参数 87.5%、转人工 91.7%）。

| 用例 | 现象 | 归因 | 根因 | 处置 | 回放 |
| --- | --- | --- | --- | --- | --- |
| EV005 | `refund → other`，缺 `refund_preview` | A 意图识别错 | 离线桩词表未覆盖「超期了还能退吗」的语义，命中兜底分支 | 记入待办：真实模型下观察同类语义；不改桩（改桩=伪造提升） | 未修复 |
| EV014 | `shipping_urge → other`，缺 `check_logistics` | A 意图识别错 | 桩词表缺「什么时候能到」 | 同上 | 未修复 |
| EV018 | `shipping_urge → other`，缺 `check_logistics` | A 意图识别错 | 桩词表缺「今天能发吗」 | 同上 | 未修复 |

**诚实说明**：这 3 条的根因都在 `app/llm/scripted.py` 的关键词表，
而不是 prompt 或工具设计。用改桩的方式把它们「修好」，指标确实会变成 100%，
但那是自己给自己出题自己改答案，对岗位没有任何说服力。因此保留失败、写进报告。

## 3. 历史修复叙述待核验：参数正确率 87.5% → 4.2%

原文将下述事件描述为评估发现的工程缺陷。当前缺少对应附件，不能直接作为本人已修复缺陷的面试证据。

**现象**：同一天第二次跑 `eval`（`--tag final`）时，分类/工具/转人工都不变，
但参数正确率从 87.5% 掉到 4.2%；失败详情却写着
`arg_errors: ["query_order 未被调用"]`，而同一行的工具集合列是 ✅。

**排查**（读 trace，不猜）：

1. `reports/eval_v3_final.md` 显示工具集合正确，说明工具真的被调用了；
2. `sqlite3 runs.db "select step,name,idempotency_key from tool_calls where session_id='…'"` 查到该 run 只有 `create_ticket_draft` 一条记录；
3. 结论：`record_tool_call` 插入失败——它捕获 `IntegrityError` 后静默返回 `False`；
4. 冲突源是 `tool_calls` 上的 `idempotency_key TEXT UNIQUE`（全局唯一），
   而幂等键 = `sha1(ticket_id|tool|args)`，评估用例的 ticket_id 是确定性的
   （`EV001R01`），第二次评估时键必然重复 → 审计行被吞。

**修复**（三处，缺一不可）：

- `app/store/db.py`：`idempotency_key TEXT UNIQUE` → 普通列，改
  `CREATE UNIQUE INDEX idx_tool_calls_idem ON tool_calls(session_id, idempotency_key)`；
- `app/store/db.py:get_cached_result(idem_key, session_id=None)`：查询按 `session_id` 过滤——
  幂等要防的是「同一次运行里的重试」，跨 run 复用缓存会让重跑读到旧结果；
- `app/core/loop.py:_execute_tool`：缓存命中时也落一条审计行（不带幂等键），
  保证 trace 完整、回放不缺步。

**原文所述回放验证，当前未执行**：

```bash
# 目标命令：为两次评估显式使用同一份隔离测试库，保留历史运行库。
python -m app.cli eval --prompt v3 --tag first --provider scripted
python -m app.cli eval --prompt v3 --tag repeat --provider scripted
# DB_PATH在运行前设为隔离路径；当前无实现，命令尚不可执行。
```

修复后两次运行指标完全一致（87.5 / 87.5 / 87.5 / 91.7，采纳率 84.0%），
说明评估可复现；回归测试 `tests/test_loop.py::test_cached_result_not_reused_across_runs`
在原文中被列为该行为的回归证据；当前包未包含此测试，待恢复实现及产物后核验。

**这条的面试价值**：它证明评估不是"跑个分"，而是能抓到静默失败的审计缺陷；
而且修复点在存储层，不在 prompt 层——很多人的迭代只会改提示词。

## 4. 迭代协议（每次改动必走）

```bash
# 1. 改 prompt / 工具 / 策略
# 2. 跑全量，拿到新报告
python -m app.cli eval --prompt v4 --tag cand --provider openai
# 3. 与上一版对比（不退化才算通过）
python scripts/compare_versions.py --old reports/eval_v3_final.json --new-prompt v4
# 4. 失败用例回放，确认不是「换个错法」
python -m app.cli replay --run-id <失败的 run_id> --prompt v4
# 5. 更新本文件的归因表
```

判定标准（写死，避免自我说服）：

- 分类准确率不得下降；单项下降 ≥ 1 条即视为退化；
- 工具/参数正确率不得下降；
- 必转安全案例不得新增漏转，同时报告误转与自动覆盖；首版没有真实动作执行，不能把漏转直接等同于资金生效；
- 成本与 P95 只看趋势，不作为通过门槛（除非超预算）。

## 5. 待真实模型验证的假设（原文标记 [阻塞 B-1]，当前状态待确认）

原文记录当时无可用Key；本轮未检查当前凭证。以下模型假设未有可核验产物，实现后按顺序验证：

| # | 假设 | 验证方式 | 若失败则 |
| --- | --- | --- | --- |
| H1 | v1 → v3 的 few-shot 与判定规则能把分类准确率抬 8pp 以上 | v1/v2/v3 各跑 24 条 | 逐例分析后再判断原因，未提升不能直接排除prompt问题 |
| H2 | 复杂工单（多实体、跨意图）是主要失败源 | 按 simple/complex 分组统计 | 加槽位抽取前置步骤 |
| H3 | 50 条草稿采纳率 ≥ 70% 需显式给「不可承诺清单」 | 对比 v2/v3 的 D 类失败条数 | 把合规词表做成后置校验器 |
| H4 | 单条成本 < ¥0.005 | 报告里的 `avg_cost_cny` | 压缩 system prompt、砍 few-shot |

## 6. 数据来源与标注口径

- **24条确定性用例**（目标`data/eval_cases.jsonl`）：原文称自建，当前未提供文件。原文记录公开语料当时不可达
  （[阻塞 B-2]），故按「4 意图 × 简单/复杂 × 3」矩阵手写，题干 15–120 字，
  每类覆盖：单一诉求 / 带情绪 / 带多实体 / 带时效争议。
- **50 条草稿用例**（`data/drafts_50.jsonl`）：自建，与 24 条不重叠（目标由scripts/check_leakage.py检查；当前文件未提供，不能声称已校验）。
- **标注方式**：每条标注 `intent`、`order_id`、`expected_tools`、`expected_args`、
  `expected_needs_human`；草稿集额外标 `required`（2–3 个必须出现的字面要素，如订单号、退款金额、承运商）。
  标注由脚本作者本人完成，无第二人复核——这是本数据集的最大局限，写在这里而不是藏起来。
- **草稿档位 rubric**：A = 要素齐全可直接发送；B = 缺 1 个要素，人工补一句即可；
  C = 缺 ≥2 个要素或含越权承诺，需重写。人工采纳率=A/已人工复核数，可用率=(A+B)/已人工复核数；自动字面要素检查单独报告。

## 7 证据恢复登记

| 历史主张 | 缺失附件 | 当前状态 |
| --- | --- | --- |
| 24条scripted运行与3条失败 | 对应代码、数据集、逐例报告、run_id及trace | 原文叙述，未核验 |
| 幂等索引缺陷及修复 | 改前改后DDL/代码、两次运行库、回归输出 | 原文叙述，未核验 |
| 草稿采纳率84% | 50条草稿、评分明细、人工评分方法 | 原文叙述，未核验，不当作模型效果 |

恢复附件后补摘要、版本与复现入口。新增实际失败另起记录，不将历史数字抄入新报告。

