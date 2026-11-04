"""模型与审批的可替换接口。

loop 只依赖这里的 Protocol，不依赖任何具体实现；scripted 与 W2 的真实
Provider 都实现同一组签名，替换时 loop 不需要改动。
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from app.schemas import ApprovalDecision, ModelRequest, ModelResponse


class ModelError(RuntimeError):
    """模型侧错误（超时、上游失败、输出无法解析）。loop 会据此降级而不抛给调用方。"""


class InvalidModelOutput(ModelError):
    """模型输出不是合法 JSON / 不符合输出契约；loop 允许修复一次。"""

    def __init__(self, message: str, *, raw_text: str = "") -> None:
        super().__init__(message)
        self.raw_text = raw_text


class UpstreamError(ModelError):
    """上游不可用（鉴权失败、重试用尽、连接中断），直接算终止原因。"""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@runtime_checkable
class ModelProvider(Protocol):
    """一次 Provider 请求 = 循环的一步。"""

    provider_name: str

    def complete(self, request: ModelRequest) -> ModelResponse:
        """返回下一步决策；失败抛 ModelError。"""
        ...


@runtime_checkable
class ApprovalGate(Protocol):
    """不可逆操作前的确认闸门；真实实现是人工审批，scripted 实现按脚本返回。"""

    def request_approval(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        run_id: str,
    ) -> ApprovalDecision:
        ...


class DenyAllApprovalGate:
    """安全默认：没有明确审批就拒绝一切不可逆操作。"""

    approver = "deny-all"

    def request_approval(
        self,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        run_id: str,
    ) -> ApprovalDecision:
        return ApprovalDecision(
            approved=False,
            approver=self.approver,
            reason=f"{tool_name} 需要人工确认，当前未配置审批来源",
        )
