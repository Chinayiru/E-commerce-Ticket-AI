"""SQLite 状态层：恰好四张表 + 按会话取回完整 trace。

约定（docs/IMPLEMENTATION.md §7）：
- 建表只用 ``CREATE TABLE IF NOT EXISTS``，W1 不做版本化迁移；
- 每个写方法 = 一个短事务，失败回滚并抛 ``StoreError``，绝不静默吞掉；
- 数据库路径由 ``Config.db_path`` 提供，本模块不硬编码任何位置；
- 模型/网络等待不放在事务里（调用方负责事务边界）。
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

SCHEMA_VERSION = 1


class StoreError(RuntimeError):
    """持久化失败。调用方必须让它终止本次运行，不得返回成功。"""

    def __init__(self, operation: str, message: str) -> None:
        self.operation = operation
        self.message = message
        super().__init__(f"数据库操作失败[{operation}]：{message}")


class SessionConflict(StoreError):
    """同一 (user_id, ticket_id) 已有 running 会话（对应 HTTP 409，W1 仅抛错）。"""


def _now() -> str:
    return datetime.now(TZ_SHANGHAI).isoformat(timespec="seconds")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


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

        statements = [
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id                TEXT PRIMARY KEY,
                ticket_id         TEXT NOT NULL,
                user_id           TEXT NOT NULL,
                text              TEXT NOT NULL,
                order_id          TEXT,
                status            TEXT NOT NULL,
                stop_reason       TEXT,
                model_config_json TEXT NOT NULL DEFAULT '{}',
                result_json       TEXT,
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
                usage_json  TEXT,
                created_at  TEXT NOT NULL,
                PRIMARY KEY (session_id, idx)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tool_calls (
                session_id     TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                call_id        TEXT NOT NULL,
                tool_name      TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                ok             INTEGER NOT NULL CHECK (ok IN (0, 1)),
                error_code     TEXT,
                error_message  TEXT,
                duration_ms    INTEGER NOT NULL,
                created_at     TEXT NOT NULL,
                PRIMARY KEY (session_id, call_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id     TEXT NOT NULL,
                session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                dataset_kind  TEXT NOT NULL,
                expected_json TEXT NOT NULL,
                actual_json   TEXT NOT NULL,
                error_json    TEXT,
                created_at    TEXT NOT NULL
            )
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_active_ticket ON sessions(user_id, ticket_id) WHERE status = 'running'",
            "CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, idx)",
            "CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_evaluations_session ON evaluations(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_evaluations_report ON evaluations(report_id)",
        ]
        with self._write("init_schema") as conn:
            for statement in statements:
                conn.execute(statement)

    # ------------------------------------------------------------------ writes
    def create_session(self, ticket: TicketIn, model_config: Mapping[str, Any]) -> str:
        """登记一个 running 会话；session_id 即 run_id。"""
        session_id = uuid.uuid4().hex
        now = _now()
        try:
            with self._write("create_session") as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (id, ticket_id, user_id, text, order_id, status,
                                          stop_reason, model_config_json, result_json,
                                          created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'running', NULL, ?, NULL, ?, ?)
                    """,
                    (
                        session_id,
                        ticket.ticket_id,
                        ticket.user_id,
                        ticket.text,
                        ticket.order_id,
                        _dumps(dict(model_config)),
                        now,
                        now,
                    ),
                )
        except StoreError as exc:
            if "idx_active_ticket" in str(exc) or "UNIQUE constraint failed" in str(exc):
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
                INSERT INTO turns (session_id, idx, role, content, usage_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    turn.session_id,
                    turn.idx,
                    turn.role,
                    turn.content,
                    None if turn.usage is None else _dumps(turn.usage.to_dict()),
                    turn.created_at or _now(),
                ),
            )

    def record_tool_call(self, record: ToolCallRecord) -> None:
        with self._write("record_tool_call") as conn:
            conn.execute(
                """
                INSERT INTO tool_calls (session_id, call_id, tool_name, arguments_json,
                                        ok, error_code, error_message, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.session_id,
                    record.call_id,
                    record.tool_name,
                    _dumps(record.arguments),
                    1 if record.ok else 0,
                    record.error_code,
                    record.error_message,
                    int(record.duration_ms),
                    record.created_at or _now(),
                ),
            )

    def save_draft(self, session_id: str, answer: Mapping[str, Any]) -> None:
        """只更新草稿，不结束会话（create_ticket_draft 的落库动作）。"""
        with self._write("save_draft") as conn:
            cursor = conn.execute(
                "UPDATE sessions SET result_json = ?, updated_at = ? WHERE id = ?",
                (_dumps(dict(answer)), _now(), session_id),
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
    ) -> None:
        """原子写入终态与结果。"""
        with self._write("finish_session") as conn:
            cursor = conn.execute(
                """
                UPDATE sessions
                   SET status = ?, stop_reason = ?, result_json = COALESCE(?, result_json),
                       updated_at = ?
                 WHERE id = ?
                """,
                (status, stop_reason, None if result is None else _dumps(dict(result)), _now(), session_id),
            )
            if cursor.rowcount != 1:
                raise StoreError("finish_session", f"会话不存在：{session_id}")

    def write_evaluation(self, evaluation: Evaluation) -> int:
        with self._write("write_evaluation") as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluations (report_id, session_id, dataset_kind,
                                         expected_json, actual_json, error_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.report_id,
                    evaluation.session_id,
                    evaluation.dataset_kind,
                    _dumps(evaluation.expected),
                    _dumps(evaluation.actual),
                    None if evaluation.error is None else _dumps(evaluation.error),
                    evaluation.created_at or _now(),
                ),
            )
            return int(cursor.lastrowid or 0)

    # ------------------------------------------------------------------ reads
    def get_session(self, session_id: str) -> Session | None:
        with self._read() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return None if row is None else _row_to_session(row)

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

    def get_trace(self, session_id: str) -> dict[str, Any] | None:
        """按会话取回完整 trace；W2 的 ``cli trace`` 直接复用。"""
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
            conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
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
        model_config=_loads(row["model_config_json"]) or {},
        result=_loads(row["result_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_turn(row: sqlite3.Row) -> Turn:
    usage_raw = _loads(row["usage_json"])
    usage = None if usage_raw is None else Usage(
        input_tokens=usage_raw.get("input_tokens", 0),
        output_tokens=usage_raw.get("output_tokens", 0),
        source=usage_raw.get("source", "estimated"),
    )
    return Turn(
        session_id=row["session_id"],
        idx=row["idx"],
        role=row["role"],
        content=row["content"],
        usage=usage,
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
        created_at=row["created_at"],
    )


def _row_to_evaluation(row: sqlite3.Row) -> Evaluation:
    return Evaluation(
        report_id=row["report_id"],
        session_id=row["session_id"],
        dataset_kind=row["dataset_kind"],
        expected=_loads(row["expected_json"]) or {},
        actual=_loads(row["actual_json"]) or {},
        error=_loads(row["error_json"]),
        created_at=row["created_at"],
    )
