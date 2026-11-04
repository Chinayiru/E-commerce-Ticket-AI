"""跑一整套用例并生成可归档的报告（含 run_id 清单与指纹）。"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.config import Config
from app.core.loop import ExecutionLoop
from app.core.prompts import prompt_hash
from app.eval import metrics
from app.eval.datasets import Dataset, mock_data_hash
from app.eval.scripted_cases import CaseRun, payload_for, run_case
from app.llm.openai_compat import OpenAICompatProvider
from app.schemas import Evaluation
from app.store.db import Database

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports"


@dataclass
class SuiteResult:
    report_id: str
    dataset: Dataset
    provider: str
    model: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""

    def report(self, config: Config, *, commit: str | None = None) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "dataset": {
                "name": self.dataset.name,
                "path": str(self.dataset.path),
                "dataset_hash": self.dataset.sha256,
                "cases": len(self.dataset),
            },
            "environment": {
                "provider": self.provider,
                "model": self.model,
                "prompt_version": config.prompt_version,
                "prompt_hash": prompt_hash(config.prompt_version),
                "mock_data_hash": mock_data_hash(),
                "demo_now": config.demo_now.isoformat(),
                "max_steps": config.max_steps,
                "token_budget": config.token_budget,
                "wall_clock_s": config.wall_clock_s,
                "window_turns": config.window_turns,
                "commit": commit or _commit(),
                "started_at": self.started_at,
            },
            "metrics": self.metrics,
            "cases": self.rows,
        }


def run_suite(
    config: Config,
    dataset: Dataset,
    *,
    store: Database | None = None,
    provider: str = "scripted",
    approve: bool = True,
) -> SuiteResult:
    """``provider="scripted"`` 走逐条脚本；``provider="openai"`` 走真实模型。"""
    store = store or Database(config.db_path)
    report_id = f"{provider}-{dataset.name}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    result = SuiteResult(
        report_id=report_id,
        dataset=dataset,
        provider=provider,
        model=config.model if provider != "scripted" else "scripted",
        started_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )

    real_model = OpenAICompatProvider(config) if provider == "openai" else None
    for case in dataset.rows:
        if real_model is None:
            case_run = run_case(config, case, store=store, approve=approve)
            run = case_run.result
        else:
            loop = ExecutionLoop(config, store, real_model)
            run = loop.run(payload_for(case))
        row = _row(case, run)
        result.rows.append(row)
        _write_evaluation(store, report_id, dataset.name, config, case, run, row)

    result.metrics = metrics.summarize(result.rows, total=len(dataset))
    return result


def _row(case: Mapping[str, Any], run: Any) -> dict[str, Any]:
    answer = run.answer
    return {
        "case_id": case["case_id"],
        "run_id": run.run_id,
        "status": run.status.value,
        "stop_reason": run.stop_reason.value,
        "steps": run.steps,
        "intent": case["intent"],
        "intent_pred": None if answer is None else answer.intent.value,
        "intent_ok": metrics.intent_ok(run, case),
        "tools_ok": metrics.tools_ok(run, case),
        "args_ok": metrics.args_ok(run, case),
        "escalation_ok": metrics.escalation_ok(run, case),
        "needs_human": None if answer is None else answer.needs_human,
        "escalate_reason": None if answer is None else answer.escalate_reason,
        "tool_calls": [item["name"] for item in run.tool_calls],
        "latency_ms": run.latency_ms,
        "cost_cny": run.usage.cost_cny,
        "usage_source": run.usage.source,
        "draft": None if answer is None else answer.reply_draft,
        "note": run.note,
    }


def _write_evaluation(
    store: Database,
    report_id: str,
    dataset_kind: str,
    config: Config,
    case: Mapping[str, Any],
    run: Any,
    row: Mapping[str, Any],
) -> None:
    answer = run.answer
    store.write_evaluation(
        Evaluation(
            report_id=report_id,
            session_id=run.run_id or "",
            dataset_kind=dataset_kind,
            case_id=str(case["case_id"]),
            prompt_version=config.prompt_version,
            intent_gold=str(case["intent"]),
            intent_pred=None if answer is None else answer.intent.value,
            intent_ok=bool(row["intent_ok"]),
            tools_ok=bool(row["tools_ok"]),
            args_ok=bool(row["args_ok"]),
            draft_grade=None,
            cost_cny=run.usage.cost_cny,
            latency_ms=run.latency_ms,
            expected={
                "intent": case["intent"],
                "expected_tools": case.get("expected_tools"),
                "expected_needs_human": case.get("expected_needs_human"),
                "expected_reason": case.get("expected_reason"),
            },
            actual={
                "intent": None if answer is None else answer.intent.value,
                "tool_calls": [item["name"] for item in run.tool_calls],
                "needs_human": None if answer is None else answer.needs_human,
                "escalate_reason": None if answer is None else answer.escalate_reason,
                "stop_reason": run.stop_reason.value,
                "status": run.status.value,
            },
            error=None if row["status"] == "ok" else {"note": run.note},
        )
    )


def write_report(result: SuiteResult, config: Config, *, out_dir: Path | None = None) -> tuple[Path, Path]:
    """JSON 给机器、Markdown 给人；两份内容同源。"""
    out = Path(out_dir or REPORT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    payload = result.report(config)
    json_path = out / f"{result.report_id}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path = out / f"{result.report_id}.md"
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return json_path, md_path


def render_markdown(payload: Mapping[str, Any]) -> str:
    env = payload["environment"]
    m = payload["metrics"]
    lines = [
        f"# 评估报告 {payload['report_id']}",
        "",
        "## 环境",
        "",
        f"- provider: `{env['provider']}`，model: `{env['model']}`",
        f"- prompt: `{env['prompt_version']}` / `{env['prompt_hash']}`",
        f"- dataset_hash: `{payload['dataset']['dataset_hash']}`",
        f"- mock_data_hash: `{env['mock_data_hash']}`",
        f"- DEMO_NOW: `{env['demo_now']}`，commit: `{env['commit']}`",
        f"- 预算：max_steps={env['max_steps']}，token_budget={env['token_budget']}，wall_clock_s={env['wall_clock_s']}",
        "",
        "## 指标",
        "",
        f"- 用例数：{m['cases']}",
        f"- 分类准确率：{m['intent_accuracy']:.2%}",
        f"- 工具调用正确率：{m['tools_accuracy']:.2%}",
        f"- 参数正确率：{m['args_accuracy']:.2%}",
        f"- 转人工准确率：{m['escalation_accuracy']:.2%}（其中改地址 {m['address_escalation']['correct']}/{m['address_escalation']['cases']}）",
        f"- 降级用例：{m['degraded_cases']}",
        f"- 时延 P95：{m['latency_p95_ms']} ms，均值：{m['mean_latency_ms']} ms",
        f"- 单次平均成本：{m['mean_cost_cny']} 元",
        f"- usage 来源：{', '.join(m['usage_source']) or '-'}",
        "",
        "## 逐例结果",
        "",
        "| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["cases"]:
        mark = lambda flag: "✅" if flag else "❌"  # noqa: E731
        lines.append(
            "| {case_id} | {run_id} | {intent_pred} {ok} | {tools} | {args} | {esc} | {status} | {stop} |".format(
                case_id=row["case_id"],
                run_id=(row["run_id"] or "-")[:12],
                intent_pred=row["intent_pred"] or "-",
                ok=mark(row["intent_ok"]),
                tools=mark(row["tools_ok"]),
                args=mark(row["args_ok"]),
                esc=mark(row["escalation_ok"]),
                status=row["status"],
                stop=row["stop_reason"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _commit() -> str:
    env = os.environ.get("GIT_COMMIT")
    if env:
        return env
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(Path(__file__).resolve().parents[2]),
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            or "unknown"
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def suite_from_report(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_reports(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    """两份报告的差异摘要：用于 W3 的“改了什么、指标动了多少”。"""
    lm, rm = left["metrics"], right["metrics"]
    keys = ("intent_accuracy", "tools_accuracy", "args_accuracy", "escalation_accuracy")
    return {
        "left": left["report_id"],
        "right": right["report_id"],
        "delta": {key: round(float(rm[key]) - float(lm[key]), 4) for key in keys},
        "changed_cases": [
            {"case_id": a["case_id"], "before": a["intent_ok"], "after": b["intent_ok"]}
            for a, b in zip(left["cases"], right["cases"])
            if a["case_id"] == b["case_id"] and a["intent_ok"] != b["intent_ok"]
        ],
    }


__all__ = [
    "REPORT_DIR",
    "SuiteResult",
    "compare_reports",
    "render_markdown",
    "run_suite",
    "suite_from_report",
    "write_report",
]


def _unused(_: Sequence[Any]) -> None:  # pragma: no cover - 保留类型引用
    return None
