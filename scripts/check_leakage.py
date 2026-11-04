"""防作弊检查（IMPLEMENTATION §10）：

1. 24 条 / 50 条题干（及其近似改写）不得出现在任何一版提示词里；
2. 提示词里不得出现策略阈值、审批字段；
3. 记录检查时的提示词指纹，便于写进报告。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.prompts import get_prompt, prompt_hash, prompt_versions  # noqa: E402
from app.eval.datasets import load_drafts, load_eval_cases, load_holdout  # noqa: E402

FORBIDDEN_PATTERNS = {
    "策略阈值_金额": re.compile(r"200\s*元|20000\s*分"),
    "策略阈值_天数": re.compile(r"7\s*天|七天"),
    "策略阈值_失败次数": re.compile(r"连续失败\s*2|失败\s*≥\s*2"),
    "审批字段": re.compile(r"approved|approval", re.IGNORECASE),
}
NGRAM = 8
THRESHOLD = 0.6


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _ngrams(text: str, size: int = NGRAM) -> set[str]:
    body = _normalize(text)
    return {body[i : i + size] for i in range(max(0, len(body) - size + 1))}


def check(threshold: float = THRESHOLD) -> dict[str, object]:
    corpus = list(load_eval_cases().rows) + list(load_holdout().rows) + list(load_drafts().rows)
    findings: list[dict[str, object]] = []
    for version in prompt_versions():
        prompt = _normalize(get_prompt(version))
        prompt_grams = _ngrams(prompt)
        for name, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(prompt):
                findings.append({"prompt": version, "kind": name, "case_id": None})
        for row in corpus:
            grams = _ngrams(str(row.get("text") or ""))
            if not grams:
                continue
            overlap = len(grams & prompt_grams) / len(grams)
            if overlap >= threshold:
                findings.append(
                    {"prompt": version, "kind": "case_text_overlap", "case_id": row.get("case_id"), "overlap": round(overlap, 3)}
                )
    return {
        "ok": not findings,
        "corpus_size": len(corpus),
        "threshold": threshold,
        "prompts": {version: prompt_hash(version) for version in prompt_versions()},
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=THRESHOLD)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    report = check(args.threshold)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
