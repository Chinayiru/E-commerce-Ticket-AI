"""运行配置：默认值可直接离线运行，环境变量覆盖，缺项 / 非法项报错到具体键名。

约束（见 docs/DEVELOPMENT.md 1.2）：
- 不内置任何真实凭据；``OPENAI_API_KEY`` 只从环境读取，没有默认值。
- 路径不硬编码在业务代码里，统一由 ``Config.db_path`` 提供。
- ``load_config(overrides=...)`` 是测试与后续 CLI/env 的统一入口，等价于“先读环境、再覆盖”。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

#: 演示时区与默认时间锚点（docs/IMPLEMENTATION.md §3）。
TZ_SHANGHAI = timezone(timedelta(hours=8))
DEFAULT_DEMO_NOW = "2026-11-04T12:00:00+08:00"

#: 环境变量名 -> Config 字段名。REFUND_AUTO_LIMIT 以“元”配置，内部转整数分。
ENV_FIELDS: dict[str, str] = {
    "PROVIDER": "provider",
    "MODEL": "model",
    "MAX_STEPS": "max_steps",
    "TOKEN_BUDGET": "token_budget",
    "WALL_CLOCK_S": "wall_clock_s",
    "DB_PATH": "db_path",
    "DEMO_NOW": "demo_now",
    "REFUND_AUTO_LIMIT": "refund_auto_limit_cents",
    "REFUND_WINDOW_DAYS": "refund_window_days",
    "OPENAI_BASE_URL": "base_url",
    "OPENAI_API_KEY": "api_key",
}

ALLOWED_PROVIDERS = ("scripted", "openai")


class ConfigError(ValueError):
    """配置缺失或非法。``field`` 是环境变量名，便于直接定位。"""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"配置项 {field} 无效：{message}")


@dataclass(frozen=True, slots=True)
class Config:
    """一次运行的不可变配置快照。"""

    provider: str = "scripted"
    model: str = "gpt-4o-mini"
    max_steps: int = 6
    token_budget: int = 6000
    wall_clock_s: float = 30.0
    db_path: str = "runs.db"
    demo_now: datetime = datetime(2026, 11, 4, 12, 0, tzinfo=TZ_SHANGHAI)
    refund_auto_limit_cents: int = 20_000
    refund_window_days: int = 7
    base_url: str = "https://api.openai.com/v1"
    api_key: str | None = None

    def with_overrides(self, **overrides: Any) -> "Config":
        """返回替换后的新配置，走与 ``load_config`` 相同的校验。"""
        unknown = sorted(set(overrides) - set(Config.__dataclass_fields__))
        if unknown:
            raise ConfigError(unknown[0], "未知配置字段，允许的字段为 Config 的字段名")
        current = {name: getattr(self, name) for name in Config.__dataclass_fields__}
        return _build(current, overrides)

    def as_mapping(self) -> dict[str, Any]:
        """可安全落库 / 打印的配置（不含凭据）。"""
        return {
            "provider": self.provider,
            "model": self.model,
            "max_steps": self.max_steps,
            "token_budget": self.token_budget,
            "wall_clock_s": self.wall_clock_s,
            "db_path": self.db_path,
            "demo_now": self.demo_now.isoformat(),
            "refund_auto_limit_cents": self.refund_auto_limit_cents,
            "refund_window_days": self.refund_window_days,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
        }


def load_config(
    overrides: Mapping[str, Any] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Config:
    """读取配置：默认值 < 环境变量 < ``overrides``。

    ``overrides`` 使用 Config 字段名（如 ``max_steps=3``）；``env`` 便于测试注入，
    缺省读进程环境。``provider=openai`` 却缺 Key 时立即失败，不等到调用模型。
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    raw: dict[str, Any] = {}

    for env_name, field_name in ENV_FIELDS.items():
        value = environ.get(env_name)
        if value is not None and value.strip() != "":
            raw[field_name] = value

    if overrides:
        unknown = sorted(set(overrides) - set(Config.__dataclass_fields__))
        if unknown:
            raise ConfigError(unknown[0], "未知配置字段，允许的字段为 Config 的字段名")
        raw.update(overrides)

    return _build(raw, {})


