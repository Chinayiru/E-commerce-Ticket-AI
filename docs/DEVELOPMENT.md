# 开发文档 · 电商售后工单处理 Agent

| 项 | 内容 |
| --- | --- |
| 文档性质 | 实施手册。回答"按什么顺序做、每步产出什么、怎样算做完" |
| 版本 | v1.3，2026-11-04同步 DESIGN v1.4 契约与验收 |
| 上游文档 | DESIGN.md v1.4；可编码细节见IMPLEMENTATION.md，本文保留工作顺序与流程 |
| 读者 | 实现者（本人）、需要复现结果的评审者 |

本文不含任何"实测指标"。所有指标在下文规定的命令执行后写入 `reports/`，并回填到交付清单；
未跑过的数字一律写 `待实测`，不允许估算。

> **当前仓库状态**：只交付文档，不含实现代码。因此第 1–2 章描述的是"实现时应有的环境、依赖与目录布局"，
> 不是本仓库的现状；第 3 章的 W1–W4 是施工顺序，第 6–7 章是评估与标注的操作规程。

---

## 1. 环境与依赖

### 1.1 运行时

| 项 | 要求 | 说明 |
| --- | --- | --- |
| Python | 3.12 | 采用统一开发基线；这些语法并非Python 3.12专有 |
| 依赖 | `fastapi`、`uvicorn[standard]`、`pydantic`、`httpx`、`pytest` | 运行时只有前四个；白名单之外的依赖需评审（见设计文档第 11 章） |
| 数据库 | SQLite（标准库 `sqlite3`） | 不引 ORM |
| 模型 | OpenAI 兼容协议（`gpt-4o-mini` 或国内兼容模型） | 通过 `OPENAI_BASE_URL` 切换，不改代码 |

### 1.2 配置契约（`.env`）

| 变量 | 默认 | 作用 | 改它的后果 |
| --- | --- | --- | --- |
| `PROVIDER` | `scripted` | `scripted`（离线桩）/ `openai` | 桩只验证链路，不能当作模型效果 |
| `OPENAI_API_KEY` | 空 | 模型密钥 | 为空且 provider=openai 时启动即报错（快速失败） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容网关地址 | 切换后还需核验工具调用、usage、输出限制及错误语义 |
| `MODEL` | `gpt-4o-mini` | 模型名 | 影响成本与延迟 |
| `MAX_STEPS` | 6 | 步数上限 | 调大 → 成本上升；调小 → 复杂工单降级 |
| `TOKEN_BUDGET` | 6000 | 单条 token 预算 | 同上 |
| `WALL_CLOCK_S` | 30 | 墙钟超时 | 调小 → 网络抖动时误判降级 |
| `WINDOW_TURNS` | 6 | 保留原文轮数 | 调大 → token 膨胀；调小 → 摘要依赖加重 |
| `REFUND_AUTO_LIMIT` | 200 | 无需额外升级的退款预览金额阈值（元），保留旧配置名 | 不存在自动退款；超过则升级人工 |
| `PRICE_IN` / `PRICE_OUT` | 示例0.15 / 0.60，需核对 | 每百万token美元单价，记录来源与计价日期 | 缺计量费用为null，不直接按示例当现价 |
| `USD_CNY` | 7.2 | 汇率 | 影响成本展示 |
| `DB_PATH` | `runs.db` | SQLite 路径 | 评估与演示建议分开库 |
| `LOG_DIR` | `logs` | 审计日志目录 | 审计文件不得进版本库 |
| `DEMO_NOW` | 固定时间戳 | 时效判断的时间锚点 | 不固定则同一用例跨日期结论不同 |

### 1.3 启动与验收命令（目标接口，当前不可执行）

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
# 程序从进程环境读取配置；若使用.env，CLI必须实现显式加载，复制文件不会自动生效。
# PowerShell示例：$env:PROVIDER="scripted"；真实Key通过本地环境设置，不提交版本库。

