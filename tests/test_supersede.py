"""继承封存：同一批 12 条样本只改运行条件时，旧记录保留、新记录显式关联旧版本、且只能运行一次。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "supersede_seal.py"

BASE_CONFIG = {
    "model": "deepseek-v4.1-flash-1017",
    "base_url": "https://example.invalid/v1",
    "prompt_version": "v3",
    "demo_now": "2026-11-04T12:00:00+08:00",
    "max_steps": 6,
    "token_budget": 12000,
    "wall_clock_s": 30.0,
    "window_turns": 6,
    "max_output_tokens": 2000,
    "refund_auto_limit_cents": 20000,
    "refund_window_days": 7,
    "price_in_usd_per_mtok": 0.15,
    "price_out_usd_per_mtok": 0.60,
    "usd_cny_fx": 7.2,
}

DECLARATION = {
    "author": "isolation-a",
    "label_reviewer": "isolation-b",
    "custodian": "custodian-c",
    "independent_from_implementer": True,
    "no_candidate_code_or_old_cases_seen": True,
    "implementer_has_not_seen_new_cases": True,
    "semantic_overlap_reviewed": True,
}


def _row(index: int, intent: str) -> dict:
    tools = {
        "refund": ["query_order", "refund_preview"],
        "address_change": ["query_order"],
        "shipping_urge": ["query_order", "check_logistics"],
        "other": [],
    }[intent]
    needs_human = intent in {"refund", "address_change"}
    return {
        "case_id": f"blind-{index:06d}",
        "user_id": "U001",
        "text": f"合成占位样本 {index}：请帮我处理一下这个单子，谢谢配合。",
        "order_id": "O1001" if tools else None,
        "intent": intent,
        "expected_tools": tools,
        "expected_args": [{"name": name, "arguments": {"order_id": "O1001"}, "error_code": None} for name in tools],
        "expected_needs_human": needs_human,
        "expected_reason": "REFUND_OVER_LIMIT" if needs_human else None,
        "label_reason": "合成占位标注，仅用于测试封存机制",
    }


def _write_dataset(path: Path) -> Path:
    rows = []
    index = 1
    for intent in ("refund", "address_change", "shipping_urge", "other"):
        for _ in range(3):
            rows.append(_row(index, intent))
            index += 1
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, value) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _seal_first(tmp_path: Path) -> tuple[Path, Path, Path]:
    """旧封存：wall_clock_s=30。"""
    work = tmp_path / "work-30s"
    dataset = _write_dataset(tmp_path / "candidate-12.jsonl")
    settings = _write_json(tmp_path / "settings-30s.json", BASE_CONFIG)
    attestation = _write_json(tmp_path / "attestation.json", DECLARATION)
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "blind_eval.py"), "freeze",
         "--work", str(work), "--config", str(settings), "--implementer", "implementer"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    done = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "blind_eval.py"), "seal",
         "--work", str(work), "--dataset", str(dataset), "--attestation", str(attestation)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert done.returncode == 0, done.stderr
    return work, dataset, attestation


def _supersede(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")


def test_supersede_links_previous_seal_and_keeps_old_record(tmp_path: Path) -> None:
    old_work, dataset, attestation = _seal_first(tmp_path)
    old_seal_bytes = (old_work / "seal.json").read_bytes()

    new_settings = _write_json(tmp_path / "settings-60s.json", {**BASE_CONFIG, "wall_clock_s": 60.0})
    new_work = tmp_path / "work-60s"
    done = _supersede(
        "--previous-work", str(old_work), "--work", str(new_work),
        "--settings", str(new_settings), "--dataset", str(dataset),
        "--attestation", str(attestation), "--implementer", "implementer",
        "--reason", "wall_clock_s 30→60，代理抖动防护",
    )
    assert done.returncode == 0, done.stderr
    summary = json.loads(done.stdout)
    assert summary["changed_config"] == {"wall_clock_s": [30.0, 60.0]}

    candidate = json.loads((new_work / "candidate.json").read_text(encoding="utf-8"))
    assert candidate["supersedes"]["same_dataset"] is True
    assert candidate["supersedes"]["previous_attempt_consumed"] is False
    assert candidate["supersedes"]["previous_seal_sha256"] == summary["supersedes_seal_sha256"]
    assert candidate["config"]["wall_clock_s"] == 60.0
    assert (new_work / "seal.json").exists()
    # 旧记录原样保留
    assert (old_work / "seal.json").read_bytes() == old_seal_bytes


def test_refuses_when_previous_attempt_consumed(tmp_path: Path) -> None:
    old_work, dataset, attestation = _seal_first(tmp_path)
    (old_work / "attempt.json").write_text(json.dumps({"state": "consumed"}), encoding="utf-8")
    new_settings = _write_json(tmp_path / "settings-60s.json", {**BASE_CONFIG, "wall_clock_s": 60.0})
    done = _supersede(
        "--previous-work", str(old_work), "--work", str(tmp_path / "work-60s"),
        "--settings", str(new_settings), "--dataset", str(dataset),
        "--attestation", str(attestation), "--implementer", "implementer", "--reason", "retry",
    )
    assert done.returncode == 2
    assert not (tmp_path / "work-60s").exists()


def test_refuses_different_dataset(tmp_path: Path) -> None:
    old_work, dataset, attestation = _seal_first(tmp_path)
    other = _write_dataset(tmp_path / "another-12.jsonl")
    other.write_text(other.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    new_settings = _write_json(tmp_path / "settings-60s.json", {**BASE_CONFIG, "wall_clock_s": 60.0})
    done = _supersede(
        "--previous-work", str(old_work), "--work", str(tmp_path / "work-60s"),
        "--settings", str(new_settings), "--dataset", str(other),
        "--attestation", str(attestation), "--implementer", "implementer", "--reason", "换数据",
    )
    assert done.returncode == 2
    assert not (tmp_path / "work-60s").exists()


def test_refuses_unexpected_config_change(tmp_path: Path) -> None:
    old_work, dataset, attestation = _seal_first(tmp_path)
    new_settings = _write_json(tmp_path / "settings-60s.json", {**BASE_CONFIG, "wall_clock_s": 60.0, "max_steps": 5})
    done = _supersede(
        "--previous-work", str(old_work), "--work", str(tmp_path / "work-60s"),
        "--settings", str(new_settings), "--dataset", str(dataset),
        "--attestation", str(attestation), "--implementer", "implementer", "--reason", "顺手改步数",
    )
    assert done.returncode == 2
    assert "max_steps" in done.stderr or not (tmp_path / "work-60s").exists()
