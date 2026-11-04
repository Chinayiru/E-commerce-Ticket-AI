"""SQLite 状态层：恰好四张表 + 按 run_id 取回完整 trace。

约定（docs/IMPLEMENTATION.md §7、docs/DESIGN.md §6.5）：
- 建表只用 ``CREATE TABLE IF NOT EXISTS``；新增列用幂等 ``ALTER TABLE`` 补齐，
  不做版本化迁移（那是 W2 之后的事，且不得建第五张表）；
- 每个写方法 = 一个短事务，失败回滚并抛 ``StoreError``，绝不静默吞掉；
  只有“活动工单唯一索引”冲突映射为 ``SessionConflict``，其他 IntegrityError 必须传播；
- 数据库路径由 ``Config.db_path`` 提供，本模块不硬编码任何位置；
- 模型/网络等待不得放在事务里（调用方负责事务边界）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Mapping

from app.config import TZ_SHANGHAI, Config
from app.schemas import (
    Evaluation,
    Session,
    TicketIn,
    ToolCallRecord,
    Turn,
    Usage,
)

SCHEMA_VERSION = 2


class StoreError(RuntimeError):
    """持久化失败。调用方必须让它终止本次运行，不得返回成功。"""

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        self.message = message
        super().__init__(f"数据库操作失败[{operation}]：{message}")


class SessionConflict(StoreError):
    """同一 (user_id, ticket_id) 已有 running 会话（HTTP 409）。"""


def _now() -> str:
    return datetime.now(TZ_SHANGHAI).isoformat(timespec="seconds")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


#: 建表语句：列名与 docs/IMPLEMENTATION.md §7 一一对应。
_TABLES: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id                TEXT PRIMARY KEY,
        ticket_id         TEXT NOT NULL,
        user_id           TEXT NOT NULL,
        order_id          TEXT,
        text              TEXT NOT NULL,
        input_text        TEXT,
        prompt_version    TEXT,
        status            TEXT NOT NULL,
        stop_reason       TEXT,
        needs_human       INTEGER,
        cost_cny          REAL,
        latency_ms        INTEGER,
        summary_json      TEXT,
        draft_text        TEXT,
        model_config_json TEXT NOT NULL DEFAULT '{}',
        result_json       TEXT,
        dataset_hash      TEXT,
        source_run_id     TEXT,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS turns (
        session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        idx         INTEGER NOT NULL,
        role        TEXT NOT NULL,
        content     TEXT NOT NULL,
        intent      TEXT,
        confidence  REAL,
        message_json TEXT,
        usage_json  TEXT,
        request_hash TEXT,
        created_at  TEXT NOT NULL,
        PRIMARY KEY (session_id, idx)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_calls (
        session_id        TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        call_id           TEXT NOT NULL,
        tool_name         TEXT NOT NULL,
        step              INTEGER NOT NULL DEFAULT 0,
        arguments_json    TEXT NOT NULL,
        ok                INTEGER NOT NULL CHECK (ok IN (0, 1)),
        error_code        TEXT,
        error_message     TEXT,
        duration_ms       INTEGER NOT NULL,
        result_json       TEXT,
        idempotency_key   TEXT,
        cached            INTEGER NOT NULL DEFAULT 0,
        approval_required INTEGER NOT NULL DEFAULT 0,
        attempt_idx       INTEGER NOT NULL DEFAULT 0,
        approved          INTEGER NOT NULL DEFAULT 0,
        created_at        TEXT NOT NULL,
        PRIMARY KEY (session_id, call_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluations (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id     TEXT NOT NULL,
        session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        case_id       TEXT,
        dataset_kind  TEXT NOT NULL,
        prompt_version TEXT,
        intent_gold   TEXT,
        intent_pred   TEXT,
        intent_ok     INTEGER,
        tools_ok      INTEGER,
        args_ok       INTEGER,
        draft_grade   TEXT,
        cost_cny      REAL,
        latency_ms    INTEGER,
        expected_json TEXT NOT NULL,
        actual_json   TEXT NOT NULL,
        error_json    TEXT,
        created_at    TEXT NOT NULL
    )
    """,
)

