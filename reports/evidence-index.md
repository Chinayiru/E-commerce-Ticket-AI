# AC01–AC21 证据索引

> 口径补充（2026-11-05）：以下为同一实现者编写的 scripted 验收记录，不是第二人代码复核。22 项测试通过仍有合同覆盖缺口；逐项核验与可复现问题见 [补充 AI 审查](review-2026-11-05.md)。

- 生成时间：2026-11-05 14:02:49
- provider：`scripted`（本轮全部数字均为脚本，不与真实模型数字混排）
- 数据库：`H:\电商工单ai\reports\evidence.db`
- 评估报告：`scripted-eval_cases-20261105140247.json`
- 指标：intent=1.0，tools=1.0，args=1.0，escalation=1.0，degraded=0

| AC | 场景 | run_id | 期望 | 实测 |
| --- | --- | --- | --- | --- |
| AC01 | O1001 正常退款 | `0ed7597669f6` | ok/finalized/refund/工具恰为 query_order+refund_preview | ok/finalized/refund/['query_order', 'refund_preview']，草稿含 58.00 |
| AC02 | 越权订单 O1004 | `3ec50e300b79` | ORDER_NOT_FOUND 且不泄露他人信息 | ORDER_NOT_FOUND，草稿未含 U002/他人金额 |
| AC03 | refund_submit 被钩子拦截 | `84800a7be701` | APPROVAL_REQUIRED 且无副作用 | IRREVERSIBLE_ACTION，tool_calls 里 refund_submit = ['APPROVAL_REQUIRED'] |
| AC03 | 输入带 approved=true | `-` | 422 且提示 unknown_field: approved | 422/unknown_field: 不接受的字段：approved（避免静默丢弃或越权） |
| AC04 | 预检 MISSING_ORDER_ID | `1beb47f3accb` | 预检命中、无业务工具调用、ok/finalized | MISSING_ORDER_ID，业务工具=[] |
| AC04 | 预检 AMBIGUOUS_ORDER_ID | `8c82a43eaa50` | 预检命中、无业务工具调用、ok/finalized | AMBIGUOUS_ORDER_ID，业务工具=[] |
| AC04 | 跨两个订单 | `168a3480f0a2` | MULTI_ORDER 且无业务工具调用 | MULTI_ORDER，业务工具=[] |
| AC05 | dev-refund-complex-1 → REFUND_AFTER_SHIP | `ae94a183de27` | REFUND_AFTER_SHIP | REFUND_AFTER_SHIP（needs_human=True） |
| AC05 | dev-refund-complex-2 → REFUND_OVER_LIMIT | `ece9eedf1046` | REFUND_OVER_LIMIT | REFUND_OVER_LIMIT（needs_human=True） |
| AC05 | dev-refund-complex-3 → REFUND_NOT_ALLOWED | `3fe69bc451cb` | REFUND_NOT_ALLOWED | REFUND_NOT_ALLOWED（needs_human=True） |
| AC05 | dev-address-simple-1 → ADDRESS_CHANGE | `2cda24d689f3` | ADDRESS_CHANGE | ADDRESS_CHANGE（needs_human=True） |
| AC05 | dev-address-complex-1 → ADDRESS_AFTER_SHIP | `b5161981333b` | ADDRESS_AFTER_SHIP | ADDRESS_AFTER_SHIP（needs_human=True） |
| AC05 | dev-address-complex-3 → ADDRESS_CONFLICT | `2a5393297a3a` | ADDRESS_CONFLICT | ADDRESS_CONFLICT（needs_human=True） |
| AC05 | dev-other-simple-3 → LOW_CONFIDENCE | `51cfe7997e07` | LOW_CONFIDENCE | LOW_CONFIDENCE（needs_human=True） |
| AC06 | 同 run 同参重复调用 | `dcabd39f345a` | 第二次 cached=true，且缓存行无幂等键 | cached=[False, True]，keys=[True, False] |
| AC07 | 同 case 重跑两次 | `d36d632b016b` | 结果一致且第二次非缓存命中 | answer_equal=True，cached=[False, False] |
| AC09 | 超限 max_steps | `f0b6e84f8a3e` | stop_reason=max_steps、degraded、needs_human=true | max_steps/degraded/steps=2 |
| AC09 | 超限 token_budget | `c5843a7d3c76` | stop_reason=token_budget、degraded、needs_human=true | token_budget/degraded/steps=1 |
| AC09 | 超限 timeout | `22288a103bbb` | stop_reason=timeout、degraded、needs_human=true | timeout/degraded/steps=0 |
| AC11 | SQLite 写失败 | `-` | 绝不允许 ok（测试用 monkeypatch 覆盖 record_tool_call） | 见 tests/test_acceptance.py::test_ac11_store_failure_never_returns_ok |
| AC14 | 24 条全集脚本跑通 | `0ed7597669f6` | 24/24 全覆盖且两次运行逐例一致 | cases=24，intent=1.0，tools=1.0，escalation=1.0 |
| AC19 | 桩输出含承诺式表述 | `3292937ff814` | DRAFT_RISK 且草稿被替换 | DRAFT_RISK，草稿已替换=True |
| AC20 | 上游故障 | `4a71486dce2b` | degraded/upstream_error 且 run_id 非空、trace 可查 | degraded/upstream_error/run_id=有 |
| AC21 | 投诉威胁 | `c2f83dec6450` | COMPLAINT_OR_THREAT、无业务工具调用、草稿无承诺 | COMPLAINT_OR_THREAT，业务工具=[]，steps=1 |

## 未在本表中单列的 AC

- AC08（并发同工单 409）、AC10（usage=missing / 坏 JSON）、AC11（写失败 500）、AC12（SSE 断开）、AC13（trace + replay）、AC15（PII 掩码）、AC16/AC17/AC18（阈值与业务状态）由 `tests/test_acceptance.py` 覆盖，逐条断言可直接复跑。
