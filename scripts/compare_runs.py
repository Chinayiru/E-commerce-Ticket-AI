"""同条件多次运行的中位数/范围对比，供“基线与候选各跑 3 次”这条纪律落地。

用法：
    python scripts/compare_runs.py \
        --arm baseline=reports/b1.json,reports/b2.json,reports/b3.json \
        --arm candidate=reports/c1.json,reports/c2.json,reports/c3.json

规则（不做让步）：
- 每个 arm 至少 3 次，少一次直接报错退出，不给“先看结果再补跑”的机会；
- 两个 arm 的 provider、model、dataset_hash 必须一致，否则拒绝比较；
- 输出原始值、中位数、最小值–最大值；任意一行的差异都不能被中位数掩盖；
- 结尾固定打印“中位数差值不等于统计显著性”，避免把噪声当提升。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from typing import Any

MIN_RUNS = 3

METRICS = (
    ("intent_accuracy", "分类准确率", True),
    ("tools_accuracy", "工具调用正确率", True),
    ("args_accuracy", "参数正确率", True),
    ("escalation_accuracy", "转人工判定准确率", True),
    ("degraded_cases", "降级条数", False),
    ("latency_p95_ms", "P95 延迟(ms)", False),
    ("mean_cost_cny", "单条成本(CNY)", False),
)

CONDITION_KEYS = ("provider", "model", "max_steps", "wall_clock_s", "window_turns", "demo_now")


def load(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "metrics" not in data or "environment" not in data:
        raise SystemExit(f"{path} 不是评估报告（缺 metrics/environment）")
    return data


def parse_arm(text: str) -> tuple[str, list[pathlib.Path]]:
    name, _, raw = text.partition("=")
    if not raw:
        raise SystemExit(f"--arm 需要 name=file1,file2,file3 的形式：{text}")
    files = [pathlib.Path(item.strip()) for item in raw.split(",") if item.strip()]
    return name.strip(), files


def stats(values: list[float]) -> dict[str, Any]:
    return {
        "raw": values,
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
    }


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def dataset_id(report: dict[str, Any]) -> str:
    block = report.get("dataset") or {}
    return str(block.get("dataset_hash") or block.get("sha256") or "")


def check_conditions(arms: dict[str, list[dict[str, Any]]]) -> list[str]:
    notes: list[str] = []
    ids = {name: dataset_id(runs[0]) for name, runs in arms.items()}
    if len(set(ids.values())) > 1:
        raise SystemExit(f"数据集不一致，拒绝比较：{ids}")
    for name, runs in arms.items():
        if len({dataset_id(run) for run in runs}) > 1:
            raise SystemExit(f"{name} 组内混用了不同数据集，拒绝比较")
    envs = {name: runs[0]["environment"] for name, runs in arms.items()}
    baseline_name = next(iter(envs))
    base = envs[baseline_name]
    for name, env in envs.items():
        for key in CONDITION_KEYS:
            if env.get(key) != base.get(key):
                raise SystemExit(f"条件不一致，拒绝比较：{key} 在 {baseline_name}={base.get(key)!r}、{name}={env.get(key)!r}")
        if env.get("token_budget") != base.get("token_budget"):
            raise SystemExit(
                f"条件不一致，拒绝比较：token_budget {baseline_name}={base.get('token_budget')}、{name}={env.get('token_budget')}")
        if env.get("prompt_version") != base.get("prompt_version"):
            notes.append(f"{name} 的 prompt_version={env.get('prompt_version')} 与 {baseline_name}={base.get('prompt_version')} 不同（预期，若同一版本请核查）")
    return notes


def per_case_diffs(arms: dict[str, list[dict[str, Any]]]) -> list[str]:
    """逐例比较：任一次运行与其余不一致的 case 全部列出，不被中位数掩盖。"""
    names = list(arms)
    by_arm: dict[str, dict[str, dict[str, Any]]] = {}
    for name in names:
        rows: dict[str, dict[str, Any]] = {}
        for run in arms[name]:
            for row in run["cases"]:
                rows.setdefault(row["case_id"], row)
        by_arm[name] = rows

    all_ids = sorted({cid for rows in by_arm.values() for cid in rows})
    lines: list[str] = []
    for cid in all_ids:
        observed = []
        for name in names:
            row = by_arm[name].get(cid, {})
            observed.append(f"{name}:{row.get('intent_ok')}/{row.get('tools_ok')}/{row.get('args_ok')}/{row.get('escalation_ok')}")
        stable_within = all(
            len({json.dumps({k: row.get(k) for k in ("intent_ok", "tools_ok", "args_ok", "escalation_ok")}, sort_keys=True)
                 for row in [next((r for r in run["cases"] if r["case_id"] == cid), {}) for run in arms[name]]}) == 1
            for name in names
        )
        across = {json.dumps({k: by_arm[name].get(cid, {}).get(k) for k in ("intent_ok", "tools_ok", "args_ok", "escalation_ok")}, sort_keys=True)
                  for name in names}
        if len(across) > 1:
            lines.append(f"| {cid} | {' / '.join(observed)} | 两臂结果不同 |")
        elif not stable_within:
            lines.append(f"| {cid} | {' / '.join(observed)} | 同臂多次运行不稳定 |")
    return lines


def render(arms: dict[str, list[dict[str, Any]]], notes: list[str]) -> str:
    names = list(arms)
    out: list[str] = ["# 同条件多次运行对比", ""]
    out.append(f"每组运行次数：{', '.join(f'{name}={len(runs)}' for name, runs in arms.items())}")
    base_env = arms[names[0]][0]["environment"]
    out.append(f"条件：provider={base_env.get('provider')} model={base_env.get('model')} "
               f"token_budget={base_env.get('token_budget')} max_steps={base_env.get('max_steps')} "
               f"wall_clock_s={base_env.get('wall_clock_s')} dataset={dataset_id(arms[names[0]][0])[:12]}")
    out.append("")
    out.append("| 指标 | " + " | ".join(f"{n} 原始值" for n in names) + " | " + " | ".join(f"{n} 中位数 [范围]" for n in names) + " |")
    out.append("| --- | " + " | ".join("---" for _ in names) + " | " + " | ".join("---" for _ in names) + " |")

    table: dict[str, dict[str, Any]] = {}
    for key, label, higher_better in METRICS:
        cells_raw, cells_stat = [], []
        table[key] = {}
        for name in names:
            values = [run["metrics"].get(key) for run in arms[name]]
            numeric = [float(v) for v in values if isinstance(v, (int, float))]
            if not numeric:
                cells_raw.append("—")
                cells_stat.append("—")
                table[key][name] = None
                continue
            info = stats(numeric)
            table[key][name] = info
            cells_raw.append(" / ".join(fmt(v) for v in values))
            cells_stat.append(f"{fmt(info['median'])} [{fmt(info['min'])}–{fmt(info['max'])}]")
        out.append(f"| {label} | " + " | ".join(cells_raw) + " | " + " | ".join(cells_stat) + " |")

    if len(names) == 2:
        out.append("")
        out.append("两臂中位数差值（仅供读数，不构成显著性结论）：")
        for key, label, _ in METRICS:
            left, right = table[key][names[0]], table[key][names[1]]
            if not left or not right:
                continue
            delta = right["median"] - left["median"]
            out.append(f"- {label}：{fmt(left['median'])} → {fmt(right['median'])}（{delta:+.4f}）")

    diffs = per_case_diffs(arms)
    out.append("")
    out.append("## 逐例不稳定/两臂不同")
    out.append("")
    if diffs:
        out.append("| case_id | 观察（intent/tools/args/escalation） | 说明 |")
        out.append("| --- | --- | --- |")
        out.extend(diffs)
    else:
        out.append("三次运行与两臂之间逐例判定完全一致。")

    if notes:
        out.append("")
        out.append("## 条件提示")
        out.append("")
        out.extend(f"- {note}" for note in notes)

    out.append("")
    out.append("**结论纪律**：中位数差值不等于统计显著性；n=3 只能证明“是否稳定复现”，不能证明“提升”。"
               "要声称提升，需要更大样本、独立数据集，或至少 5 次以上且范围不重叠。")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="基线与候选各 3 次同条件运行的中位数/范围对比")
    parser.add_argument("--arm", action="append", required=True, help="name=report1.json,report2.json,report3.json")
    parser.add_argument("--out", default=None, help="写入 markdown 报告路径")
    args = parser.parse_args(argv)

    arms: dict[str, list[dict[str, Any]]] = {}
    for raw in args.arm:
        name, files = parse_arm(raw)
        if len(files) < MIN_RUNS:
            raise SystemExit(f"{name} 只有 {len(files)} 次运行，协议要求至少 {MIN_RUNS} 次；不补跑就拒绝给出结论")
        arms[name] = [load(path) for path in files]

    notes = check_conditions(arms)
    markdown = render(arms, notes)
    print(markdown)
    if args.out:
        target = pathlib.Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        print(f"written: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
