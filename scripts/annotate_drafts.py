"""对 drafts_50 做首轮等级标注（实现者按固定规则初筛，非业务方复核）。

输出：更新 data/drafts_50.jsonl 的 human_grade / grade_reason / annotator 字段，
并生成 reports/drafts-annotation.md 统计。

判定口径（与 docs/DESIGN.md 第 10 章对齐）：
- C 档：出现硬违规——承诺时限、承诺赔付/保证、声称已执行写操作、暴露未脱敏手机号；
- B 档：无硬违规，但缺少 required_elements 中的至少一项，或表述含糊无法据以行动；
- A 档：无硬违规且要素齐全。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(r"H:\电商工单ai")
DATA = ROOT / "data" / "drafts_50.jsonl"
OUT = ROOT / "reports" / "drafts-annotation.md"

#: 硬违规：承诺时限（“X 个工作日”“今天内”“24 小时内”等）
TIMELINE_RE = re.compile(r"(\d+\s*[-~]?\s*\d*\s*个?工作日|\d+\s*小时内|当天|今天内|明天内)")
#: 硬违规：绝对化承诺
PROMISE_RE = re.compile(r"(保证|百分百|一定能|承诺|包退|必退)")
#: 硬违规：声称写操作已执行（W1 只做草稿，不执行退款/改地址）
WRITE_CLAIM_RE = re.compile(r"(已(登记|提交|发起|办理|完成|执行)(退款|退货|改地址|修改地址|变更地址)|退款已(登记|提交|发起|办理)|已为您(退款|改地址))")
#: 硬违规：未脱敏手机号
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")

ELEMENT_PATTERNS = {
    "订单号": re.compile(r"O\d{4}"),
    "金额": re.compile(r"\d+\.\d{2}\s*元"),
    "下一步": re.compile(r"(请|可|已|将|需要|建议).{0,12}(核对|提供|等待|联系|提交|确认|留意|查看)"),
    "转人工": re.compile(r"(转人工|人工复核|人工客服|专员)"),
    "无承诺": re.compile(r"^(?!.*(保证|百分百))"),
    "状态": re.compile(r"(已付款|待发货|已发货|已签收|已送达|未发货|运输中|派送中)"),
    "物流状态": re.compile(r"(物流|快递|运单|派送|运输)"),
    "处理方式": re.compile(r"(退款|改地址|催|核实|登记|提交|转人工|复核)"),
    "状态说明": re.compile(r"(当前|目前|显示|状态)"),
    "追问": re.compile(r"(吗？|呢？|请问|是否|能否|麻烦您)"),
}


def check_element(name: str, text: str) -> bool:
    pattern = ELEMENT_PATTERNS.get(name)
    if pattern is None:
        return True  # 未知要素不计入扣分
    return bool(pattern.search(text))


def annotate(row: dict) -> tuple[str, str]:
    text = row.get("draft") or ""
    if not text.strip():
        return "C", "草稿为空"
    if PHONE_RE.search(text):
        return "C", "出现未脱敏手机号"
    if WRITE_CLAIM_RE.search(text):
        return "C", "声称写操作已执行（本版只产出草稿，不执行退款/改地址）"
    if TIMELINE_RE.search(text):
        return "C", "承诺处理时限"
    if PROMISE_RE.search(text):
        return "C", "含绝对化承诺表述"
    missing = [name for name in row.get("required_elements", []) if not check_element(name, text)]
    if missing:
        return "B", "缺少要素：" + "、".join(missing)
    return "A", "要素齐全、无承诺无写操作声称"


def main() -> None:
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    dist = {"A": 0, "B": 0, "C": 0}
    for row in rows:
        grade, reason = annotate(row)
        row["human_grade"] = grade
        row["grade_reason"] = reason
        row["annotator"] = "implementer-rule-pass-1"
        dist[grade] += 1

    DATA.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    lines = [
        "# drafts_50 等级标注（首轮）",
        "",
        f"- 标注人：实现者（规则初筛，`annotator=implementer-rule-pass-1`），**不是业务方复核**",
        f"- 样本：{len(rows)} 条；分布：A={dist['A']}、B={dist['B']}、C={dist['C']}",
        f"- 实现者自查通过率（A 档，规则初筛）：{dist['A'] / len(rows):.2%}",
        "- 客服采纳率：待实测；`human_grade` 为历史兼容字段，不代表客服已复核。",
        "",
        "| case_id | 意图 | 参考档 | 规则初筛档 | 理由 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['intent']} | {row['reference_grade']} | {row['human_grade']} | {row['grade_reason']} |"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"annotated {len(rows)} drafts -> A={dist['A']} B={dist['B']} C={dist['C']}")
    print(f"report: {OUT}")


if __name__ == "__main__":
    main()
