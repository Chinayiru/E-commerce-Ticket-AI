"""写操作类工具：``create_ticket_draft`` / ``refund_submit`` / ``address_change``。

两条不同性质的路径，别混：
- ``create_ticket_draft`` 是**程序内部**工具，loop 在最终答案校验通过后才调用，
  调用前过“转人工确认”闸门；写入失败返回 ``STORE_WRITE_FAILED``，由 loop 判定致命。
- ``refund_submit`` / ``address_change`` 是**业务写操作**，首版没有成功分支：
  只要被请求就先被前置钩子拦成 ``APPROVAL_REQUIRED``；即便绕过钩子直达实现，
  实现本身也只会返回 ``APPROVAL_REQUIRED``，不存在“悄悄执行”的路径。
"""

from __future__ import annotations

from typing import Any, Mapping

from app.redaction import mask_pii
from app.schemas import ToolContext, ToolResult
from app.tools.registry import tool

STORE_WRITE_FAILED = "STORE_WRITE_FAILED"
INVALID_DRAFT = "INVALID_DRAFT"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

_REQUIRED_DRAFT_KEYS = ("intent", "reply_draft", "needs_human", "used_tools")


@tool(
    name="create_ticket_draft",
    description="把已验证的最终答案保存为工单草稿（内部工具，不可逆）。",
    parameters={
        "validated_answer": {"type": "object", "description": "已通过校验的 FinalAnswer 字典", "required": True},
        "run_id": {"type": "string", "description": "当前运行 id", "required": True},
    },
    returns={"run_id": "str", "draft_saved": "bool"},
    irreversible=True,
)
def create_ticket_draft(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    answer = arguments.get("validated_answer")
    run_id = str(arguments.get("run_id", "")).strip()

    if not isinstance(answer, dict) or not answer:
        return ToolResult.failure(INVALID_DRAFT, "validated_answer 必须是非空对象")
    missing = [key for key in _REQUIRED_DRAFT_KEYS if key not in answer]
    if missing:
        return ToolResult.failure(
            INVALID_DRAFT,
            f"草稿缺少字段：{', '.join(missing)}",
            hint="只接受经过 loop 事实校验的 FinalAnswer",
        )
    if run_id != context.run_id:
        return ToolResult.failure(
            INVALID_DRAFT,
            "run_id 与当前上下文不一致，拒绝跨会话写草稿",
        )
    if context.store is None:
        return ToolResult.failure(STORE_WRITE_FAILED, "上下文缺少 store，无法落库")

    try:
        context.store.save_draft(run_id, answer)
    except Exception as exc:  # 持久化失败必须让 loop 终止，不能返回成功
        return ToolResult.failure(
            STORE_WRITE_FAILED,
            f"写入草稿失败：{type(exc).__name__}: {exc}",
            hint="本次运行不可标记为成功",
        )

    return ToolResult.success({"run_id": run_id, "draft_saved": True})


@tool(
    name="refund_submit",
    description="提交退款申请（写操作，首版必须人工审批，不会直接生效）。",
    parameters={
        "order_id": {"type": "string", "description": "订单号，形如 O1001", "required": True},
    },
    returns={"order_id": "str", "approval_required": "bool"},
    irreversible=True,
)
def refund_submit(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    """首版不存在成功分支：无论谁调用，都只能得到 APPROVAL_REQUIRED。"""
    order_id = str(arguments.get("order_id", "")).strip().upper()
    return ToolResult.failure(
        APPROVAL_REQUIRED,
        f"退款提交需要人工审批，未执行（订单 {order_id}）",
        hint="已转人工，不要重复提交",
    )


@tool(
    name="address_change",
    description="修改收货地址（写操作，首版必须人工审批，不会直接生效）。",
    parameters={
        "order_id": {"type": "string", "description": "订单号，形如 O1001", "required": True},
        "new_address": {"type": "string", "description": "新收货地址（落库前脱敏）", "required": True},
    },
    returns={"order_id": "str", "approval_required": "bool"},
    irreversible=True,
)
def address_change(arguments: Mapping[str, Any], context: ToolContext) -> ToolResult:
    """同样是“无成功分支”：只在错误信息里回显脱敏后的地址，证明未落库。"""
    order_id = str(arguments.get("order_id", "")).strip().upper()
    masked = mask_pii(str(arguments.get("new_address", "")))
    return ToolResult.failure(
        APPROVAL_REQUIRED,
        f"地址变更需要人工审批，未执行（订单 {order_id}，新地址 {masked}）",
        hint="已转人工，请勿重复提交",
    )
