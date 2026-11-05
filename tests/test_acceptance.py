"""验收测试：逐条对应 docs 的 AC01–AC21（DESIGN §12 / IMPLEMENTATION §12）。

一条 AC 一个测试函数，函数名带编号，失败时能直接对上文档条目。
所有断言只看“可观察行为”：RunResult、库里的四张表、HTTP 响应——不看内部实现细节。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config import load_config
from app.core.loop import DEGRADED_DRAFT, ExecutionLoop
from app.eval.datasets import load_eval_cases, load_holdout
from app.eval.scripted_cases import run_case, steps_for
from app.eval import runner
from app.eval.metrics import tool_names
from app.llm.base import InvalidModelOutput, ModelError, UpstreamError
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.schemas import ModelDecision, ModelResponse, Usage
from app.store.db import Database

EVAL = {row["case_id"]: row for row in load_eval_cases().rows}


def case(case_id: str) -> dict[str, Any]:
    return dict(EVAL[case_id])


def make(overrides: dict[str, Any] | None = None):
    settings = {"db_path": ":memory:"}
    settings.update(overrides or {})
    config = load_config(settings, env={})
    return config, Database(config.db_path)


def run(store: Database, payload: dict[str, Any], steps: list[dict[str, Any]], **kwargs: Any):
    config = kwargs.pop("config", None) or load_config({"db_path": str(store.path)}, env={})
    gate = kwargs.pop("gate", ScriptedApprovalGate(True))
    model = kwargs.pop("model", ScriptedModel(steps))
    return ExecutionLoop(config, store, model, approval_gate=gate, **kwargs).run(payload)


def payload(case_id: str, **extra: Any) -> dict[str, Any]:
    row = case(case_id)
    body = {
        "ticket_id": row["case_id"],
        "user_id": row["user_id"],
        "text": row["text"],
        "order_id": row["order_id"],
    }
    body.update(extra)
    return body


class FakeClock:
    """按预设序列返回时间；用于精确触发 wall_clock 超时。"""

    def __init__(self, values: list[float]) -> None:
        self.values = values
        self.index = 0

    def __call__(self) -> float:
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


class BoomProvider:
    """固定抛错的 Provider，用来验证上游失败语义。"""

    provider_name = "boom"

    def __init__(self, error: Exception) -> None:
        self.error = error

    def complete(self, request: Any) -> ModelResponse:  # noqa: ARG002
        raise self.error


class NoUsageProvider:
    """返回合法决策但不报 usage：用来验证“缺失即 missing”的口径。"""

    provider_name = "no-usage"

    def complete(self, request: Any) -> ModelResponse:  # noqa: ARG002
        return ModelResponse(
            decision=ModelDecision(tool_calls=[{"name": "query_order", "arguments": {"order_id": "O1001"}}]),
            usage=Usage(0, 0, "missing"),
            raw_text="{}",
        )


class SlowProvider:
    provider_name = "slow"

    def __init__(self, delay: float = 0.3) -> None:
        self.delay = delay

    def complete(self, request: Any) -> ModelResponse:  # noqa: ARG002
        time.sleep(self.delay)
        return ModelResponse(
            decision=ModelDecision(final=None, tool_calls=[{"name": "query_order", "arguments": {"order_id": "O1001"}}]),
            usage=Usage(10, 10, "reported"),
            raw_text="{}",
        )


# ---------------------------------------------------------------- AC01
def test_ac01_happy_refund_path(make_env):
    config, store = make_env()
    out = run_case(config, case("dev-refund-simple-1"), store=store).result
    assert out.status.value == "ok"
    assert out.stop_reason.value == "finalized"
    assert out.answer.intent.value == "refund"
    assert out.answer.needs_human is False
    assert {item["name"] for item in out.tool_calls} == {"query_order", "refund_preview"}
    assert "58.00" in out.answer.reply_draft
    assert "refund_submit" not in {item["name"] for item in out.tool_calls}


# ---------------------------------------------------------------- AC02
def test_ac02_cross_user_order_is_not_found(make_env):
    config, store = make_env()
    out = run_case(config, case("dev-other-complex-1"), store=store).result
    assert out.answer.escalate_reason == "ORDER_NOT_FOUND"
    assert out.answer.needs_human is True
    # 不泄露他人信息：草稿里不能出现其他用户或金额
    assert "U002" not in out.answer.reply_draft


# ---------------------------------------------------------------- AC03
def test_ac03_approved_field_and_irreversible_actions(make_env):
    config, store = make_env()
    out = run_case(
        config,
        case("dev-refund-simple-1"),
        store=store,
        steps=[
            {"tool_calls": [{"name": "refund_submit", "arguments": {"order_id": "O1001"}}]},
        ],
    ).result
    assert out.answer.escalate_reason == "IRREVERSIBLE_ACTION"
    assert out.answer.needs_human is True
    calls = store.list_tool_calls(out.run_id)
    submit = [call for call in calls if call.tool_name == "refund_submit"]
    assert [call.error_code for call in submit] == ["APPROVAL_REQUIRED"]
    assert all(call.ok is False for call in submit)

    # approved 不是合法输入字段：在入口就被拒，不进循环
    rejected = run(
        store,
        {**payload("dev-refund-simple-2"), "approved": True},
        steps=[{"final": {"intent": "refund", "confidence": 0.9, "slots": {}, "reply_draft": "x",
                          "needs_human": False, "escalate_reason": None, "used_tools": []}}],
    )
    assert rejected.status.value == "rejected"
    assert rejected.http_status == 422
    assert "approved" in rejected.note


# ---------------------------------------------------------------- AC04
def test_ac04_precheck_branches(make_env):
    config, store = make_env()
    missing = run(
        store,
        {"ticket_id": "ac04-missing", "user_id": "U001", "text": "我要退款，不想说订单号。"},
        steps=[{"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]}],
    )
    assert missing.answer.escalate_reason == "MISSING_ORDER_ID"
    assert tool_names(missing) == []
    assert missing.status.value == "ok" and missing.stop_reason.value == "finalized"

    ambiguous = run(
        store,
        {"ticket_id": "ac04-ambiguous", "user_id": "U001", "text": "订单 O1002 和 O1006 哪个更适合退款？"},
        steps=[{"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1002"}}]}],
    )
    assert ambiguous.answer.escalate_reason == "AMBIGUOUS_ORDER_ID"
    assert tool_names(ambiguous) == []

    multi = run_case(config, case("dev-other-complex-2"), store=store).result
    assert multi.answer.escalate_reason == "MULTI_ORDER"
    assert tool_names(multi) == []


# ---------------------------------------------------------------- AC05
def test_ac05_policy_matrix(make_env):
    config, store = make_env()
    expected = {
        "dev-refund-complex-1": "REFUND_AFTER_SHIP",
        "dev-refund-complex-2": "REFUND_OVER_LIMIT",
        "dev-refund-complex-3": "REFUND_NOT_ALLOWED",
        "dev-address-simple-1": "ADDRESS_CHANGE",
        "dev-address-complex-1": "ADDRESS_AFTER_SHIP",
        "dev-address-complex-3": "ADDRESS_CONFLICT",
        "dev-other-simple-3": "LOW_CONFIDENCE",
    }
    for case_id, reason in expected.items():
        out = run_case(config, case(case_id), store=store).result
        assert out.answer.escalate_reason == reason, case_id
        assert out.answer.needs_human is True, case_id
        assert out.answer.reply_draft, case_id
        names = {item["name"] for item in out.tool_calls}
        assert not names & {"refund_submit", "address_change"}, case_id


# ---------------------------------------------------------------- AC06
def test_ac06_idempotent_tool_call(make_env):
    config, store = make_env()
    # 订单号必须与工单绑定的一致：跨单调用在 R04 之后会判 INVALID_ARGS。
    c = case("dev-shipping-simple-2")
    raw_args = c.get("expected_args") or []
    if isinstance(raw_args, dict):
        order_id = (raw_args.get("query_order") or {}).get("order_id") or c.get("order_id")
    else:
        order_id = c.get("order_id")
        for name, args in zip(c.get("expected_tools") or [], raw_args):
            if name == "query_order" and isinstance(args, dict) and args.get("order_id"):
                order_id = args["order_id"]
                break
    step = {"tool_calls": [{"name": "query_order", "arguments": {"order_id": order_id}}]}
    out = run(
        store,
        payload("dev-shipping-simple-2"),
        steps=[step, step, dict(steps_for(case("dev-shipping-simple-2"))[-1])],
        config=config,
    )
    calls = store.list_tool_calls(out.run_id)
    assert [call.ok for call in calls] == [True, True]
    assert calls[1].cached is True
    assert calls[0].idempotency_key and calls[1].idempotency_key is None


# ---------------------------------------------------------------- AC07
def test_ac07_rerun_is_stable_and_not_cached(make_env):
    config, store = make_env()
    first = run_case(config, case("dev-refund-simple-1"), store=store).result
    second = run_case(config, case("dev-refund-simple-1"), store=store).result
    assert first.status == second.status
    assert first.answer.to_dict() == second.answer.to_dict()
    assert [c["name"] for c in first.tool_calls] == [c["name"] for c in second.tool_calls]
    assert all(call.cached is False for call in store.list_tool_calls(second.run_id))


# ---------------------------------------------------------------- AC08
def test_ac08_duplicate_running_ticket_is_409(make_env):
    config, store = make_env()
    results: list[Any] = []

    def worker() -> None:
        db = Database(config.db_path)
        results.append(
            ExecutionLoop(config, db, SlowProvider(), approval_gate=ScriptedApprovalGate(True)).run(
                payload("dev-shipping-simple-1")
            )
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
        time.sleep(0.05)
    for thread in threads:
        thread.join(timeout=10)

    codes = sorted(result.http_status for result in results)
    assert codes == [200, 409]
    rows = store.list_sessions_by_ticket("dev-shipping-simple-1")
    assert sum(1 for row in rows if row.status == "running") <= 1


# ---------------------------------------------------------------- AC09
def test_ac09_three_limits(make_env):
    config, store = make_env()

    loop_step = {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]}
    out = run(
        store,
        payload("dev-shipping-simple-1"),
        steps=[loop_step],
        config=load_config({"db_path": config.db_path, "max_steps": 2}, env={}),
        model=ScriptedModel([loop_step], repeat_last=True),
    )
    assert out.stop_reason.value == "max_steps"
    assert out.status.value == "degraded"
    assert out.answer.needs_human is True
    assert out.answer.reply_draft == DEGRADED_DRAFT

    token = run(
        store,
        payload("dev-shipping-simple-2"),
        steps=[loop_step],
        config=load_config({"db_path": config.db_path, "token_budget": 100}, env={}),
        model=ScriptedModel([loop_step], usage_per_step=Usage(80, 40, "scripted"), repeat_last=True),
    )
    assert token.stop_reason.value == "token_budget"
    assert token.status.value == "degraded"

    slow = ExecutionLoop(
        load_config({"db_path": config.db_path, "wall_clock_s": 1}, env={}),
        store,
        ScriptedModel([loop_step], repeat_last=True),
        clock=FakeClock([0.0, 0.0, 5.0]),
    ).run(payload("dev-shipping-simple-3"))
    assert slow.stop_reason.value == "timeout"
    assert slow.answer.needs_human is True


# ---------------------------------------------------------------- AC10
def test_ac10_usage_source_and_invalid_output(make_env):
    config, store = make_env()
    loop_step = {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]}
    out = ExecutionLoop(
        load_config({"db_path": config.db_path, "max_steps": 1}, env={}),
        store,
        NoUsageProvider(),
    ).run(payload("dev-shipping-simple-1"))
    # 模型没报 usage：来源必须是 missing，成本不得编造
    assert out.usage.source == "missing"
    assert out.usage.cost_cny is None
    assert tool_names(out) == ["query_order"]

    broken = ExecutionLoop(config, store, BoomProvider(InvalidModelOutput("坏 JSON", raw_text="{{")))
    bad = broken.run(payload("dev-shipping-simple-2"))
    assert bad.stop_reason.value == "invalid_output"
    assert bad.status.value == "degraded"


# ---------------------------------------------------------------- AC11
def test_ac11_store_failure_never_returns_ok(make_env, monkeypatch):
    config, store = make_env()
    from app.store.db import StoreError

    def boom(*args: Any, **kwargs: Any) -> None:
        raise StoreError("record_tool_call", "磁盘满了")

    monkeypatch.setattr(store, "record_tool_call", boom)
    client = TestClient(create_app(config, store=store, provider=ScriptedModel([{"tool_calls": [
        {"name": "query_order", "arguments": {"order_id": "O1001"}}]}])))
    response = client.post("/v1/tickets", json=payload("dev-shipping-simple-1"))
    assert response.status_code == 500
    assert "ok" != response.json().get("status")


# ---------------------------------------------------------------- AC12
def test_ac12_stream_events_and_disconnect(make_env):
    config, store = make_env()
    steps = steps_for(case("dev-refund-simple-1"))
    client = TestClient(create_app(config, store=store, provider=ScriptedModel(steps)))
    with client.stream("POST", "/v1/tickets/stream", json=payload("dev-refund-simple-1")) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = [line.split(": ", 1)[1] for line in body.splitlines() if line.startswith("event: ")]
    assert events[0] == "open"
    assert events[-1] in {"final", "error"}
    assert events.count("final") + events.count("error") == 1

    # 断开等价于“时间预算耗尽”：不抛异常，落 degraded/timeout
    out = ExecutionLoop(
        config,
        store,
        ScriptedModel([{"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]}], repeat_last=True),
        clock=FakeClock([0.0, 0.0, 100.0]),
    ).run(payload("dev-shipping-simple-1"))
    assert out.stop_reason.value == "timeout"


# ---------------------------------------------------------------- AC13
def test_ac13_trace_and_replay(make_env):
    config, store = make_env()
    first = run_case(config, case("dev-refund-simple-1"), store=store).result
    trace = store.get_trace(first.run_id)
    assert trace["session"].status == "ok"
    assert [turn.role for turn in trace["turns"]][:2] == ["user", "assistant"]

    steps = [
        {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]},
        {"tool_calls": [{"name": "refund_preview", "arguments": {"order_id": "O1001"}}]},
        {"final": first.answer.to_dict()},
    ]
    replay = ExecutionLoop(config, store, ScriptedModel(steps), approval_gate=ScriptedApprovalGate(True)).run(
        payload("dev-refund-simple-1"), source_run_id=first.run_id
    )
    assert replay.answer.intent == first.answer.intent
    assert store.get_session(replay.run_id).source_run_id == first.run_id

    # 冻结快照缺失 → 工具不可用，不静默降级
    frozen = run(
        store,
        payload("dev-refund-simple-2"),
        steps=[{"tool_calls": [{"name": "replay_snapshot", "arguments": {}}]},
               {"final": {"intent": "refund", "confidence": 0.5, "slots": {}, "reply_draft": "已查询。",
                          "needs_human": False, "escalate_reason": None, "used_tools": []}}],
        config=config,
    )
    codes = [call["error_code"] for call in frozen.tool_calls if call["name"] == "replay_snapshot"]
    assert codes == ["TOOL_UNAVAILABLE"]


# ---------------------------------------------------------------- AC14
def test_ac14_full_suite_is_deterministic(make_env):
    config, store = make_env()
    dataset = load_eval_cases()
    first = runner.run_suite(config, dataset, store=store)
    second = runner.run_suite(config, dataset, store=store)
    assert first.metrics["cases"] == 24
    assert [row["intent_pred"] for row in first.rows] == [row["intent_pred"] for row in second.rows]
    assert [row["tool_calls"] for row in first.rows] == [row["tool_calls"] for row in second.rows]
    assert first.metrics["degraded_cases"] == 0


# ---------------------------------------------------------------- AC15
def test_ac15_pii_is_masked(make_env):
    config, store = make_env()
    text = "订单 O1001 收货手机 13812345678，地址是上海市浦东新区世纪大道 1 号 502 室，想改地址。"
    out = run(
        store,
        {"ticket_id": "ac15-pii-1", "user_id": "U001", "text": text, "order_id": "O1001"},
        steps=[{"final": {"intent": "address_change", "confidence": 0.9, "slots": {"order_id": "O1001"},
                          "reply_draft": "已登记改地址需求，稍后人工联系 13812345678 确认。",
                          "needs_human": True, "escalate_reason": "ADDRESS_CHANGE", "used_tools": []}}],
        config=config,
    )
    client = TestClient(create_app(config, store=store, provider=ScriptedModel([{"final": {"intent": "other", "confidence": 0.1, "slots": {}, "reply_draft": "x", "needs_human": False, "escalate_reason": None, "used_tools": []}}])))
    trace = client.get(f"/v1/runs/{out.run_id}").text
    assert "13812345678" not in trace
    import re

    # 只检查人写的文本字段：整段 JSON 里含随机 run_id（32 位十六进制），会有连续 11 位数字的巧合。
    payload = client.get(f"/v1/runs/{out.run_id}").json()
    texts = [payload["session"].get("text") or "", payload["session"].get("draft_text") or ""]
    texts += [turn.get("content") or "" for turn in payload.get("turns", [])]
    texts += [str(call.get("arguments") or "") for call in payload.get("tool_calls", [])]
    assert not any(re.search(r"\d{11}", item) for item in texts)


# ---------------------------------------------------------------- AC16
def test_ac16_refund_amount_boundary(make_env):
    config, store = make_env()
    equal = run_case(config, case("dev-refund-simple-2"), store=store).result
    assert equal.answer.needs_human is False
    over = run_case(config, case("dev-refund-complex-2"), store=store).result
    assert over.answer.escalate_reason == "REFUND_OVER_LIMIT"


# ---------------------------------------------------------------- AC17
def test_ac17_refund_window_boundary(make_env):
    config, store = make_env()
    within = run_case(config, case("dev-refund-simple-3"), store=store).result
    assert within.answer.needs_human is False
    expired = run_case(config, case("dev-refund-complex-3"), store=store).result
    assert expired.answer.escalate_reason == "REFUND_NOT_ALLOWED"


# ---------------------------------------------------------------- AC18
def test_ac18_not_shipped_is_business_state(make_env):
    config, store = make_env()
    unshipped = run_case(config, case("dev-shipping-simple-1"), store=store).result
    assert unshipped.answer.needs_human is False
    shipped = run_case(config, case("dev-shipping-complex-1"), store=store).result
    assert shipped.answer.needs_human is False


# ---------------------------------------------------------------- AC19
def test_ac19_risky_draft_is_replaced(make_env):
    config, store = make_env()
    out = run(
        store,
        payload("dev-refund-simple-1"),
        steps=[
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]},
            {"final": {"intent": "refund", "confidence": 0.9, "slots": {"order_id": "O1001"},
                       "reply_draft": "我们保证赔偿并已退款，百分百到账。", "needs_human": False,
                       "escalate_reason": None, "used_tools": ["query_order"]}},
        ],
        config=config,
    )
    assert out.answer.escalate_reason == "DRAFT_RISK"
    assert out.answer.needs_human is True
    assert "保证" not in out.answer.reply_draft


# ---------------------------------------------------------------- AC20
def test_ac20_upstream_error_is_503_with_trace(make_env):
    config, store = make_env()
    client = TestClient(create_app(config, store=store, provider=BoomProvider(UpstreamError("网关 502", status_code=502))))
    response = client.post("/v1/tickets", json=payload("dev-shipping-simple-1"))
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["stop_reason"] == "upstream_error"
    assert body["run_id"]
    assert client.get(f"/v1/runs/{body['run_id']}").status_code == 200


# ---------------------------------------------------------------- AC21
def test_ac21_complaint_precheck(make_env):
    config, store = make_env()
    out = run_case(config, case("dev-other-complex-3"), store=store).result
    assert out.answer.escalate_reason == "COMPLAINT_OR_THREAT"
    assert tool_names(out) == []
    assert out.status.value == "ok"
    assert out.steps == 1
    assert "保证" not in out.answer.reply_draft
    assert "小时" not in out.answer.reply_draft


def test_holdout_runs_offline(make_env):
    """旧公开 holdout 的回归冒烟；不是新盲测，不证明独立性或泛化。"""
    config, store = make_env()
    dataset = load_holdout()
    assert len(dataset) == 12
    result = runner.run_suite(config, dataset, store=store)
    assert result.metrics["cases"] == 12
    assert result.metrics["degraded_cases"] == 0
