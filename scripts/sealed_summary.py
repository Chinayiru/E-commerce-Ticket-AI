"""只输出封存运行的汇总数字，不输出逐例结果、题干或失败样本。

实现者的盲态约束：一次封存运行结束后，实现者只应拿到 `report.json` 里的聚合指标。
本脚本把这件事变成默认动作——它只接受 `report.json`，拒绝 `results.jsonl` 这类逐例文件，
并且拒绝打印任何看起来像单条记录/题干的键。

用法：
    python scripts/sealed_summary.py --report <封存目录>/report.json
    python scripts/sealed_summary.py --report report.json --json   # 机器可读
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

AGGREGATE_KEYS = {
    "completed_at", "candidate_sha256", "dataset_sha256", "metrics",
    "escalation_confusion", "missing_answers", "degraded", "cases",
    "human_adoption_rate", "scope",
}
METRIC_LABELS = {
    "intent_ok": "分类准确率",
    "tools_ok": "工具调用正确率",
    "args_ok": "参数正确率",
    "escalation_ok": "转人工判定准确率",
}


def summarize(report: dict) -> dict:
    unknown = sorted(set(report) - AGGREGATE_KEYS)
    if unknown:
        raise ValueError(f"报告含非聚合字段，拒绝展示：{unknown}")
    metrics = report.get("metrics") or {}
    rows = []
    for key, label in METRIC_LABELS.items():
        item = metrics.get(key) or {}
        rows.append({
            "metric": key,
            "label": label,
            "correct": item.get("correct"),
            "total": item.get("total"),
            "accuracy": item.get("accuracy"),
            "wilson_95": item.get("wilson_95"),
        })
    return {
        "completed_at": report.get("completed_at"),
        "cases": report.get("cases"),
        "degraded": report.get("degraded"),
        "missing_answers": report.get("missing_answers"),
        "escalation_confusion": report.get("escalation_confusion"),
        "metrics": rows,
        "hashes": {
            "candidate_sha256": report.get("candidate_sha256"),
            "dataset_sha256": report.get("dataset_sha256"),
            "report_sha256": hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        },
        "human_adoption_rate": report.get("human_adoption_rate"),
        "scope": report.get("scope"),
    }


def render(summary: dict) -> str:
    lines = ["# 封存运行汇总（仅聚合数字）", ""]
    lines.append(f"- 完成时间：{summary['completed_at']}")
    lines.append(f"- 样本数：{summary['cases']}")
    lines.append(f"- 降级条数：{summary['degraded']}；缺答案：{summary['missing_answers']}")
    confusion = summary["escalation_confusion"] or {}
    lines.append(f"- 转人工混淆：TP={confusion.get('TP')} FN={confusion.get('FN')} FP={confusion.get('FP')} TN={confusion.get('TN')}")
    lines.append(f"- 候选 sha256：{summary['hashes']['candidate_sha256']}")
    lines.append(f"- 数据 sha256：{summary['hashes']['dataset_sha256']}")
    lines.append("")
    lines.append("| 指标 | 正确/总数 | 比率 | Wilson 95% |")
    lines.append("| --- | --- | --- | --- |")
    for row in summary["metrics"]:
        lines.append(f"| {row['label']} | {row['correct']}/{row['total']} | {row['accuracy']} | {row['wilson_95']} |")
    lines.append("")
    lines.append(f"人工采纳率：{summary['human_adoption_rate'] or '待实测'}")
    lines.append("")
    lines.append(f"> {summary['scope']}")
    lines.append("")
    lines.append("**本文件不含逐例结果、题干或失败样本**；逐例数据由保管方留存，实现者不接触。")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="封存运行报告的聚合视图（不含逐例数据）")
    parser.add_argument("--report", required=True, type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.report.suffix == ".jsonl":
        print("拒绝：这是逐例结果文件，实现者不得读取；请提供 report.json", file=sys.stderr)
        return 2
    try:
        summary = summarize(json.loads(args.report.read_text(encoding="utf-8")))
    except (ValueError, OSError, KeyError) as exc:
        print(f"未完成（{type(exc).__name__}）：{exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
