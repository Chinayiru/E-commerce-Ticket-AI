"""把一条评估用例翻译成 scripted 脚本，并跑通一次 run。

这样做的目的不是“让测试好看”，而是：评估链路、工具调用、落库、断言全部走
与真实模型完全相同的代码路径，只把 Provider 换掉。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.config import Config
from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.schemas import RunResult, Usage
from app.store.db import Database
from app.tools.registry import ToolRegistry, default_registry


@dataclass(frozen=True, slots=True)
class CaseRun:
    result: RunResult
    model: ScriptedModel
    gate: ScriptedApprovalGate
    case: Mapping[str, Any]


def final_step(case: Mapping[str, Any]) -> dict[str, Any]:
    """按用例的期望标签构造“模型最终答复”步骤。"""
    needs_human = bool(case.get("expected_needs_human"))
    reason = case.get("expected_reason") if needs_human else None
    return {
        "final": {
            "intent": case["intent"],
            "confidence": float(case.get("confidence", 0.9)),
            "slots": {"order_id": case["order_id"]} if case.get("order_id") else {},
            "reply_draft": case.get("reply_draft") or "已按流程处理，结果会同步给您。",
            "needs_human": needs_human,
            "escalate_reason": reason,
            "used_tools": list(case.get("expected_tools") or []),
        }
    }


def steps_for(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    """先按期望调用工具，再给最终答复；无工具用例只有一步。"""
    steps: list[dict[str, Any]] = []
    for call in case.get("expected_args") or []:
        steps.append({"tool_calls": [{"name": call["name"], "arguments": dict(call.get("arguments") or {})}]})
    steps.append(final_step(case))
    return steps


def run_case(
    config: Config,
    case: Mapping[str, Any],
    *,
    store: Database | None = None,
    registry: ToolRegistry | None = None,
    approve: bool = True,
    usage_per_step: Usage | None = None,
    steps: Sequence[Mapping[str, Any]] | None = None,
    gate: ScriptedApprovalGate | None = None,
) -> CaseRun:
    store = store or Database(config.db_path)
    model = ScriptedModel(list(steps) if steps is not None else steps_for(case), usage_per_step=usage_per_step)
    gate = gate or ScriptedApprovalGate(approve)
    loop = ExecutionLoop(
        config,
        store,
        model,
        registry=registry or default_registry(),
        approval_gate=gate,
    )
    payload = {
        "ticket_id": case["case_id"],
        "user_id": case.get("user_id", "U001"),
        "text": case["text"],
        "order_id": case.get("order_id"),
    }
    result = loop.run(payload, dataset_hash=case.get("dataset_hash"))
    return CaseRun(result=result, model=model, gate=gate, case=case)


def payload_for(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ticket_id": case["case_id"],
        "user_id": case.get("user_id", "U001"),
        "text": case["text"],
        "order_id": case.get("order_id"),
    }


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
