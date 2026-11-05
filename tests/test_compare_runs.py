"""compare_runs 的协议护栏：少于 3 次、数据集不同、条件不同都必须拒绝比较。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_runs.py"


def _report(path: Path, *, dataset_hash: str = "abc123", value: float = 1.0, provider: str = "scripted") -> Path:
    path.write_text(
        json.dumps(
            {
                "report_id": path.stem,
                "dataset": {"name": "eval_cases", "dataset_hash": dataset_hash},
                "environment": {
                    "provider": provider,
                    "model": "scripted",
                    "max_steps": 6,
                    "wall_clock_s": 30.0,
                    "window_turns": 6,
                    "demo_now": "2026-11-04T12:00:00+08:00",
                    "token_budget": 6000,
                    "prompt_version": "v3",
                },
                "metrics": {"intent_accuracy": value, "tools_accuracy": value, "args_accuracy": value,
                            "escalation_accuracy": value, "degraded_cases": 0, "latency_p95_ms": 10, "mean_cost_cny": None},
                "cases": [{"case_id": "dev-refund-simple-1", "intent_ok": True, "tools_ok": True,
                           "args_ok": True, "escalation_ok": True}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _run(*arms: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arms], capture_output=True, text=True, encoding="utf-8")


def test_rejects_fewer_than_three_runs(tmp_path: Path) -> None:
    one = _report(tmp_path / "a.json")
    done = _run(f"--arm=only={one}")
    assert done.returncode != 0
    assert "至少 3 次" in (done.stdout + done.stderr)


def test_rejects_mixed_dataset(tmp_path: Path) -> None:
    left = [_report(tmp_path / f"l{i}.json", dataset_hash="aaa") for i in range(3)]
    right = [_report(tmp_path / f"r{i}.json", dataset_hash="bbb") for i in range(3)]
    done = _run(f"--arm=baseline={','.join(map(str, left))}", f"--arm=candidate={','.join(map(str, right))}")
    assert done.returncode != 0
    assert "数据集不一致" in (done.stdout + done.stderr)


def test_accepts_three_each_and_reports_median_range(tmp_path: Path) -> None:
    left = [_report(tmp_path / f"l{i}.json", value=1.0) for i in range(3)]
    right = [_report(tmp_path / f"r{i}.json", value=0.9) for i in range(3)]
    out = tmp_path / "cmp.md"
    done = _run(
        f"--arm=baseline={','.join(map(str, left))}",
        f"--arm=candidate={','.join(map(str, right))}",
        f"--out={out}",
    )
    assert done.returncode == 0, done.stderr
    text = out.read_text(encoding="utf-8")
    assert "1.0000 [1.0000–1.0000]" in text
    assert "0.9000 [0.9000–0.9000]" in text
    assert "中位数差值不等于统计显著性" in text
