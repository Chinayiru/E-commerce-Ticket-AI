"""实现者盲态：封存结果只给聚合数字，逐例文件与非聚合字段必须被拒绝。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sealed_summary.py"

REPORT = {
    "completed_at": "2026-11-06T01:00:00+08:00",
    "candidate_sha256": "a" * 64,
    "dataset_sha256": "b" * 64,
    "metrics": {
        "intent_ok": {"correct": 10, "total": 12, "accuracy": 0.8333, "wilson_95": [0.55, 0.95]},
        "tools_ok": {"correct": 11, "total": 12, "accuracy": 0.9167, "wilson_95": [0.65, 0.99]},
        "args_ok": {"correct": 9, "total": 12, "accuracy": 0.75, "wilson_95": [0.47, 0.91]},
        "escalation_ok": {"correct": 8, "total": 12, "accuracy": 0.6667, "wilson_95": [0.39, 0.86]},
    },
    "escalation_confusion": {"TP": 4, "FN": 1, "FP": 2, "TN": 5},
    "missing_answers": 0,
    "degraded": 1,
    "cases": 12,
    "human_adoption_rate": None,
    "scope": "仅适用于这 12 条独立合成样本；不能代表线上总体或人工采纳率。",
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_aggregate_only_output(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(REPORT, ensure_ascii=False), encoding="utf-8")
    done = _run("--report", str(path))
    assert done.returncode == 0, done.stderr
    assert "分类准确率" in done.stdout
    assert "10/12" in done.stdout
    assert "case_id" not in done.stdout
    assert "本文件不含逐例结果" in done.stdout


def test_rejects_jsonl_input(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text('{"case_id": "blind-000001"}\n', encoding="utf-8")
    done = _run("--report", str(path))
    assert done.returncode == 2
    assert "逐例结果文件" in done.stderr


def test_rejects_non_aggregate_keys(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({**REPORT, "cases_detail": [{"case_id": "x"}]}, ensure_ascii=False), encoding="utf-8")
    done = _run("--report", str(path))
    assert done.returncode == 2
    assert "非聚合字段" in done.stderr