python -m app.cli demo                              # 1) 命令行演示（离线可跑）
python -m app.cli serve                             # 2) HTTP + 单页 + SSE
python -m app.cli eval --prompt v3 --provider openai # 3) 24 条全量评估
```

---

## 2. 目录结构（与六组件一一对应；实现时按此创建，本仓库不含代码）

```
aftermarket-agent/
├── app/
│   ├── cli.py                 # 入口：run / demo / serve / trace / replay / eval / stats
│   ├── config.py              # 配置与成本核算（含时间锚点）
│   ├── schemas.py             # 契约模型 + 模型输出容错解析
│   ├── core/
│   │   ├── loop.py            # E 有界执行循环
│   │   ├── context.py         # C 窗口 + 摘要
│   │   ├── hooks.py           # L 审计 / 打点 / 拦截
│   │   ├── policy.py          # 转人工策略层（覆写模型结论）
│   │   └── prompts.py         # 提示词版本（v1 / v2 / v3 …）
│   ├── tools/
│   │   ├── registry.py        # T @tool 注册与校验
│   │   ├── business.py        # query_order / check_logistics / refund_preview
│   │   └── actions.py         # create_ticket_draft / refund_submit / address_change
│   ├── store/db.py            # S 四张表与读写接口
│   ├── llm/
│   │   ├── base.py            # Provider 协议 + 统一 usage
│   │   ├── openai_compat.py   # 真实模型
│   │   └── scripted.py        # 离线确定性桩（禁止用它撑指标）
│   ├── api/main.py            # FastAPI + SSE
│   └── eval/                  # V 数据集 / 跑批 / 回放 / 报告
├── data/                      # mock_orders.json / eval_cases.jsonl / drafts_50.jsonl / holdout_12.jsonl
├── docs/                      # DESIGN.md / IMPLEMENTATION.md / DEVELOPMENT.md / INTERVIEW_READINESS.md / BADCASE.md / README.md
├── reports/                   # 每版评估产物（json + md）
├── scripts/                   # check_leakage.py / compare_versions.py
├── tests/                     # 单元测试与契约测试
├── Dockerfile
└── requirements.txt
```

**分层铁律**：`core` 不 import 具体工具实现；`tools` 不 import `core`；`api` 与 `cli` 只调 `core.loop` 与 `store`；
`store` 不 import 任何上层。跨层直连视为重构信号。

---

## 3. 四周计划（WBS + DoD）

W1至W4是四个工作包标签，不代表已用四周。个人排期估计共13工作日，尚无实际工时记录；按产物和验收更新进展。

### W1 骨架 + 最小可跑（3 天）

| 任务 | 产出 | 完成定义（DoD） |
| --- | --- | --- |
| W1-1 配置与契约 | `config.py`、`schemas.py` | 输入非法时返回 `rejected`，且不创建会话、不消耗模型 |
| W1-2 工具注册表 | `tools/registry.py` + 6 个工具（3 个只读、2 个拦截动作、1 个内部草稿工具） | 未知参数返回 `INVALID_ARGS`；订单不存在返回 `ORDER_NOT_FOUND`；合法动作调用被钩子拦截为 `APPROVAL_REQUIRED`；两者都不抛异常 |
| W1-3 执行循环 | `core/loop.py` + `llm/base.py` + `llm/openai_compat.py` | 一条退款工单能跑出分类、草稿和工具轨迹；模型策略与离线桩明确区分 |
| W1-4 CLI | `cli.py` 的 `run` / `demo` | `python -m app.cli demo` 一条命令出 4 条结果 |

验收命令：`python -m app.cli run --text "订单 O1001 买错了，退款" --order-id O1001 --user-id U001 --ticket-id DEMO001`
通过标准：`status=ok`、工具轨迹含 `query_order → refund_preview`、草稿非空。

### W2 上下文 + 状态 + 钩子（3 天）

| 任务 | 产出 | DoD |
| --- | --- | --- |
| W2-1 上下文折叠 | `core/context.py` | 单测注入至少 8 轮消息，验证超出 6 轮窗口的旧轮被折叠；`role=tool` 不被截断；摘要 6 字段齐全 |
| W2-2 四表持久化 | `store/db.py` | 任意 `run_id` 能取回完整 trace；`UNIQUE(session_id, idempotency_key)` 生效 |
| W2-3 生命周期钩子 | `core/hooks.py` | 审计行含工具名/耗时/结果/是否拦截；手机号脱敏 |
| W2-4 不可逆转人工 | `policy.py` + `actions.py` | 首版refund_submit/address_change总被钩子拦截且无副作用，不接受模型或请求的approved字段 |
| W2-5 手工验收 | 10 条用例 | "该转人工的确实转了"，逐条记录 `escalate_reason` |

验收命令：`python -m app.cli trace --run-id <id>`；手工用例表见第 7.4 节。
通过标准：10 条里转人工判定全对；审计文件无完整手机号。

### W3 评估闭环 + 迭代（5 天，不可压缩）

| 任务 | 产出 | DoD |
| --- | --- | --- |
| W3-1 数据集 | `data/eval_cases.jsonl`（24）+ `data/drafts_50.jsonl`（50） | 4×2×3 矩阵填满；每条含期望输出；与 prompt 无重叠（脚本校验） |
| W3-2 跑批与报告 | `eval/dataset.py`、`runner.py`、`report.py` | 一条命令产出json+md；scripted重复性一致，真实模型报告多次波动 |
| W3-3 基线 | `reports/eval_v1_baseline.*` | 四个指标 + 成本 + P95 全部有数（真实模型） |
| W3-4 归因与修复 | `docs/BADCASE.md` 第一版 | 每条失败落到四类之一，带 trace |
| W3-5 两到三轮迭代 | `reports/eval_v2_*`、`eval_v3_*` + 对比表 | 冻结离线回归无退化；真实模型记录逐次变化，不预设必须提升，保留实际修复证据 |
| W3-6 成本与延迟打点 | 报告中的 `avg_cost_cny` / `p95_latency_ms` | 单条成本与 P95 有真实数字，超预算有解释 |

验收命令：

```bash
python scripts/check_leakage.py
python -m app.cli eval --prompt v1 --tag baseline --provider openai
python -m app.cli eval --prompt v3 --tag final --provider openai
python scripts/compare_versions.py --old reports/eval_v1_baseline.json --new-prompt v3
python -m app.cli replay --run-id <失败run> --prompt v4
```

通过标准：报告存在且可复现；`compare` 表能说明每一版的增减；失败集有归因记录。

### W4 包装 + 演示（2 天）

| 任务 | 产出 | DoD |
| --- | --- | --- |
| W4-1 README | 三问成稿（为什么不用 LangGraph / 上下文怎么裁剪 / Bad Case 怎么闭环） | 每问 300–500 字，含具体数字与取舍 |
| W4-2 演示 | 3 分钟录屏脚本（含"改地址转人工"与"回放对比"两段） | 一条命令可复现录像中的每个画面 |
| W4-3 简历 | STAR + 量化描述 | 每句都能对应到代码或报告里的证据 |
| W4-4 交付校验 | 第 8 章清单逐项打勾 | 无未勾选项，或有明确"阻塞+原因" |

---

## 4. 编码规范

| 项 | 规则 | 理由 |
| --- | --- | --- |
| 类型标注 | 公开函数必须全标注；内部允许省略但要一致 | 契约即文档 |
| 错误处理 | 工具内不抛异常；循环内捕获 `UpstreamError`；其余异常允许冒泡到进程边界 | 业务失败要被模型读懂，程序错误要被开发者看到 |
| 冻结配置 | `Settings` 用 frozen dataclass，运行期用 `dataclasses.replace` 派生 | 避免隐式全局可变状态 |
| 无全局可变状态 | 除工具注册表（启动期一次性注册）外不允许模块级可变对象 | 评估要能重复跑 |
| 时间 | 一律用 `settings.now()`，禁止裸 `datetime.now()` | 时效判断必须可复现 |
| 日志 | 只写结构化 JSON 行到 `LOG_DIR`；敏感字段先脱敏 | 审计可机读、可合规 |
| 命名 | 工具名为动词短语（`query_order`），错误码为大写蛇形 | 与 schema 生成规则一致 |
| 注释 | 只解释"为什么"，不复述"做了什么" | 代码即行为 |
| 禁止项 | 禁止 `print` 进业务代码（CLI 层除外）、禁止 `except: pass`、禁止在工具里 `sleep`、禁止把 Key 写进代码 | 见设计文档 13.1 自检清单 |

---

## 5. 测试策略

### 5.1 分层

| 层 | 测什么 | 数量级 | 例子 |
| --- | --- | --- | --- |
| 契约测试 | 解析、校验、错误码 | 20+ | 非法工单号被拒；未知参数返回 `INVALID_ARGS` |
| 组件测试 | 六组件各自行为 | 30+ | 窗口折叠不截断工具消息；钩子拦截不产生副作用 |
| 循环测试 | 五种降级原因可达 | 目标至少5类 | 步数、预算、超时、解析和上游失败；详见IMPLEMENTATION AC09至10 |
| 接口测试 | HTTP + SSE | 8 | 409 重复、422 非法、事件序列含 `final` |
| 数据集测试 | 24 条矩阵与引用完整性 | 5 | 4×2 各 3 条；订单号在 mock 数据中存在 |
| 回放测试 | trace 可重建、重跑可比 | 3 | 同一工单重跑意图一致；未知 run 报错 |

### 5.2 回归门槛

- 任一测试失败不得提交；
- 改动 `policy.py` / `context.py` / 工具签名时，必须同步跑 24 条全量评估（单元测试覆盖不到语义退化）；
- 评估报告与代码同批提交，不允许"代码先合、报告后补"。

---

## 6. 评估与迭代操作手册

### 6.1 标准流程（每次改 prompt / 工具 / 策略都走）

```bash
# 1. 改之前先留基线（若还没有）
python -m app.cli eval --prompt v1 --tag baseline --provider openai

