"""生成 24 条 Mock 工单：4 类意图 × 简单/复杂 × 3 条，固定种子可复现。

用法：
    python scripts/seed_mock_orders.py --out data/mock_cases.json
    python scripts/seed_mock_orders.py --out D:/tmp/cases.json --seed 20261104

设计约束：
    * 订单分配沿用 docs/DEVELOPMENT.md §7.1 的表（每类每形态 3 条，共 24 条）；
    * 每条带期望意图、期望工具、是否应转人工、期望原因，供 W2 评估直接读取；
    * 文本长度落在 schemas 的 15–120 字约束内；
    * 输出顺序由 ``random.Random(seed)`` 打乱，同一种子结果逐字节一致。

W1 本地原因码（文档未定的部分，W2 由策略层统一）：
    REFUND_AFTER_SHIP / REFUND_NOT_ALLOWED / REFUND_OVER_LIMIT / ORDER_NOT_FOUND /
    ADDRESS_AFTER_SHIP / DELIVERY_DISPUTE / MULTI_ORDER / COMPLAINT_OR_THREAT
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # 允许直接 `python scripts/seed_mock_orders.py`
    sys.path.insert(0, str(REPO_ROOT))

from app.schemas import MAX_TEXT_CHARS, MIN_TEXT_CHARS  # noqa: E402
from app.tools.mock_data import DEMO_ORDER_IDS  # noqa: E402
from app.tools.registry import default_registry  # noqa: E402

DEFAULT_SEED = 20261104
DEFAULT_OUT = REPO_ROOT / "data" / "mock_cases.json"
#: 故意不在订单表里的“查无此单”用例（docs/DEVELOPMENT.md §7.1 的 other/O9999）。
MISSING_ORDER_IDS = frozenset({"O9999"})
INTENTS = ("refund", "address_change", "shipping_urge", "other")
FORMS = ("simple", "complex")

_REFUND = ["query_order", "refund_preview"]
_ADDRESS = ["query_order"]
_SHIPPING = ["query_order", "check_logistics"]


def _case(
    case_id: str,
    intent: str,
    form: str,
    order_id: str | None,
    text: str,
    tools: list[str],
    needs_human: bool,
    reason: str | None,
) -> dict[str, Any]:
    expected_args = {
        name: ({"order_id": order_id} if order_id else {}) for name in tools
    }
    return {
        "case_id": case_id,
        "split": "development",
        "form": form,
        "intent": intent,
        "order_id": order_id,
        "text": text,
        "expected_tools": list(tools),
        "expected_args": expected_args,
        "expected_needs_human": needs_human,
        "expected_reason": reason,
    }


#: 24 条数据的唯一来源；顺序在这里固定，输出前再按种子打乱。
CASES: list[dict[str, Any]] = [
    # ---- refund / simple：都在自动退款额度内或在售后期内
    _case("refund-simple-1", "refund", "simple", "O1001",
          "订单 O1001 刚买没多久，我想申请退款，麻烦帮我看看能不能退。", _REFUND, False, None),
    _case("refund-simple-2", "refund", "simple", "O1005",
          "订单 O1005 我不想要了，想走退款流程，金额不大，麻烦处理一下。", _REFUND, False, None),
    _case("refund-simple-3", "refund", "simple", "O1007",
          "订单 O1007 收到货了但不太合适，想退款，麻烦帮我确认下还能不能退。", _REFUND, False, None),
    # ---- refund / complex：已发货、已超售后期、超自动额度
    _case("refund-complex-1", "refund", "complex", "O1002",
          "订单 O1002 已经发货了，我现在想退款；如果退不了请告诉我怎么拒收，另外运费谁出？",
          _REFUND, True, "REFUND_AFTER_SHIP"),
    _case("refund-complex-2", "refund", "complex", "O1003",
          "订单 O1003 签收已经很久了，我还是要退款；你们再不处理我就去平台投诉。",
          _REFUND, True, "REFUND_NOT_ALLOWED"),
    _case("refund-complex-3", "refund", "complex", "O1006",
          "订单 O1006 金额有点大，我要退款，能不能分两笔退？今天之内必须给我答复。",
          _REFUND, True, "REFUND_OVER_LIMIT"),
    # ---- address_change / simple：未发货，可直接改
    _case("address-simple-1", "address_change", "simple", "O1001",
          "订单 O1001 还没发货吧？我想把收货地址改一下，麻烦帮我处理。", _ADDRESS, False, None),
    _case("address-simple-2", "address_change", "simple", "O1005",
          "订单 O1005 地址填错了，麻烦帮我改成新的收货地址，谢谢。", _ADDRESS, False, None),
    _case("address-simple-3", "address_change", "simple", "O1007",
          "订单 O1007 我想把地址从公司改到家里，还能改吗？", _ADDRESS, False, None),
    # ---- address_change / complex：已发货需人工拦截，或一次提两件事
    _case("address-complex-1", "address_change", "complex", "O1002",
          "订单 O1002 已经发货了，但地址写错了，能不能改？不能改的话我该怎么办？",
          _ADDRESS, True, "ADDRESS_AFTER_SHIP"),
    _case("address-complex-2", "address_change", "complex", "O1008",
          "订单 O1008 物流显示已发出，我地址填错，既要改地址又担心包裹丢了。",
          _ADDRESS, True, "ADDRESS_AFTER_SHIP"),
    _case("address-complex-3", "address_change", "complex", "O1006",
          "订单 O1006 我要改地址，另外想顺便问一下什么时候发货，两件事一起处理。",
          _ADDRESS, False, None),
    # ---- shipping_urge / simple：未发货，催仓库
    _case("shipping-simple-1", "shipping_urge", "simple", "O1001",
          "订单 O1001 付款两天了还没发货，麻烦帮我催一下。", _SHIPPING, False, None),
    _case("shipping-simple-2", "shipping_urge", "simple", "O1005",
          "订单 O1005 一直显示待发货，能不能催催仓库？", _SHIPPING, False, None),
    _case("shipping-simple-3", "shipping_urge", "simple", "O1006",
          "订单 O1006 什么时候能发？我等得有点久了，帮忙催一下。", _SHIPPING, False, None),
    # ---- shipping_urge / complex：物流停滞、承诺未达、签收争议
    _case("shipping-complex-1", "shipping_urge", "complex", "O1002",
          "订单 O1002 显示已发货三天了，物流一直不动，麻烦查一下到底到哪了。", _SHIPPING, False, None),
    _case("shipping-complex-2", "shipping_urge", "complex", "O1008",
          "订单 O1008 说好昨天到，现在还没影子，我要催发货也想知道快递单号。", _SHIPPING, False, None),
    _case("shipping-complex-3", "shipping_urge", "complex", "O1003",
          "订单 O1003 显示签收但我根本没收到，快递说放门口了，再不管我就投诉。",
          _SHIPPING, True, "DELIVERY_DISPUTE"),
    # ---- other / simple：无单号咨询、错误单号、闲聊
    _case("other-simple-1", "other", "simple", None,
          "你们双十一有什么活动？想先了解一下再下单。", [], False, None),
    _case("other-simple-2", "other", "simple", "O9999",
          "订单 O9999 是什么情况？我查不到这个单号，帮我看看。", ["query_order"], True, "ORDER_NOT_FOUND"),
    _case("other-simple-3", "other", "simple", None,
          "上次的问题已经解决了，谢谢你们的客服，服务态度很好。", [], False, None),
    # ---- other / complex：越权、跨订单、投诉威胁
    _case("other-complex-1", "other", "complex", "O1004",
          "我帮朋友问一下订单 O1004 的退款进度，他的账号登不上了。", ["query_order"], True, "ORDER_NOT_FOUND"),
    _case("other-complex-2", "other", "complex", None,
          "订单 O1001 和 O1008 我都想改地址，能不能一起改？", [], True, "MULTI_ORDER"),
    _case("other-complex-3", "other", "complex", None,
          "你们这什么服务？再不给我个说法我就去 12315 投诉，还要发微博曝光。", [], True, "COMPLAINT_OR_THREAT"),
]


def validate(cases: list[dict[str, Any]]) -> None:
    """结构自检：数量、覆盖、长度、订单、工具名、转人工与原因的一致性。"""
    if len(cases) != 24:
        raise SystemExit(f"用例数应为 24，实际 {len(cases)}")

    ids = [case["case_id"] for case in cases]
    if len(set(ids)) != len(ids):
        raise SystemExit("case_id 存在重复")

    for intent in INTENTS:
        for form in FORMS:
            group = [c for c in cases if c["intent"] == intent and c["form"] == form]
            if len(group) != 3:
                raise SystemExit(f"{intent}/{form} 应有 3 条，实际 {len(group)}")

    registry_names = set(default_registry().names())
    for case in cases:
        if case["intent"] not in INTENTS:
            raise SystemExit(f"{case['case_id']} 意图非法：{case['intent']}")
        if case["form"] not in FORMS:
            raise SystemExit(f"{case['case_id']} 形态非法：{case['form']}")
        text = case["text"]
        if not MIN_TEXT_CHARS <= len(text) <= MAX_TEXT_CHARS:
            raise SystemExit(f"{case['case_id']} 文本长度 {len(text)} 超出 {MIN_TEXT_CHARS}–{MAX_TEXT_CHARS}")
        order_id = case["order_id"]
        if order_id is not None and order_id not in DEMO_ORDER_IDS and order_id not in MISSING_ORDER_IDS:
            raise SystemExit(f"{case['case_id']} 订单不在合成订单表内：{order_id}")
        unknown = set(case["expected_tools"]) - registry_names
        if unknown:
            raise SystemExit(f"{case['case_id']} 期望工具未注册：{sorted(unknown)}")
        if "create_ticket_draft" in case["expected_tools"]:
            raise SystemExit(f"{case['case_id']} 内部工具不应出现在期望工具里")
        if case["expected_needs_human"] and not case["expected_reason"]:
            raise SystemExit(f"{case['case_id']} 转人工必须给出原因")
        if not case["expected_needs_human"] and case["expected_reason"]:
            raise SystemExit(f"{case['case_id']} 未转人工却给了原因")


def build(seed: int = DEFAULT_SEED) -> dict[str, Any]:
    cases = [dict(case) for case in CASES]
    validate(cases)
    random.Random(seed).shuffle(cases)
    return {"version": "w1-seed-1", "seed": seed, "count": len(cases), "cases": cases}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 24 条 Mock 工单 JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"输出路径（默认 {DEFAULT_OUT}）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子，固定后结果可复现")
    args = parser.parse_args(argv)

    payload = build(args.seed)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts: dict[tuple[str, str], int] = {}
    for case in payload["cases"]:
        key = (case["intent"], case["form"])
        counts[key] = counts.get(key, 0) + 1
    summary = " ".join(f"{intent}/{form}={counts.get((intent, form), 0)}" for intent in INTENTS for form in FORMS)
    print(f"wrote {payload['count']} cases (seed={args.seed}) -> {out_path}")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
