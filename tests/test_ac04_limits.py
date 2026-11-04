"""AC04 有界循环与终止原因：max_steps / token_budget / timeout 三类都不抛异常。"""

from __future__ import annotations

from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedModel
from app.schemas import Usage

TICKET = {
    "ticket_id": "AC04-1",
    "user_id": "U001",
    "text": "订单 O1002 一直没动静，帮我查一下物流。",
    "order_id": "O1002",
}
STEP = {"tool_calls": [{"name": "check_logistics", "arguments": {"order_id": "O1002"}}]}


class FakeClock:
    """按序列返回时间，用尽后停在最后一个值。"""

    def __init__(self, values: list[float]) -> None:
        self._values = list(values)
        self._last = values[0] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


def test_max_steps_stops_with_step_limit(make_env):
    config, store = make_env(max_steps=3)
    loop = ExecutionLoop(config, store, ScriptedModel([STEP], repeat_last=True))
    result = loop.run(dict(TICKET, ticket_id="AC04-STEPS"))

    assert result.stop_reason.value == "max_steps"
    assert result.status.value == "degraded"
    assert result.steps == 3
    assert result.answer is not None
    assert result.answer.needs_human is True
    assert result.answer.escalate_reason == "STEP_LIMIT"
    assert store.get_session(result.run_id).stop_reason == "max_steps"


def test_token_budget_stops_with_token_budget(make_env):
    config, store = make_env(token_budget=1000)
    model = ScriptedModel(
        [STEP], repeat_last=True, usage_per_step=Usage(600, 40, source="scripted")
    )
    result = ExecutionLoop(config, store, model).run(dict(TICKET, ticket_id="AC04-TOKENS"))

    assert result.stop_reason.value == "token_budget"
    assert result.status.value == "degraded"
    assert result.steps == 2
    assert result.usage.total_tokens == 1280
    assert result.usage.source == "scripted"


def test_timeout_stops_with_timeout(make_env):
    config, store = make_env(wall_clock_s=5.0)
    clock = FakeClock([0.0, 0.0, 0.0, 100.0])
    loop = ExecutionLoop(config, store, ScriptedModel([STEP], repeat_last=True), clock=clock)
    result = loop.run(dict(TICKET, ticket_id="AC04-TIMEOUT"))

    assert result.stop_reason.value == "timeout"
    assert result.status.value == "degraded"
    assert result.steps == 1
    assert result.answer.escalate_reason == "TIMEOUT"
    assert result.latency_ms >= 0


def test_all_limits_return_structured_result_without_raising(make_env):
    cases = [
        (dict(max_steps=2), None),
        (dict(token_budget=1), Usage(10, 10, source="scripted")),
    ]
    for index, (overrides, usage) in enumerate(cases):
        config, store = make_env(**overrides)
        model = ScriptedModel([STEP], repeat_last=True, usage_per_step=usage)
        result = ExecutionLoop(config, store, model).run(
            dict(TICKET, ticket_id=f"AC04-NORAISE-{index}")
        )
        assert result.stop_reason.value in {"max_steps", "token_budget"}
        assert result.answer is not None
        assert result.answer.reply_draft
