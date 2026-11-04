"""本阶段的数据契约：输入、意图、工具、轮次、会话、执行结果与模型协议。

全部使用标准库 ``dataclass``（本机无 pydantic，且 W1 不引第三方依赖）；
字段与 ``app/store/db.py`` 的四张表一一对应，JSON 字段在落库时统一序列化。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from app.config import Config

#: 工单文本长度边界：短于下限视为噪声，超出上限拒绝（对应 AC02 的“空/超长”）。
MIN_TEXT_CHARS = 5
MAX_TEXT_CHARS = 500
MAX_ID_CHARS = 64
MAX_TOOL_CALLS_PER_STEP = 3


class Intent(str, Enum):
    """意图标签，本阶段固定四类（docs/README.md）。"""

    REFUND = "refund"
    ADDRESS_CHANGE = "address_change"
    SHIPPING_URGE = "shipping_urge"
    OTHER = "other"

    @classmethod
    def parse(cls, value: Any) -> "Intent":
        try:
            return cls(str(value))
        except ValueError as exc:
            allowed = ", ".join(item.value for item in cls)
            raise ValueError(f"intent 必须是 [{allowed}] 之一，收到 {value!r}") from exc


class StopReason(str, Enum):
    """终止原因。取值沿用 docs/IMPLEMENTATION.md §5 与 AC09 的命名。"""

    FINALIZED = "finalized"
    MAX_STEPS = "max_steps"
    TOKEN_BUDGET = "token_budget"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    UPSTREAM_ERROR = "upstream_error"


class RunStatus(str, Enum):
    """运行状态：正常收尾 / 降级（触发上限）/ 输入被拒（未建会话）。"""

    OK = "ok"
    DEGRADED = "degraded"
    REJECTED = "rejected"


class TicketValidationError(ValueError):
    """输入校验失败。``field`` 与 ``code`` 供 AC02 断言，不外抛给进程。"""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"[{code}] {field}: {message}")


@dataclass(frozen=True, slots=True)
class TicketIn:
    """一条工单输入。``order_id`` 可为空，缺号由策略层处理，不在这里猜。"""

    ticket_id: str
    user_id: str
    text: str
    order_id: str | None = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TicketIn":
        if not isinstance(payload, Mapping):
            raise TicketValidationError("invalid_type", "payload", "工单必须是 JSON 对象")

        allowed = {"ticket_id", "user_id", "text", "order_id"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise TicketValidationError("unknown_field", unknown[0], "不接受的字段（避免静默丢弃）")

        for name in ("ticket_id", "user_id", "text"):
            if name not in payload or payload[name] is None:
                raise TicketValidationError("missing_field", name, "必填字段缺失")

        def _required_id(field_name: str) -> str:
            value = payload[field_name]
            if not isinstance(value, str):
                raise TicketValidationError("invalid_type", field_name, "应为字符串")
            text = value.strip()
            if not text:
                raise TicketValidationError("empty_field", field_name, "不能为空")
            if len(text) > MAX_ID_CHARS:
                raise TicketValidationError("too_long", field_name, f"长度不得超过 {MAX_ID_CHARS}")
            return text

        ticket_id = _required_id("ticket_id")
        user_id = _required_id("user_id")

        text_value = payload["text"]
        if not isinstance(text_value, str):
            raise TicketValidationError("invalid_type", "text", "应为字符串")
        text = text_value.strip()
        if not text:
            raise TicketValidationError("empty_text", "text", "工单内容为空")
        if len(text) < MIN_TEXT_CHARS:
            raise TicketValidationError(
                "text_too_short", "text", f"至少 {MIN_TEXT_CHARS} 个字符，收到 {len(text)}"
            )
        if len(text) > MAX_TEXT_CHARS:
            raise TicketValidationError(
                "text_too_long", "text", f"最长 {MAX_TEXT_CHARS} 个字符，收到 {len(text)}"
            )

        order_id = payload.get("order_id")
        if order_id is not None:
            if not isinstance(order_id, str):
                raise TicketValidationError("invalid_type", "order_id", "应为字符串或 null")
            order_id = order_id.strip() or None
            if order_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", order_id):
                raise TicketValidationError(
                    "invalid_order_id", "order_id", "只允许字母、数字、下划线与连字符"
                )
            if order_id is not None:
                order_id = order_id.upper()

        return cls(ticket_id=ticket_id, user_id=user_id, text=text, order_id=order_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "user_id": self.user_id,
            "text": self.text,
            "order_id": self.order_id,
        }


@dataclass(frozen=True, slots=True)
class Usage:
    """token 计量。``source`` 区分实测与估算，缺计量时不得填 0 冒充真实值。"""

    input_tokens: int = 0
    output_tokens: int = 0
    source: str = "estimated"  # reported | estimated | missing

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        sources = {self.source, other.source}
        if "missing" in sources:
            source = "missing"
        elif len(sources) == 1:
            source = self.source  # 同源累加保留来源（scripted 数字不得标成 reported）
        else:
            source = "estimated"
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class ToolError:
    """结构化工具错误。code 是封闭集，message 面向人，hint 面向下一步动作。"""

    code: str
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "hint": self.hint}


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: ToolError | None = None

    @classmethod
    def success(cls, data: dict[str, Any]) -> "ToolResult":
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, code: str, message: str, hint: str | None = None) -> "ToolResult":
        return cls(ok=False, error=ToolError(code=code, message=message, hint=hint))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": None if self.error is None else self.error.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ApprovalDecision:
    """不可逆操作前的“转人工确认”结果。

    本阶段由 scripted 闸门给出；W2 接真实审批（人工工单）时结构保持不变。
    """

    approved: bool
    approver: str = "scripted"
    reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.approved, bool):
            raise ValueError("approval.approved 必须是布尔值")

    def to_dict(self) -> dict[str, Any]:
        return {"approved": self.approved, "approver": self.approver, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class ToolCallRequest:
    """模型请求的一次工具调用（尚未执行）。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("tool_call.name 必须是非空字符串")
        if not isinstance(self.arguments, dict):
            raise ValueError("tool_call.arguments 必须是对象")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments)}


