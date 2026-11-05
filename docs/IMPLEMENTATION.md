# 实现规格与开发验收

日期：2026-11-04。状态：待实现。本文件提供可编码的接口、数据流和验收场景，不代表已经完成开发。
范围依据 `DESIGN.md` v1.4；工作顺序依据 `DEVELOPMENT.md`。文中的命令都是实现完成后的目标命令。

## 1 当前起点与最小交付

当前目录只有 Markdown 文档，没有 `app/`、`data/`、`tests/`、`reports/` 或依赖清单。
第一版的目标是可演示的一条工单处理链路：输入 → 模型选工具 → 读取合成订单 → 生成草稿 → 策略复核 → 持久化。
真实模型、离线桩、历史记录三个来源分别标记，不能合并计算效果。

| 阶段 | 必须形成的产物 | 完成依据 |
| --- | --- | --- |
| M0 契约与数据 | schemas、8条合成订单（含200元与售后期边界样本）、Provider协议 | 类型、金额、日期、订单归属规则明确；24条用例的每个分支都有订单可用 |
| M1 离线链路 | 注册表、只读工具、执行循环、CLI | 四类工单均产生结构化结果；异常可定位 |
| M2 运行记录 | SQLite四表、钩子、trace | 每次模型请求及工具尝试可追查，跨run无缓存污染 |
| M3 服务入口 | 同步HTTP、SSE | 与CLI共用核心；断开和超时不遗留运行状态 |
| M4 模型与评估 | 真实Provider、数据文件、报告生成器 | 有模型元数据、逐例结果、成本来源和失败案例 |
| M5 面试演示 | 录屏、证据索引、简历草稿 | 每个技术主张能对应代码、命令或报告 |

工期沿用开发文档的个人计划作为安排参考，完成状态以产物为准。没有模型Key仍可推进M0至M3；不得填写真实模型效果。

## 2 契约先行

建议先在 `app/schemas.py` 定义下面的结构，使用 Pydantic v2 且 `extra="forbid"`。

| 结构 | 必要字段 | 校验及来源 |
| --- | --- | --- |
| TicketIn | ticket_id、user_id、text、order_id? | 沿用DESIGN 6.1；user_id在本地演示中来自调用者，不代表生产身份认证 |
| ToolContext | run_id、user_id、deadline、now、store | 由程序构造，不进入模型工具参数；不允许模型传approved |
| ToolResult | status、data?、error? | status为ok/error；成功只含data，失败含code/message/hint |
| ModelDecision | tool_calls或final | 两者互斥；tool_calls每次最多3个，并按返回顺序串行执行 |
| FinalAnswer | intent、confidence、slots、reply_draft、needs_human、escalate_reason、used_tools | intent封闭四类，confidence在0至1之间；工具事实、转人工和used_tools由程序复核 |
| Usage | input_tokens、output_tokens、total_tokens、cost_cny | 另记录来源reported/estimated/missing；缺计量时成本为null |
| RunResult | run_id?、status、stop_reason、steps、answer、tool_calls、usage、latency_ms、prompt_version、note | 未建run的拒绝结果run_id=null；已建run正常返回均可查trace |

模型最终输出示意，金额字段采用整数分：

```json
{
  "intent": "refund",
  "confidence": 0.94,
  "slots": {"order_id": "O1001"},
  "reply_draft": "订单O1001的退款条件已核对，预计可退金额为58.00元。本草稿不代表退款已经执行。",
  "needs_human": false,
  "escalate_reason": null,
  "used_tools": ["query_order", "refund_preview"]
}
```

`needs_human=false`表示草稿可供客服复核，不代表可自行执行退款。模型的confidence是自报值，不能解释为校准后的正确概率。
`slots`仅允许已定义字段；订单号与输入、已授权工具结果不一致时，不接受模型生成的金额或处理结论。

## 3 合成业务数据与授权边界

订单文件使用JSON数组，只包含合成信息。业务查询读文件；四张SQLite表仅记录Agent运行。

