"""pytest 全局配置：把仓库根加入 sys.path，并提供临时库工厂 fixture。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_config  # noqa: E402
from app.store.db import Database  # noqa: E402


@pytest.fixture
def make_env(tmp_path: Path):
    """返回 (config, store) 工厂；每个测试用自己的临时 SQLite 文件。"""

    def _make(**overrides):
        settings = dict(overrides)
        settings.setdefault("db_path", str(tmp_path / "runs.db"))
        config = load_config(settings, env={})
        return config, Database(config.db_path)

    return _make
