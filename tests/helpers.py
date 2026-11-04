"""AC01–AC05 共用的测试脚手架：临时库、脚本拼装、单次运行。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.store.db import Database

REPO_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = REPO_ROOT / "data" / "mock_cases.json"


def script_for(case: dict[str, Any]) -> list[dict[str, Any]]:
    """把一条 Mock 用例翻译成 scripted 脚本：先按期望顺序调工具，再给最终答案。"""
    steps: list[dict[str, Any]] = []
    for name in case["expected_tools"]:
        steps.append(
            {"tool_calls": [{"name": name, "arguments": dict(case["expected_args"].get(name) or {})}]}
        )
    steps.append(
        {
            "final": {
                "intent": case["intent"],
                "confidence": 0.9,
                "slots": {"order_id": case["order_id"]} if case["order_id"] else {},
                "reply_draft": f"关于 {case['case_id']} 的处理说明草稿。",
                "needs_human": case["expected_needs_human"],
                "escalate_reason": case["expected_reason"],
                "used_tools": list(case["expected_tools"]),
            }
        }
    )
    return steps


def run_case(
    config: Any,
    store: Database,
    case: dict[str, Any],
    *,
    approve: bool = True,
):
    """用一条用例驱动一次完整运行，返回 (RunResult, ScriptedModel, ScriptedApprovalGate)。"""
    model = ScriptedModel(script_for(case))
    gate = ScriptedApprovalGate(approve)
    loop = ExecutionLoop(config, store, model, approval_gate=gate)
    payload = {
        "ticket_id": case["case_id"],
        "user_id": "U001",
        "text": case["text"],
        "order_id": case["order_id"],
    }
    return loop.run(payload), model, gate
