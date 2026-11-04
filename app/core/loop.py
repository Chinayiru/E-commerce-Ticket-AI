"""有界执行循环（DESIGN §7、IMPLEMENTATION §5）。

一次 ``run`` 的顺序是固定的，改顺序等于改产品语义：

    校验输入 → 登记 running → 预算/时限检查 → 请求模型 → 写 assistant turn
    → 预检（仅第一次响应）→ 逐个工具：参数校验 → 前置钩子 → 幂等缓存 → 执行 → 审计
    → 终局：事实核对 + 策略复核 → 保存草稿 → 收尾

三条边界必须显式可见（``max_steps`` / ``token_budget`` / ``wall_clock_s``），
任一条触发都返回结构化结果并标 ``degraded``，不抛异常给调用方。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from app.config import Config
from app.core import policy
from app.core.context import ContextBuilder, SessionSummary
from app.core.hooks import HookDecision, Hooks, build_default_hooks
from app.core.prompts import REPAIR_INSTRUCTION, get_prompt, prompt_hash
from app.llm.base import ApprovalGate, DenyAllApprovalGate, InvalidModelOutput, ModelError, ModelProvider
from app.schemas import (
    FinalAnswer,
    Intent,
    ModelRequest,
    RunResult,
    RunStatus,
    Session,
    StopReason,
    TicketIn,
    TicketValidationError,
    ToolCallRecord,
    ToolContext,
    ToolResult,
    Turn,
    Usage,
    args_digest,
    idempotency_key,
)
from app.store.db import Database, SessionConflict, StoreError
from app.tools.registry import ToolRegistry, default_registry

DEGRADED_DRAFT = (
    "本次处理因系统原因未能完成，已转人工客服接手，稍后会有同事联系您。"
    "本条不构成任何赔付、补偿或时效承诺。"
)
ESCALATION_DRAFT = (
    "已收到您的工单，当前情况需要人工客服进一步核实，已转人工处理。"
    "本条不构成任何赔付、补偿或时效承诺。"
)
#: 非正常终止 → escalate_reason 的映射（§9.1 第 1 条：stop_reason 大写）。
STOP_REASON_TO_ESCALATION = {
    StopReason.MAX_STEPS: "MAX_STEPS",
    StopReason.TOKEN_BUDGET: "TOKEN_BUDGET",
    StopReason.TIMEOUT: "TIMEOUT",
    StopReason.INVALID_OUTPUT: "INVALID_OUTPUT",
    StopReason.UPSTREAM_ERROR: "UPSTREAM_ERROR",
    StopReason.DUPLICATE_TICKET: "DUPLICATE_TICKET",
    StopReason.INPUT_INVALID: "INPUT_INVALID",
}


@dataclass
class _State:
    """单次运行的滚动状态；只在这里累加 usage / steps / 工具序列。"""

    run_id: str
    ticket: TicketIn
    steps: int = 0
    usage: Usage | None = None
    outcomes: list[Any] = field(default_factory=list)
    tool_summaries: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    next_idx: int = 1
    repaired: bool = False
    reasons: list[str] = field(default_factory=list)


class ExecutionLoop:
    """有界循环；模型、工具表、钩子、审批闸门都可替换。"""

    def __init__(
        self,
        config: Config,
        store: Database,
        model: ModelProvider,
        *,
        registry: ToolRegistry | None = None,
        approval_gate: ApprovalGate | None = None,
        hooks: Hooks | None = None,
        clock: Callable[[], float] = time.monotonic,
        listener: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._model = model
        self._registry = registry or default_registry()
        self._gate = approval_gate or DenyAllApprovalGate()
        self._hooks = hooks or build_default_hooks(config)
        self._clock = clock
        self._listener = listener
        self._context = ContextBuilder(config)
        self._prompt = get_prompt(config.prompt_version)

    # ------------------------------------------------------------------ public
    def run(
        self,
        payload: dict[str, Any],
        *,
        dataset_hash: str | None = None,
        source_run_id: str | None = None,
    ) -> RunResult:
        started = self._clock()
        try:
            ticket = TicketIn.from_payload(payload)
        except TicketValidationError as exc:
            return RunResult(
                status=RunStatus.REJECTED,
                stop_reason=StopReason.INPUT_INVALID,
                steps=0,
                run_id=None,
                answer=None,
                note=f"{exc.code}: {exc.message}",
                http_status=422,
                prompt_version=self._config.prompt_version,
            )

        try:
            run_id = self._store.create_session(
                ticket,
                self._config.as_mapping(),
                prompt_version=self._config.prompt_version,
                dataset_hash=dataset_hash,
                source_run_id=source_run_id,
            )
        except SessionConflict as exc:
            return RunResult(
                status=RunStatus.REJECTED,
                stop_reason=StopReason.DUPLICATE_TICKET,
                steps=0,
                run_id=None,
                answer=None,
                note=f"duplicate_ticket: {exc}",
                http_status=409,
                prompt_version=self._config.prompt_version,
            )

        state = _State(run_id=run_id, ticket=ticket)
        deadline = started + self._config.wall_clock_s
        self._record_user_turn(state)

        try:
            result = self._loop(state, deadline)
        except StoreError as exc:
            # 持久化是硬失败：清理 running 后把错误交给进程边界（API → 500）。
            self._best_effort_finish(state, RunStatus.DEGRADED, StopReason.UPSTREAM_ERROR, None, f"store_error: {exc}")
            raise

        latency_ms = max(0, int(round((self._clock() - started) * 1000)))
        return self._finish(
            state,
            result.answer,
            status=result.status,
            stop_reason=result.stop_reason,
            note=result.note,
            latency_ms=latency_ms,
            http_status=result.http_status,
        )

    # ------------------------------------------------------------------- inner
    def _loop(self, state: _State, deadline: float) -> "_Outcome":
        while True:
            exceeded = self._exceeded(state, deadline)
            if exceeded is not None:
                return self._degrade(state, exceeded)

            state.steps += 1
            try:
                response = self._model.complete(self._request(state, deadline))
            except InvalidModelOutput as exc:
                self._append_turn(
                    state,
                    role="assistant",
                    content=exc.raw_text or f"[invalid_output] {exc}",
                )
                if state.repaired:
                    return self._degrade(state, StopReason.INVALID_OUTPUT, note=str(exc))
                state.repaired = True
                state.history.append({"role": "user", "content": REPAIR_INSTRUCTION})
                continue
            except ModelError as exc:
                return self._degrade(state, StopReason.UPSTREAM_ERROR, note=str(exc))

            state.usage = response.usage if state.usage is None else state.usage + response.usage
            decision = response.decision
            raw = response.raw_text or json.dumps(decision.to_dict(), ensure_ascii=False)
            final = decision.final
            self._append_turn(
                state,
                role="assistant",
                content=raw,
                usage=response.usage,
                intent=None if final is None else final.intent.value,
                confidence=None if final is None else final.confidence,
                message_json=decision.to_dict(),
                request_hash=_request_hash(self._request(state, deadline)),
            )

            # 预检只发生在第一次模型响应上：命中即丢弃本次响应里的工具请求。
            self._emit("step", {"step": state.steps, "final": final is not None})
            if state.steps == 1:
                pre = policy.precheck(state.ticket, policy.classify_text(state.ticket.text))
                if pre.hit:
                    state.reasons.extend(pre.matched)
                    return self._finalize_with_reason(state, str(pre.reason))

            if final is not None:
                return self._finalize(state, final, deadline)

            blocked = self._run_tools(state, decision.tool_calls, deadline)
            if blocked is not None:
                return blocked
            if len(state.outcomes) > 3 * self._config.max_steps:
                return self._degrade(state, StopReason.MAX_STEPS, note="tool_calls_exceeded")

    # ------------------------------------------------------------------- tools
    def _run_tools(
        self, state: _State, calls: Sequence[Any], deadline: float
    ) -> "_Outcome | None":
        for call in calls:
            item = self._registry.get(call.name)
            if item is None:
                self._record_tool(
                    state,
                    call.name,
                    call.arguments,
                    ToolResult.failure("TOOL_UNAVAILABLE", f"未知工具：{call.name}"),
                    0,
                )
                self._append_tool_turn(state, call.name, ToolResult.failure("TOOL_UNAVAILABLE", f"未知工具：{call.name}"))
                continue

            decision: HookDecision = self._hooks.pre_tool(
                item.spec, call.arguments, run_id=state.run_id, step=state.steps
            )
            if not decision.allowed:
                # 第 2 优先级：钩子拦截 → 立即收尾为转人工，不执行、不占幂等键。
                self._record_tool(
                    state,
                    call.name,
                    call.arguments,
                    ToolResult.failure("APPROVAL_REQUIRED", decision.reason or "APPROVAL_REQUIRED"),
                    0,
                    approval_required=True,
                )
                return self._finalize_with_reason(state, "IRREVERSIBLE_ACTION")

            key = idempotency_key(state.ticket.ticket_id, call.name, call.arguments)
            cached = self._store.find_tool_call(state.run_id, idempotency_key=key)
            if cached is not None:
                result = ToolResult.success(cached.result or {})
                self._record_tool(
                    state, call.name, call.arguments, result, cached.duration_ms,
                    cached=True, idempotency_key=None, attempt_idx=2,
                )
                self._append_tool_turn(state, call.name, result)
                continue

            self._emit(
                "tool_call",
                {"step": state.steps, "name": call.name, "args_digest": args_digest(call.arguments)},
            )
            context = ToolContext(
                run_id=state.run_id,
                user_id=state.ticket.user_id,
                now=self._config.demo_now,
                config=self._config,
                store=self._store,
            )
            result, elapsed_ms = self._registry.execute(call.name, call.arguments, context)
            self._emit(
                "tool_result",
                {
                    "step": state.steps,
                    "name": call.name,
                    "ok": result.ok,
                    "error_code": None if result.error is None else result.error.code,
                    "duration_ms": elapsed_ms,
                },
            )
            self._hooks.post_tool(
                run_id=state.run_id,
                name=call.name,
                ok=result.ok,
                duration_ms=elapsed_ms,
                error_code=None if result.error is None else result.error.code,
            )
            self._record_tool(
                state, call.name, call.arguments, result, elapsed_ms,
                idempotency_key=key if result.ok else None,
            )
            self._append_tool_turn(state, call.name, result)
        return None

    # ---------------------------------------------------------------- finalize
    def _finalize(self, state: _State, answer: FinalAnswer, deadline: float) -> "_Outcome":
        facts = policy.PolicyFacts.from_outcomes(state.outcomes)
        outcome = policy.evaluate(
            answer,
            facts=facts,
            outcomes=state.outcomes,
            text=state.ticket.text,
            now=self._config.demo_now,
            refund_limit_cents=self._config.refund_auto_limit_cents,
            refund_window_days=self._config.refund_window_days,
        )
        state.reasons.extend(outcome.reasons)
        note = None
        if outcome.draft_replaced:
            note = "draft_replaced:DRAFT_RISK"
        if outcome.answer.needs_human:
            note = self._maybe_create_draft(state, outcome.answer) or note
        return _Outcome(
            answer=outcome.answer,
            status=RunStatus.OK,
            stop_reason=StopReason.FINALIZED,
            note=note,
        )

    def _finalize_with_reason(self, state: _State, reason: str) -> "_Outcome":
        """预检命中 / 钩子拦截：不执行工具，直接给固定安全草稿。"""
        draft = policy.safe_draft(reason) if reason != "IRREVERSIBLE_ACTION" else ESCALATION_DRAFT
        answer = FinalAnswer(
            intent=policy.classify_text(state.ticket.text),
            confidence=1.0 if reason != "IRREVERSIBLE_ACTION" else 0.0,
            slots={},
            reply_draft=draft,
            needs_human=True,
            escalate_reason=reason,
            used_tools=[item.name for item in state.outcomes],
        )
        state.reasons.append(reason)
        self._maybe_create_draft(state, answer)
        return _Outcome(
            answer=answer,
            status=RunStatus.OK,
            stop_reason=StopReason.FINALIZED,
            note=f"precheck:{reason}" if reason != "IRREVERSIBLE_ACTION" else "hook:APPROVAL_REQUIRED",
        )

    def _maybe_create_draft(self, state: _State, answer: FinalAnswer) -> str | None:
        """转人工草稿落库：不可逆，必须过审批闸门；拒绝不改变原因，只留痕。"""
        arguments = {"validated_answer": answer.to_dict(), "run_id": state.run_id}
        decision = self._gate.request_approval(
            tool_name="create_ticket_draft", arguments=arguments, run_id=state.run_id
        )
        if not decision.approved:
            return f"irreversible_action_denied: {decision.reason or 'rejected'}"
        result, elapsed_ms = self._registry.execute(
            "create_ticket_draft",
            arguments,
            ToolContext(
                run_id=state.run_id,
                user_id=state.ticket.user_id,
                now=self._config.demo_now,
                config=self._config,
                store=self._store,
            ),
        )
        self._record_tool(
            state, "create_ticket_draft", arguments, result, elapsed_ms,
            idempotency_key=None, attempt_idx=1,
        )
        return None if result.ok else f"draft_failed:{result.error.code if result.error else 'unknown'}"

    # ----------------------------------------------------------------- degrade
    def _degrade(self, state: _State, reason: StopReason, *, note: str | None = None) -> "_Outcome":
        answer = FinalAnswer(
            intent=policy.classify_text(state.ticket.text),
            confidence=0.0,
            slots={},
            reply_draft=DEGRADED_DRAFT,
            needs_human=True,
            escalate_reason=STOP_REASON_TO_ESCALATION.get(reason, str(reason).upper()),
            used_tools=[item.name for item in state.outcomes],
        )
        return _Outcome(
            answer=answer,
            status=RunStatus.DEGRADED,
            stop_reason=reason,
            note=note,
        )

    # ------------------------------------------------------------------ events
    def _emit(self, event: str, data: dict[str, Any]) -> None:
        """SSE 用的旁路通知：失败绝不影响主流程。"""
        if self._listener is None:
            return
        try:
            self._listener(event, data)
        except Exception:  # noqa: BLE001 - 观察者不能拖垮业务
            return None

    # ------------------------------------------------------------------ limits
    def _exceeded(self, state: _State, deadline: float) -> StopReason | None:
        # 顺序即优先级：墙钟优先（超时要优先记为 timeout），再 token，最后步数。
        if deadline - self._clock() <= 0:
            return StopReason.TIMEOUT
        if (state.usage.total_tokens if state.usage else 0) >= self._config.token_budget:
            return StopReason.TOKEN_BUDGET
        if state.steps >= self._config.max_steps:
            return StopReason.MAX_STEPS
        return None

    def _request(self, state: _State, deadline: float) -> ModelRequest:
        built = self._context.build(
            system_prompt=self._prompt,
            user_text=state.ticket.text,
            history=state.history,
            summary=state_summary(state),
        )
        return ModelRequest(
            messages=list(built.messages),
            tools=self._registry.schema_list(),
            step=state.steps,
            remaining_ms=max(0, int((deadline - self._clock()) * 1000)),
            run_id=state.run_id,
        )

    # ---------------------------------------------------------------- persist
    def _record_user_turn(self, state: _State) -> None:
        self._store.append_turn(
            Turn(
                session_id=state.run_id,
                idx=0,
                role="user",
                content=state.ticket.text,
                message_json=state.ticket.to_dict(),
            )
        )

    def _append_turn(self, state: _State, *, role: str, content: str, **kwargs: Any) -> None:
        self._store.append_turn(
            Turn(session_id=state.run_id, idx=state.next_idx, role=role, content=content, **kwargs)
        )
        state.next_idx += 1
        state.history.append({"role": role, "content": content})

    def _append_tool_turn(self, state: _State, name: str, result: ToolResult) -> None:
        self._append_turn(
            state,
            role="tool",
            content=json.dumps({"name": name, **result.to_dict()}, ensure_ascii=False),
        )

    def _record_tool(
        self,
        state: _State,
        name: str,
        arguments: dict[str, Any],
        result: ToolResult,
        duration_ms: int,
        *,
        cached: bool = False,
        approval_required: bool = False,
        idempotency_key: str | None = None,
        attempt_idx: int = 1,
    ) -> None:
        record = ToolCallRecord(
            session_id=state.run_id,
            call_id=f"{state.next_idx}-{attempt_idx}-{len(state.outcomes) + 1}",
            tool_name=name,
            arguments=dict(arguments),
            ok=result.ok,
            error_code=None if result.error is None else result.error.code,
            error_message=None if result.error is None else result.error.message,
            duration_ms=duration_ms,
            step=state.steps,
            cached=cached,
            approval_required=approval_required,
            attempt_idx=attempt_idx,
            idempotency_key=idempotency_key,
            result=result.data,
        )
        self._store.record_tool_call(record)
        state.outcomes.append(_Outcome(name=name, result=result))
        state.tool_summaries.append(record.summary())

    def _finish(
        self,
        state: _State,
        answer: FinalAnswer | None,
        *,
        status: RunStatus,
        stop_reason: StopReason,
        note: str | None,
        latency_ms: int,
        http_status: int = 200,
    ) -> RunResult:
        if answer is not None:
            self._store.save_draft(state.run_id, answer.to_dict())
        usage = state.usage or Usage(source="missing")
        cost = usage.cost_cny
        if cost is None:
            cost = None  # scripted / 估算用量不折成钱，避免与真实成本混排
        summary = state_summary(state)
        self._store.finish_session(
            state.run_id,
            status=status.value,
            stop_reason=stop_reason.value,
            result={
                "answer": None if answer is None else answer.to_dict(),
                "stop_reason": stop_reason.value,
                "steps": state.steps,
                "tool_calls": [item.name for item in state.outcomes],
                "reasons": list(dict.fromkeys(state.reasons)),
                "note": note,
            },
            needs_human=None if answer is None else answer.needs_human,
            cost_cny=None if answer is None else cost,
            latency_ms=latency_ms,
            summary=summary.to_dict(),
        )
        return RunResult(
            status=status,
            stop_reason=stop_reason,
            steps=state.steps,
            run_id=state.run_id,
            answer=answer,
            tool_calls=list(state.tool_summaries),
            usage=usage,
            latency_ms=latency_ms,
            note=note,
            http_status=http_status,
            prompt_version=self._config.prompt_version,
        )

    def _best_effort_finish(
        self,
        state: _State,
        status: RunStatus,
        stop_reason: StopReason,
        answer: FinalAnswer | None,
        note: str,
    ) -> None:
        try:
            self._store.finish_session(
                state.run_id,
                status=status.value,
                stop_reason=stop_reason.value,
                result={"note": note, "steps": state.steps},
                needs_human=True,
            )
        except StoreError:
            pass


@dataclass(frozen=True, slots=True)
class _Outcome:
    """内部结果载体：既表示“工具执行记录”，也表示“本轮终局”。"""

    name: str = ""
    result: ToolResult = field(default_factory=lambda: ToolResult.success({}))
    answer: FinalAnswer | None = None
    status: RunStatus = RunStatus.OK
    stop_reason: StopReason = StopReason.FINALIZED
    note: str | None = None
    http_status: int = 200

    def summary(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.result.ok}


def state_summary(state: _State) -> SessionSummary:
    """从工具序列与历史推出摘要（确定性，只依赖已有消息）。"""
    tools: list[str] = []
    for item in state.history:
        payload = _loads(str(item.get("content") or ""))
        if isinstance(payload, dict) and isinstance(payload.get("name"), str):
            if payload["name"] not in tools:
                tools.append(payload["name"])
    return SessionSummary(
        intent_history=[policy.classify_text(state.ticket.text).value],
        slots={"order_id": state.ticket.order_id} if state.ticket.order_id else {},
        tools_called=tools,
        last_decision="",
        open_questions=[],
        need_summary=len(state.history) > 0,
    )


def _loads(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _request_hash(request: ModelRequest) -> str:
    payload = json.dumps(
        {"messages": request.messages, "step": request.step}, ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


__all__ = [
    "DEGRADED_DRAFT",
    "ESCALATION_DRAFT",
    "ExecutionLoop",
    "STOP_REASON_TO_ESCALATION",
    "Session",
    "Usage",
    "Intent",
    "prompt_hash",
]
