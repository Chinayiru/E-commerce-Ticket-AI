"""数据契约：输入、意图、工具、轮次、会话、执行结果与模型协议。

字段与 ``app/store/db.py`` 的四张表一一对应（docs/IMPLEMENTATION.md §7）；
所有结构都是标准库 ``dataclass``，落库时统一序列化为 JSON 文本。

设计约定：
- 构造即校验（``__post_init__``），非法值在进入循环前就失败，不靠下游兜底；
- ``to_dict()`` 是唯一对外序列化出口，HTTP 响应、``result_json``、审计都复用它；
- 控制字段（``user_id`` / ``approved``）不进入 ``ModelRequest``，避免模型越权。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from app.config import Config

#: 工单文本长度（DESIGN §6.1）：1–2000 字符，去空白后非空。
MIN_TEXT_CHARS = 1
MAX_TEXT_CHARS = 2000
#: 标识字段长度（DESIGN §6.1）。
MAX_ID_CHARS = 64
#: 工单号格式：``O`` + 4 位数字。
TICKET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,40}$")
ORDER_ID_RE = re.compile(r"^O\d{4}$")
#: 单次响应最多 3 个工具调用（IMPLEMENTATION §5）。
MAX_TOOL_CALLS_PER_STEP = 3


class Intent(str, Enum):
    """意图标签，固定四类。"""

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
    """终止原因封闭集（DESIGN §6.2）；取值不得自造。"""

    FINALIZED = "finalized"
    MAX_STEPS = "max_steps"
    TOKEN_BUDGET = "token_budget"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    UPSTREAM_ERROR = "upstream_error"
    DUPLICATE_TICKET = "duplicate_ticket"
    INPUT_INVALID = "input_invalid"


class RunStatus(str, Enum):
    """运行状态三态封闭（DESIGN §6.2）：不允许“部分成功”。"""

    OK = "ok"
    DEGRADED = "degraded"
    REJECTED = "rejected"


class TicketValidationError(ValueError):
    """输入校验失败。``code`` / ``field`` 用于断言与日志定位。"""

    def __init__(self, code: str, field: str, message: str) -> None:
        self.code = code
        self.field = field
        self.message = message
        super().__init__(f"[{code}] {field}: {message}")


@dataclass(frozen=True, slots=True)
class TicketIn:
    """一条工单输入。``order_id`` 可为空；缺号由策略层判 0d，不在这里猜。"""

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
            # 对应 extra="forbid"：approved 之类的越权字段在这里就被拒。
            raise TicketValidationError(
                "unknown_field",
                unknown[0],
                f"不接受的字段：{unknown[0]}（避免静默丢弃或越权）",
            )

        for name in ("ticket_id", "user_id", "text"):
            if name not in payload or payload[name] is None:
                raise TicketValidationError("missing_field", name, "必填字段缺失")

        ticket_id = _as_text(payload["ticket_id"], "ticket_id")
        if not TICKET_ID_RE.match(ticket_id):
            raise TicketValidationError(
                "invalid_ticket_id", "ticket_id", "需满足 ^[A-Za-z0-9_-]{6,40}$"
            )
        user_id = _as_text(payload["user_id"], "user_id")
        if len(user_id) > MAX_ID_CHARS:
            raise TicketValidationError(
                "too_long", "user_id", f"长度不得超过 {MAX_ID_CHARS}"
            )

        text = _as_text(payload["text"], "text")
        if len(text) < MIN_TEXT_CHARS:
            raise TicketValidationError("empty_text", "text", "工单内容为空")
        if len(text) > MAX_TEXT_CHARS:
            raise TicketValidationError(
                "text_too_long", "text", f"最长 {MAX_TEXT_CHARS} 个字符，收到 {len(text)}"
            )

        order_id = payload.get("order_id")
        if order_id is not None:
            if not isinstance(order_id, str):
                raise TicketValidationError("invalid_type", "order_id", "应为字符串或 null")
            order_id = order_id.strip().upper() or None
            if order_id is not None and not ORDER_ID_RE.match(order_id):
                raise TicketValidationError(
                    "invalid_order_id", "order_id", "订单号格式应为 O + 4 位数字"
                )

        return cls(ticket_id=ticket_id, user_id=user_id, text=text, order_id=order_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "user_id": self.user_id,
            "text": self.text,
            "order_id": self.order_id,
        }


def _as_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TicketValidationError("invalid_type", field_name, "应为字符串")
    text = value.strip()
    if not text:
        raise TicketValidationError("empty_field", field_name, "不能为空")
    return text


@dataclass(frozen=True, slots=True)
class Usage:
    """token 计量与成本。缺计量时 ``source=missing`` 且 ``cost_cny=None``，不得填 0。"""

    input_tokens: int = 0
    output_tokens: int = 0
    source: str = "estimated"  # reported | estimated | missing | scripted | frozen
    cost_cny: float | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        sources = {self.source, other.source}
        if "missing" in sources:
            source = "missing"
        elif len(sources) == 1:
            source = self.source  # 同源累加保留来源（scripted 数字不得标成 reported）
        elif sources == {"reported", "scripted"}:
            source = "mixed"  # 混排必须显式暴露，供报告分流
        else:
            source = "estimated"
        if self.cost_cny is None or other.cost_cny is None:
            cost: float | None = None
        else:
            cost = round(self.cost_cny + other.cost_cny, 6)
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            source=source,
            cost_cny=cost,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "source": self.source,
            "cost_cny": self.cost_cny,
        }


@dataclass(frozen=True, slots=True)
class ToolError:
    """结构化工具错误。``code`` 属封闭集，``hint`` 面向下一步动作。"""

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
    """不可逆操作前的转人工确认结果；结构对 scripted 与真实审批一致。"""

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

    def args_digest(self) -> str:
        return args_digest(self.arguments)


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
    """模型最终输出。``needs_human`` / ``escalate_reason`` 由程序复核后覆盖。"""

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

    def with_draft(self, reply_draft: str) -> "FinalAnswer":
        return FinalAnswer(
            intent=self.intent,
            confidence=self.confidence,
            slots=dict(self.slots),
            reply_draft=reply_draft,
            needs_human=self.needs_human,
            escalate_reason=self.escalate_reason,
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
        # 允许构造时直接给 dict（脚本/测试常用），统一成 ToolCallRequest。
        calls = [
            call
            if isinstance(call, ToolCallRequest)
            else ToolCallRequest(name=str(call["name"]), arguments=dict(call.get("arguments") or {}))
            for call in self.tool_calls
        ]
        object.__setattr__(self, "tool_calls", calls)
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

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ModelDecision":
        """把模型 JSON 转成决策；结构非法即 ``ValueError``（交给 invalid_output）。"""
        if not isinstance(payload, Mapping):
            raise ValueError("模型输出必须是 JSON 对象")
        calls_raw = payload.get("tool_calls") or []
        final_raw = payload.get("final")
        if not isinstance(calls_raw, list):
            raise ValueError("tool_calls 必须是数组")
        calls = []
        for item in calls_raw:
            if not isinstance(item, Mapping):
                raise ValueError("tool_calls 的元素必须是对象")
            name = item.get("name")
            arguments = item.get("arguments", {})
            if not isinstance(arguments, Mapping):
                raise ValueError("tool_call.arguments 必须是对象")
            calls.append(ToolCallRequest(name=str(name), arguments=dict(arguments)))
        final = None
        if final_raw is not None:
            if not isinstance(final_raw, Mapping):
                raise ValueError("final 必须是对象")
            used_tools = final_raw.get("used_tools") or []
            if not isinstance(used_tools, list):
                raise ValueError("final.used_tools 必须是数组")
            final = FinalAnswer(
                intent=Intent.parse(final_raw.get("intent", "")),
                confidence=float(final_raw.get("confidence", 0) or 0),
                slots=dict(final_raw.get("slots") or {}),
                reply_draft=str(final_raw.get("reply_draft") or ""),
                needs_human=bool(final_raw.get("needs_human", False)),
                escalate_reason=(
                    None
                    if final_raw.get("escalate_reason") in (None, "", "null")
                    else str(final_raw["escalate_reason"])
                ),
                used_tools=[str(item) for item in used_tools],
            )
        return cls(tool_calls=calls, final=final)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """模型输入：只有脱敏消息与工具声明，不含 user_id / approved 等控制字段。"""

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
    """一轮消息；``role=tool`` 与工具调用一一对应。"""

    session_id: str
    idx: int
    role: str  # user | assistant | tool
    content: str
    usage: Usage | None = None
    intent: str | None = None
    confidence: float | None = None
    message_json: dict[str, Any] | None = None
    request_hash: str | None = None
    created_at: str | None = None

    def content_json(self) -> dict[str, Any]:
        if self.message_json is not None:
            return dict(self.message_json)
        try:
            loaded = json.loads(self.content)
        except json.JSONDecodeError:
            return {"text": self.content}
        return loaded if isinstance(loaded, dict) else {"text": self.content}

    def to_dict(self) -> dict[str, Any]:
        return {
            "idx": self.idx,
            "role": self.role,
            "content": self.content,
            "usage": None if self.usage is None else self.usage.to_dict(),
            "intent": self.intent,
            "confidence": self.confidence,
            "message_json": self.message_json,
            "request_hash": self.request_hash,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """一次工具尝试的审计记录；失败、被拦截、缓存命中都落库。"""

    session_id: str
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    error_code: str | None
    error_message: str | None
    duration_ms: int
    step: int = 0
    cached: bool = False
    approval_required: bool = False
    attempt_idx: int = 0
    idempotency_key: str | None = None
    result: dict[str, Any] | None = None
    created_at: str | None = None

    def args_digest(self) -> str:
        return args_digest(self.arguments)

    def summary(self) -> dict[str, Any]:
        """``RunResult.tool_calls`` 的对外摘要（DESIGN §6.2）。"""
        return {
            "step": self.step,
            "name": self.tool_name,
            "ok": self.ok,
            "latency_ms": self.duration_ms,
            "error_code": self.error_code,
            "cached": self.cached,
            "approval_required": self.approval_required,
            "args_digest": self.args_digest(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "ok": self.ok,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "step": self.step,
            "cached": self.cached,
            "approval_required": self.approval_required,
            "attempt_idx": self.attempt_idx,
            "idempotency_key": self.idempotency_key,
            "result": self.result,
            **self.summary(),
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
    prompt_version: str | None = None
    needs_human: bool | None = None
    cost_cny: float | None = None
    latency_ms: int | None = None
    summary: dict[str, Any] | None = None
    draft_text: str | None = None
    model_config: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    dataset_hash: str | None = None
    source_run_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.session_id,
            "ticket_id": self.ticket_id,
            "user_id": self.user_id,
            "text": self.text,
            "order_id": self.order_id,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "prompt_version": self.prompt_version,
            "needs_human": self.needs_human,
            "cost_cny": self.cost_cny,
            "latency_ms": self.latency_ms,
            "summary": self.summary,
            "draft_text": self.draft_text,
            "model_config": self.model_config,
            "result": self.result,
            "dataset_hash": self.dataset_hash,
            "source_run_id": self.source_run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class RunResult:
    """循环的结构化返回。输入被拒或重复工单时 ``run_id`` 为空且未建会话。"""

    status: RunStatus
    stop_reason: StopReason
    steps: int
    run_id: str | None = None
    answer: FinalAnswer | None = None
    #: 序列化后的工具调用摘要（ToolCallRecord.summary()），供 HTTP/报告直接使用。
    tool_calls: list[Any] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    prompt_version: str | None = None
    note: str | None = None
    http_status: int = 200

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "stop_reason": self.stop_reason.value,
            "steps": self.steps,
            "answer": None if self.answer is None else self.answer.to_dict(),
            "tool_calls": [
                record.summary() if hasattr(record, "summary") else dict(record)
                for record in self.tool_calls
            ],
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
            "prompt_version": self.prompt_version,
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class Evaluation:
    """一条逐例评估结果（四表之一，不许建第五张表）。"""

    report_id: str
    session_id: str
    dataset_kind: str  # development | holdout | drafts
    expected: dict[str, Any]
    actual: dict[str, Any]
    case_id: str | None = None
    prompt_version: str | None = None
    intent_gold: str | None = None
    intent_pred: str | None = None
    intent_ok: bool | None = None
    tools_ok: bool | None = None
    args_ok: bool | None = None
    draft_grade: str | None = None
    cost_cny: float | None = None
    latency_ms: int | None = None
    error: dict[str, Any] | None = None
    created_at: str | None = None


def args_digest(arguments: Mapping[str, Any]) -> str:
    """参数摘要：稳定排序后取 sha1 前 12 位，供报告与审计比对，不泄露原文。"""
    canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]


def idempotency_key(ticket_id: str, tool_name: str, arguments: Mapping[str, Any]) -> str:
    """幂等键 = sha1(ticket_id | tool_name | canonical_args)，作用域单 run（DESIGN §9.2）。"""
    canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    raw = f"{ticket_id}|{tool_name}|{canonical}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
