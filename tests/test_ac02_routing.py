"""AC02 输入校验与意图路由：24 条全部出标签，非法输入被拒且原因明确。"""

from __future__ import annotations

import json

import pytest

from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedModel
from app.schemas import Intent, RunStatus
from tests.helpers import CASES_PATH, run_case


def _cases() -> list[dict]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert payload["count"] == 24
    return payload["cases"]


def test_all_24_cases_get_an_intent_label(make_env):
    config, store = make_env()
    cases = _cases()
    assert len(cases) == 24

    seen = set()
    for case in cases:
        result, _, _ = run_case(config, store, case)
        assert result.status is RunStatus.OK, (case["case_id"], result.note)
        assert result.answer is not None, case["case_id"]
        assert result.answer.intent is Intent.parse(case["intent"]), case["case_id"]
        seen.add(result.answer.intent.value)

    assert seen == {"refund", "address_change", "shipping_urge", "other"}


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"ticket_id": "T-1", "user_id": "U001", "text": "   "}, "empty_text"),
        ({"ticket_id": "T-2", "user_id": "U001", "text": "退款" * 400}, "text_too_long"),
        ({"ticket_id": "T-3", "user_id": "U001"}, "missing_field"),
        ({"ticket_id": "T-4", "user_id": "U001", "text": "我要退款，请处理", "approved": True}, "unknown_field"),
        ({"ticket_id": "T-5", "user_id": "U001", "text": "我要退款，请处理", "order_id": "O 1001"}, "invalid_order_id"),
        ({"ticket_id": "", "user_id": "U001", "text": "我要退款，请处理"}, "empty_field"),
        ("不是对象", "invalid_type"),
    ],
)
def test_invalid_input_is_rejected_with_explicit_reason(make_env, payload, code):
    config, store = make_env()
    loop = ExecutionLoop(config, store, ScriptedModel([{"final": {
        "intent": "other", "confidence": 0.5, "reply_draft": "草稿", "needs_human": False,
    }}]))
    result = loop.run(payload)
    assert result.status is RunStatus.REJECTED
    assert result.stop_reason.value == "invalid_input"
    assert result.run_id is None
    assert code in (result.note or "")


def test_rejected_input_leaves_no_session_row(make_env):
    config, store = make_env()
    loop = ExecutionLoop(config, store, ScriptedModel([{"final": {
        "intent": "other", "confidence": 0.5, "reply_draft": "草稿", "needs_human": False,
    }}]))
    result = loop.run({"ticket_id": "T-9", "user_id": "U001", "text": ""})
    assert result.run_id is None
    import sqlite3

    with sqlite3.connect(config.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 0
