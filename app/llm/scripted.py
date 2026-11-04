"""scripted 假模型：按预设脚本返回“下一步做什么”。

返回值结构与真实 Provider 完全一致（``ModelResponse(decision, usage)``），
因此把 ``ScriptedModel`` 换成 ``OpenAICompatProvider`` 时 loop 不需要改。

脚本每一步是一个 dict，三选一：
    {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]}
    {"final": {"intent": "refund", "confidence": 0.9, "slots": {...},
               "reply_draft": "...", "needs_human": false, "used_tools": ["query_order"]}}
    {"usage": {"input_tokens": 600, "output_tokens": 40}}   # 可选，覆盖本次用量

也支持在构造时给 ``usage_per_step`` 作为默认用量。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.llm.base import ModelError
from app.schemas import (
    ApprovalDecision,
    FinalAnswer,
    ModelDecision,
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    Usage,
)

_FINAL_FIELDS = {
    "intent",
    "confidence",
    "slots",
    "reply_draft",
    "needs_human",
    "escalate_reason",
    "used_tools",
}


class ScriptExhausted(ModelError):
    """脚本步数用尽：说明测试脚本与循环预期不一致，必须显式失败。"""


def _build_usage(raw: Mapping[str, Any] | None) -> Usage | None:
    if not raw:
        return None
    return Usage(
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        source=str(raw.get("source", "scripted")),
    )


def _build_final(raw: Mapping[str, Any]) -> FinalAnswer:
    unknown = set(raw) - _FINAL_FIELDS
    if unknown:
        raise ValueError(f"scripted final 含未知字段：{sorted(unknown)}")
    missing = {"intent", "confidence", "reply_draft", "needs_human"} - set(raw)
    if missing:
        raise ValueError(f"scripted final 缺少字段：{sorted(missing)}")
    return FinalAnswer(
        intent=raw["intent"],
        confidence=raw["confidence"],
        slots=dict(raw.get("slots") or {}),
        reply_draft=raw["reply_draft"],
        needs_human=bool(raw["needs_human"]),
        escalate_reason=raw.get("escalate_reason"),
        used_tools=list(raw.get("used_tools") or []),
    )


class ScriptedModel:
    """按预设序列返回决策的假模型。"""

    provider_name = "scripted"

    def __init__(
        self,
        steps: Sequence[Mapping[str, Any]],
        *,
        usage_per_step: Usage | None = None,
        repeat_last: bool = False,
    ) -> None:
        if not steps:
            raise ValueError("scripted 脚本不能为空")
        for index, step in enumerate(steps):
            keys = set(step) & {"tool_calls", "final"}
            if len(keys) != 1:
                raise ValueError(
                    f"scripted 第 {index} 步必须且只能包含 tool_calls 或 final 之一，收到 {sorted(step)}"
                )
        self._steps = [dict(step) for step in steps]
        self._usage_per_step = usage_per_step
        self._repeat_last = repeat_last
        self._index = 0
        self.calls: list[ModelRequest] = []

    @property
    def remaining(self) -> int:
        return len(self._steps) - self._index

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _next_step(self) -> Mapping[str, Any]:
        if self._index < len(self._steps):
            step = self._steps[self._index]
            self._index += 1
            return step
        if self._repeat_last:
            return self._steps[-1]
        raise ScriptExhausted(
            f"scripted 脚本已用尽（共 {len(self._steps)} 步，第 {len(self.calls) + 1} 次调用）"
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        step = self._next_step()
        usage = _build_usage(step.get("usage")) or self._usage_per_step or Usage(source="scripted")
        if "tool_calls" in step:
            calls = []
            for item in step["tool_calls"]:
                if not isinstance(item, Mapping) or "name" not in item:
                    raise ValueError("scripted tool_calls 每项必须是 {name, arguments}")
                calls.append(
                    ToolCallRequest(name=str(item["name"]), arguments=dict(item.get("arguments") or {}))
                )
            decision = ModelDecision(tool_calls=calls)
        else:
            decision = ModelDecision(final=_build_final(step["final"]))
        return ModelResponse(decision=decision, usage=usage)


class ScriptedApprovalGate:
    """按脚本确认/拒绝不可逆操作。

    ``approve`` 可以是单个布尔值（每次同答），也可以是一个布尔序列（按调用顺序消费，
    用尽后抛 ``ScriptExhausted``，避免测试悄悄复用上一次的答案）。
    """

    approver = "scripted"

    def __init__(self, approve: bool | Sequence[bool], *, reason: str | None = None) -> None:
        self._queue: list[bool] | None = None
        self._fixed: bool | None = None
        if isinstance(approve, bool):
            self._fixed = approve
        else:
            self._queue = [bool(item) for item in approve]
            if not self._queue:
                raise ValueError("approve 序列不能为空")
        self._reason = reason
        self.calls: list[dict[str, Any]] = []

    def request_approval(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        run_id: str,
    ) -> ApprovalDecision:
        self.calls.append({"tool_name": tool_name, "arguments": dict(arguments), "run_id": run_id})
        if self._fixed is not None:
            approved = self._fixed
        elif self._queue:
            approved = self._queue.pop(0)
        else:
            raise ScriptExhausted(f"审批脚本已用尽：第 {len(self.calls)} 次请求 {tool_name}")
        reason = self._reason
        if reason is None:
            reason = "scripted approve" if approved else "scripted reject"
        return ApprovalDecision(approved=approved, approver=self.approver, reason=reason)