_INDEXES: tuple[str, ...] = (
    # 活动工单唯一：原子防重复登记（并发同 user+ticket 只能有一个 running）。
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_active_ticket ON sessions(user_id, ticket_id) WHERE status = 'running'",
    # 幂等键作用域必须带 session_id，否则两次评估会互相吞掉审计（DESIGN §5.4 教训）。
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_call_idempotency ON tool_calls(session_id, idempotency_key) WHERE idempotency_key IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, idx)",
    "CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_session ON evaluations(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_report ON evaluations(report_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_ticket ON sessions(ticket_id)",
)

#: 旧库补列（W1 建的表缺列时补齐，保证同一份代码可读历史库）。
_EXPECTED_COLUMNS: dict[str, dict[str, str]] = {
    "sessions": {
        "input_text": "TEXT",
        "prompt_version": "TEXT",
        "needs_human": "INTEGER",
        "cost_cny": "REAL",
        "latency_ms": "INTEGER",
        "summary_json": "TEXT",
        "draft_text": "TEXT",
        "dataset_hash": "TEXT",
        "source_run_id": "TEXT",
    },
    "turns": {
        "intent": "TEXT",
        "confidence": "REAL",
        "message_json": "TEXT",
        "request_hash": "TEXT",
    },
    "tool_calls": {
        "step": "INTEGER NOT NULL DEFAULT 0",
        "result_json": "TEXT",
        "idempotency_key": "TEXT",
        "cached": "INTEGER NOT NULL DEFAULT 0",
        "approval_required": "INTEGER NOT NULL DEFAULT 0",
        "attempt_idx": "INTEGER NOT NULL DEFAULT 0",
        "approved": "INTEGER NOT NULL DEFAULT 0",
    },
    "evaluations": {
        "case_id": "TEXT",
        "prompt_version": "TEXT",
        "intent_gold": "TEXT",
        "intent_pred": "TEXT",
        "intent_ok": "INTEGER",
        "tools_ok": "INTEGER",
        "args_ok": "INTEGER",
        "draft_grade": "TEXT",
        "cost_cny": "REAL",
        "latency_ms": "INTEGER",
    },
}