# 2. 改完跑候选版本
python -m app.cli eval --prompt v4 --tag cand --provider openai

# 3. 与上一版对比（不退化才继续）
python scripts/compare_versions.py --old reports/eval_v3_final.json --new-prompt v4

# 4. 失败用例回放，确认不是"换个错法"
python -m app.cli replay --run-id <失败run_id> --prompt v4

# 5. 更新 docs/BADCASE.md 的归因表与修复记录
```

### 6.2 判定表

| 情况 | 处置 |
| --- | --- |
| 分类准确率下降 | 离线冻结回归拒绝；真实模型复跑定位波动并比对逐例变化 |
| 工具集合正确率下降 | 检查是否新增工具描述歧义 |
| 参数正确率下降 | 检查槽位抽取表述是否被改动 |
| 转人工变化 | 检查必转案例的FN，同时看FP及自动覆盖，不能仅凭总数增减判定 |
| 成本上升 > 20% | 需要解释，或砍 few-shot |
| 延迟 P95 上升 > 30% | 检查是否新增串行工具调用 |

### 6.3 迭代记录格式（每轮一行）

| 版本 | 改动 | 分类 | 工具 | 参数 | 转人工 | 采纳率 | 成本 | P95 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1 | 基线 | 待实测 | 待实测 | 待实测 | 待实测 | 待实测 | 待实测 | 待实测 | — |
| v2 | … | | | | | | | | |

> 这张表只能由 `reports/` 里的真实报告填写。任何未跑出的格子写"待实测"，不写估算。

---

## 7. 数据与标注

### 7.1 24 条确定性集构造规则

| 维度 | 规则 |
| --- | --- |
| 意图 | 4 类各 6 条（简单 3 + 复杂 3） |
| 简单 | 单一诉求，一句话说清，含订单号 |
| 复杂 | 满足任一：≥2 个诉求 / 带时效或超期争议 / 带情绪或威胁 |
| 长度 | 15–120 字，模拟真实客服工单口吻 |
| 标注字段 | `case_id`、`split`、`text`、`intent`、`order_id`、`expected_tools`、`expected_args`、`expected_needs_human`、`expected_reason`（可空） |
| 订单分配 | 按 IMPLEMENTATION 第 3 章的分配表取材，每单最多出现 3 次；四个分支（未发货大额、200 元、售后期到期、优先级叠加）必须各有独立订单 |
| 覆盖要求 | 正常样例订单存在且归属匹配；缺号/未知/越权样例显式标记并有期望错误；工具须已注册 |

### 7.2 50 条草稿集构造规则

| 维度 | 规则 |
| --- | --- |
| 来源 | 与 24 条不重叠（脚本校验重复） |
| 标注 | 每条 2–3 个"必需要素"（订单号、金额、承运商、处理动作、时限） |
| 不评 | 主指标评草稿，但保留完整运行轨迹；无依据的金额和动作承诺必须判失败 |

### 7.3 标注 rubric

| 档位 | 定义 | 计数方式 |
| --- | --- | --- |
| A | 人工核对事实及语义，要素齐全且无越权承诺，可直接发送 | 计入人工采纳率分子；自动要素检查另报 |
| B | 缺 1 个要素，人工补一句即可 | 计入可用率，不计采纳率 |
| C | 缺 ≥2 个要素、<20 字、或含承诺性措辞 | 不可用 |

标注由作者本人完成时，必须在报告中声明"单人标注、无二次复核"，并抽样 10 条给出标注理由。

### 7.4 10 条手工验收集（钩子正确性）

| # | 场景 | 期望 |
| --- | --- | --- |
| 1 | 未发货订单退款，金额 < 200 | 不转人工 |
| 2 | 未发货订单退款，金额 > 200 | 转人工（`REFUND_OVER_LIMIT`） |
| 3 | 已发货订单退款 | 转人工（`REFUND_AFTER_SHIP`） |
| 4 | 已签收且超售后期退款 | 转人工（`REFUND_NOT_ALLOWED`） |
| 5 | 未发货订单改地址 | 转人工（`ADDRESS_CHANGE`） |
| 6 | 已发货订单改地址 | 转人工（`ADDRESS_AFTER_SHIP`） |
| 7 | 催发货，已发货 | 不转人工 |
| 8 | 催发货，未发货 | 不转人工（单次 `NOT_SHIPPED` 不算失败） |
| 9 | 完全无关咨询 | 转人工（`LOW_CONFIDENCE`） |
| 10 | 草稿出现"我们保证赔偿" | 转人工（`DRAFT_RISK`） |

> 编号已并入 IMPLEMENTATION 第 11 章，两处不再各自演进：1→AC01、2→AC16、3→AC05、4→AC17、5→AC05、6→AC05、7→AC18、8→AC18、9→AC05、10→AC19。
> 本表只写"转不转人工"；AC 表额外给出命令、观察字段与具体期望值，那才是可执行的部分。

**冻结 holdout**：另建 12 条（4 意图 × 3），标注后写入 `data/holdout_12.jsonl` 并冻结，只在版本定稿时跑一次，不参与 prompt 调整、不进 few-shot。24 条与 holdout 不共用题干；去重脚本只管字面，语义近似的改写靠写作纪律。

---

## 8. 交付清单

| # | 交付物 | 位置 | 自检 |
| --- | --- | --- | --- |
| 1 | 设计文档（边界契约） | `docs/DESIGN.md` | 13.1 十条全勾 |
| 2 | 开发文档（本文） | `docs/DEVELOPMENT.md` | W1–W4 的 DoD 全达标 |
| 3 | Bad Case 归因与迭代记录 | `docs/BADCASE.md` | 每条失败有归因、每次修复有回放 |
| 4 | 24 条确定性集 + 50 条草稿集 + 12 条冻结 holdout | `data/`（含 `holdout_12.jsonl`） | 泄漏检查通过，holdout 只在最终报告解封 |
| 5 | 各版本评估报告 | `reports/` | 每个数字可一条命令复现 |
| 6 | README（三问成稿 + 指标表） | `README.md` | 桩数据已标注 `provider=scripted` |
| 7 | 演示录屏（3 分钟） | 外部链接 | 画面可复现 |
| 8 | 简历描述（STAR + 量化） | 简历文件 | 每句对应到证据 |
| 9 | 一条命令启动 | `Dockerfile` / CLI | 干净环境可跑 |

---

## 9. 风险登记册

| 编号 | 风险 | 触发信号 | 应对 | 状态 |
| --- | --- | --- | --- | --- |
| R-1 | 模型凭证未配置时不能实测 | 真实Provider启动校验失败 | 先用scripted推进；本次未检查凭证，不能断言当前无Key | 待开发时确认 |
| R-2 | 公开语料不可达 | 抓取失败 | 自建数据集，构造规则与标注口径写入 7.1/7.2，声明单人标注局限 | 已定方案 |
| R-3 | 24 条太少，指标波动大 | 一条用例改变 4pp | 报告里同时给"条数"而非只有百分比；改动判定以"条"为单位 | 已缓解 |
| R-4 | 模型供应商不稳定 | 429 / 5xx | 有限重试+deadline，报告注明运行时段 | 方案已写，待实现 |
| R-5 | 场景太窄被质疑 | 面试官问"这算 Agent 吗" | 用设计文档 2.3 节回答：窄换来可穷举、可归因、可回放、可约束 | 叙事已备 |
| R-6 | 自己调prompt又自己评分 | 无法排除过拟合 | 24条明确为development；泛化另建冻结holdout；人工和自动评分分开 | 已定规则，待执行 |
| R-7 | 单人标注偏差 | 采纳率偏高 | 公开评分理由；人工与自动评分分开，B档仅计可用率 | 待执行 |

---

## 10. 变更控制

| 改动类型 | 必须同步更新 | 是否需要评审 |
| --- | --- | --- |
| 新增/删除工具 | `DESIGN.md` 5.2/6.4、本文件 2、测试 | 是（边界三问） |
| 修改错误码集合 | `DESIGN.md` 5.2、所有调用方 | 是 |
| 修改表结构 | `DESIGN.md` 6.5、`store/db.py`、回放脚本 | 是 |
| 修改转人工条件 | `DESIGN.md` 9.1、`policy.py`、7.4 手工集 | 是（合规相关） |
| 修改 prompt | 本文件 6.3 迭代表、`BADCASE.md` | 否，但必须跑全量 |
| 修改上下文字段 | `DESIGN.md` 第 8 章、`context.py` | 是 |
| 纯重构（不改行为） | 无 | 否，但测试与全量评估必须通过 |

**红线**：任何让"评估闭环"变弱的改动（减少用例、放宽判定、把桩数据混进报告）一律拒绝，不接受"先合后补"。

## 11 本轮新增开发文档与状态

- [IMPLEMENTATION.md](IMPLEMENTATION.md)：对象合同、六工具参数、8 条合成订单与分支矩阵、提示词契约、授权、循环、事务、回放、API、计量，以及 AC01–AC21 四列断言（场景 / 命令 / 观察字段 / 期望值）。
- [INTERVIEW_READINESS.md](INTERVIEW_READINESS.md)：当前面试判断、原文问题、证据缺口、讲解与简历边界。

当前仍仅文档。代码、数据集、评估报告、容器文件和录屏都未建立；上文命令不能作为运行成功证明。
状态只在获得对应产物后更新；历史脚本运行及参考实现记录不自动算作当前版本完成。

