"""HTTP 边界（IMPLEMENTATION §9）：把循环结果映射成状态码，别的地方不改语义。

状态码约定（改这里等于改对外契约）：
- 200：正常完成，包括“策略性转人工”；
- 422：输入非法（不建会话）；
- 409：同 user+ticket 仍有 running 会话；
- 503：仅 upstream_error，响应体仍是完整 RunResult；
- 500：内部错误/持久化失败。
timeout / max_steps / token_budget / invalid_output 一律 200 + degraded。
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import time
from typing import Any, AsyncIterator

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.config import Config, load_config
from app.core.loop import ExecutionLoop
from app.llm.openai_compat import OpenAICompatProvider
from app.redaction import mask_pii
from app.store.db import Database, StoreError


def _build_provider(config: Config) -> Any:
    if config.provider == "openai":
        return OpenAICompatProvider(config)
    return None


def create_app(
    config: Config | None = None,
    *,
    store: Database | None = None,
    provider: Any | None = None,
) -> FastAPI:
    cfg = config or load_config()
    db = store or Database(cfg.db_path)
    model = provider if provider is not None else _build_provider(cfg)

    app = FastAPI(title="E-commerce Ticket Agent", version="w1")

    page = Path(__file__).with_name("static") / "index.html"

    @app.get("/", include_in_schema=False)
    async def console() -> FileResponse:
        # 本地演示页：只调用下面两个公开接口，不含任何业务规则。
        return FileResponse(page, media_type="text/html; charset=utf-8")

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        # 只暴露“用什么模式在跑”，不暴露凭据或库路径。
        return JSONResponse(
            {"status": "ok", "provider": cfg.provider, "model": cfg.model, "prompt_version": cfg.prompt_version}
        )

    def _new_loop(**kwargs: Any) -> ExecutionLoop:
        if model is None:
            raise RuntimeError("provider=scripted 必须显式注入 provider")
        return ExecutionLoop(cfg, db, model, **kwargs)

    @app.post("/v1/tickets")
    async def create_ticket(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                {"error": "input_invalid", "detail": "请求体不是合法 JSON"}, status_code=422
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "input_invalid", "detail": "请求体必须是 JSON 对象"}, status_code=422
            )
        try:
            result = _new_loop().run(payload)
        except StoreError as exc:
            return JSONResponse(
                {"error": "internal_error", "detail": f"持久化失败：{exc}"}, status_code=500
            )
        body = result.to_dict()
        if result.status.value == "degraded" and result.stop_reason.value == "upstream_error":
            return JSONResponse(body, status_code=503)
        return JSONResponse(body, status_code=result.http_status)

    @app.get("/v1/runs/{run_id}")
    async def get_run(run_id: str) -> JSONResponse:
        trace = db.get_trace(run_id)
        if trace is None:
            return JSONResponse({"error": "not_found", "detail": "run 不存在"}, status_code=404)
        return JSONResponse(_mask(_jsonable(trace)))

    @app.post("/v1/tickets/stream")
    async def stream_ticket(request: Request) -> StreamingResponse:
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                {"error": "input_invalid", "detail": "请求体不是合法 JSON"}, status_code=422
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                {"error": "input_invalid", "detail": "请求体必须是 JSON 对象"}, status_code=422
            )

        events: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        loop_ref = asyncio.get_running_loop()
        cancelled = threading.Event()
        holder: dict[str, Any] = {}

        def listener(event: str, data: dict[str, Any]) -> None:
            loop_ref.call_soon_threadsafe(events.put_nowait, ("event", (event, data)))

        def clock() -> float:
            # 客户端断开后让 deadline 立刻过期，循环自己走 timeout 收尾。
            return time.monotonic() + (1e9 if cancelled.is_set() else 0.0)

        def work() -> None:
            try:
                result = _new_loop(listener=listener, clock=clock).run(payload)
                holder["result"] = result
            except StoreError as exc:
                holder["error"] = f"store_error: {exc}"
            except Exception as exc:  # noqa: BLE001 - 线程内异常必须带回主线程
                holder["error"] = f"unexpected: {exc}"
            finally:
                if cancelled.is_set() and holder.get("result") is not None:
                    run_id = holder["result"].run_id
                    if run_id:
                        try:
                            db.set_note(run_id, "client_disconnected")
                        except StoreError:
                            pass
                loop_ref.call_soon_threadsafe(events.put_nowait, ("done", None))

        thread = threading.Thread(target=work, name="agent-run", daemon=True)
        thread.start()

        async def generate() -> AsyncIterator[bytes]:
            yield _sse("open", {"status": "accepted"})
            final_sent = False
            while True:
                if await request.is_disconnected():
                    cancelled.set()
                    thread.join(timeout=5)
                    if not final_sent:
                        yield _sse(
                            "error",
                            {"stop_reason": "timeout", "note": "client_disconnected"},
                        )
                    return
                try:
                    kind, value = await asyncio.wait_for(events.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue
                if kind == "event":
                    name, data = value
                    yield _sse(name, data)
                    continue
                final_sent = True
                if "error" in holder:
                    yield _sse("error", {"detail": holder["error"]})
                else:
                    yield _sse("final", _mask(holder["result"].to_dict()))
                return

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n".encode("utf-8")


def _jsonable(value: Any) -> Any:
    """把 trace 里的 dataclass 摊平成可序列化结构；不做任何业务加工。"""
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _mask(value: Any) -> Any:
    if isinstance(value, str):
        return mask_pii(value)
    if isinstance(value, dict):
        return {key: _mask(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


app = None  # 由 `uvicorn app.api.main:app` 时按需创建（见 cli serve）


__all__ = ["create_app"]