@dataclass(frozen=True, slots=True)
class ToolContext:
    """程序构造的工具上下文；模型无法传入或覆盖 user_id / 审批结果。"""

    run_id: str
    user_id: str
    now: datetime
    config: Config
    store: Any = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """工具声明：名称、参数 schema、不可逆标记、返回结构。"""

    name: str
    description: str
    parameters: dict[str, dict[str, Any]]
    returns: dict[str, str]
    irreversible: bool = False

    def json_schema(self) -> dict[str, Any]:
        """生成供模型使用的 JSON Schema（参数白名单即此，未声明的键一律拒绝）。"""
        properties = {
            key: {"type": spec.get("type", "string"), "description": spec.get("description", "")}
            for key, spec in self.parameters.items()
        }
        required = [key for key, spec in self.parameters.items() if spec.get("required", True)]
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }


@dataclass(frozen=True, slots=True)
class FinalAnswer:
    """模型最终输出。事实与转人工判定由程序复核，不能只信模型自报。"""

    intent: Intent
    confidence: float
    slots: dict[str, Any]
    reply_draft: str
    needs_human: bool
    escalate_reason: str | None = None
    used_tools: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.intent, Intent):
            object.__setattr__(self, "intent", Intent.parse(self.intent))
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError(f"confidence 必须在 0..1，收到 {self.confidence!r}")
        if not isinstance(self.slots, dict):
            raise ValueError("slots 必须是对象")
        if not isinstance(self.reply_draft, str) or not self.reply_draft.strip():
            raise ValueError("reply_draft 不能为空")
        if self.escalate_reason is not None and not self.needs_human:
            raise ValueError("escalate_reason 只在 needs_human=true 时出现")

    def with_escalation(self, reason: str) -> "FinalAnswer":
        return FinalAnswer(
            intent=self.intent,
            confidence=self.confidence,
            slots=dict(self.slots),
            reply_draft=self.reply_draft,
            needs_human=True,
            escalate_reason=reason,
            used_tools=list(self.used_tools),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "slots": dict(self.slots),
            "reply_draft": self.reply_draft,
            "needs_human": self.needs_human,
            "escalate_reason": self.escalate_reason,
            "used_tools": list(self.used_tools),
        }


@dataclass(frozen=True, slots=True)
class ModelDecision:
    """一次模型响应：要么请求工具，要么给最终答案，两者互斥。"""

    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    final: FinalAnswer | None = None

    def __post_init__(self) -> None:
        if self.final is not None and self.tool_calls:
            raise ValueError("tool_calls 与 final 互斥，不能同时出现")
        if self.final is None and not self.tool_calls:
            raise ValueError("模型响应必须包含 tool_calls 或 final")
        if len(self.tool_calls) > MAX_TOOL_CALLS_PER_STEP:
            raise ValueError(f"单次响应最多 {MAX_TOOL_CALLS_PER_STEP} 个工具调用")
        if self.final is not None and not isinstance(self.final, FinalAnswer):
            raise ValueError("final 必须是 FinalAnswer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "final": None if self.final is None else self.final.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """模型输入：只有脱敏后的消息与工具声明，不含 user_id / approved 等控制字段。"""

    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    step: int
    remaining_ms: int
    run_id: str


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """模型输出：``decision`` 结构对真实模型与 scripted 完全一致。"""

    decision: ModelDecision
    usage: Usage = field(default_factory=Usage)
    raw_text: str | None = None


@dataclass(frozen=True, slots=True)
class Turn:
    """一轮消息。role=tool 的轮次与工具调用一一对应。"""

    session_id: str
    idx: int
    role: str  # user | assistant | tool
    content: str
    usage: Usage | None = None
    created_at: str | None = None

    def content_json(self) -> dict[str, Any]:
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return {"text": self.content}


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """一次工具尝试的审计记录；失败也落库（ok=False 且带错误码）。"""

    session_id: str
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    error_code: str | None
    error_message: str | None
    duration_ms: int
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "ok": self.ok,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class Session:
    """一个 run（``session_id`` 即 docs 中的 ``run_id``）。"""

    session_id: str
    ticket_id: str
    user_id: str
    text: str
    order_id: str | None
    status: str
    stop_reason: str | None
    model_config: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    """循环的结构化返回。输入被拒时 ``run_id`` 为空且未建会话。"""

    status: RunStatus
    stop_reason: StopReason
    steps: int
    run_id: str | None = None
    answer: FinalAnswer | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "stop_reason": self.stop_reason.value,
            "steps": self.steps,
            "answer": None if self.answer is None else self.answer.to_dict(),
            "tool_calls": [record.to_dict() for record in self.tool_calls],
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class Evaluation:
    """一条逐例评估结果；本阶段只提供写入与按会话查询接口。"""

    report_id: str
    session_id: str
    dataset_kind: str  # development | holdout | drafts
    expected: dict[str, Any]
    actual: dict[str, Any]
    error: dict[str, Any] | None = None
    created_at: str | None = None
