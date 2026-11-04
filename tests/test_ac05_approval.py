"""AC05 不可逆操作的转人工分支：不确认则不调用，确认则落库。"""

from __future__ import annotations

from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel

TICKET = {
    "ticket_id": "AC05-1",
    "user_id": "U001",
    "text": "订单 O1002 已经发货了，但地址写错了，能不能改？",
    "order_id": "O1002",
}
ESCALATED_FINAL = {
    "final": {
        "intent": "address_change",
        "confidence": 0.7,
        "slots": {"order_id": "O1002"},
        "reply_draft": "订单已发货，改地址需要人工介入拦截包裹。",
        "needs_human": True,
        "escalate_reason": "ADDRESS_AFTER_SHIP",
        "used_tools": [],
    }
}


def test_denied_approval_does_not_call_irreversible_tool(make_env):
    config, store = make_env()
    gate = ScriptedApprovalGate(False)
    result = ExecutionLoop(config, store, ScriptedModel([dict(ESCALATED_FINAL)]), approval_gate=gate).run(
        dict(TICKET, ticket_id="AC05-DENY")
    )

    # 工具没有被调用：tool_calls 表为空，结果仍是转人工
    assert result.tool_calls == []
    assert store.list_tool_calls(result.run_id) == []
    assert result.answer.needs_human is True
    assert result.answer.escalate_reason == "APPROVAL_REQUIRED"
    assert result.stop_reason.value == "finalized"
    assert "denied" in (result.note or "")

    # 闸门确实被问过，且问的是不可逆工具
    assert len(gate.calls) == 1
    assert gate.calls[0]["tool_name"] == "create_ticket_draft"


def test_approved_approval_calls_tool_and_persists(make_env):
    config, store = make_env()
    gate = ScriptedApprovalGate(True)
    result = ExecutionLoop(config, store, ScriptedModel([dict(ESCALATED_FINAL)]), approval_gate=gate).run(
        dict(TICKET, ticket_id="AC05-APPROVE")
    )

    calls = store.list_tool_calls(result.run_id)
    assert [call.tool_name for call in calls] == ["create_ticket_draft"]
    assert calls[0].ok is True
    assert gate.calls[0]["tool_name"] == "create_ticket_draft"

    session = store.get_session(result.run_id)
    assert session.status == "ok"
    assert session.result["answer"]["needs_human"] is True
    assert session.result["answer"]["reply_draft"]


def test_model_requested_irreversible_call_is_gated(make_env):
    config, store = make_env()
    gate = ScriptedApprovalGate(False)
    script = [
        {"tool_calls": [{"name": "create_ticket_draft", "arguments": {"run_id": "spoofed"}}]},
        {"final": {
            "intent": "refund", "confidence": 0.5, "slots": {},
            "reply_draft": "已转人工。", "needs_human": True,
            "escalate_reason": "APPROVAL_REQUIRED",
        }},
    ]
    result = ExecutionLoop(config, store, ScriptedModel(script), approval_gate=gate).run(
        dict(TICKET, ticket_id="AC05-SPOOF", order_id="O1001")
    )

    assert result.tool_calls == []
    assert result.answer.escalate_reason == "APPROVAL_REQUIRED"
    assert store.list_tool_calls(result.run_id) == []
    # 脚本第一步就被拦下，没有继续走第二步
    assert result.steps == 1
    assert gate.calls[0]["tool_name"] == "create_ticket_draft"