```json
[
  {"order_id":"O1001","user_id":"U001","amount_cents":5800,"status":"paid","paid_at":"2026-11-01T10:00:00+08:00","delivered_at":null,"carrier":null,"tracking_id":null},
  {"order_id":"O1002","user_id":"U001","amount_cents":25800,"status":"shipped","paid_at":"2026-11-01T10:00:00+08:00","delivered_at":null,"carrier":"合成快递","tracking_id":"MOCK002"},
  {"order_id":"O1003","user_id":"U001","amount_cents":9900,"status":"delivered","paid_at":"2026-10-01T10:00:00+08:00","delivered_at":"2026-10-05T12:00:00+08:00","carrier":"合成快递","tracking_id":"MOCK003"},
  {"order_id":"O1004","user_id":"U002","amount_cents":8800,"status":"paid","paid_at":"2026-11-01T10:00:00+08:00","delivered_at":null,"carrier":null,"tracking_id":null},
  {"order_id":"O1005","user_id":"U001","amount_cents":20000,"status":"paid","paid_at":"2026-11-02T10:00:00+08:00","delivered_at":null,"carrier":null,"tracking_id":null},
  {"order_id":"O1006","user_id":"U001","amount_cents":25000,"status":"paid","paid_at":"2026-11-02T10:00:00+08:00","delivered_at":null,"carrier":null,"tracking_id":null},
  {"order_id":"O1007","user_id":"U001","amount_cents":12900,"status":"delivered","paid_at":"2026-10-15T10:00:00+08:00","delivered_at":"2026-10-28T12:00:00+08:00","carrier":"合成快递","tracking_id":"MOCK007"},
  {"order_id":"O1008","user_id":"U001","amount_cents":39900,"status":"shipped","paid_at":"2026-10-30T10:00:00+08:00","delivered_at":null,"carrier":"合成快递","tracking_id":"MOCK008"}
]
```

演示时间设为 `2026-11-04T12:00:00+08:00`；售后期采用可配置的7天演示规则，按签收时刻计算。
这不是任何电商平台的真实规则。未发货且金额不超过200元时可以生成不转人工的退款预览草稿。
已发货、大额、超期等仍按策略转人工。恰好200元不触发“超过200元”；恰好到期时刻仍在期内，超过才算超期。

**订单 × 状态 × 可触发分支**（订单是JSON文件，不是第五张表；加订单不改表结构）

| 订单 | 归属 | 金额 | 状态 | 签收时间 | 用途（可触发分支） |
| --- | --- | --- | --- | --- | --- |
| O1001 | U001 | 58.00 | paid | — | 未发货小额：退款不转人工、`ADDRESS_CHANGE`、`NOT_SHIPPED` |
| O1002 | U001 | 258.00 | shipped | — | 已发货：`REFUND_AFTER_SHIP`、`ADDRESS_AFTER_SHIP`、物流可查 |
| O1003 | U001 | 99.00 | delivered | 2026-10-05 12:00 | 超期（签收已 30 天）：`REFUND_NOT_ALLOWED` |
| O1004 | U002 | 88.00 | paid | — | 越权：U001 查询一律 `ORDER_NOT_FOUND`，不泄露金额/状态/物流 |
| O1005 | U001 | 200.00 | paid | — | 边界：恰好 200 元，不触发 `REFUND_OVER_LIMIT` |
| O1006 | U001 | 250.00 | paid | — | 未发货大额：`REFUND_OVER_LIMIT` |
| O1007 | U001 | 129.00 | delivered | 2026-10-28 12:00 | 边界：恰好 7 天，仍在售后期内，退款不转人工 |
| O1008 | U001 | 399.00 | shipped | — | 优先级：已发货（5）与超限（6）同时命中，取 `REFUND_AFTER_SHIP` |

四个分支无法用同一个订单表达：未发货大额、恰好 200 元、售后期恰好到期、优先级叠加。缺少任一订单，24 条用例里对应条目的 `expected_needs_human` 就无法成立——这是数据先于用例的原因。

**24 条用例的订单分配**（每单最多出现 3 次，避免模型记住单一订单）：

| 意图 | 简单 3 条 | 复杂 3 条 |
| --- | --- | --- |
| refund | O1001、O1005、O1007 | O1002 已发货 / O1003 超期 / O1006 未发货大额 |
| address_change | O1001、O1005、O1007（均未发货 → `ADDRESS_CHANGE`） | O1002、O1008（已发货 → `ADDRESS_AFTER_SHIP`）、O1006 正文两处互相矛盾的地址 → `ADDRESS_CONFLICT` |
| shipping_urge | O1001、O1005、O1006（`NOT_SHIPPED`） | O1002、O1008（有物流）、O1003（显示签收但未收到） |
| other | 无订单号 / 格式合法但库中不存在的 O9999（→ `ORDER_NOT_FOUND`，走工具而非缺号预检） / 闲聊 | O1004 越权（→ `ORDER_NOT_FOUND`，不泄露他人订单）、跨订单冲突（→ `MULTI_ORDER`）、投诉威胁（→ `COMPLAINT_OR_THREAT`） |

分配是约束不是清单：允许替换同类订单，但不能改变每条用例要触发的分支。

