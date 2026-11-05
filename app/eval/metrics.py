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


def _normalize_args(value: Any) -> dict[str, Any] | None:
    """数据集里的期望参数有两种写法：{"order_id": ...} 或 {"name":..., "arguments": {...}}。"""
    if not isinstance(value, Mapping):
        return None
    inner = value.get("arguments")
    if isinstance(inner, Mapping):
        return dict(inner)
    return dict(value)


def _expected_calls(case: Mapping[str, Any]) -> list[tuple[str, dict[str, Any] | None]]:
    tools = list(case.get("expected_tools") or [])
    expected_args = case.get("expected_args")
    pairs: list[tuple[str, dict[str, Any] | None]] = []
    if isinstance(expected_args, Mapping):
        for name in tools:
            pairs.append((name, _normalize_args(expected_args.get(name))))
    elif isinstance(expected_args, (list, tuple)):
        for i, name in enumerate(tools):
            value = expected_args[i] if i < len(expected_args) else None
            pairs.append((name, _normalize_args(value)))
    else:
        pairs.extend((name, None) for name in tools)
    return pairs


def args_ok(result: Any, case: Mapping[str, Any], calls: Any = None) -> bool:
    """参数正确率：期望调用与实调必须逐条、逐键对上。

    三条硬规则：没有调用明细时不能默认通过；多余调用算错；任何非预期的错误码算错
    （只有标注里写明的业务错误，例如 ORDER_NOT_FOUND，才允许出现）。
    """
    if calls is None:
        return False
    records = [item for item in calls if item.tool_name not in INTERNAL_TOOLS]
    if any(item.error_code == "INVALID_ARGS" for item in records):
        return False
    if any(item.approval_required for item in records):
        return False
    allowed_errors = {case.get("expected_reason"), "NOT_SHIPPED"}
    if any(item.error_code and item.error_code not in allowed_errors for item in records):
        return False

    expected = _expected_calls(case)
    if len(records) != len(expected):
        return False
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in records:
        by_name.setdefault(item.tool_name, []).append(dict(item.arguments or {}))
    for name, want in expected:
        got = by_name.get(name) or []
        if len(got) != 1:
            return False
        if want is not None and got[0] != want:
            return False
    return True


def escalation_ok(result: Any, case: Mapping[str, Any]) -> bool | None:
    """转人工判定：标注为 None 时不计分；没有最终答案一律算错（不能因为没跑完就默认通过）。"""
    expected = case.get("expected_needs_human")
    if expected is None:
        return None
    answer = getattr(result, "answer", None)
    if answer is None:
        return False
    if bool(answer.needs_human) != bool(expected):
        return False
    reason = case.get("expected_reason")
    if expected and reason:
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

    scored = [row for row in rows if row.get("escalation_ok") is not None]
    escalation_ratio = (
        round(sum(1 for row in scored if row["escalation_ok"]) / len(scored), 4) if scored else None
    )
    latencies = [int(row["latency_ms"]) for row in rows if row.get("latency_ms") is not None]
    costs = [float(row["cost_cny"]) for row in rows if row.get("cost_cny") is not None]
    return {
        "cases": total,
        "intent_accuracy": ratio("intent_ok"),
        "tools_accuracy": ratio("tools_ok"),
        "args_accuracy": ratio("args_ok"),
        "escalation_accuracy": escalation_ratio,
        "escalation_scored": len(scored),
        "escalation_excluded": total - len(scored),
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
