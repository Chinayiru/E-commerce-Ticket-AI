"""补充 AI 审查的反例；不加载旧评估集、不调用远端、不修改业务代码。

退出码 1 表示仍有问题复现，0 表示本脚本的反例均未再复现。
这不是新的泛化评估集，也不是业务方或第二人的复核。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import TZ_SHANGHAI, load_config
from app.core.loop import ExecutionLoop
from app.core.policy import delivery_dispute
from app.eval.metrics import args_ok, escalation_ok
from app.llm.scripted import ScriptedApprovalGate, ScriptedModel
from app.schemas import Usage
from app.store.db import Database, StoreError


def final(**changes):
    answer = dict(intent="refund", confidence=0.99, slots={},
                  reply_draft="已核实，可退 58.00 元。", needs_human=False,
                  escalate_reason=None, used_tools=[])
    answer.update(changes)
    return {"final": answer}


def probe(out: Path) -> dict:
    findings = []

    def record(key, expected, observed, reproduced, run_id=None):
        findings.append(dict(id=key, expected=expected, observed=observed,
                             reproduced=bool(reproduced), run_id=run_id))

    with tempfile.TemporaryDirectory(prefix="ticket-review-") as folder:
        cfg = load_config(dict(db_path=str(Path(folder) / "runs.db"),
                               log_dir=str(Path(folder) / "logs")), env={})
        store = Database(cfg.db_path)

        def run(key, steps, text="订单 O1001 需要退款", **kwargs):
            config = kwargs.pop("config", cfg)
            model = kwargs.pop("model", None) or ScriptedModel(steps)
            return ExecutionLoop(config, store, model,
                                 approval_gate=ScriptedApprovalGate(True), **kwargs).run(
                dict(ticket_id=f"audit-{key}", user_id="U001", text=text, order_id="O1001"))

        result = SimpleNamespace(tool_calls=[], answer=None)
        got = args_ok(result, {"expected_args": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]})
        record("R01a", "缺少必需调用明细时参数不得判通过", got, got is True)
        bad = SimpleNamespace(tool_name="query_order", arguments={"order_id": "O1004"},
                              error_code="ORDER_NOT_FOUND", approval_required=False)
        got = args_ok(result, {"expected_args": [{"name": "query_order", "arguments": bad.arguments}]}, [bad])
        record("R01b", "越权订单尝试不得判参数正确", got, got is True)
        got = escalation_ok(result, {"expected_needs_human": False})
        record("R02", "没有答案时判定失败", got, got is True)

        got = run("facts", [final(reply_draft="已为您完成退款，24小时到账。", used_tools=["query_order", "refund_preview"])])
        record("R03", "未查询时不得接受虚构事实、已退款声称及伪造 used_tools",
               got.to_dict(), got.status.value == "ok" and not got.tool_calls and
               got.answer.used_tools == ["query_order", "refund_preview"] and not got.answer.needs_human, got.run_id)

        class CaptureModel(ScriptedModel):
            messages = None
            def complete(self, request):
                if self.messages is None:
                    self.messages = request.messages
                return super().complete(request)

        model = CaptureModel([
            {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1005"}}]},
            {"tool_calls": [{"name": "refund_preview", "arguments": {"order_id": "O1005"}}]},
            final(reply_draft="订单 O1005 可退 200.00 元。")])
        got = run("binding", [], text="请帮我核实这笔退款申请", model=model)
        visible = json.dumps(model.messages, ensure_ascii=False)
        record("R04", "结构化 O1001 不得被工具调用中的 O1005 替代",
               dict(structured_id_visible="O1001" in visible, result=got.to_dict()),
               got.status.value == "ok" and not got.answer.needs_human, got.run_id)

        class Clock:
            value = 0.0
            def __call__(self):
                return self.value
        clock = Clock()
        class LateModel(ScriptedModel):
            def complete(self, request):
                response = super().complete(request)
                clock.value = 2.0
                return response
        got = run("deadline", [], config=cfg.with_overrides(wall_clock_s=1), clock=clock,
                  model=LateModel([final()]))
        record("R05a", "超时后收到终局仍须 timeout/degraded", got.to_dict(),
               got.status.value == "ok" and got.latency_ms >= 2000, got.run_id)
        got = run("tokens", [], config=cfg.with_overrides(token_budget=100),
                  model=ScriptedModel([final()], usage_per_step=Usage(90, 30, "scripted")))
        record("R05b", "终局已耗超 token 预算须降级", got.to_dict(),
               got.status.value == "ok" and got.usage.total_tokens > 100, got.run_id)

        phrases = [("物流记录已签收，可我一直没拿到包裹", True),
                   ("签收时间没问题，并不存在不一致", False)]
        observed = [dict(text=t, expected=e, actual=delivery_dispute(t)) for t, e in phrases]
        for i, (text, expected) in enumerate(phrases):
            dispute = run(f"dispute-{i}", [
                {"tool_calls": [{"name": "query_order", "arguments": {"order_id": "O1001"}}]},
                final(intent="shipping_urge", needs_human=False, reply_draft="物流事实请进一步核实。")],
                text="订单 O1001 " + text)
            observed[i]["final_reason"] = dispute.answer.escalate_reason
            observed[i]["run_id"] = dispute.run_id
        positive = run("dispute-positive", [final(intent="shipping_urge")], text="订单 O1001 显示已签收但我没收到")
        observed.append(dict(text="常见正例", expected=True, actual=positive.answer.escalate_reason == "DELIVERY_DISPUTE"))
        compensation = run("dispute-compensation", [final(intent="shipping_urge")],
                           text="订单 O1001 显示已签收但我没收到，我要求赔偿")
        observed.append(dict(text="含赔偿诉求", expected=False,
                             actual=compensation.answer.escalate_reason == "DELIVERY_DISPUTE",
                             final_reason=compensation.answer.escalate_reason, run_id=compensation.run_id))
        record("R06", "肯定争议识别、否定争议排除", observed,
               any(row["expected"] != row["actual"] for row in observed))

        got = run("approved", [{"tool_calls": [{"name": "refund_submit", "arguments": {"order_id": "O1001", "approved": True}}]}])
        code = got.tool_calls[0]["error_code"]
        record("R07", "AC03 要求非法动作字段先判 INVALID_ARGS", code, code != "INVALID_ARGS", got.run_id)

        raw_phone = "13812345678"  # 合成敏感字段，仅检查临时库
        got = run("pii", [final(intent="address_change", reply_draft=f"请联系 {raw_phone} 核实地址。")],
                  text=f"订单 O1001 请修改收货手机为 {raw_phone}")
        trace = store.get_trace(got.run_id)
        raw_content = "\n".join(turn.content for turn in trace["turns"])
        record("R08", "AC15 要求存储的 turns 也脱敏",
               dict(raw_phone_in_stored_turns=raw_phone in raw_content), raw_phone in raw_content, got.run_id)

        original = store.save_draft
        attempts = []
        def fail_once(*args, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise StoreError("save_draft", "audit injected transient failure")
            return original(*args, **kwargs)
        store.save_draft = fail_once
        # 修复后的合同是“写失败必须向调用方传播”（HTTP 层转 500），因此抛出即视为未复现。
        try:
            got = run("store", [final(intent="address_change", needs_human=True,
                                      escalate_reason="ADDRESS_CHANGE")], text="订单 O1001 要改地址")
        except StoreError as exc:
            record("R09", "内部草稿写失败不得仍返回 ok", dict(raised="StoreError", detail=str(exc)[:120]),
                   False, None)
        else:
            record("R09", "内部草稿写失败不得仍返回 ok", got.to_dict(),
                   got.status.value == "ok" and "draft_failed:STORE_WRITE_FAILED" in (got.note or ""), got.run_id)

        # R10 原本只是演示“正则能匹配 11 位数字”，永远为真；改为检查测试源码是否仍在整段 JSON 上扫 11 位数字。
        test_source = (ROOT / "tests" / "test_acceptance.py").read_text(encoding="utf-8")
        still_scans_whole_trace = '"\\d{11}", trace' in test_source
        record("R10", "仅含随机 run_id 的元数据不能被视为手机号泄漏",
               dict(scans_whole_trace=still_scans_whole_trace), still_scans_whole_trace)

    report = dict(created_at=datetime.now(TZ_SHANGHAI).isoformat(),
                  reviewer="supplemental AI review; no human review; old holdout already exposed",
                  source_hashes={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted([*(ROOT / "app").rglob("*.py"), ROOT / "tests/test_acceptance.py", Path(__file__)])},
                  probe_count=len(findings), reproduced=sum(f["reproduced"] for f in findings), findings=findings,
                  evidence_note="临时 SQLite 已删除；run_id 仅关联本次内存记录，非可查询的持久 trace；运行输出保存在本 JSON。")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "reports/review-probes-2026-11-05.json")
    args = parser.parse_args()
    report = probe(args.out)
    print(f"probes={report['probe_count']} reproduced={report['reproduced']} report={args.out}")
    return int(report["reproduced"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
