"""生命周期钩子：前置审批、后置审计、PII 脱敏（DESIGN §6.2、§9.2）。

钩子是“策略之外的最后一道闸”：
- 前置钩子决定某个工具调用**能否**执行（不可逆操作首版一律拦成 APPROVAL_REQUIRED）；
- 后置钩子只做审计与脱敏，不修改业务返回值；
- 审计落 JSONL，写失败降级为告警，绝不影响主流程。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from app.config import Config
from app.redaction import mask_pii
from app.schemas import ToolCallRequest, ToolSpec

#: 首版一律需要人工审批的工具（无成功分支，见 IMPLEMENTATION §4）。
ALWAYS_APPROVAL_TOOLS = ("refund_submit", "address_change")

__all__ = [
    "ALWAYS_APPROVAL_TOOLS",
    "HookDecision",
    "Hooks",
    "LifecycleHooks",
    "build_default_hooks",
    "mask_pii",
    "request_from_decision",
]


@dataclass(frozen=True, slots=True)
class HookDecision:
    """前置钩子结论。``approval_required`` 为真时 loop 不得执行该调用。"""

    allowed: bool
    approval_required: bool = False
    reason: str | None = None

    @classmethod
    def allow(cls) -> "HookDecision":
        return cls(allowed=True)

    @classmethod
    def intercept(cls, reason: str) -> "HookDecision":
        return cls(allowed=False, approval_required=True, reason=reason)


class Hooks(Protocol):
    def pre_tool(self, spec: ToolSpec, arguments: dict[str, Any], *, run_id: str, step: int) -> HookDecision: ...

    def post_tool(self, *, run_id: str, name: str, ok: bool, duration_ms: int, error_code: str | None) -> None: ...


class LifecycleHooks:
    """默认钩子实现：不可逆工具拦成审批，其余放行；所有调用写审计。"""

    def __init__(self, config: Config, *, audit_path: str | Path | None = None) -> None:
        self._config = config
        self._audit_path = Path(audit_path) if audit_path else None
        self._audit: list[dict[str, Any]] = []

    @property
    def audit_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._audit)

    def pre_tool(
        self, spec: ToolSpec, arguments: dict[str, Any], *, run_id: str, step: int
    ) -> HookDecision:
        decision = HookDecision.allow()
        if spec.irreversible or spec.name in ALWAYS_APPROVAL_TOOLS:
            decision = HookDecision.intercept("APPROVAL_REQUIRED")
        self._write(
            {
                "event": "pre_tool",
                "run_id": run_id,
                "step": step,
                "tool": spec.name,
                "irreversible": bool(spec.irreversible),
                "arguments": _mask_arguments(arguments),
                "allowed": decision.allowed,
                "approval_required": decision.approval_required,
                "reason": decision.reason,
            }
        )
        return decision

    def post_tool(
        self, *, run_id: str, name: str, ok: bool, duration_ms: int, error_code: str | None
    ) -> None:
        self._write(
            {
                "event": "post_tool",
                "run_id": run_id,
                "tool": name,
                "ok": ok,
                "duration_ms": duration_ms,
                "error_code": error_code,
            }
        )

    # -- internal ---------------------------------------------------------
    def _write(self, record: dict[str, Any]) -> None:
        enriched = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        self._audit.append(enriched)
        if self._audit_path is None:
            return
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(enriched, ensure_ascii=False) + "\n")
        except OSError:
            # 审计不可用不能拖垮主流程，但要在记录里留下痕迹。
            self._audit.append({"ts": enriched["ts"], "event": "audit_write_failed"})


def _mask_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in arguments.items():
        masked[key] = mask_pii(value) if isinstance(value, str) else value
    return masked


def build_default_hooks(config: Config) -> LifecycleHooks:
    """默认审计文件：``<log_dir>/audit-YYYYMMDD.jsonl``（路径来自 config，不硬编码）。"""
    stamp = config.demo_now.strftime("%Y%m%d")
    return LifecycleHooks(config, audit_path=Path(config.log_dir) / f"audit-{stamp}.jsonl")


def request_from_decision(name: str, arguments: dict[str, Any]) -> ToolCallRequest:
    """便捷构造（loop 与测试共用），参数校验失败会抛 ValueError。"""
    return ToolCallRequest(name=name, arguments=arguments)
