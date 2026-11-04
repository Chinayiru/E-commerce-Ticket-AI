"""PII 脱敏（无依赖的小工具，core 与 tools 都可引用，避免分层互相 import）。"""

from __future__ import annotations

import re

_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
_ADDRESS_DETAIL_RE = re.compile(r"((?:号楼|栋|单元|室|层|弄|号)[\u4e00-\u9fa5A-Za-z0-9]{0,8})")
_ELEVEN_DIGITS_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")


def mask_pii(text: str) -> str:
    """手机号留前三后四、身份证留首六尾四、门牌细节整段打码。"""
    if not text:
        return text
    masked = _PHONE_RE.sub(r"\1****\3", text)
    masked = _ID_CARD_RE.sub(r"\1********\2", masked)
    masked = _ADDRESS_DETAIL_RE.sub("***", masked)
    return masked


def has_plain_phone(text: str) -> bool:
    """是否残留 11 位连续数字（AC15 的检索口径）。"""
    return bool(_ELEVEN_DIGITS_RE.search(text or ""))
