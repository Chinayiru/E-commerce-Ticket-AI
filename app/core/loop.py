"""有界执行循环：校验输入 → 选工具 → 调工具 → 判断是否继续。

三条硬约束在这里显式实现，全部可配置，任一触发都返回结构化结果而不抛异常：
    * 最大步数     —— 一次 Provider 请求算一步；
    * token 预算   —— 累计用量触顶即停；
    * 墙钟超时     —— 由注入的 ``clock`` 计量，测试可替换。

模型与审批都只通过 ``app.llm.base`` 的 Protocol 交互，因此 scripted 与真实
Provider 可互换，循环本身不需要分叉。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

from app.config import Config
from app.llm.base import ApprovalGate, DenyAllApprovalGate, ModelProvider
from app.schemas import (
    ApprovalDecision,
    FinalAnswer,
    Intent,
    ModelRequest,
    RunResult,
    RunStatus,
    StopReason,
    TicketIn,
    TicketValidationError,
    ToolCallRecord,
    ToolContext,
    ToolResult,
    Turn,
    Usage,
)
from app.store.db import StoreError
from app.tools.registry import default_registry

PROMPT_VERSION = "w1-skeleton-1"

SYSTEM_PROMPT = (
    "你是电商售后工单处理助手。意图标签只有四类：refund（退款）、address_change（改地址）、"
    "shipping_urge（催发货）、other（其他）。需要订单事实时先调用工具，不要臆造金额、物流或政策。"
    "确认信息充分后给出最终答复；无法确定或涉及权限、投诉时把 needs_human 置为 true。"
)

_DEGRADED_DRAFT = (
    "本次自动处理未能在限制内完成，已转人工复核。"
    "当前草稿不构成任何退款、改址或补发承诺，请以人工客服的最终答复为准。"
)

_LIMIT_REASONS = {
    StopReason.MAX_STEPS: "STEP_LIMIT",
    StopReason.TOKEN_BUDGET: "TOKEN_BUDGET",
    StopReason.TIMEOUT: "TIMEOUT",
    StopReason.UPSTREAM_ERROR: "UPSTREAM_ERROR",
}


@dataclass
class _ToolOutcome:
    """本次 run 内一次工具调用的结果视图，供策略复核使用。"""

    name: str
    arguments: dict[str, Any]
    result: ToolResult
    record: ToolCallRecord


@dataclass
class _RunState:
    run_id: str
    ticket: TicketIn
    started_at: float
    deadline: float
    steps: int = 0
    usage: Usage = field(default_factory=lambda: Usage(source="scripted"))
    turns: int = 0
    messages: list[dict[str, Any]] = field(default_factory=list)
    outcomes: list[_ToolOutcome] = field(default_factory=list)
    records: list[ToolCallRecord] = field(default_factory=list)
    last_intent: Intent = Intent.OTHER


class ExecutionLoop:
    """一次 ``run`` 处理一条工单；循环内部逐步落库，不做批量补写。"""

    def __init__(
        self,
        config: Config,
        store: Any,
        model: ModelProvider,
        *,
        registry: Any = None,
        approval_gate: ApprovalGate | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self.store = store
        self.model = model
        self.registry = registry if registry is not None else default_registry()
        self.approval_gate = approval_gate or DenyAllApprovalGate()
        self.clock = clock

    # ------------------------------------------------------------------- public
    def run(self, payload: Mapping[str, Any]) -> RunResult:
        started = self.clock()
        try:
            ticket = TicketIn.from_payload(payload)
        except TicketValidationError as exc:
            # 输入被拒时不建会话，避免脏数据进入 trace。
            return RunResult(
                status=RunStatus.REJECTED,
                stop_reason=StopReason.INVALID_INPUT,
                steps=0,
                latency_ms=self._elapsed_ms(started),
                note=str(exc),
            )

        state = _RunState(
            run_id=self.store.create_session(ticket, self.config.as_mapping()),
            ticket=ticket,
            started_at=started,
            deadline=started + self.config.wall_clock_s,
        )
        state.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ticket.text},
        ]
        self._write_turn(state, role="user", content=ticket.text)

        while state.steps < self.config.max_steps:
            over, stop, note = self._check_limits(state)
            if over:
                return self._degrade(state, stop, note)

            state.steps += 1
            request = ModelRequest(
                messages=list(state.messages),
                tools=self.registry.schema_list(),
                step=state.steps,
                remaining_ms=max(0, int((state.deadline - self.clock()) * 1000)),
                run_id=state.run_id,
            )
            try:
                response = self.model.complete(request)
            except Exception as exc:  # 上游失败不向调用方抛，降级为结构化结果
                return self._degrade(
                    state,
                    StopReason.UPSTREAM_ERROR,
                    f"模型调用失败：{type(exc).__name__}: {exc}",
                )

            state.usage = state.usage + response.usage
            decision = response.decision
            self._write_turn(
                state,
                role="assistant",
                content=json.dumps(decision.to_dict(), ensure_ascii=False),
                usage=response.usage,
            )
            state.messages.append(
                {"role": "assistant", "content": json.dumps(decision.to_dict(), ensure_ascii=False)}
            )

            if decision.final is not None:
                state.last_intent = decision.final.intent
                return self._finalize(state, decision.final)

            stop = self._run_tool_calls(state, decision.tool_calls)
            if stop is not None:
                return stop

        return self._degrade(state, StopReason.MAX_STEPS, f"达到最大步数 {self.config.max_steps}")

    # -------------------------------------------------------------------- steps
    def _check_limits(self, state: _RunState) -> tuple[bool, StopReason, str]:
        if state.usage.total_tokens >= self.config.token_budget:
            return True, StopReason.TOKEN_BUDGET, (
                f"累计 token {state.usage.total_tokens} 已达预算 {self.config.token_budget}"
            )
        remaining = state.deadline - self.clock()
        if remaining <= 0:
            return True, StopReason.TIMEOUT, (
                f"墙钟超时：预算 {self.config.wall_clock_s}s，剩余 {remaining:.3f}s"
            )
        return False, StopReason.FINALIZED, ""

    def _run_tool_calls(self, state: _RunState, tool_calls: Sequence[Any]) -> RunResult | None:
        for call in tool_calls:
            if self.registry.get(call.name) is None:
                # 未知工具同样落一条失败记录，便于审计模型乱编工具名。
                outcome = self._execute(state, call.name, dict(call.arguments))
            else:
                if self.registry.is_irreversible(call.name):
                    decision = self._ask_approval(state, call)
                    if not decision.approved:
                        answer = self._escalated_answer(
                            intent=self._last_intent(state),
                            reason="APPROVAL_REQUIRED",
                        )
                        return self._finish(state, answer, RunStatus.OK, StopReason.FINALIZED,
                                            note="irreversible_action_denied")
                outcome = self._execute(state, call.name, dict(call.arguments))

            state.messages.append(
                {
                    "role": "tool",
                    "name": outcome.name,
                    "content": json.dumps(outcome.result.to_dict(), ensure_ascii=False),
                }
            )
            if not outcome.result.ok:
                error = outcome.result.error
                if error is not None and error.code == "STORE_WRITE_FAILED":
                    # 落库失败属于进程级故障，不伪装成可重试的工具错误。
                    raise StoreError("tool:" + outcome.name, error.message)
        return None

    def _execute(self, state: _RunState, name: str, arguments: dict[str, Any]) -> _ToolOutcome:
        context = ToolContext(
            run_id=state.run_id,
            user_id=state.ticket.user_id,
            now=self.config.demo_now,
            config=self.config,
            store=self.store,
        )
        result, duration_ms = self.registry.execute(name, arguments, context)
        record = ToolCallRecord(
            session_id=state.run_id,
            call_id=uuid.uuid4().hex,
            tool_name=name,
            arguments=dict(arguments),
            ok=result.ok,
            error_code=None if result.error is None else result.error.code,
            error_message=None if result.error is None else result.error.message,
            duration_ms=duration_ms,
            created_at=_now_iso(),
        )
        self.store.record_tool_call(record)  # 每次调用即落库，不留到最后补写
        self._write_turn(
            state,
            role="tool",
            content=json.dumps({"tool": name, "result": result.to_dict()}, ensure_ascii=False),
        )
        outcome = _ToolOutcome(name=name, arguments=dict(arguments), result=result, record=record)
        state.outcomes.append(outcome)
        state.records.append(record)
        return outcome

    # ----------------------------------------------------------------- finalize
    def _finalize(self, state: _RunState, answer: FinalAnswer) -> RunResult:
        answer = self._apply_policy(answer, state)
        self.store.save_draft(state.run_id, answer.to_dict())

        note = None
        if answer.needs_human:
            gate_decision = self._ask_approval(
                state,
                _DraftCall(
                    name="create_ticket_draft",
                    arguments={"run_id": state.run_id, "validated_answer": answer.to_dict()},
                ),
            )
            if not gate_decision.approved:
                answer = answer.with_escalation("APPROVAL_REQUIRED")
                self.store.save_draft(state.run_id, answer.to_dict())
                note = "irreversible_action_denied: " + (gate_decision.reason or "")
            else:
                outcome = self._execute(
                    state,
                    "create_ticket_draft",
                    {"run_id": state.run_id, "validated_answer": answer.to_dict()},
                )
                if not outcome.result.ok:
                    error = outcome.result.error
                    if error is not None and error.code == "STORE_WRITE_FAILED":
                        raise StoreError("create_ticket_draft", error.message)
                    answer = answer.with_escalation(
                        error.code if error is not None else "TOOL_FAILED"
                    )
                    note = "create_ticket_draft failed"

        return self._finish(state, answer, RunStatus.OK, StopReason.FINALIZED, note=note)

    def _apply_policy(self, answer: FinalAnswer, state: _RunState) -> FinalAnswer:
        """程序侧窄规则：只做“升级为转人工”，不替模型改事实、不改金额。"""
        if answer.needs_human:
            return answer
        for outcome in state.outcomes:
            error = outcome.result.error
            if error is not None and error.code == "ORDER_NOT_FOUND":
                return answer.with_escalation("ORDER_NOT_FOUND")
            if outcome.name != "refund_preview":
                continue
            if error is not None and error.code == "REFUND_NOT_ALLOWED":
                return answer.with_escalation("REFUND_NOT_ALLOWED")
            data = outcome.result.data or {}
            if data.get("allowed") is False:
                return answer.with_escalation(str(data.get("policy_reason") or "REFUND_NOT_ALLOWED"))
        if answer.intent is Intent.OTHER and answer.confidence < 0.5:
            return answer.with_escalation("LOW_CONFIDENCE")
        return answer

    # ---------------------------------------------------------------- terminate
    def _degrade(self, state: _RunState, stop: StopReason, note: str) -> RunResult:
        answer = self._escalated_answer(
            intent=self._last_intent(state),
            reason=_LIMIT_REASONS.get(stop, "STEP_LIMIT"),
        )
        return self._finish(state, answer, RunStatus.DEGRADED, stop, note=note)

    def _finish(
        self,
        state: _RunState,
        answer: FinalAnswer,
        status: RunStatus,
        stop: StopReason,
        *,
        note: str | None = None,
    ) -> RunResult:
        result = {
            "answer": answer.to_dict(),
            "stop_reason": stop.value,
            "steps": state.steps,
            "tool_calls": [record.tool_name for record in state.records],
            "note": note,
        }
        self.store.finish_session(
            state.run_id, status=status.value, stop_reason=stop.value, result=result
        )
        return RunResult(
            status=status,
            stop_reason=stop,
            steps=state.steps,
            run_id=state.run_id,
            answer=answer,
            tool_calls=list(state.records),
            usage=state.usage,
            latency_ms=self._elapsed_ms(state.started_at),
            note=note,
        )

    def _ask_approval(self, state: _RunState, call: Any) -> ApprovalDecision:
        return self.approval_gate.request_approval(
            tool_name=call.name,
            arguments=dict(call.arguments),
            run_id=state.run_id,
        )

    def _escalated_answer(self, intent: Intent, reason: str) -> FinalAnswer:
        return FinalAnswer(
            intent=intent,
            confidence=0.0,
            slots={},
            reply_draft=_DEGRADED_DRAFT,
            needs_human=True,
            escalate_reason=reason,
            used_tools=[],
        )

    # ------------------------------------------------------------------- helpers
    def _write_turn(
        self,
        state: _RunState,
        *,
        role: str,
        content: str,
        usage: Usage | None = None,
    ) -> None:
        self.store.append_turn(
            Turn(
                session_id=state.run_id,
                idx=state.turns,
                role=role,
                content=content,
                usage=usage,
                created_at=_now_iso(),
            )
        )
        state.turns += 1

    def _last_intent(self, state: _RunState) -> Intent:
        """降级时沿用模型已给出的意图；尚未给出最终答案则记 other。"""
        return state.last_intent

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int(round((self.clock() - started) * 1000)))


@dataclass(frozen=True, slots=True)
class _DraftCall:
    name: str
    arguments: dict[str, Any]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
