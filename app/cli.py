"""命令行入口（DEVELOPMENT §5）：只做“驱动”，业务逻辑一律在 app 包内。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from app.config import load_config
from app.core.loop import ExecutionLoop
from app.eval import runner
from app.eval.datasets import load_drafts, load_eval_cases, load_holdout
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.store.db import Database


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _step_from_call(call: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": call.tool_name, "arguments": dict(call.arguments)}]}


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config({} if args.db is None else {"db_path": args.db})
    store = Database(config.db_path)
    payload = {
        "ticket_id": args.ticket_id,
        "user_id": args.user_id,
        "text": args.text,
        "order_id": args.order_id,
    }
    if args.script:
        steps = json.loads(Path(args.script).read_text(encoding="utf-8"))
        model: Any = ScriptedModel(steps)
        gate: Any = ScriptedApprovalGate(args.approve)
    else:
        if config.provider != "openai":
            print("provider=scripted 时请用 --script 指定脚本；或用 PROVIDER=openai 走真实模型", file=sys.stderr)
            return 2
        from app.llm.openai_compat import OpenAICompatProvider

        model = OpenAICompatProvider(config)
        gate = ScriptedApprovalGate(True)
    result = ExecutionLoop(config, store, model, approval_gate=gate).run(payload)
    _print(result.to_dict())
    return 0 if result.http_status < 500 else 1


def cmd_trace(args: argparse.Namespace) -> int:
    config = load_config({} if args.db is None else {"db_path": args.db})
    trace = Database(config.db_path).get_trace(args.run_id)
    if trace is None:
        print(f"run 不存在：{args.run_id}", file=sys.stderr)
        return 1
    _print(trace)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    config = load_config({} if args.db is None else {"db_path": args.db})
    dataset = {
        "eval": load_eval_cases,
        "holdout": load_holdout,
        "drafts": load_drafts,
    }[args.dataset]()
    result = runner.run_suite(config, dataset, provider=args.provider, approve=args.approve)
    json_path, md_path = runner.write_report(result, config)
    _print({"report": str(json_path), "markdown": str(md_path), "metrics": result.metrics})
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    """用历史工具序列重放一次：验证“同输入同输出”，不碰真实模型。"""
    config = load_config({} if args.db is None else {"db_path": args.db})
    store = Database(config.db_path)
    trace = store.get_trace(args.run_id)
    if trace is None:
        print(f"run 不存在：{args.run_id}", file=sys.stderr)
        return 1
    session = trace["session"]
    calls = [call for call in trace["tool_calls"] if call.tool_name != "create_ticket_draft"]
    steps = [_step_from_call(call) for call in calls]
    final = (session.result or {}).get("answer")
    if final is None:
        print("该 run 没有最终答复，无法重放", file=sys.stderr)
        return 1
    steps.append({"final": {key: final[key] for key in (
        "intent", "confidence", "slots", "reply_draft", "needs_human", "escalate_reason", "used_tools"
    )}})
    payload = {
        "ticket_id": session.ticket_id,
        "user_id": session.user_id,
        "text": session.text,
        "order_id": session.order_id,
    }
    result = ExecutionLoop(
        config,
        store,
        ScriptedModel(steps),
        approval_gate=ScriptedApprovalGate(args.approve),
    ).run(payload, source_run_id=session.id)
    _print(result.to_dict())
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from app.api.main import create_app

    uvicorn.run(create_app(load_config()), host=args.host, port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="电商售后工单 Agent")
    parser.add_argument("--db", default=None, help="覆盖 DB_PATH")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="跑一次工单")
    run.add_argument("--ticket-id", required=True)
    run.add_argument("--user-id", default="U001")
    run.add_argument("--text", required=True)
    run.add_argument("--order-id", default=None)
    run.add_argument("--script", default=None, help="scripted 步骤 JSON 文件")
    run.add_argument("--approve", action="store_true", help="审批闸门放行不可逆草稿")
    run.set_defaults(func=cmd_run)

    trace = sub.add_parser("trace", help="查看 run 的完整 trace")
    trace.add_argument("run_id")
    trace.set_defaults(func=cmd_trace)

    evaluate = sub.add_parser("eval", help="跑评估并写报告")
    evaluate.add_argument("--dataset", choices=("eval", "holdout", "drafts"), default="eval")
    evaluate.add_argument("--provider", choices=("scripted", "openai"), default="scripted")
    evaluate.add_argument("--approve", action="store_true", default=True)
    evaluate.set_defaults(func=cmd_eval)

    replay = sub.add_parser("replay", help="按历史工具序列重放")
    replay.add_argument("run_id")
    replay.add_argument("--approve", action="store_true", default=True)
    replay.set_defaults(func=cmd_replay)

    serve = sub.add_parser("serve", help="启动 HTTP 服务")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
