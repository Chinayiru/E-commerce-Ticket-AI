"""只读业务工具：query_order / check_logistics / refund_preview。

共同规则：订单存在且 ``order.user_id == context.user_id`` 才可读；
不存在与越权对外统一 ``ORDER_NOT_FOUND``，不泄露金额、状态、运单号。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from app.schemas import ToolContext, ToolResult
from app.tools.mock_data import MOCK_ORDERS
from app.tools.registry import tool

ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
NOT_SHIPPED = "NOT_SHIPPED"
REFUND_NOT_ALLOWED = "REFUND_NOT_ALLOWED"
ORDER_STATE_UNSUPPORTED = "ORDER_STATE_UNSUPPORTED"

POLICY_VERSION = "w1-demo-1"

_ORDER_ID_PARAM = {
    "order_id": {"type": "string", "description": "订单号，形如 O1001", "required": True}
}


def _parse_time(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def _authorized_order(arguments: Mapping[str, Any], context: ToolContext) -> tuple[dict[str, Any] | None, ToolResult | None]:
    """订单存在性 + 归属校验；失败返回统一错误，不暴露他人订单。"""
    order_id = str(arguments.get("order_id", "")).strip().upper()
    order = MOCK_ORDERS.get(order_id)
    if order is None or order["user_id"] != context.user_id:
        return None, ToolResult.failure(
            ORDER_NOT_FOUND,
            "订单不存在或不属于当前用户",
            hint="请核对订单号，或转人工核实后处理",
        )
    return order, None


@tool(
    name="query_order",
    description="按订单号查询订单状态、金额与时间（只读）。",
    parameters=_ORDER_ID_PARAM,
    returns={
        "order_id": "str",
        "status": "str: paid | shipped | delivered",
        "amount_cents": "int",
        "paid_at": "str | null",
        "delivered_at": "str | null",
    },
)
def query_order(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    order, error = _authorized_order(arguments, context)
    if error is not None:
        return error
    assert order is not None
    return ToolResult.success(
        {
            "order_id": order["order_id"],
            "status": order["status"],
            "amount_cents": order["amount_cents"],
            "paid_at": order["paid_at"],
            "delivered_at": order["delivered_at"],
        }
    )


@tool(
    name="check_logistics",
    description="查询订单物流信息（只读）；未发货返回 NOT_SHIPPED。",
    parameters=_ORDER_ID_PARAM,
    returns={
        "order_id": "str",
        "carrier": "str",
        "tracking_id": "str",
        "status": "str",
    },
)
def check_logistics(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    order, error = _authorized_order(arguments, context)
    if error is not None:
        return error
    assert order is not None

    if order["status"] == "paid" or not order["carrier"] or not order["tracking_id"]:
        return ToolResult.failure(
            NOT_SHIPPED,
            "该订单尚未发货，暂无物流信息",
            hint="未发货不等于异常状态，不要重复查询",
        )

    return ToolResult.success(
        {
            "order_id": order["order_id"],
            "carrier": order["carrier"],
            "tracking_id": order["tracking_id"],
            "status": order["status"],
        }
    )


@tool(
    name="refund_preview",
    description="按演示规则预览退款资格与金额（只读，不代表退款已执行）。",
    parameters=_ORDER_ID_PARAM,
    returns={
        "allowed": "bool",
        "amount_cents": "int",
        "policy_reason": "str",
        "policy_version": "str",
    },
)
def refund_preview(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    order, error = _authorized_order(arguments, context)
    if error is not None:
        return error
    assert order is not None

    status = order["status"]
    amount_cents = int(order["amount_cents"])

    if status == "shipped":
        # 已发货：预览可以给出金额，但不代表允许直接退（优先级高于金额超限）。
        return ToolResult.success(
            {
                "allowed": False,
                "amount_cents": amount_cents,
                "policy_reason": "REFUND_AFTER_SHIP",
                "policy_version": POLICY_VERSION,
            }
        )

    if status == "delivered":
        delivered_at = _parse_time(order["delivered_at"])
        if delivered_at is None:
            return ToolResult.failure(
                ORDER_STATE_UNSUPPORTED,
                "订单已签收但缺少签收时间，无法判定售后期",
                hint="转人工核实签收时间",
            )
        deadline = delivered_at + timedelta(days=context.config.refund_window_days)
        if context.now > deadline:
            return ToolResult.failure(
                REFUND_NOT_ALLOWED,
                f"已超过售后 {context.config.refund_window_days} 天（签收于 {delivered_at.date().isoformat()}）",
                hint="按超期规则转人工",
            )
        return ToolResult.success(
            {
                "allowed": True,
                "amount_cents": amount_cents,
                "policy_reason": "REFUND_WITHIN_WINDOW",
                "policy_version": POLICY_VERSION,
            }
        )

    if status == "paid":
        limit = context.config.refund_auto_limit_cents
        allowed = amount_cents <= limit
        return ToolResult.success(
            {
                "allowed": allowed,
                "amount_cents": amount_cents,
                "policy_reason": "REFUND_WITHIN_LIMIT" if allowed else "REFUND_OVER_LIMIT",
                "policy_version": POLICY_VERSION,
            }
        )

    return ToolResult.failure(
        ORDER_STATE_UNSUPPORTED,
        f"订单状态 {status!r} 暂不支持退款预览",
        hint="转人工核实订单状态",
    )
