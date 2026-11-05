"""策略层：预检（0a–0d）与终局复核（2–11），优先级严格按 DESIGN §9.1。

两条边界，越界就回到文档讨论：
- 预检只读原始文本、意图与订单号候选，不调用任何工具；
- 终局复核只做“升级为转人工 / 替换越权草稿”，不替模型改写事实、不改金额。

本模块不 import ``app.tools``：策略判定只看工具结果的**字段**，不看实现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Sequence

from app.schemas import FinalAnswer, Intent, TicketIn, ToolResult

#: 必须带订单号才能给出可靠答复的意图（0d 只对这三类生效）。
REQUIRED_ORDER_INTENTS = (Intent.REFUND, Intent.ADDRESS_CHANGE, Intent.SHIPPING_URGE)

#: 0a 投诉 / 法律威胁关键词。
COMPLAINT_KEYWORDS = (
    "投诉", "举报", "曝光", "起诉", "律师", "消协", "工商", "12315",
    "法律", "追责", "维权", "必须给说法", "媒体",
)
#: 0b 明确跨订单处理。
MULTI_ORDER_KEYWORDS = ("两个订单", "两笔订单", "一起处理", "同时处理", "分别处理", "都退", "批量")
#: 10 草稿承诺性措辞。
PROMISE_KEYWORDS = ("赔付", "赔偿", "补偿", "保证", "一定", "百分百")
#: 声称写操作已执行（本版只产出草稿，任何“已退款/已改地址”都是越权口吻）。
_WRITE_CLAIM_RE = re.compile(
    r"(已(为您)?(退款|退货|改地址|修改地址|变更地址|登记退款|提交退款|发起退款)"
    r"|退款已(到账|完成)|地址已(改|修改|变更))"
)
#: 承诺处理时限。
_TIMELINE_RE = re.compile(r"(\d+\s*[-~]?\s*\d*\s*个?工作日|\d+\s*小时内|当天(内)?|今天内|明天内|24\s*小时)")

#: 可退事实成立时，模型仍可用的转人工理由（其余理由一律作废，由事实层决定）。
_MODEL_REASON_ALLOWLIST = frozenset({
    "COMPLAINT_OR_THREAT",
    "MULTI_ORDER",
    "AMBIGUOUS_ORDER_ID",
    "MISSING_ORDER_ID",
    "ORDER_NOT_FOUND",
    "TOOL_FAILURE",
    "DRAFT_RISK",
})

_ORDER_RE = re.compile(r"O\d{4}", re.IGNORECASE)
_ADDRESS_HINT_RE = re.compile(r"(?:地址|改到|改成|改寄|寄到|送到|收货信息)")
_ADDRESS_BODY_RE = re.compile(
    r"(?:地址|改到|改成|改寄|寄到|送到|收货信息)[^，。；;！!？?\n]{0,10}?"
    r"([\u4e00-\u9fa5A-Za-z0-9]{2,}(?:省|市|区|县|镇|路|街|号|弄|号楼|小区|大厦|单元|室|层)[^，。；;！!？?\n]{0,30})"
)

_RISK_SAFE_DRAFT = (
    "您反馈的问题已记录，涉及处理结果与时效，已转人工客服核实后回复。"
    "本条不构成任何赔付、补偿或时效承诺。"
)
_ESCALATION_DRAFT = (
    "已收到您的工单，当前情况需要人工客服进一步核实，已转人工处理。"
    "本条不构成任何赔付、补偿或时效承诺。"
)


@dataclass(frozen=True, slots=True)
class Precheck:
    """预检结论。``reason`` 非空即命中，命中后不得执行任何工具。"""

    reason: str | None = None
    candidates: tuple[str, ...] = ()
    matched: tuple[str, ...] = ()

    @property
    def hit(self) -> bool:
        return self.reason is not None


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    """终局复核结论：主原因 + 全部命中原因（都要进运行元数据）。"""

    answer: FinalAnswer
    reasons: tuple[str, ...] = ()
    primary: str | None = None
    draft_replaced: bool = False


#: 签收争议的特征片段：签收时间/签收状态与用户实际收到情况不一致。
_DISPUTE_RE = re.compile(
    r"(签收时间.{0,12}(不一致|不符|不对)|没收到.{0,12}(显示|写着).{0,8}(已签收|已送达)"
    r"|(显示|明明).{0,8}(已签收|已送达).{0,12}(没收到|没见到|没拿到))"
)


#: 用户明确说“没问题/一致/不存在不一致”时不算争议。
_DISPUTE_NEGATED_RE = re.compile(r"(没问题|不存在.{0,4}不一致|并不.{0,4}不一致|是一致的|时间对得上|时间没错)")
#: 有赔偿/追责诉求时走投诉口径，不落 DELIVERY_DISPUTE。
_DISPUTE_CLAIM_RE = re.compile(r"(赔偿|赔付|补偿|追责|起诉|曝光)")
#: “显示已签收但我没拿到”这类：签收记录与实物不符。
_DISPUTE_SIGNED_RE = re.compile(
    r"((已签收|已送达|显示签收|显示已签收).{0,16}(没(拿到|收到|见到)|未(收到|签收)|找不到))"
)


def delivery_dispute(text: str) -> bool:
    """是否属于“签收事实有争议”，需要人工核实而不是自动回复。"""
    t = text or ""
    if _DISPUTE_CLAIM_RE.search(t) or _DISPUTE_NEGATED_RE.search(t):
        return False
    return bool(_DISPUTE_RE.search(t) or _DISPUTE_SIGNED_RE.search(t))


def draft_risk(draft: str) -> bool:
    """草稿是否含绝对化承诺（DESIGN §9.1 第 10 条，仅此五类词）。"""
    text = draft or ""
    return any(word in text for word in PROMISE_KEYWORDS)


def order_candidates(text: str) -> tuple[str, ...]:
    """正文中的订单号候选，按出现顺序去重并大写。"""
    seen: list[str] = []
    for match in _ORDER_RE.findall(text or ""):
        value = match.upper()
        if value not in seen:
            seen.append(value)
    return tuple(seen)


def classify_text(text: str) -> Intent:
    """预检用的确定性意图启发式（不调用模型）。

    只服务 0d（缺号判定）与报告分流，不替代模型分类；
    最终 intent 一律以模型 ``final.intent`` 为准（见 loop）。
    """
    lowered = text or ""
    refund_hits = sum(word in lowered for word in ("退款", "退货", "退钱", "退掉", "申请退"))
    address_hits = sum(word in lowered for word in ("地址", "改地址", "寄到", "改寄", "收货信息"))
    shipping_hits = sum(word in lowered for word in ("发货", "什么时候发", "催", "物流", "快递", "没发"))
    scores = {
        Intent.REFUND: refund_hits,
        Intent.ADDRESS_CHANGE: address_hits,
        Intent.SHIPPING_URGE: shipping_hits,
    }
    best = max(scores, key=lambda key: scores[key])
    return best if scores[best] > 0 else Intent.OTHER


def precheck(ticket: TicketIn, intent: Intent) -> Precheck:
    """0a → 0b → 0c → 0d，命中即停；顺序不可调换（投诉优先于其他预检原因）。"""
    text = ticket.text or ""
    candidates = order_candidates(text)
    matched: list[str] = []

    if any(word in text for word in COMPLAINT_KEYWORDS):
        matched.append("0a:COMPLAINT_OR_THREAT")
        return Precheck("COMPLAINT_OR_THREAT", candidates, tuple(matched))

    wants_multi = any(word in text for word in MULTI_ORDER_KEYWORDS)
    if wants_multi and len(candidates) >= 2:
        matched.append("0b:MULTI_ORDER")
        return Precheck("MULTI_ORDER", candidates, tuple(matched))

    structured = ticket.order_id.upper() if ticket.order_id else None
    if len(candidates) >= 2 or (structured and candidates and structured not in candidates):
        matched.append("0c:AMBIGUOUS_ORDER_ID")
        return Precheck("AMBIGUOUS_ORDER_ID", candidates, tuple(matched))

    if intent in REQUIRED_ORDER_INTENTS and not candidates and not structured:
        matched.append("0d:MISSING_ORDER_ID")
        return Precheck("MISSING_ORDER_ID", candidates, tuple(matched))

    return Precheck(None, candidates, tuple(matched))


def safe_draft(reason: str) -> str:
    """预检命中时的固定安全草稿：无承诺、无时限、说明已转人工。"""
    return f"{_ESCALATION_DRAFT}（原因：{reason}）"


def conflicting_addresses(text: str) -> tuple[str, ...]:
    """正文里互相矛盾的收货地址；≥2 个不同值即 ADDRESS_CONFLICT（先于发货判定）。"""
    found: list[str] = []
    for match in _ADDRESS_BODY_RE.finditer(text or ""):
        normalized = re.sub(r"\s+", "", match.group(1))
        if normalized and normalized not in found:
            found.append(normalized)
    return tuple(found)


@dataclass
class PolicyFacts:
    """从工具结果抽取的事实视图；策略只读这些字段。"""

    order_status: str | None = None
    amount_cents: int | None = None
    delivered_at: datetime | None = None
    refund_allowed: bool | None = None
    refund_reason: str | None = None
    error_codes: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)

    @classmethod
    def from_outcomes(cls, outcomes: Iterable[Any]) -> "PolicyFacts":
        facts = cls()
        for outcome in outcomes:
            result: ToolResult = outcome.result
            facts.tool_names.append(outcome.name)
            if result.error is not None:
                facts.error_codes.append(result.error.code)
            data = result.data or {}
            if outcome.name == "query_order" and data:
                facts.order_status = data.get("status")
                facts.amount_cents = data.get("amount_cents")
                facts.delivered_at = _parse_dt(data.get("delivered_at"))
            elif outcome.name == "refund_preview":
                if data:
                    facts.refund_allowed = data.get("allowed")
                    facts.refund_reason = data.get("policy_reason")
                elif result.error is not None and result.error.code == "REFUND_NOT_ALLOWED":
                    facts.refund_allowed = False
                    facts.refund_reason = "REFUND_NOT_ALLOWED"
        return facts


def consecutive_failures(outcomes: Sequence[Any]) -> tuple[int, str | None]:
    """连续技术失败次数与工具名；``NOT_SHIPPED`` 属可预期业务状态，不计入。"""
    count = 0
    name: str | None = None
    for outcome in reversed(outcomes):
        result: ToolResult = outcome.result
        error = result.error
        if error is None:
            break
        if error.code in ("NOT_SHIPPED", "APPROVAL_REQUIRED", "STORE_WRITE_FAILED"):
            break
        count += 1
        name = outcome.name
    return count, name


def evaluate(
    answer: FinalAnswer,
    *,
    facts: PolicyFacts,
    outcomes: Sequence[Any],
    text: str,
    now: datetime,
    refund_limit_cents: int,
    refund_window_days: int,
) -> PolicyOutcome:
    """按 §9.1 的 3–11 顺序复核；返回主原因与全部命中原因。"""
    reasons: list[str] = []
    status = facts.order_status

    if "ORDER_NOT_FOUND" in facts.error_codes:
        reasons.append("ORDER_NOT_FOUND")

    failures, _ = consecutive_failures(outcomes)
    if failures >= 2:
        reasons.append("TOOL_FAILURE")

    if answer.intent == Intent.REFUND:
        if status == "shipped":
            reasons.append("REFUND_AFTER_SHIP")
        elif facts.amount_cents is not None and facts.amount_cents > refund_limit_cents:
            reasons.append("REFUND_OVER_LIMIT")
        elif status == "delivered" and _beyond_window(facts.delivered_at, now, refund_window_days):
            reasons.append("REFUND_NOT_ALLOWED")
        elif facts.refund_allowed is False:
            reasons.append(str(facts.refund_reason or "REFUND_NOT_ALLOWED"))

    if answer.intent == Intent.ADDRESS_CHANGE:
        if len(conflicting_addresses(text)) >= 2:
            reasons.append("ADDRESS_CONFLICT")
        elif status == "shipped":
            reasons.append("ADDRESS_AFTER_SHIP")
        else:
            reasons.append("ADDRESS_CHANGE")

    # 签收事实与物流记录矛盾（例如“显示已签收但我没收到”）：属需要人工向承运方核实的争议，
    # 与“投诉/追责”不同——投诉走 0a，这里只在 shipping_urge 且没有赔偿诉求时命中。
    if answer.intent == Intent.SHIPPING_URGE and delivery_dispute(text):
        reasons.append("DELIVERY_DISPUTE")


    if answer.intent == Intent.OTHER and answer.confidence < 0.5:
        reasons.append("LOW_CONFIDENCE")

    draft = answer.reply_draft
    if draft_risk(draft):
        reasons.append("DRAFT_RISK")
        draft = _RISK_SAFE_DRAFT

    # 证据不足：退款结论必须有 refund_preview 的实测结果，模型不能凭想象宣布“可退/已退”。
    if answer.intent == Intent.REFUND and "refund_preview" not in facts.tool_names:
        reasons.append("INSUFFICIENT_EVIDENCE")

    blocked_model_flag = False
    if answer.needs_human:
        reason = str(answer.escalate_reason) if answer.escalate_reason else "MODEL_FLAGGED"
        # 事实优先：refund_preview 判定可退时，模型自述的“退款受阻 / 低置信”都不构成转人工理由，
        # 否则模型一句“不能退”就能盖过工具事实（AC01 靠这条守住）。
        blocked_model_flag = (
            facts.refund_allowed is True
            and answer.intent == Intent.REFUND
            and reason not in _MODEL_REASON_ALLOWLIST
        )
        if not blocked_model_flag:
            reasons.append(reason)

    primary = reasons[0] if reasons else None
    updated = answer.with_draft(draft)
    if primary is not None:
        updated = FinalAnswer(
            intent=updated.intent,
            confidence=updated.confidence,
            slots=dict(updated.slots),
            reply_draft=updated.reply_draft,
            needs_human=True,
            escalate_reason=primary,
            used_tools=list(updated.used_tools),
        )
    elif updated.needs_human:
        updated = FinalAnswer(
            intent=updated.intent,
            confidence=updated.confidence,
            slots=dict(updated.slots),
            reply_draft=updated.reply_draft,
            needs_human=not blocked_model_flag,
            escalate_reason=None if blocked_model_flag else (updated.escalate_reason or "MODEL_FLAGGED"),
            used_tools=list(updated.used_tools),
        )
    return PolicyOutcome(
        answer=updated,
        reasons=tuple(dict.fromkeys(reasons)),
        primary=primary,
        draft_replaced=updated.reply_draft != answer.reply_draft,
    )


def _beyond_window(delivered_at: datetime | None, now: datetime, days: int) -> bool:
    """售后期判定必须用 DEMO_NOW（``now``），不能用墙钟。"""
    if delivered_at is None:
        return False
    return (now - delivered_at).days > days


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
