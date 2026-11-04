"""上下文管理：窗口保留 + 确定性结构化摘要（DESIGN §5.3、§8）。

规则只有三条，多的都不做：
1. 单 run 内保留最近 ``WINDOW_TURNS`` 轮原文，更早的折叠；
2. 折叠产物是**确定性结构化摘要**（同输入必得同摘要），不由模型生成；
3. 不拆散工具调用与结果：窗口边界落在 role=tool 上时向前扩展，role=tool 永不截断。

不做向量检索、不做跨 run 记忆——那不在本阶段范围内。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from app.config import Config

#: 摘要固定六字段；缺一不可，缺值用空值补位（不省略 key）。
SUMMARY_FIELDS = (
    "intent_history",
    "slots",
    "tools_called",
    "last_decision",
    "open_questions",
    "need_summary",
)

LAST_DECISION_LIMIT = 200


@dataclass
class SessionSummary:
    """折叠摘要。字段顺序即渲染顺序，便于比对与快照测试。"""

    intent_history: list[str] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    tools_called: list[str] = field(default_factory=list)
    last_decision: str = ""
    open_questions: list[str] = field(default_factory=list)
    need_summary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_history": list(self.intent_history),
            "slots": dict(self.slots),
            "tools_called": list(self.tools_called),
            "last_decision": self.last_decision,
            "open_questions": list(self.open_questions),
            "need_summary": bool(self.need_summary),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "SessionSummary":
        payload = payload or {}
        return cls(
            intent_history=list(payload.get("intent_history") or []),
            slots=dict(payload.get("slots") or {}),
            tools_called=list(payload.get("tools_called") or []),
            last_decision=str(payload.get("last_decision") or ""),
            open_questions=list(payload.get("open_questions") or []),
            need_summary=bool(payload.get("need_summary")),
        )

    def render(self) -> str:
        """渲染成一段稳定文本（六字段恒在，缺值写空列表/空对象）。"""
        lines = [
            "【会话摘要】",
            f"intent_history={json.dumps(self.intent_history, ensure_ascii=False)}",
            f"slots={json.dumps(self.slots, ensure_ascii=False, sort_keys=True)}",
            f"tools_called={json.dumps(self.tools_called, ensure_ascii=False)}",
            f"last_decision={self.last_decision}",
            f"open_questions={json.dumps(self.open_questions, ensure_ascii=False)}",
            f"need_summary={'true' if self.need_summary else 'false'}",
        ]
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Context:
    """一次 Provider 请求要用的消息与摘要。"""

    messages: tuple[dict[str, str], ...]
    summary: SessionSummary
    folded_messages: int = 0


class ContextBuilder:
    """按配置窗口折叠历史；无状态，可复用。"""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def window_messages(self) -> int:
        return max(2, self._config.window_turns * 2)

    def build(
        self,
        *,
        system_prompt: str,
        user_text: str,
        history: Sequence[Mapping[str, str]],
        summary: SessionSummary | None = None,
    ) -> Context:
        current = summary or SessionSummary()
        messages = [dict(item) for item in history]
        budget = self.window_messages
        if len(messages) <= budget:
            return Context(
                messages=self._compose(system_prompt, user_text, messages, current),
                summary=current,
                folded_messages=0,
            )

        cut = len(messages) - budget
        # 窗口起点不能是工具结果：向前并入触发它的 assistant 消息。
        while cut > 0 and messages[cut].get("role") == "tool":
            cut -= 1
        folded = messages[:cut]
        kept = messages[cut:]
        updated = self._fold(folded, current)
        return Context(
            messages=self._compose(system_prompt, user_text, kept, updated),
            summary=updated,
            folded_messages=len(folded),
        )

    # -- internal ---------------------------------------------------------
    def _compose(
        self,
        system_prompt: str,
        user_text: str,
        kept: Sequence[Mapping[str, str]],
        summary: SessionSummary,
    ) -> tuple[dict[str, str], ...]:
        system = system_prompt
        if summary.need_summary or summary.intent_history or summary.tools_called:
            system = f"{system_prompt}\n\n{summary.render()}"
        composed = [{"role": "system", "content": system}]
        composed.append({"role": "user", "content": user_text})
        composed.extend(dict(item) for item in kept)
        return tuple(composed)

    def _fold(self, folded: Sequence[Mapping[str, str]], summary: SessionSummary) -> SessionSummary:
        """确定性合并：同输入 → 同输出，不调用模型、不看时间。"""
        intents = list(summary.intent_history)
        slots = dict(summary.slots)
        tools = list(summary.tools_called)
        last = summary.last_decision
        questions = list(summary.open_questions)

        for item in folded:
            role = item.get("role")
            content = str(item.get("content") or "")
            if role == "tool":
                continue
            payload = _loads(content)
            if not isinstance(payload, dict):
                continue
            final = payload.get("final")
            if isinstance(final, dict):
                intent = final.get("intent")
                if isinstance(intent, str) and intent:
                    intents.append(intent)
                if isinstance(final.get("slots"), dict):
                    slots.update(final["slots"])
                last = _shorten(str(final.get("reply_draft") or ""))
                if final.get("needs_human"):
                    questions.append("needs_human")
            for call in payload.get("tool_calls") or []:
                if isinstance(call, dict) and isinstance(call.get("name"), str):
                    if call["name"] not in tools:
                        tools.append(call["name"])

        return SessionSummary(
            intent_history=intents[-6:],
            slots=slots,
            tools_called=tools,
            last_decision=last,
            open_questions=list(dict.fromkeys(questions)),
            need_summary=True,
        )


def _loads(content: str) -> Any:
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return None


def _shorten(text: str) -> str:
    text = " ".join(text.split())
    return text[:LAST_DECISION_LIMIT]
