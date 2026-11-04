"""合成订单数据（W1 走文件内常量；接入真实数据时只换这一处）。

只包含虚构信息，对齐 docs/IMPLEMENTATION.md §3 的 8 条订单；
订单不是第五张表，新增订单不改数据库结构。
"""

from __future__ import annotations

from typing import Any

#: 订单号 -> 订单事实。金额统一整数分。
MOCK_ORDERS: dict[str, dict[str, Any]] = {
    "O1001": {
        "order_id": "O1001",
        "user_id": "U001",
        "amount_cents": 5800,
        "status": "paid",
        "paid_at": "2026-11-01T10:00:00+08:00",
        "delivered_at": None,
        "carrier": None,
        "tracking_id": None,
    },
    "O1002": {
        "order_id": "O1002",
        "user_id": "U001",
        "amount_cents": 25800,
        "status": "shipped",
        "paid_at": "2026-11-01T10:00:00+08:00",
        "delivered_at": None,
        "carrier": "合成快递",
        "tracking_id": "MOCK002",
    },
    "O1003": {
        "order_id": "O1003",
        "user_id": "U001",
        "amount_cents": 9900,
        "status": "delivered",
        "paid_at": "2026-10-01T10:00:00+08:00",
        "delivered_at": "2026-10-05T12:00:00+08:00",
        "carrier": "合成快递",
        "tracking_id": "MOCK003",
    },
    "O1004": {
        "order_id": "O1004",
        "user_id": "U002",
        "amount_cents": 8800,
        "status": "paid",
        "paid_at": "2026-11-01T10:00:00+08:00",
        "delivered_at": None,
        "carrier": None,
        "tracking_id": None,
    },
    "O1005": {
        "order_id": "O1005",
        "user_id": "U001",
        "amount_cents": 20000,
        "status": "paid",
        "paid_at": "2026-11-02T10:00:00+08:00",
        "delivered_at": None,
        "carrier": None,
        "tracking_id": None,
    },
    "O1006": {
        "order_id": "O1006",
        "user_id": "U001",
        "amount_cents": 25000,
        "status": "paid",
        "paid_at": "2026-11-02T10:00:00+08:00",
        "delivered_at": None,
        "carrier": None,
        "tracking_id": None,
    },
    "O1007": {
        "order_id": "O1007",
        "user_id": "U001",
        "amount_cents": 12900,
        "status": "delivered",
        "paid_at": "2026-10-15T10:00:00+08:00",
        "delivered_at": "2026-10-28T12:00:00+08:00",
        "carrier": "合成快递",
        "tracking_id": "MOCK007",
    },
    "O1008": {
        "order_id": "O1008",
        "user_id": "U001",
        "amount_cents": 39900,
        "status": "shipped",
        "paid_at": "2026-10-30T10:00:00+08:00",
        "delivered_at": None,
        "carrier": "合成快递",
        "tracking_id": "MOCK008",
    },
}

#: 供 seed 脚本与测试引用，避免两处各写一份。
DEMO_ORDER_IDS: tuple[str, ...] = tuple(MOCK_ORDERS)
