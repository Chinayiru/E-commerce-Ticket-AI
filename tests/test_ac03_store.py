"""AC03 工具调用与状态落库：正常路径一次调用一条记录，失败也落库。"""

from __future__ import annotations

import sqlite3

from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.schemas import RunStatus


def _ticket(**overrides):
    payload = {
        "ticket_id": "AC03-1",
        "user_id": "U001",
        "text": "订单 O1001 我想退款，麻烦帮我看看能不能退。",
        "order_id": "O1001",
    }
    payload.update(overrides)
    return payload


def test_normal_path_writes_session_turns_and_one_tool_call(make_env):
    config, store = make_env()
    model = ScriptedModel([
        {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]},
        {"final": {
            "intent": "refund", "confidence": 0.9, "slots": {"order_id": "O1001"},
            "reply_draft": "已核实订单 O1001，可进入退款流程。",
            "needs_human": False, "used_tools": ["query_order"],
        }},
    ])
    result = ExecutionLoop(config, store, model, approval_gate=ScriptedApprovalGate(True)).run(_ticket())

    assert result.status is RunStatus.OK
    assert result.stop_reason.value == "finalized"
    assert result.steps == 2

    # sessions：一行，终态 ok
    trace = store.get_trace(result.run_id)
    assert trace is not None
    session = trace["session"]
    assert session.session_id == result.run_id
    assert session.status == "ok"
    assert session.stop_reason == "finalized"
    assert session.result["answer"]["intent"] == "refund"

    # tool_calls：恰好一条，成功，参数与返回都能追溯
    calls = trace["tool_calls"]
    assert len(calls) == 1
    call = calls[0]
    assert call.tool_name == "query_order"
    assert call.ok is True
    assert call.error_code is None
    assert call.arguments == {"order_id": "O1001"}
    assert call.duration_ms >= 0

    # turns：user / assistant / tool / assistant 四轮，idx 连续
    roles = [(turn.idx, turn.role) for turn in trace["turns"]]
    assert roles == [(0, "user"), (1, "assistant"), (2, "tool"), (3, "assistant")]


def test_tool_failure_is_recorded_with_error(make_env):
    config, store = make_env()
    model = ScriptedModel([
        {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O9999"}}]},
        {"final": {
            "intent": "refund", "confidence": 0.8, "slots": {"order_id": "O9999"},
            "reply_draft": "查不到该订单，已转人工核实。",
            "needs_human": True, "escalate_reason": "ORDER_NOT_FOUND",
            "used_tools": [],
        }},
    ])
    result = ExecutionLoop(config, store, model, approval_gate=ScriptedApprovalGate(True)).run(
        _ticket(ticket_id="AC03-2", order_id="O9999")
    )

    assert result.status is RunStatus.OK
    calls = {call.tool_name: call for call in store.list_tool_calls(result.run_id)}
    failed = calls["query_order"]
    assert failed.ok is False
    assert failed.error_code == "ORDER_NOT_FOUND"
    assert failed.error_message

    # 工具失败不抛异常，循环继续到最终答案
    assert result.answer is not None
    assert result.answer.needs_human is True


def test_tool_failure_survives_reload(make_env):
    config, store = make_env()
    model = ScriptedModel([
        {"tool_calls": [{"name": "check_logistics", "arguments": {"order_id": "O1001"}}]},
        {"final": {
            "intent": "shipping_urge", "confidence": 0.9, "slots": {},
            "reply_draft": "订单尚未发货，暂时没有物流信息。",
            "needs_human": False, "used_tools": ["check_logistics"],
        }},
    ])
    result = ExecutionLoop(config, store, model, approval_gate=ScriptedApprovalGate(True)).run(
        _ticket(ticket_id="AC03-3")
    )

    with sqlite3.connect(config.db_path) as conn:
        rows = conn.execute(
            "SELECT tool_name, ok, error_code FROM tool_calls WHERE session_id = ?",
            (result.run_id,),
        ).fetchall()
    assert rows == [("check_logistics", 0, "NOT_SHIPPED")]