每个读取工具都必须通过同一订单访问检查：订单存在且 `order.user_id == context.user_id`。
不存在与不属于当前用户，对外统一返回 `ORDER_NOT_FOUND`，不泄露他人订单信息；内部使用非敏感诊断类别区分。
禁止仅凭工单中出现订单号就读取；禁止让模型提供或覆盖ToolContext中的user_id。
不引入认证系统的本地演示仅绑定 `127.0.0.1`，不声称具备生产级多用户访问控制。

缺订单号时返回请求补充信息的草稿，`needs_human=true`、`escalate_reason=MISSING_ORDER_ID`，本run结束。
订单预检按 DESIGN 9.1 的 0a→0d 顺序执行，位置固定在第一轮响应解析出 `intent` 与订单槽位之后、任何工具请求交给注册表之前：同一响应里的工具请求先暂存、不执行，也不写 `tool_calls`；命中预检则直接写固定安全草稿并收尾（`status=ok`、`stop_reason=finalized`、`steps` 为已完成的模型请求数、`usage` 记该请求实际计量）。判定口径：投诉或法律威胁 → `COMPLAINT_OR_THREAT`；明确要求同时处理两个及以上订单 → `MULTI_ORDER`；存在订单号候选但互相冲突或无法唯一确定（正文多个订单号且未表达批量，或结构化 order_id 与正文候选冲突）→ `AMBIGUOUS_ORDER_ID`；`refund` / `address_change` / `shipping_urge` 的正文与结构化输入都没有有效订单号候选 → `MISSING_ORDER_ID`；`other` 不因缺号命中该原因。不得猜测选择或逐个试单。
被暂存的工具请求保留在 `turns` 的原始响应里，`tool_calls` 保持空数组；这与执行到钩子才被拦截、会留下 `APPROVAL_REQUIRED` 记录的调用是两回事，统计时不得混算。
用户补充信息后发起新run，不复用旧run继续对话。这些reason属于策略原因，不新增工具错误码。

## 4 六个工具的具体合同

全部注册六个工具。模型可见前三个只读工具和两个拦截演示工具；`create_ticket_draft`是程序内部工具，在最终校验后调用。
业务事实在工具结果中提供，模型不得自行编造退款额、承运商或已完成操作。

| 工具 | 模型可传参数 | 成功data | 失败或拦截 |
| --- | --- | --- | --- |
| query_order | order_id:str | order_id、status、amount_cents、paid_at、delivered_at | INVALID_ARGS、ORDER_NOT_FOUND |
| check_logistics | order_id:str | order_id、carrier、tracking_id、status | 未发货返回NOT_SHIPPED；其余同上 |
| refund_preview | order_id:str | allowed、amount_cents、policy_reason、policy_version | 超期返回REFUND_NOT_ALLOWED；已发货的预览不等于允许执行 |
| create_ticket_draft | validated_answer:FinalAnswer，仅程序构造 | run_id、draft_saved:true | Store写入失败向进程边界传播，不伪装成成功 |
| refund_submit | order_id:str | 第一版没有成功执行分支 | 钩子总是返回APPROVAL_REQUIRED；不得改订单或余额 |
| address_change | order_id:str、new_address:str | 第一版没有成功执行分支 | 同上；地址先脱敏再持久化 |

`approved`不出现在任何模型或HTTP输入Schema中。工具调用严格先做字段白名单与类型校验，再执行前置钩子：包含未知字段（如 `approved=true`）返回 `INVALID_ARGS`；合法参数调用退款或改地址工具时，钩子返回 `APPROVAL_REQUIRED`。第一版没有审批接口，没有真实动作后端；程序不得把布尔值当作授权凭证。
未来增加人工审批需要单独设计身份、权限、请求摘要绑定、防重放和动作幂等，本次不实现。

注册表通过类型标注生成JSON Schema，首版只支持str/int/bool/可选字段及明确的嵌套模型；
遇到未支持类型应在启动时失败，不生成看似可用的Schema。未知工具返回TOOL_UNAVAILABLE，未知参数返回INVALID_ARGS。
工具业务错误结构化返回；程序缺陷不在日志中静默吞掉。持久化失败必须终止该次运行，返回HTTP 500。

## 5 执行循环和停止语义

step定义为一次Provider请求尝试，包括上游重试和格式修复。最多6次；每次模型返回最多3个工具调用。
工具尝试另外用 `tool_call_id` 计数，避免把模型步数与工具次数混为一谈。