class Database:
    """四表读写。单进程使用；写入串行，读取可并发。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.init_schema()

    @classmethod
    def from_config(cls, config: Config) -> "Database":
        return cls(config.db_path)

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StoreError("init_schema", f"无法创建数据库目录 {self.path.parent}：{exc}") from exc

        with self._write("init_schema") as conn:
            for statement in _TABLES:
                conn.execute(statement)
            self._ensure_columns(conn)
            for statement in _INDEXES:
                conn.execute(statement)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        for table, columns in _EXPECTED_COLUMNS.items():
            existing = {
                row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for name, decl in columns.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")

    # ------------------------------------------------------------------ writes
    def create_session(
        self,
        ticket: TicketIn,
        model_config: Mapping[str, Any],
        *,
        prompt_version: str | None = None,
        dataset_hash: str | None = None,
        source_run_id: str | None = None,
    ) -> str:
        """登记一个 running 会话；session_id 即 run_id。只把活动工单冲突映射为 409。"""
        session_id = uuid.uuid4().hex
        now = _now()
        try:
            with self._write("create_session") as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (id, ticket_id, user_id, text, input_text, order_id,
                                          prompt_version, status, stop_reason, needs_human,
                                          model_config_json, dataset_hash, source_run_id,
                                          created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'running', NULL, NULL, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        ticket.ticket_id,
                        ticket.user_id,
                        ticket.text,
                        ticket.text,
                        ticket.order_id,
                        prompt_version,
                        _dumps(dict(model_config)),
                        dataset_hash,
                        source_run_id,
                        now,
                        now,
                    ),
                )
        except StoreError as exc:
            message = str(exc)
            if (
                "idx_active_ticket" in message
                or "UNIQUE constraint failed: sessions.user_id, sessions.ticket_id" in message
            ):
                raise SessionConflict(
                    "create_session",
                    f"用户 {ticket.user_id} 的工单 {ticket.ticket_id} 已有 running 会话",
                ) from exc
            raise
        return session_id

    def append_turn(self, turn: Turn) -> None:
        with self._write("append_turn") as conn:
            conn.execute(
                """
                INSERT INTO turns (session_id, idx, role, content, intent, confidence,
                                   message_json, usage_json, request_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.session_id,
                    turn.idx,
                    turn.role,
                    turn.content,
                    turn.intent,
                    turn.confidence,
                    None if turn.message_json is None else _dumps(turn.message_json),
                    None if turn.usage is None else _dumps(turn.usage.to_dict()),
                    turn.request_hash,
                    turn.created_at or _now(),
                ),
            )

    def record_tool_call(self, record: ToolCallRecord) -> None:
        with self._write("record_tool_call") as conn:
            conn.execute(
                """
                INSERT INTO tool_calls (session_id, call_id, tool_name, step, arguments_json,
                                        ok, error_code, error_message, duration_ms, result_json,
                                        idempotency_key, cached, approval_required, attempt_idx,
                                        approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    record.session_id,
                    record.call_id,
                    record.tool_name,
                    int(record.step),
                    _dumps(record.arguments),
                    1 if record.ok else 0,
                    record.error_code,
                    record.error_message,
                    int(record.duration_ms),
                    None if record.result is None else _dumps(record.result),
                    record.idempotency_key,
                    1 if record.cached else 0,
                    1 if record.approval_required else 0,
                    int(record.attempt_idx),
                    record.created_at or _now(),
                ),
            )

    def save_draft(self, session_id: str, answer: Mapping[str, Any]) -> None:
        """只更新草稿与结果，不结束会话（create_ticket_draft 的落库动作）。"""
        draft_text = str(answer.get("reply_draft") or "")
        with self._write("save_draft") as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                   SET result_json = ?, draft_text = ?, needs_human = ?, updated_at = ?
                 WHERE id = ?
                """,
                (
                    _dumps(dict(answer)),
                    draft_text,
                    1 if answer.get("needs_human") else 0,
                    _now(),
                    session_id,
                ),
            )
            if cursor.rowcount != 1:
                raise StoreError("save_draft", f"会话不存在：{session_id}")

    def finish_session(
        self,
        session_id: str,
        *,
        status: str,
        stop_reason: str,
        result: Mapping[str, Any] | None,
        needs_human: bool | None = None,
        cost_cny: float | None = None,
        latency_ms: int | None = None,
        summary: Mapping[str, Any] | None = None,
    ) -> None:
        """原子写入终态；``status`` 离开 running 后才能释放活动工单索引。"""
        with self._write("finish_session") as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                   SET status = ?, stop_reason = ?,
                       result_json = COALESCE(?, result_json),
                       needs_human = COALESCE(?, needs_human),
                       cost_cny = COALESCE(?, cost_cny),
                       latency_ms = COALESCE(?, latency_ms),
                       summary_json = COALESCE(?, summary_json),
                       updated_at = ?
                 WHERE id = ?
                """,
                (
                    status,
                    stop_reason,
                    None if result is None else _dumps(dict(result)),
                    None if needs_human is None else (1 if needs_human else 0),
                    cost_cny,
                    latency_ms,
                    None if summary is None else _dumps(dict(summary)),
                    _now(),
                    session_id,
                ),
            )
            if cursor.rowcount != 1:
                raise StoreError("finish_session", f"会话不存在：{session_id}")

    def write_evaluation(self, evaluation: Evaluation) -> int:
        with self._write("write_evaluation") as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluations (report_id, session_id, case_id, dataset_kind,
                                         prompt_version, intent_gold, intent_pred, intent_ok,
                                         tools_ok, args_ok, draft_grade, cost_cny, latency_ms,
                                         expected_json, actual_json, error_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.report_id,
                    evaluation.session_id,
                    evaluation.case_id,
                    evaluation.dataset_kind,
                    evaluation.prompt_version,
                    evaluation.intent_gold,
                    evaluation.intent_pred,
                    _opt_int(evaluation.intent_ok),
                    _opt_int(evaluation.tools_ok),
                    _opt_int(evaluation.args_ok),
                    evaluation.draft_grade,
                    evaluation.cost_cny,
                    evaluation.latency_ms,
                    _dumps(evaluation.expected),
                    _dumps(evaluation.actual),
                    None if evaluation.error is None else _dumps(evaluation.error),
                    evaluation.created_at or _now(),
                ),
            )
            return int(cursor.lastrowid or 0)

    def mark_interrupted_runs(self, note: str = "process_interrupted") -> int:
        """进程重启后把遗留 running 收尾为 degraded/upstream_error，避免幽灵会话。"""
        with self._write("mark_interrupted_runs") as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                   SET status = 'degraded', stop_reason = 'upstream_error',
                       needs_human = 1, summary_json = ?, updated_at = ?
                 WHERE status = 'running'
                """,
                (_dumps({"interrupted": note}), _now()),
            )
            return cursor.rowcount

    def set_note(self, session_id: str, note: str) -> None:
        """给已收尾的 run 追加一条运行说明（如 client_disconnected），不改终态。"""
        with self._write("set_note") as conn:
            row = conn.execute(
                "SELECT result_json FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if row is None:
                raise StoreError("set_note", f"会话不存在：{session_id}")
            payload = _loads(row["result_json"]) or {}
            payload["note"] = note
            conn.execute(
                "UPDATE sessions SET result_json = ?, updated_at = ? WHERE id = ?",
                (_dumps(payload), _now(), session_id),
            )

    # ------------------------------------------------------------------ reads
    def get_session(self, session_id: str) -> Session | None:
        with self._read() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return None if row is None else _row_to_session(row)

    def find_tool_call(self, session_id: str, *, idempotency_key: str) -> ToolCallRecord | None:
        with self._read() as conn:
            row = conn.execute(
                """
                SELECT * FROM tool_calls
                 WHERE session_id = ? AND idempotency_key = ?
                 ORDER BY rowid LIMIT 1
                """,
                (session_id, idempotency_key),
            ).fetchone()
        return None if row is None else _row_to_tool_call(row)

    def list_turns(self, session_id: str) -> list[Turn]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM turns WHERE session_id = ? ORDER BY idx", (session_id,)
            ).fetchall()
        return [_row_to_turn(row) for row in rows]

    def list_tool_calls(self, session_id: str) -> list[ToolCallRecord]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY rowid",
                (session_id,),
            ).fetchall()
        return [_row_to_tool_call(row) for row in rows]

    def list_evaluations(self, session_id: str) -> list[Evaluation]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE session_id = ? ORDER BY id", (session_id,)
            ).fetchall()
        return [_row_to_evaluation(row) for row in rows]

    def list_evaluations_by_report(self, report_id: str) -> list[Evaluation]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE report_id = ? ORDER BY id", (report_id,)
            ).fetchall()
        return [_row_to_evaluation(row) for row in rows]

    def list_sessions_by_ticket(self, ticket_id: str) -> list[Session]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE ticket_id = ? ORDER BY created_at", (ticket_id,)
            ).fetchall()
        return [_row_to_session(row) for row in rows]

    def get_trace(self, session_id: str) -> dict[str, Any] | None:
        """按会话取回完整 trace；``cli trace`` 与 ``GET /v1/runs/{id}`` 复用。"""
        session = self.get_session(session_id)
        if session is None:
            return None
        return {
            "session": session,
            "turns": self.list_turns(session_id),
            "tool_calls": self.list_tool_calls(session_id),
            "evaluations": self.list_evaluations(session_id),
        }

    # ------------------------------------------------------------------ plumbing
    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.path), timeout=5.0, isolation_level=None)
        except sqlite3.Error as exc:
            raise StoreError("connect", f"无法打开 {self.path}：{exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @contextmanager
    def _write(self, operation: str) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        except StoreError:
            raise
        except sqlite3.IntegrityError as exc:
            raise StoreError(operation, f"约束冲突：{exc}") from exc
        except sqlite3.Error as exc:
            raise StoreError(operation, str(exc)) from exc
        finally:
            conn.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        except sqlite3.Error as exc:
            raise StoreError("read", str(exc)) from exc
        finally:
            conn.close()


def _opt_int(value: bool | None) -> int | None:
    return None if value is None else (1 if value else 0)


def _loads(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(
        session_id=row["id"],
        ticket_id=row["ticket_id"],
        user_id=row["user_id"],
        text=row["text"],
        order_id=row["order_id"],
        status=row["status"],
        stop_reason=row["stop_reason"],
        prompt_version=row["prompt_version"],
        needs_human=None if row["needs_human"] is None else bool(row["needs_human"]),
        cost_cny=row["cost_cny"],
        latency_ms=row["latency_ms"],
        summary=_loads(row["summary_json"]),
        draft_text=row["draft_text"],
        model_config=_loads(row["model_config_json"]) or {},
        result=_loads(row["result_json"]),
        dataset_hash=row["dataset_hash"],
        source_run_id=row["source_run_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_turn(row: sqlite3.Row) -> Turn:
    usage_raw = _loads(row["usage_json"])
    usage = None if usage_raw is None else Usage(
        input_tokens=usage_raw.get("input_tokens", 0),
        output_tokens=usage_raw.get("output_tokens", 0),
        source=usage_raw.get("source", "estimated"),
        cost_cny=usage_raw.get("cost_cny"),
    )
    return Turn(
        session_id=row["session_id"],
        idx=row["idx"],
        role=row["role"],
        content=row["content"],
        usage=usage,
        intent=row["intent"],
        confidence=row["confidence"],
        message_json=_loads(row["message_json"]),
        request_hash=row["request_hash"],
        created_at=row["created_at"],
    )


def _row_to_tool_call(row: sqlite3.Row) -> ToolCallRecord:
    return ToolCallRecord(
        session_id=row["session_id"],
        call_id=row["call_id"],
        tool_name=row["tool_name"],
        arguments=_loads(row["arguments_json"]) or {},
        ok=bool(row["ok"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        duration_ms=row["duration_ms"],
        step=row["step"] or 0,
        cached=bool(row["cached"]),
        approval_required=bool(row["approval_required"]),
        attempt_idx=row["attempt_idx"] or 0,
        idempotency_key=row["idempotency_key"],
        result=_loads(row["result_json"]),
        created_at=row["created_at"],
    )


def _row_to_evaluation(row: sqlite3.Row) -> Evaluation:
    return Evaluation(
        report_id=row["report_id"],
        session_id=row["session_id"],
        dataset_kind=row["dataset_kind"],
        expected=_loads(row["expected_json"]) or {},
        actual=_loads(row["actual_json"]) or {},
        case_id=row["case_id"],
        prompt_version=row["prompt_version"],
        intent_gold=row["intent_gold"],
        intent_pred=row["intent_pred"],
        intent_ok=None if row["intent_ok"] is None else bool(row["intent_ok"]),
        tools_ok=None if row["tools_ok"] is None else bool(row["tools_ok"]),
        args_ok=None if row["args_ok"] is None else bool(row["args_ok"]),
        draft_grade=row["draft_grade"],
        cost_cny=row["cost_cny"],
        latency_ms=row["latency_ms"],
        error=_loads(row["error_json"]),
        created_at=row["created_at"],
    )
