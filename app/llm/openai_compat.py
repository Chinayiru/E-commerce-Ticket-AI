"""OpenAI 兼容 Provider（W1-2 接入，W2 起作为唯一真实模型入口）。

约束（IMPLEMENTATION §5）：
- 最多重试一次，只对 429 / 连接失败 / 5xx；401/403/参数错不重试；
- 退避也吃 deadline，超时优先记 timeout（由 loop 判定）；
- 输出允许去掉**单层** Markdown 围栏后严格 JSON 校验，不 eval、不从混杂文本里猜。
"""

from __future__ import annotations

import json
import time
from typing import Any, Mapping

from app.config import Config
from app.llm.base import InvalidModelOutput, ModelError, UpstreamError
from app.schemas import ModelDecision, ModelRequest, ModelResponse, Usage

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_FENCE_RE = "```"


class OpenAICompatProvider:
    """``/chat/completions`` 的最小封装；不引入任何编排框架。"""

    provider_name = "openai"

    def __init__(
        self,
        config: Config,
        *,
        client: Any | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        if not config.api_key:
            raise UpstreamError("缺少 OPENAI_API_KEY，无法调用真实模型")
        self._config = config
        self._sleep = sleep
        if client is None:
            import httpx  # 延迟导入：scripted 模式完全不需要 httpx

            client = httpx.Client(timeout=None)
        self._client = client

    # ------------------------------------------------------------------ public
    def complete(self, request: ModelRequest) -> ModelResponse:
        payload = self._payload(request)
        last_error: Exception | None = None

        for attempt in range(2):
            if request.remaining_ms <= 0:
                raise UpstreamError("模型调用前已超时")
            try:
                response = self._post(payload, request.remaining_ms)
            except UpstreamError:
                raise
            except Exception as exc:  # 连接类错误 → 可重试一次
                last_error = exc
                if attempt == 0:
                    self._backoff(request)
                    continue
                raise UpstreamError(f"模型连接失败：{type(exc).__name__}: {exc}") from exc

            status = getattr(response, "status_code", 0)
            if status in _RETRYABLE_STATUS and attempt == 0:
                last_error = UpstreamError(f"上游返回 {status}", status_code=status)
                self._backoff(request)
                continue
            if status in (401, 403):
                raise UpstreamError(f"上游鉴权失败（{status}），不重试", status_code=status)
            if status >= 400:
                raise UpstreamError(f"上游返回 {status}", status_code=status)

            return self._parse(response)

        raise UpstreamError(f"上游重试用尽：{last_error}")

    # ---------------------------------------------------------------- internal
    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        return {
            "model": self._config.model,
            "messages": [_to_openai_message(item) for item in request.messages],
            "tools": [
                {"type": "function", "function": spec} for spec in request.tools
            ] or None,
            "tool_choice": "auto" if request.tools else None,
            "max_tokens": self._config.max_output_tokens,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

    def _post(self, payload: Mapping[str, Any], remaining_ms: int) -> Any:
        timeout = max(0.1, remaining_ms / 1000.0)
        body = {key: value for key, value in payload.items() if value is not None}
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        return self._client.post(
            url,
            json=body,
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def _parse(self, response: Any) -> ModelResponse:
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise InvalidModelOutput(f"上游响应结构异常：{exc}") from exc

        text = _strip_fence(str(content or "")).strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidModelOutput(f"模型输出不是合法 JSON：{exc}", raw_text=text) from exc
        try:
            decision = ModelDecision.from_payload(payload)
        except (ValueError, TypeError) as exc:
            raise InvalidModelOutput(f"模型输出不符合契约：{exc}", raw_text=text) from exc

        usage_raw = data.get("usage") or {}
        usage = Usage(
            input_tokens=usage_raw.get("prompt_tokens"),
            output_tokens=usage_raw.get("completion_tokens"),
            source="reported",
            cost_cny=self._config.estimate_cost_cny(
                usage_raw.get("prompt_tokens") or 0, usage_raw.get("completion_tokens") or 0
            )
            if usage_raw
            else None,
        )
        return ModelResponse(decision=decision, usage=usage, raw_text=text)

    def _backoff(self, request: ModelRequest) -> None:
        delay = min(0.5, max(0.0, request.remaining_ms / 1000.0 - 0.05))
        if delay > 0:
            self._sleep(delay)


def _to_openai_message(message: Mapping[str, Any]) -> dict[str, Any]:
    role = str(message.get("role") or "user")
    content = str(message.get("content") or "")
    if role == "tool":
        # 首版不用 tool_call_id 回填：把工具结果作为用户侧事实陈述，避免伪造 id。
        return {"role": "user", "content": f"工具返回：{content}"}
    if role not in ("system", "user", "assistant"):
        role = "user"
    return {"role": role, "content": content}


def _strip_fence(text: str) -> str:
    """只剥一层 ```lang ... ``` 围栏，别的一律不动。"""
    stripped = text.strip()
    if not stripped.startswith(_FENCE_RE):
        return stripped
    body = stripped[len(_FENCE_RE) :]
    newline = body.find("\n")
    if newline == -1:
        return stripped
    body = body[newline + 1 :]
    if body.rstrip().endswith(_FENCE_RE):
        body = body.rstrip()[: -len(_FENCE_RE)]
    return body


def build_provider(config: Config, **kwargs: Any) -> Any:
    """按 ``config.provider`` 选 Provider；scripted 只允许测试注入脚本。"""
    if config.provider == "openai":
        return OpenAICompatProvider(config, **kwargs)
    if config.provider == "scripted":
        raise ModelError("scripted 模式必须显式注入 ScriptedModel，不能按配置自动构造")
    raise ModelError(f"未知 provider：{config.provider!r}")