```text
校验输入 → 生成run_id → 原子登记running
deadline = monotonic() + WALL_CLOCK_S
while steps < MAX_STEPS:
    检查剩余时间、累计usage和下一次输出额度
    构造脱敏消息；保存请求快照和prompt摘要
    steps += 1
    用剩余时间调用Provider
    保存响应、usage来源与耗时
    有工具调用：逐个参数校验 → 前置钩子 → 单run缓存 → 调用 → 审计 → 后置钩子
    有最终结果：解析 → 事实核对 → policy覆盖 → 保存草稿与终态 → 返回
    非法结果：有剩余步数和额度时最多修复一次
达到上限：生成固定降级草稿 → needs_human=true → 保存终态 → 返回
```

`time.monotonic()`测经过时间，`settings.now()`判断售后期，两者不能互换。
同步函数在外层检查elapsed不能中断正在悬挂的网络；Provider应使用异步httpx，并以剩余deadline包裹请求及重试。
连接、读取超时都不得超过剩余时间。取消需要向外传播，不能捕获取消后继续执行。

6000 token是应用预算目标，当前白名单没有通用精确tokenizer。首版须：

1. 每次请求先估算完整消息和工具Schema的输入占用，再限制最大输出；输入估计过大时先折叠或停止。
2. 返回后累计供应商usage，不能只计算最后一次响应。重试可能计费但无usage时记录missing。
3. 无usage的成本写null，另列估计，不能填0或混入真实成本均值。
4. 兼容供应商的计量、缓存计价可能不同，因此不承诺精确的调用前6000硬限制或绝对费用上限。

最多一次上游重试仅用于429、连接失败和部分5xx；不重试401、403、参数错误。
退避时间也消耗全局deadline。重试后仍失败时 `stop_reason=upstream_error`，超时优先记timeout。
最终解析允许去掉单层Markdown代码围栏，随后严格校验JSON；不得用eval或从混杂文本中猜取一段JSON。

## 6 策略执行与草稿真实性

策略层读取已验证的订单/工具事实、系统运行状态和草稿，输出转人工判定及全部命中原因。
`escalate_reason`保存主原因，完整原因保存在运行元数据中。优先级沿用DESIGN 9.1，并在订单查询前处理缺失/歧义订单。
投诉、法律威胁、跨订单诉求单独命中 `COMPLAINT_OR_THREAT`、`MULTI_ORDER`，不能依赖模型confidence兜底。

若未发货调用物流工具返回NOT_SHIPPED，这是可预期业务状态，不累计为连续技术失败。
无依据的“已退款”“已改地址”“保证明天到达”必须被替换成固定、无承诺的待核实草稿并转人工；
只把needs_human设为true却保留错误承诺，仍判为失败。
关键词规则可作兜底，但“不会保证到账”等否定句也可能误报；需记录误报并用样例持续复核，不能宣称正则已经解决合规。

所有路径中动作后端均不存在。漏转人工会造成草稿风险；实际不可逆操作的阻断由独立钩子保障，不能将两者混成同一指标。

### 6.1 提示词契约（段落与版本）

提示词正文属于代码（`app/core/prompts.py`），这里只约束**必须包含什么、禁止包含什么**，防止实现时把规则写重或写偏。

| 段落 | 必须包含 | 漏写的后果 |
| --- | --- | --- |
| 角色与范围 | 只处理电商售后工单；只有四类意图；不闲聊、不承诺时效 | 模型自由发挥，`other` 泛滥 |
| 输出契约 | 单一 JSON、字段与类型、禁止围栏外文本、缺字段视为无效 | 解析失败率上升，修复步吃掉步数预算 |
| 意图判别 | 四类定义 + `other` 的边界（投诉、跨订单归策略层） | 相近意图混淆 |
| 工具使用 | 何时必须查订单/物流/退款；一次最多 3 个调用；参数只能来自输入或工具结果 | 编造订单号与金额 |
| 事实与合规 | 不得声称已退款/已改地址/保证到货；金额只来自工具；无依据时给待核实草稿 | 草稿含越权承诺，D 类失败 |
| 缺信息处理 | 缺订单号不猜号、不调用查询工具；补号草稿由预检程序写定并覆盖模型输出（见第 3 章） | 用错订单，C 类失败且风险最高 |

**禁止写进提示词**（写了算缺陷，不是风格问题）：

- 策略阈值：200 元、7 天售后期、失败次数。属于策略层常量（DESIGN 9.1），写进 prompt 会产生"模型说不转、policy 说必须转"的双份真值。
- `approval` / `approved`：模型永远看不到审批概念，也不可能获得授权。
- 24 条与 50 条的题干或近义改写：脚本只能拦字面重复与编号，语义改写靠写作纪律。
- 真实订单号与金额的组合示例：few-shot 里出现 `O1001` + 58 元，等于把答案写进提示词。

