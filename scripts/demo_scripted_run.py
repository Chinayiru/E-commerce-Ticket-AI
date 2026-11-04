"""单次运行演示：不接真实模型，用 scripted 跑一条工单，把 trace 打印出来。

用法：
    python scripts/demo_scripted_run.py                 # 默认正常路径
    python scripts/demo_scripted_run.py tool_error      # 工具失败
    python scripts/demo_scripted_run.py escalate_deny   # 转人工被拒
    python scripts/demo_scripted_run.py escalate_allow  # 转人工被批准
    python scripts/demo_scripted_run.py --approve       # 给默认场景打开审批
    python scripts/demo_scripted_run.py --db data/demo_runs.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config import load_config
from app.core.loop import ExecutionLoop
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.store.db import Database

SCENARIOS: dict[str, dict] = {
    "normal": {
        "payload": {
            "ticket_id": "DEMO-NORMAL",
            "user_id": "U001",
            "text": "订单 O1001 不想要了，麻烦帮我退款。",
            "order_id": "O1001",
        },
        "script": [
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]},
            {"tool_calls": [{"name": "refund_preview", "arguments": {"order_id": "O1001"}}]},
            {"final": {
                "intent": "refund", "confidence": 0.92, "slots": {"order_id": "O1001"},
                "reply_draft": "订单 O1001 已付款未发货，金额在自动退款额度内，可全额退款。",
                "needs_human": False, "used_tools": ["query_order", "refund_preview"],
            }},
        ],
        "approve": True,
    },
    "tool_error": {
        "payload": {
            "ticket_id": "DEMO-TOOL-ERROR",
            "user_id": "U001",
            "text": "帮我查一下订单 O9999 的物流，好几天没动了。",
            "order_id": "O9999",
        },
        "script": [
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O9999"}}]},
            {"final": {
                "intent": "shipping_urge", "confidence": 0.6, "slots": {"order_id": "O9999"},
                "reply_draft": "查不到该订单，请核对订单号，或转人工核实。",
                "needs_human": True, "escalate_reason": "ORDER_NOT_FOUND", "used_tools": [],
            }},
        ],
        "approve": True,
    },
    "escalate_deny": {
        "payload": {
            "ticket_id": "DEMO-ESCALATE-DENY",
            "user_id": "U001",
            "text": "订单 O1002 已经发货了，但收货地址填错了，能不能改一下？",
            "order_id": "O1002",
        },
        "script": [
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1002"}}]},
            {"final": {
                "intent": "address_change", "confidence": 0.75, "slots": {"order_id": "O1002"},
                "reply_draft": "订单已发货，改地址需要人工拦截包裹后处理。",
                "needs_human": True, "escalate_reason": "ADDRESS_AFTER_SHIP",
                "used_tools": ["query_order"],
            }},
        ],
        "approve": False,
    },
    "escalate_allow": {
        "payload": {
            "ticket_id": "DEMO-ESCALATE-ALLOW",
            "user_id": "U001",
            "text": "订单 O1002 已经发货了，但收货地址填错了，能不能改一下？",
            "order_id": "O1002",
        },
        "script": [
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1002"}}]},
            {"final": {
                "intent": "address_change", "confidence": 0.75, "slots": {"order_id": "O1002"},
                "reply_draft": "订单已发货，已为你创建人工改地址工单。",
                "needs_human": True, "escalate_reason": "ADDRESS_AFTER_SHIP",
                "used_tools": ["query_order"],
            }},
        ],
        "approve": True,
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="scripted 模式的单次运行演示")
    parser.add_argument("scenario", nargs="?", default="normal", choices=sorted(SCENARIOS))
    parser.add_argument("--approve", action="store_true", help="对不可逆操作全部批准")
    parser.add_argument("--deny", action="store_true", help="对不可逆操作全部拒绝")
    parser.add_argument("--db", default=str(REPO_ROOT / "data" / "demo_runs.db"))
    args = parser.parse_args(argv)

    scenario = SCENARIOS[args.scenario]
    approve = scenario["approve"]
    if args.approve:
        approve = True
    if args.deny:
        approve = False

    config = load_config({"db_path": args.db}, env={})
    store = Database(config.db_path)
    model = ScriptedModel(scenario["script"])
    gate = ScriptedApprovalGate(approve)
    loop = ExecutionLoop(config, store, model, approval_gate=gate)

    payload = scenario["payload"]
    print(f"== 场景 {args.scenario} ==")
    print(f"工单: {payload['ticket_id']} / {payload['text']}")
    print(f"模型: provider={model.provider_name} 脚本步数={len(scenario['script'])} 审批={approve}")
    print()

    result = loop.run(payload)

    print("== RunResult ==")
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str))

    print("\n== turns ==")
    for turn in store.list_turns(result.run_id):
        content = turn.content if len(turn.content) <= 70 else turn.content[:70] + "…"
        print(f"  [{turn.idx}] {turn.role:<9} {content}")

    print("\n== tool_calls ==")
    calls = store.list_tool_calls(result.run_id)
    if not calls:
        print("  (无)")
    for call in calls:
        flag = "ok" if call.ok else f"error {call.error_code}"
        print(f"  {call.tool_name:<20} {flag:<28} {call.duration_ms}ms args={call.arguments}")

    print("\n== session ==")
    session = store.get_session(result.run_id)
    print(f"  {session.session_id} status={session.status} stop_reason={session.stop_reason}")
    print(f"  db={config.db_path}")
    print(f"  闸门询问次数={len(gate.calls)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
