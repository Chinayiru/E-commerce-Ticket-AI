"""数据集装载与指纹：一切“可复现”都从这里的哈希开始。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
EVAL_CASES = DATA_DIR / "eval_cases.jsonl"
HOLDOUT_CASES = DATA_DIR / "holdout.jsonl"
DRAFTS_50 = DATA_DIR / "drafts_50.jsonl"


@dataclass(frozen=True, slots=True)
class Dataset:
    name: str
    path: Path
    rows: tuple[dict[str, Any], ...]
    sha256: str

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.rows)


def load_dataset(path: Path, *, name: str | None = None) -> Dataset:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"数据集不存在：{path}（先跑 python scripts/seed_datasets.py）")
    raw = path.read_bytes()
    rows = tuple(json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip())
    return Dataset(
        name=name or path.stem,
        path=path,
        rows=rows,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def load_eval_cases(path: Path | None = None) -> Dataset:
    return load_dataset(path or EVAL_CASES, name="eval_cases")


def load_holdout(path: Path | None = None) -> Dataset:
    """历史兼容入口：默认文件已暴露，只作回归；新独立集见 scripts/blind_eval.py。"""
    return load_dataset(path or HOLDOUT_CASES, name="holdout")


def load_drafts(path: Path | None = None) -> Dataset:
    return load_dataset(path or DRAFTS_50, name="drafts_50")


def mock_data_hash() -> str:
    """合成订单表的指纹，防止“改了订单数据再说结果没变”。"""
    from app.tools.mock_data import MOCK_ORDERS

    payload = json.dumps(MOCK_ORDERS, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