**版本差异必须可解释**，只改措辞不算一版：

| 版本 | 相对上一版增加 | 预期提升 | 不该期待 |
| --- | --- | --- | --- |
| v1 | 角色、输出契约、四类意图定义 | 能跑通，分类是下限 | 工具顺序、参数正确 |
| v2 | 工具使用规则 + 事实合规清单 + 缺信息处理 | 工具集合与参数正确率 | 200 元/售后期这类边界分支 |
| v3 | 判定规则措辞 + 3 条 few-shot（退款/改地址/催发货各一）+ 一次 JSON 修复提示 | 复杂用例与草稿质量 | 超出策略层兜底的能力 |

few-shot 选取原则：订单号一律用占位（如 `O9xxx`），每条只覆盖一个易错点，单条不超过 80 字，且不得从 24/50 条改写。

## 7 四张表和存储事务

`run_id == sessions.id`。下表为在原有关键列上的必要补充，建表时统一纳入，不增加第五张业务表。

| 表 | 补充列或约束 | 目的 |
| --- | --- | --- |
| sessions | created_at、updated_at、result_json、model_config_json、dataset_hash?、source_run_id? | 保存终态、模型配置、数据版本及回放来源 |
| turns | idx、role、content、message_json、usage_json、request_hash | 保留模型消息协议与计量；UNIQUE(session_id,idx) |
| tool_calls | call_id、cached、approval_required、attempt_idx | 区分工具尝试；UNIQUE(session_id,call_id) |
| evaluations | report_id、dataset_kind、expected_json、actual_json、error_json | 两类数据集区分，逐例结果和异常可核查 |

关键SQL目标：

```sql
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
CREATE UNIQUE INDEX idx_active_ticket
  ON sessions(user_id, ticket_id) WHERE status = 'running';
CREATE UNIQUE INDEX idx_call_idempotency
  ON tool_calls(session_id, idempotency_key);
```

登记run使用短事务，靠唯一索引防止同一用户同一工单同时进入两次，不能只做“先查再插”。
只将这个明确的唯一约束冲突映射为409，其他IntegrityError必须传播。
模型调用和网络等待不得放在SQLite写事务中。单进程、有限并发是首版目标；SQLite可以并发读，写入需要串行，不能描述为“无并发能力”。
原子保存最终草稿和sessions终态；失败时不返回成功。额外JSON日志写失败可以降级警告，但数据库trace写失败必须中止。
进程重启后，将遗留running标为degraded并记录upstream_error及process_interrupted说明，不自动继续或重新执行动作。

幂等结果只在单run内复用。成功且未拦截的首次调用保存幂等键；缓存命中仍新增call_id不同、idempotency_key为NULL的审计行。
失败和被拦截的调用不作为成功缓存。重复调用可能有多次审计，但首次实际执行只有一次。
`create_ticket_draft`同run只保存一次已验证结果，异常重试不生成新的工单草稿。

## 8 脱敏、trace与两种回放

本地数据全部使用合成订单；模型消息、工具参数、结果、草稿、HTTP错误、审计日志均经过相同脱敏入口。
保留订单号用于合成数据回放；手机号和地址使用稳定占位符，不打印Key、Authorization或完整供应商错误体。
API Key只从环境读取，`.env`不进版本库。环境配置若使用.env文件，启动命令显式加载；仅复制.env并不会自动生效。

| 模式 | 输入 | 输出 | 能说明什么 |
| --- | --- | --- | --- |
| trace | run_id | 原运行已保存消息、工具尝试和终态 | 历史发生了什么；不产生模型费用 |
| replay --mode frozen | run_id、新prompt | 使用原工具快照生成的新run | 控制工具事实后比较模型/提示词差异 |
| replay --mode fresh | run_id、新prompt | 使用当前合成订单生成的新run | 当前数据下结果如何变化，可能同时受数据变化影响 |

新run保存source_run_id。frozen模式遇到原trace没有的工具或参数，返回TOOL_UNAVAILABLE并标记快照缺失，不偷偷查新数据。
原消息中已脱敏的信息无法完整恢复，回放只承诺对保存的合成/脱敏输入重建，不能声称无损恢复真实隐私数据。
scripted或冻结的完整响应可以确定性复现；重新调用真实模型只要求实验条件可追溯，不能保证输出或得分完全一致。

## 9 API与SSE落地合同

| 入口 | 成功 | 失败 |
| --- | --- | --- |
| POST /v1/tickets | RunResult，包含正常转人工的200 | 422输入错误、409重复、503上游不可用（响应体仍是RunResult）、500内部持久化错误 |
| GET /v1/runs/{run_id} | 脱敏trace | 404不存在 |
| POST /v1/tickets/stream | text/event-stream | 发响应头前同同步HTTP语义；发头后通过error事件表达 |

