"""生成三份数据集：24 条开发集、12 条留出集、50 条草稿样本。

一切可复现的前提是这里**只有字面量表**，没有随机拼装：
同一条记录的 case_id / 文本 / 期望标签永远一致，改文本必须改常量。

用法：
    python scripts/seed_datasets.py                # 写到 data/ 下三个文件
    python scripts/seed_datasets.py --out-dir data # 指定目录
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data"

_SPLIT_DEV = "development"
_SPLIT_HOLDOUT = "holdout"

#: 只读三件套 / 催发货两件套，写死在数据集里，评估时按集合比对。
_TOOLS_REFUND = ["query_order", "refund_preview"]
_TOOLS_ADDRESS = ["query_order"]
_TOOLS_SHIPPING = ["query_order", "check_logistics"]


def _case(
    case_id: str,
    *,
    intent: str,
    text: str,
    order_id: str | None,
    tools: list[str],
    needs_human: bool,
    reason: str | None,
    user_id: str = "U001",
    reply_draft: str | None = None,
    confidence: float = 0.9,
    split: str = _SPLIT_DEV,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "split": split,
        "user_id": user_id,
        "text": text,
        "intent": intent,
        "order_id": order_id,
        "expected_tools": list(tools),
        "expected_args": [
            {"name": name, "arguments": {"order_id": order_id}} if order_id else {"name": name, "arguments": {}}
            for name in tools
        ],
        "expected_needs_human": needs_human,
        "expected_reason": reason,
        "reply_draft": reply_draft,
        "confidence": confidence,
    }


#: 24 条开发集：4 意图 × 简单/复杂 × 3 条。
DEV_CASES: list[dict[str, Any]] = [
    # ---- refund / simple ----
    _case(
        "dev-refund-simple-1",
        intent="refund",
        text="订单 O1001 买错了，想申请退款，麻烦帮我看看能不能退。",
        order_id="O1001",
        tools=_TOOLS_REFUND,
        needs_human=False,
        reason=None,
        reply_draft="已核对订单 O1001，实付 58.00 元，符合退款条件，已为您登记退款，1-3 个工作日原路退回。",
    ),
    _case(
        "dev-refund-simple-2",
        intent="refund",
        text="O1005 这个订单我不想要了，金额是 200 元，可以直接退吗？",
        order_id="O1005",
        tools=_TOOLS_REFUND,
        needs_human=False,
        reason=None,
        reply_draft="已核对订单 O1005，实付 200.00 元，符合退款条件，已为您登记退款。",
    ),
    _case(
        "dev-refund-simple-3",
        intent="refund",
        text="订单 O1007 昨天刚收到，想退货退款，还在售后期内吧？",
        order_id="O1007",
        tools=_TOOLS_REFUND,
        needs_human=False,
        reason=None,
        reply_draft="已核对订单 O1007，签收未超过售后期限，可以申请退货退款，已为您登记。",
    ),
    # ---- refund / complex ----
    _case(
        "dev-refund-complex-1",
        intent="refund",
        text="订单 O1002 已经发货了，但我现在不想要了，能不能直接退款？",
        order_id="O1002",
        tools=_TOOLS_REFUND,
        needs_human=True,
        reason="REFUND_AFTER_SHIP",
        reply_draft="订单 O1002 已发货，退款需要先拦截物流并人工核实，已转人工处理。",
    ),
    _case(
        "dev-refund-complex-2",
        intent="refund",
        text="订单 O1006 金额 250 元，我想整单退款，你们能直接处理吗？",
        order_id="O1006",
        tools=_TOOLS_REFUND,
        needs_human=True,
        reason="REFUND_OVER_LIMIT",
        reply_draft="订单 O1006 退款金额超出自动处理范围，已转人工复核。",
    ),
    _case(
        "dev-refund-complex-3",
        intent="refund",
        text="订单 O1003 是上个月签收的，现在还能退款吗？已经过了挺久了。",
        order_id="O1003",
        tools=_TOOLS_REFUND,
        needs_human=True,
        reason="REFUND_NOT_ALLOWED",
        reply_draft="订单 O1003 已超过售后期，无法直接退款，已转人工核实。",
    ),
    # ---- address_change / simple ----
    _case(
        "dev-address-simple-1",
        intent="address_change",
        text="订单 O1001 的收货地址填错了，想改到公司，麻烦帮我改一下。",
        order_id="O1001",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CHANGE",
        reply_draft="已收到改地址申请，涉及收货信息变更，已转人工核实后处理。",
    ),
    _case(
        "dev-address-simple-2",
        intent="address_change",
        text="O1005 还没发货，改一下收货地址可以吗？我要换到另一个城市。",
        order_id="O1005",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CHANGE",
        reply_draft="已收到改地址申请，已转人工核实新地址后处理。",
    ),
    _case(
        "dev-address-simple-3",
        intent="address_change",
        text="订单 O1007 想改收货信息，手机号也要一起换掉，可以吗？",
        order_id="O1007",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CHANGE",
        reply_draft="已收到收货信息变更申请，已转人工核实后处理。",
    ),
    # ---- address_change / complex ----
    _case(
        "dev-address-complex-1",
        intent="address_change",
        text="订单 O1002 已经发货了，还能改收货地址吗？我想换到别的城市。",
        order_id="O1002",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_AFTER_SHIP",
        reply_draft="订单 O1002 已发货，地址变更需要人工联系物流核实，已转人工。",
    ),
    _case(
        "dev-address-complex-2",
        intent="address_change",
        text="订单 O1008 的地址写错了，我要改寄到另一个地方，越快越好。",
        order_id="O1008",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_AFTER_SHIP",
        reply_draft="订单 O1008 已发货，地址变更需人工核实物流状态，已转人工。",
    ),
    _case(
        "dev-address-complex-3",
        intent="address_change",
        text="订单 O1006 地址改到上海市浦东新区，另外也要改到杭州市西湖区，到底按哪个？",
        order_id="O1006",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CONFLICT",
        reply_draft="您提供了两个不同的收货地址，需要人工确认后再变更，已转人工。",
    ),
    # ---- shipping_urge / simple ----
    _case(
        "dev-shipping-simple-1",
        intent="shipping_urge",
        text="订单 O1001 付款好几天了还没发货，什么时候能发出来？",
        order_id="O1001",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        reply_draft="订单 O1001 目前已付款但尚未发货，物流信息暂未生成，我们会尽快安排。",
    ),
    _case(
        "dev-shipping-simple-2",
        intent="shipping_urge",
        text="O1005 一直没动静，帮我催一下发货吧，等得有点久了。",
        order_id="O1005",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        reply_draft="订单 O1005 尚未发货，已为您催单，发货后会同步物流信息。",
    ),
    _case(
        "dev-shipping-simple-3",
        intent="shipping_urge",
        text="订单 O1006 下单后一直没有物流更新，是不是漏发了？",
        order_id="O1006",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        reply_draft="订单 O1006 尚未发货，暂无物流轨迹，已为您催单。",
    ),
    # ---- shipping_urge / complex ----
    _case(
        "dev-shipping-complex-1",
        intent="shipping_urge",
        text="订单 O1002 发货三天了，物流一直停在一个地方不动，能查一下吗？",
        order_id="O1002",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        reply_draft="已查询订单 O1002 物流，目前运输中，建议再观察一到两天。",
    ),
    _case(
        "dev-shipping-complex-2",
        intent="shipping_urge",
        text="O1008 明明显示已发货，但快递一直没更新，我要投诉物流太慢。",
        order_id="O1008",
        # 0a 投诉优先于查物流：预检命中即收尾，不产生工具调用。
        tools=[],
        needs_human=True,
        reason="COMPLAINT_OR_THREAT",
        reply_draft="已记录您对物流时效的反馈，已转人工跟进。",
    ),
    _case(
        "dev-shipping-complex-3",
        intent="shipping_urge",
        text="订单 O1003 签收时间和我实际收到的不一致，物流显示早就到了。",
        order_id="O1003",
        tools=_TOOLS_SHIPPING,
        needs_human=True,
        reason="DELIVERY_DISPUTE",
        reply_draft="签收时间存在争议，需要人工核实物流记录，已转人工。",
    ),
    # ---- other / simple ----
    _case(
        "dev-other-simple-1",
        intent="other",
        text="你们客服几点下班？我想咨询一下发票怎么开。",
        order_id=None,
        tools=[],
        # 信息类咨询：是否转人工取决于模型置信度，标 None 不计入转人工判定（口径见 DESIGN §10）。
        needs_human=None,
        reason=None,
        reply_draft="客服在线时间为每天 9:00-21:00，发票可在订单详情页申请开具。",
        confidence=0.8,
    ),
    _case(
        "dev-other-simple-2",
        intent="other",
        text="请问支持哪些支付方式？我想了解下有没有分期。",
        order_id=None,
        tools=[],
        # 同上：信息类咨询，标 None 不计入判定。
        needs_human=None,
        reason=None,
        reply_draft="支持常见在线支付方式，分期以支付页面展示为准。",
        confidence=0.7,
    ),
    _case(
        "dev-other-simple-3",
        intent="other",
        text="这个怎么办？我也不太清楚要问什么，反正就是有点问题。",
        order_id=None,
        tools=[],
        needs_human=True,
        reason="LOW_CONFIDENCE",
        reply_draft="您的描述还不够明确，麻烦补充订单号或具体问题，已转人工协助。",
        confidence=0.3,
    ),
    # ---- other / complex ----
    _case(
        "dev-other-complex-1",
        intent="other",
        text="帮我查一下订单 O1004 的情况，我好像看不到详情。",
        order_id="O1004",
        tools=["query_order"],
        needs_human=True,
        reason="ORDER_NOT_FOUND",
        reply_draft="未查询到该订单，请核对订单号，已转人工协助核实。",
    ),
    _case(
        "dev-other-complex-2",
        intent="other",
        text="订单 O1001 和 O1007 都有问题，两个订单想一起处理一下。",
        order_id=None,
        tools=[],
        needs_human=True,
        reason="MULTI_ORDER",
        reply_draft="涉及多个订单，需要人工分别核实，已转人工处理。",
    ),
    _case(
        "dev-other-complex-3",
        intent="other",
        text="你们这服务太差了，再不给处理我就去投诉，还要找律师维权。",
        order_id=None,
        tools=[],
        needs_human=True,
        reason="COMPLAINT_OR_THREAT",
        reply_draft="已记录您的反馈，已转人工专员跟进处理。",
        confidence=0.6,
    ),
]

#: 12 条留出集：与开发集同分布但文本不同，冻结后只用一次。
HOLDOUT_CASES: list[dict[str, Any]] = [
    _case(
        "hold-refund-1",
        intent="refund",
        text="O1001 这件商品和描述不符，我想退回并退款。",
        order_id="O1001",
        tools=_TOOLS_REFUND,
        needs_human=False,
        reason=None,
        split=_SPLIT_HOLDOUT,
        reply_draft="已核对订单 O1001，实付 58.00 元，符合退款条件，已登记退款。",
    ),
    _case(
        "hold-refund-2",
        intent="refund",
        text="订单 O1002 货已经发出，我临时不要了，怎么退款？",
        order_id="O1002",
        tools=_TOOLS_REFUND,
        needs_human=True,
        reason="REFUND_AFTER_SHIP",
        split=_SPLIT_HOLDOUT,
        reply_draft="订单 O1002 已发货，退款需人工核实物流，已转人工。",
    ),
    _case(
        "hold-refund-3",
        intent="refund",
        text="O1006 这个订单可以退吗，金额有点大。",
        order_id="O1006",
        tools=_TOOLS_REFUND,
        needs_human=True,
        reason="REFUND_OVER_LIMIT",
        split=_SPLIT_HOLDOUT,
        reply_draft="订单 O1006 退款金额超出自动处理范围，已转人工复核。",
    ),
    _case(
        "hold-address-1",
        intent="address_change",
        text="订单 O1001 想换个收货地址，改到公司那边。",
        order_id="O1001",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CHANGE",
        split=_SPLIT_HOLDOUT,
        reply_draft="已收到改地址申请，已转人工核实后处理。",
    ),
    _case(
        "hold-address-2",
        intent="address_change",
        text="O1005 地址填错了，能帮我改到另一个区吗？",
        order_id="O1005",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_CHANGE",
        split=_SPLIT_HOLDOUT,
        reply_draft="已收到改地址申请，已转人工核实后处理。",
    ),
    _case(
        "hold-address-3",
        intent="address_change",
        text="订单 O1008 已经发出了，地址还能改吗？",
        order_id="O1008",
        tools=_TOOLS_ADDRESS,
        needs_human=True,
        reason="ADDRESS_AFTER_SHIP",
        split=_SPLIT_HOLDOUT,
        reply_draft="订单 O1008 已发货，地址变更需人工联系物流核实。",
    ),
    _case(
        "hold-shipping-1",
        intent="shipping_urge",
        text="O1001 什么时候发货？已经等了两天了。",
        order_id="O1001",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        split=_SPLIT_HOLDOUT,
        reply_draft="订单 O1001 尚未发货，已为您催单。",
    ),
    _case(
        "hold-shipping-2",
        intent="shipping_urge",
        text="订单 O1005 一直没发货，能催一下吗？",
        order_id="O1005",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        split=_SPLIT_HOLDOUT,
        reply_draft="订单 O1005 尚未发货，已为您催单。",
    ),
    _case(
        "hold-shipping-3",
        intent="shipping_urge",
        text="订单 O1002 的快递好几天没更新了，帮我看看。",
        order_id="O1002",
        tools=_TOOLS_SHIPPING,
        needs_human=False,
        reason=None,
        split=_SPLIT_HOLDOUT,
        reply_draft="已查询订单 O1002 物流，目前运输中。",
    ),
    _case(
        "hold-other-1",
        intent="other",
        text="想问下你们的售后退款一般要多久到账？",
        order_id=None,
        tools=[],
        needs_human=False,
        reason=None,
        split=_SPLIT_HOLDOUT,
        reply_draft="退款到账时间以支付渠道为准，一般 1-3 个工作日。",
        confidence=0.7,
    ),
    _case(
        "hold-other-2",
        intent="other",
        text="订单 O1004 我查不到，是怎么回事？",
        order_id="O1004",
        tools=["query_order"],
        needs_human=True,
        reason="ORDER_NOT_FOUND",
        split=_SPLIT_HOLDOUT,
        reply_draft="未查询到该订单，请核对订单号，已转人工协助。",
    ),
    _case(
        "hold-other-3",
        intent="other",
        text="你们再不处理我就去 12315 投诉你们。",
        order_id=None,
        tools=[],
        needs_human=True,
        reason="COMPLAINT_OR_THREAT",
        split=_SPLIT_HOLDOUT,
        reply_draft="已记录您的反馈，已转人工专员跟进。",
        confidence=0.6,
    ),
]

#: 50 条草稿样本：只用于自动要素检查与人工抽检，不与 24 条题干重叠。
_DRAFT_TEMPLATES: list[tuple[str, str, str, list[str]]] = [
    ("refund", "订单 {order} 已核对，实付 {amount} 元，符合退款条件，已登记退款，1-3 个工作日原路退回。", "A", ["订单号", "金额", "下一步"]),
    ("refund", "订单 {order} 已发货，需要先拦截物流，已转人工核实，请留意后续联系。", "B", ["订单号", "处理方式"]),
    ("refund", "订单 {order} 退款金额超出自动处理范围，已转人工复核，结果会在核实后同步。", "B", ["订单号", "转人工"]),
    ("address_change", "已收到订单 {order} 的改地址申请，因涉及收货信息变更，已转人工核实后处理。", "B", ["订单号", "转人工"]),
    ("address_change", "订单 {order} 已发货，地址变更需要人工联系物流确认，已转人工。", "B", ["订单号", "状态说明"]),
    ("shipping_urge", "订单 {order} 目前尚未发货，已为您催单，发货后会同步物流信息。", "A", ["订单号", "状态", "下一步"]),
    ("shipping_urge", "已查询订单 {order} 物流，目前运输中，建议再观察一到两天。", "A", ["订单号", "物流状态"]),
    ("other", "您的问题已记录，麻烦补充订单号或更具体的信息，我们会尽快协助。", "B", ["追问"]),
    ("other", "该诉求需要人工进一步核实，已转人工处理。", "B", ["转人工"]),
    ("other", "您反馈的问题已记录，涉及处理结果与时效，已转人工客服核实后回复。", "B", ["转人工", "无承诺"]),
]

_AMOUNTS = ["58.00", "88.00", "129.00", "200.00", "258.00", "399.00"]
_ORDERS = ["O1001", "O1005", "O1007", "O1002", "O1008"]


def build_drafts_50() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(50):
        intent, template, grade, elements = _DRAFT_TEMPLATES[index % len(_DRAFT_TEMPLATES)]
        order = _ORDERS[index % len(_ORDERS)]
        amount = _AMOUNTS[index % len(_AMOUNTS)]
        draft = template.format(order=order, amount=amount)
        rows.append(
            {
                "case_id": f"draft-{index + 1:02d}",
                "intent": intent,
                "order_id": None if intent == "other" else order,
                "draft": draft,
                "required_elements": list(elements),
                "reference_grade": grade,
                "grade_reason": "由模板生成的参考答案，等级待人工复核" if grade == "A" else "含转人工或追问，等级待人工复核",
                "human_grade": None,
            }
        )
    return rows


def _validate(cases: list[dict[str, Any]], *, expect: int, split: str) -> None:
    if len(cases) != expect:
        raise SystemExit(f"{split} 应有 {expect} 条，实际 {len(cases)}")
    ids = [item["case_id"] for item in cases]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{split} case_id 重复")
    for intent in ("refund", "address_change", "shipping_urge", "other"):
        got = [item for item in cases if item["intent"] == intent]
        if len(got) != expect // 4:
            raise SystemExit(f"{split} 中 {intent} 应有 {expect // 4} 条，实际 {len(got)}")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 W3 数据集")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)

    _validate(DEV_CASES, expect=24, split="eval_cases")
    _validate(HOLDOUT_CASES, expect=12, split="holdout")

    drafts = build_drafts_50()
    if len(drafts) != 50:
        raise SystemExit("drafts_50 必须是 50 条")

    files = {
        "eval_cases.jsonl": DEV_CASES,
        "holdout.jsonl": HOLDOUT_CASES,
        "drafts_50.jsonl": drafts,
    }
    for name, rows in files.items():
        digest = _write_jsonl(out_dir / name, rows)
        print(f"{name}: {len(rows)} 条, sha256={digest[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
