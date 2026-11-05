"""工具注册表：``@tool`` 声明 → 参数白名单校验 → 执行 → 结构化结果。

设计约束（docs/IMPLEMENTATION.md §4）：
- 参数 schema 由工具声明，未声明的键（如 ``approved=true``）一律 ``INVALID_ARGS``；
- 工具内部异常不抛给 loop，统一转 ``TOOL_ERROR``；
- 注册表可被 loop 枚举（名称 + JSON Schema），loop 不 import 具体工具实现。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from app.schemas import ToolContext, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
INVALID_ARGS = "INVALID_ARGS"
TOOL_ERROR = "TOOL_ERROR"

#: 仅支持首版声明的类型；未支持类型在注册时直接失败，避免生成“看似可用”的 Schema。
_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
}

Handler = Callable[[Mapping[str, Any], ToolContext], ToolResult]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    spec: ToolSpec
    handler: Handler


class ToolRegistry:
    """一个进程内可枚举的工具表；测试可自建实例，不污染默认表。"""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    # ------------------------------------------------------------- registration
    def tool(
        self,
        *,
        name: str,
        description: str,
        parameters: Mapping[str, Mapping[str, Any]],
        returns: Mapping[str, str] | None = None,
        irreversible: bool = False,
    ) -> Callable[[Handler], Handler]:
        """装饰器：声明名称、参数 schema、返回结构、是否不可逆。"""

        def decorate(handler: Handler) -> Handler:
            spec = ToolSpec(
                name=name,
                description=description,
                parameters={key: dict(value) for key, value in parameters.items()},
                returns=dict(returns or {}),
                irreversible=irreversible,
            )
            self.register(spec, handler)
            handler.__tool_spec__ = spec  # type: ignore[attr-defined]
            return handler

        return decorate

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具重复注册：{spec.name}")
        for param_name, param_spec in spec.parameters.items():
            param_type = param_spec.get("type", "string")
            if param_type not in _TYPE_CHECKS:
                raise ValueError(f"工具 {spec.name} 的参数 {param_name} 使用了不支持的类型 {param_type!r}")
        self._tools[spec.name] = RegisteredTool(spec=spec, handler=handler)

    # ------------------------------------------------------------------ queries
    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [item.spec for item in self._tools.values()]

    def schema_list(self) -> list[dict[str, Any]]:
        """供模型使用的工具声明列表。"""
        return [spec.json_schema() for spec in self.specs()]

    def is_irreversible(self, name: str) -> bool:
        item = self._tools.get(name)
        return bool(item and item.spec.irreversible)

    # ------------------------------------------------------------------ execute
    def validate(self, name: str, arguments: Mapping[str, Any]) -> ToolResult | None:
        """只做参数校验、不执行；loop 必须在钩子之前调用它。

        否则 ``approved=true`` 这类越权字段会先被钩子截成 APPROVAL_REQUIRED，
        掩盖掉本该返回的 INVALID_ARGS（合同要求参数校验优先）。
        """
        item = self.get(name)
        if item is None:
            return ToolResult.failure("TOOL_UNAVAILABLE", f"未知工具：{name}")
        return self._validate(item.spec, arguments)

    def execute(self, name: str, arguments: Mapping[str, Any], context: ToolContext) -> tuple[ToolResult, int]:
        """执行一次工具尝试，返回 (结构化结果, 耗时毫秒)；任何失败都不抛异常。"""
        started = time.perf_counter()
        item = self._tools.get(name)
        if item is None:
            return self._finish(ToolResult.failure(TOOL_UNAVAILABLE, f"未知工具：{name}"), started)

        invalid = self._validate(item.spec, arguments)
        if invalid is not None:
            return self._finish(invalid, started)

        try:
            result = item.handler(arguments, context)
        except Exception as exc:  # 工具缺陷不阻断 loop，但必须带错误码落库
            logger.warning("tool %s raised %s", name, type(exc).__name__)
            result = ToolResult.failure(TOOL_ERROR, f"{type(exc).__name__}: {exc}")

        if not isinstance(result, ToolResult):
            result = ToolResult.failure(TOOL_ERROR, f"工具 {name} 返回了非 ToolResult 对象")
        return self._finish(result, started)

    def _finish(self, result: ToolResult, started: float) -> tuple[ToolResult, int]:
        elapsed_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
        return result, elapsed_ms

    def _validate(self, spec: ToolSpec, arguments: Mapping[str, Any]) -> ToolResult | None:
        if not isinstance(arguments, Mapping):
            return ToolResult.failure(INVALID_ARGS, "arguments 必须是对象")

        unknown = sorted(set(arguments) - set(spec.parameters))
        if unknown:
            return ToolResult.failure(
                INVALID_ARGS,
                f"工具 {spec.name} 不接受参数：{', '.join(unknown)}",
                hint="只允许 schema 中声明的参数",
            )

        missing = [
            key
            for key, param in spec.parameters.items()
            if param.get("required", True) and key not in arguments
        ]
        if missing:
            return ToolResult.failure(
                INVALID_ARGS,
                f"工具 {spec.name} 缺少参数：{', '.join(missing)}",
                hint="按 schema 补全必填参数",
            )

        for key, param in spec.parameters.items():
            if key not in arguments:
                continue
            value = arguments[key]
            if value is None and not param.get("required", True):
                continue
            check = _TYPE_CHECKS[param.get("type", "string")]
            if not check(value):
                return ToolResult.failure(
                    INVALID_ARGS,
                    f"参数 {key} 类型应为 {param.get('type', 'string')}，收到 {type(value).__name__}",
                )
        return None


#: 默认注册表：业务模块通过本模块的 ``tool`` 装饰器注册进去。
_DEFAULT = ToolRegistry()


def tool(
    *,
    name: str,
    description: str,
    parameters: Mapping[str, Mapping[str, Any]],
    returns: Mapping[str, str] | None = None,
    irreversible: bool = False,
) -> Callable[[Handler], Handler]:
    return _DEFAULT.tool(
        name=name,
        description=description,
        parameters=parameters,
        returns=returns,
        irreversible=irreversible,
    )


def default_registry() -> ToolRegistry:
    """返回默认注册表，并按需 import 业务模块触发装饰器注册。"""
    import app.tools.actions  # noqa: F401  （注册副作用）
    import app.tools.business  # noqa: F401

    return _DEFAULT