timeout、max_steps、token_budget、invalid_output产生可用的降级RunResult，HTTP 200且status=degraded。
`upstream_error` 是唯一例外：重试耗尽或鉴权失败时返回 503，但响应体仍是完整 RunResult（`status=degraded`、`stop_reason=upstream_error`、`run_id` 非空），运行记录已落库、可查 trace。语义区别只有一条：503 表示"上游故障、可重试"，200 表示"这次运行已正常收尾（含降级和转人工）"。不得出现"503 但 body 是空错误串"的写法，那会让 run 变成不可追踪的黑洞。
SSE第一版提供步骤和工具事件，不假定实现逐token文本流。每个事件为 `event: 类型`、`data: 单行JSON`，空行结束。
终态只发送一次final或error；error含run_id、code、message和已有降级结果，不再跟随final。
客户端断开时取消Provider请求，保存degraded/timeout及client_disconnected说明，不发送已不可达的终态事件。
首版不支持Last-Event-ID续传；重连查询run的trace，不隐式再次创建工单。

## 10 评估数据、指标和版本比较

24条开发回归集保持4意图×2复杂度×3条，允许用于提示词调试，但必须标记 `split=development`。
50条草稿集是独立任务集；如果也用于调参，就不能称为独立留出集。去除完全重复题干不能证明语义没有泄漏。
后续需独立小样本结果时，按 BLIND_EVAL.md 由独立流程另出 12 条（4 意图 × 3），独立复核后由外部保管方封存并运行一次；先冻结候选与评分规则。当前旧 holdout 已由同一实现者生成、阅读并运行，仅作历史/回归资料，不再作为独立泛化证据。

单条JSONL格式示意（三条：正常、策略升级、缺信息；只示范标注粒度，不代表24条数据文件已经建立）：

```json
{"case_id":"EV001R01","split":"development","user_id":"U001","text":"请帮我核对订单O1001，我买错了需要退款。","intent":"refund","order_id":"O1001","expected_tools":["query_order","refund_preview"],"expected_args":{"query_order":{"order_id":"O1001"},"refund_preview":{"order_id":"O1001"}},"expected_needs_human":false,"expected_reason":null}
{"case_id":"EV004R01","split":"development","user_id":"U001","text":"订单O1002昨天显示已发货，我现在不要了必须退款，已经等了三天没人处理，今天必须给个说法。","intent":"refund","order_id":"O1002","expected_tools":["query_order","refund_preview"],"expected_args":{"query_order":{"order_id":"O1002"},"refund_preview":{"order_id":"O1002"}},"expected_needs_human":true,"expected_reason":"REFUND_AFTER_SHIP"}
{"case_id":"EV024R01","split":"development","user_id":"U001","text":"我要退款，快点处理。","intent":"refund","order_id":null,"expected_tools":[],"expected_args":{},"expected_needs_human":true,"expected_reason":"MISSING_ORDER_ID"}
```

标注粒度（三条分别示范的正是这三件事）：

1. **`expected_tools` 只列业务工具**，内部 `create_ticket_draft` 不参与比较；缺号样例是空数组，表示"不该调用任何查询工具"。
2. **`expected_args` 只写期望工具的参数子集**，不要求模型补全未用到的字段；订单号规范化后比较，地址等字符串不统一大小写，金额用整数分。
3. **`expected_reason` 是可空字段**，只在与 `expected_needs_human=true` 配对时填写；它把"转人工"从布尔值升级为可核对的策略原因，AC05/AC16/AC17 的断言依赖它。
4. 历史数据的 `split` 仍保留原值，但旧 `holdout` 已暴露，不因字段名而恢复独立性。新 12 条使用 BLIND_AUTHOR_CONTRACT.md 的独立格式和 scripts/blind_eval.py 流程，保管在仓库外，不进入原数据生成器或日常验收。

每个报告至少保存dataset_hash、mock_data_hash、prompt_hash、配置摘要、运行时间、provider、model、DEMO_NOW、逐例run_id。
仓库存在Git时保存commit；没有Git时保存代码文件摘要。不要仅用v1/v2名称识别一次实验。