def _build(raw: Mapping[str, Any], overrides: Mapping[str, Any]) -> Config:
    merged: dict[str, Any] = dict(raw)
    merged.update(overrides)

    provider = _as_str(merged, "provider", "PROVIDER", "scripted")
    if provider not in ALLOWED_PROVIDERS:
        raise ConfigError("PROVIDER", f"只支持 {ALLOWED_PROVIDERS}，收到 {provider!r}")

    api_key = merged.get("api_key")
    if api_key is not None:
        api_key = str(api_key).strip() or None
    if provider == "openai" and not api_key:
        raise ConfigError(
            "OPENAI_API_KEY",
            "provider=openai 时必须通过环境变量 OPENAI_API_KEY 提供密钥（本仓库不写默认值）",
        )

    model = _as_str(merged, "model", "MODEL", "gpt-4o-mini")
    max_steps = _as_int(merged, "max_steps", "MAX_STEPS", 6, minimum=1)
    token_budget = _as_int(merged, "token_budget", "TOKEN_BUDGET", 6000, minimum=1)
    wall_clock_s = _as_float(merged, "wall_clock_s", "WALL_CLOCK_S", 30.0, minimum_exclusive=0.0)
    db_path = _as_str(merged, "db_path", "DB_PATH", "runs.db")
    demo_now = _as_datetime(merged, "demo_now", "DEMO_NOW", DEFAULT_DEMO_NOW)
    refund_auto_limit_cents = _as_int(
        merged,
        "refund_auto_limit_cents",
        "REFUND_AUTO_LIMIT",
        20_000,
        minimum=0,
        env_name_is_yuan=True,
    )
    refund_window_days = _as_int(merged, "refund_window_days", "REFUND_WINDOW_DAYS", 7, minimum=0)
    base_url = _as_str(merged, "base_url", "OPENAI_BASE_URL", "https://api.openai.com/v1")

    return Config(
        provider=provider,
        model=model,
        max_steps=max_steps,
        token_budget=token_budget,
        wall_clock_s=wall_clock_s,
        db_path=db_path,
        demo_now=demo_now,
        refund_auto_limit_cents=refund_auto_limit_cents,
        refund_window_days=refund_window_days,
        base_url=base_url,
        api_key=api_key,
    )


def _as_str(raw: Mapping[str, Any], field: str, env_name: str, default: str) -> str:
    value = raw.get(field, default)
    text = str(value).strip()
    if not text:
        raise ConfigError(env_name, "不能为空")
    return text


def _as_int(
    raw: Mapping[str, Any],
    field: str,
    env_name: str,
    default: int,
    *,
    minimum: int | None = None,
    env_name_is_yuan: bool = False,
) -> int:
    value = raw.get(field, default)
    if field in raw and env_name_is_yuan and not isinstance(value, int):
        # REFUND_AUTO_LIMIT 在环境变量里以“元”书写，允许 200 或 199.5。
        try:
            value = round(float(value) * 100)
        except (TypeError, ValueError) as exc:
            raise ConfigError(env_name, f"应为数字（单位：元），收到 {value!r}") from exc
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ConfigError(env_name, f"应为整数，收到 {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(env_name, f"应为整数，收到 {value!r}") from exc
    if minimum is not None and number < minimum:
        raise ConfigError(env_name, f"必须 >= {minimum}，收到 {number}")
    return number


def _as_float(
    raw: Mapping[str, Any],
    field: str,
    env_name: str,
    default: float,
    *,
    minimum_exclusive: float | None = None,
) -> float:
    value = raw.get(field, default)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ConfigError(env_name, f"应为数字，收到 {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(env_name, f"应为数字，收到 {value!r}") from exc
    if minimum_exclusive is not None and number <= minimum_exclusive:
        raise ConfigError(env_name, f"必须 > {minimum_exclusive}，收到 {number}")
    return number


def _as_datetime(raw: Mapping[str, Any], field: str, env_name: str, default: str) -> datetime:
    value = raw.get(field, default)
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise ConfigError(env_name, f"应为 ISO 8601 时间，收到 {value!r}") from exc
    if parsed.tzinfo is None:
        raise ConfigError(env_name, "必须带时区（例如 2026-11-04T12:00:00+08:00），否则时效判定不可复现")
    return parsed
