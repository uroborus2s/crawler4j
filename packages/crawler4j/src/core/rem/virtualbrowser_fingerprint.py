"""VirtualBrowser 指纹模板的创建期展开。"""

from __future__ import annotations

import secrets
import string
import uuid
from typing import Any

VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY = "__randomize_fingerprint__"
VIRTUALBROWSER_RANDOM_MODE_KEYS = (
    "fonts",
    "canvas",
    "webgl-img",
    "audio-context",
    "client-rects",
    "speech_voices",
)
VIRTUALBROWSER_UA_TEMPLATES = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_10) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_7_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36",
)


def normalize_chrome_version(value: Any, *, default: int) -> int:
    """把浏览器版本归一为合法整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_random_user_agent(chrome_version: int) -> str:
    """生成随机 UA。"""
    template = secrets.choice(VIRTUALBROWSER_UA_TEMPLATES)
    return template.format(version=chrome_version)


def generate_device_name() -> str:
    """生成随机设备名。"""
    prefix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"


def generate_mac_address() -> str:
    """生成本地管理的随机 MAC。"""
    octets = bytearray(secrets.token_bytes(6))
    octets[0] = (octets[0] & 0b11111100) | 0b00000010
    return "-".join(f"{octet:02X}" for octet in octets)


def materialize_virtualbrowser_fingerprint(
    fingerprint: dict[str, Any] | None,
    *,
    default_chrome_version: int,
) -> tuple[int, dict[str, Any]]:
    """把运行模板中的指纹模板展开为本次创建真正下发的参数。"""
    payload = dict(fingerprint or {})
    should_randomize = bool(payload.pop(VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY, False))

    # 旧方案彻底下线，但仍在创建前剥离无效内部字段，避免透传到官方 API。
    payload.pop("__randomize_after_create__", None)

    chrome_version = normalize_chrome_version(
        payload.pop("chrome_version", default_chrome_version),
        default=default_chrome_version,
    )

    if should_randomize:
        payload["ua"] = {"mode": 1, "value": generate_random_user_agent(chrome_version)}
        payload["device-name"] = {"mode": 1, "value": generate_device_name()}
        payload["mac"] = {"mode": 1, "value": generate_mac_address()}

    return chrome_version, payload