| 指标 | 必须说明的口径 |
| --- | --- |
| 分类正确率 | 正确条数/有效总样本，同时列失败条数 |
| 工具集合正确率 | 只比较业务工具；排除内部create_ticket_draft；允许的缓存重试不改变集合，但调用次数另报 |
| 参数正确率 | 每个期望工具至少一次有效匹配，且所有实际尝试不得出现越权/错误订单；不能只取一条碰巧正确的调用 |
| 转人工判定 | 给出TP/FP/FN/TN及FN、误转率；全部转人工不能被当作优化成功 |
| 草稿自动要素通过率 | 字面要素及风险词检查，仅是自动代理指标 |
| 人工草稿采纳率 | 人工A档/已复核数；注明单人或双人、评分理由；没有人工评分就写待实测 |
| 模型成本 | usage完整且价格有来源的总成本/对应样本数；失败调用也计入；缺usage数量单列 |
| P95 | 端到端毫秒升序，取ceil(0.95*n)位置，n=24时取第23个；同时报告n、冷启动和超时样本 |

价格以每百万token单价配置：单次美元成本=(输入token×PRICE_IN+输出token×PRICE_OUT)/1,000,000，再乘汇率。
单价、币种、汇率、计价日期和是否估算随报告保存；文档默认值不是当前供应商报价。

离线桩连跑两次应一致。真实模型按相同配置重复实验时保存每次结果，报告波动与逐例变化。
“少一条就拒绝”适合作为冻结离线回归门槛；真实模型候选的差异需要复跑定位，不能把采样噪声直接等同于代码退化。
不得为了减少FN将所有工单都转人工；额外报告自动草稿覆盖率和误转变化。

失败归因保留A/B/C/D用于模型和业务链路，新增运行故障台账记录存储、超时、计量缺失等问题。
没有trace的失败仍计入失败数，并标记evidence_missing；不得因难以定位而从分母中删除。

## 11 必做验收场景

以下是合同要求，不等同于当前测试已覆盖全部要求。现有 22 项测试重跑通过；补充 AI 审查已逐项记录 AC01–AC21 的覆盖缺口，并复现未被断言覆盖的缺陷，见 `reports/review-2026-11-05.md`。

