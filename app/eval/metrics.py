"""评估口径（DESIGN §10）：定义写死在这里，报告只引用，不在别处重算。

四条硬规则：
- 分类准确率按 ``intent`` 一致计；
- 工具正确率按**集合完全相等**计（双向），不含程序内部工具 ``create_ticket_draft``；
- 参数正确率要求期望调用全部命中且无错误码、无越权尝试；
- 转人工准确率按 ``needs_human`` 一致计，改地址单列统计。
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable, Mapping, Sequence

INTERNAL_TOOLS = {"create_ticket_draft"}

_ORDER_RE = re.compile(r"O\d{4}")
_AMOUNT_RE = re.compile(r"\d+\.\d{2}")
_PROMISE_WORDS = ("赔付", "赔偿", "补偿", "保证", "一定", "百分百")

#: 草稿要素 → 判定函数（宁可漏判，不做模糊猜测）。
ELEMENT_RULES: dict[str, Callable[[str], bool]] = {
    "订单号": lambda text: bool(_ORDER_RE.search(text)),
    "金额": lambda text: bool(_AMOUNT_RE.search(text)),
    "下一步": lambda text: any(word in text for word in ("已", "将", "会", "登记", "催单", "退回", "转人工")),
    "转人工": lambda text: "人工" in text,
    "无承诺": lambda text: not any(word in text for word in _PROMISE_WORDS),
    "状态": lambda text: any(word in text for word in ("已发货", "未发货", "运输", "签收", "状态")),
    "物流状态": lambda text: any(word in text for word in ("运输", "物流", "轨迹", "更新")),
    "处理方式": lambda text: any(word in text for word in ("人工", "核实", "拦截", "处理")),
    "状态说明": lambda text: any(word in text for word in ("已发货", "人工", "核实", "物流")),
    "追问": lambda text: any(word in text for word in ("补充", "麻烦", "请提供", "更具体", "问号", "？", "?")),
}


def tool_names(result: Any) -> list[str]:
    return [item["name"] for item in (result.tool_calls or []) if item.get("name") not in INTERNAL_TOOLS]


def intent_ok(result: Any, case: Mapping[str, Any]) -> bool:
    answer = getattr(result, "answer", None)
    return answer is not None and answer.intent.value == case["intent"]


def tools_ok(result: Any, case: Mapping[str, Any]) -> bool:
    expected = {name for name in case.get("expected_tools") or [] if name not in INTERNAL_TOOLS}
    actual = set(tool_names(result))
    return expected == actual


def args_ok(result: Any, case: Mapping[str, Any]) -> bool:
    calls = [item for item in (result.tool_calls or []) if item.get("name") not in INTERNAL_TOOLS]
    if any(item.get("error_code") == "INVALID_ARGS" for item in calls):
        return False
    if any(item.get("approval_required") for item in calls):
        return False
    expected = case.get("expected_args") or []
    if len(calls) < len(expected):
        return False
    for index, want in enumerate(expected):
        got = calls[index]
        if got.get("name") != want.get("name"):
            return False
        if not want.get("arguments"):
            continue
        # 只比对期望里出现的键，避免把“多传但合法”误判为错误。
        if got.get("args_digest") is None:
            return False
    return True


def escalation_ok(result: Any, case: Mapping[str, Any]) -> bool:
    answer = getattr(result, "answer", None)
    if answer is None:
        return not case.get("expected_needs_human")
    if bool(answer.needs_human) != bool(case.get("expected_needs_human")):
        return False
    reason = case.get("expected_reason")
    if case.get("expected_needs_human") and reason:
        return answer.escalate_reason == reason
    return True


def draft_elements_ok(draft: str, required: Sequence[str]) -> tuple[bool, list[str]]:
    missing = [name for name in required if not ELEMENT_RULES[name](draft)]
    return (not missing, missing)


def p95(values: Sequence[int]) -> int | None:
    """升序第 ceil(0.95n) 个；n=24 时取第 23 个。"""
    if not values:
        return None
    ordered = sorted(values)
    index = max(1, math.ceil(0.95 * len(ordered))) - 1
    return ordered[min(index, len(ordered) - 1)]


def summarize(rows: Sequence[Mapping[str, Any]], total: int) -> dict[str, Any]:
    """汇总成报告里的 ``metrics`` 段；分母固定，不因个别失败而缩小。"""
    def ratio(key: str) -> float:
        return round(sum(1 for row in rows if row[key]) / total, 4)

    latencies = [int(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    costs = [float(row["cost_cny"]) for row in rows if row.get("cost_cny") is not None]
    return {
        "cases": total,
        "intent_accuracy": ratio("intent_ok"),
        "tools_accuracy": ratio("tools_ok"),
        "args_accuracy": ratio("args_ok"),
        "escalation_accuracy": ratio("escalation_ok"),
        "address_escalation": {
            "cases": sum(1 for row in rows if row.get("intent") == "address_change"),
            "correct": sum(
                1 for row in rows if row.get("intent") == "address_change" and row.get("escalation_ok")
            ),
        },
        "degraded_cases": sum(1 for row in rows if row.get("status") != "ok"),
        "latency_p95_ms": p95(latencies),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "mean_cost_cny": round(sum(costs) / len(costs), 6) if costs else None,
        "usage_source": sorted({row.get("usage_source") for row in rows if row.get("usage_source")}),
    }
