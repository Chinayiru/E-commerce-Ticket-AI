"""内部动作工具：``create_ticket_draft``（不可逆）。

它不是模型可自由调用的业务工具：loop 在最终答案校验通过后才调用，调用前必须
经过“转人工确认”闸门（批准才执行）。工具自身只负责把已验证草稿写进 store，
写入失败返回结构化错误，由 loop 判定为致命并降级，绝不伪装成功。
"""

from __future__ import annotations

from typing import Any, Mapping

from app.schemas import ToolContext, ToolResult
from app.tools.registry import tool

STORE_WRITE_FAILED = "STORE_WRITE_FAILED"
INVALID_DRAFT = "INVALID_DRAFT"

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