| ID | 场景 | 触发命令（目标接口，待实现） | 观察字段 | 期望值 |
| --- | --- | --- | --- | --- |
| AC01 | O1001 正常退款 | `cli run --text "订单O1001买错了要退款" --order-id O1001 --user-id U001 --ticket-id AC01A --provider scripted` | `status` / `stop_reason` / `answer.intent` / `needs_human` / `tool_calls` | `ok` / `finalized` / `refund` / `false` / 恰为 `{query_order, refund_preview}`；草稿含 58.00；mock 订单与余额无写操作 |
| AC02 | U001 查 U002 的 O1004 | 同上，`--order-id O1004` | `tool_calls[].error_code` / `needs_human` / `escalate_reason` | `ORDER_NOT_FOUND` / `true` / `ORDER_NOT_FOUND`；响应与 trace 中不出现他人金额、状态、运单号 |
| AC03 | 非法授权字段与动作拦截 | 桩尝试以 `approved=true` 调用动作工具；另以合法参数调用 `refund_submit`、`address_change` | `tool_calls[].error_code` / mock副作用 | 非法字段在校验阶段返回 `INVALID_ARGS`；合法调用在钩子阶段返回 `APPROVAL_REQUIRED`；无执行分支、订单或余额无写操作 |
| AC04 | 缺号 / 歧义 / 明确跨订单 | `--text "我要退款"`；`--text "O1001还是O1002？我要退"`；`--text "O1001和O1002都要退"` | `escalate_reason` / `tool_calls` / `status` | 分别为 `MISSING_ORDER_ID`、`AMBIGUOUS_ORDER_ID`、`MULTI_ORDER`；三者均 `tool_calls=[]`、`status=ok`、`stop_reason=finalized`，不调用任何订单工具 |
| AC05 | 策略分支矩阵 | 依次用 O1002 / O1006 / O1003 退款，O1001 / O1002 改地址，O1006 提交两处互相矛盾的地址，再提交无关咨询 | `escalate_reason` | `REFUND_AFTER_SHIP` / `REFUND_OVER_LIMIT` / `REFUND_NOT_ALLOWED` / `ADDRESS_CHANGE` / `ADDRESS_AFTER_SHIP` / `ADDRESS_CONFLICT` / `LOW_CONFIDENCE`；七条均有草稿落库、无业务写操作 |
| AC06 | 同 run 重复同参数 | 桩强制两次 `query_order` 同参 | `tool_calls[].cached` | 第二次 `true`，审计行两条，缓存行 `idempotency_key` 为空 |
| AC07 | 相同 case 重跑两次 | `cli eval --prompt v3 --tag a/b`（隔离 DB） | 两次 `tool_calls` 条数与 `ok` | 完全一致；第二次不得是缓存命中 |
| AC08 | 并发同 user+ticket | `serve` 后并发两个 `POST /v1/tickets` | HTTP 码 / `sessions.status` | 一条 200、一条 409；`running` 恰 1 条；其他 `IntegrityError` 不被误判为重复 |
| AC09 | 三类停止 | 桩：死循环调工具 / 输出超预算 / 挂起不返回 | `stop_reason` | 分别 `max_steps` / `token_budget` / `timeout`；三者 `needs_human=true` 且有固定降级草稿 |
| AC10 | 缺计量 / 坏 JSON | 桩返回无 usage；桩返回非 JSON | `usage.source` / `cost_cny` / `stop_reason` | 缺计量 `missing` 且成本 `null`，均值剔除该样本；坏 JSON 修复一次后 `invalid_output` |
| AC11 | SQLite 写入失败 | 只读目录或注入抛错的 store | HTTP 码 / `status` | 500 或 SSE `error`；绝不返回 `ok` |
| AC12 | SSE 中途断开 | `serve` 后 curl 流式请求中途 kill | `stop_reason` / `note` | `timeout` + `client_disconnected`；无残留 `running` |
| AC13 | trace 与两种 replay | `cli trace --run-id X`；`replay --mode frozen` 与 `--mode fresh` | 原 trace / 新 run `source_run_id` | 原 trace 不变；新 run 关联 X；frozen 缺快照 → `TOOL_UNAVAILABLE` |
| AC14 | 全集两次 | `cli eval --provider scripted` ×2 | 逐条指标 | 桩：两次逐条相等；真实模型：报告逐次波动，不合并成单值 |
| AC15 | 手机号 / 地址 | 输入与工具结果均含敏感信息 | `turns` / `tool_calls` / 审计日志 / 草稿 | 全部掩码；全文检索不到 11 位连续数字 |
| AC16 | 200 元边界 | O1005 与 O1006 各跑一次退款 | `needs_human` / `escalate_reason` | O1005（恰好 200）不命中超限；O1006（250）命中 `REFUND_OVER_LIMIT` |
| AC17 | 售后期边界 | O1007 与 O1003 各跑一次退款 | `needs_human` / `escalate_reason` | O1007（恰好 7 天）在期内不转人工；O1003（30 天）`REFUND_NOT_ALLOWED`；判定用 `DEMO_NOW` 而非系统时钟 |
| AC18 | 催发货两态 | O1001 与 O1002 各跑一次催发货 | `tool_calls[].error_code` / `needs_human` | O1001 单次 `NOT_SHIPPED` 且不转人工；O1002 有物流可查且不转人工 |
| AC19 | 无依据承诺 | 桩输出"我们保证赔偿并已退款" | `escalate_reason` / `reply_draft` | `DRAFT_RISK` 且草稿被替换为待核实版本，不是只翻 `needs_human` |
| AC20 | 上游故障 | 桩模拟鉴权失败和重试耗尽的 5xx | HTTP码 / RunResult / trace | HTTP 503；响应体为完整 RunResult，`status=degraded`、`stop_reason=upstream_error`、`run_id` 非空；运行已落库且 trace 可查 |
| AC21 | 投诉 / 法律威胁 | `--text "再不退款我就去12315投诉，已经咨询律师了"` | `escalate_reason` / `tool_calls` / `steps` / `reply_draft` | `COMPLAINT_OR_THREAT`；`tool_calls=[]`、`status=ok`、`stop_reason=finalized`、`steps` 为已完成的模型请求数（通常 1）；草稿不含任何承诺或时限措辞 |

命令列给的是目标形态：CLI 类必须一条命令可复现；HTTP/SSE 类用 `serve` + curl 或 `pytest tests/acceptance.py -k acXX`。每条验收都要留 `run_id` 并在 `reports/evidence-index.md` 登记，没有 run_id 的"通过"不算证据。

## 12 开发提交与面试证据对应

推荐每个阶段形成一次独立、可运行的版本。先完成CLI，再做HTTP/SSE，最后整理演示。
建立 `reports/evidence-index.md`：主张 → 实现文件与符号 → 验收命令 → 原始产物 → 当前状态。
目前已有代码、报告和证据索引，但断言、规则和样本原先来自同一实现者；第二人代码及业务复核仍未完成。索引中的运行记录与合同验收强度须分开阅读，不能把路径存在或测试通过当作独立审查结论。

面试先展示一条成功工单，再展示订单越权、动作拦截和降级，最后展开trace定位一次实际失败。
只有亲自完成且有产物的步骤，才使用“我实现了”“我修复了”“实测达到”等表述。
