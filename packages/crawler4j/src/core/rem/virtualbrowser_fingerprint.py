"""VirtualBrowser 指纹模板的创建期展开。"""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY = "__randomize_fingerprint__"
VIRTUALBROWSER_RANDOM_CHROME_VERSIONS = tuple(range(139, 146))
VIRTUALBROWSER_RANDOM_MODE_KEYS = (
    "fonts",
    "canvas",
    "webgl-img",
    "audio-context",
    "client-rects",
    "speech_voices",
)
VIRTUALBROWSER_RANDOM_IDENTITY_KEYS = (
    "ua",
    "ua-full-version",
    "sec-ch-ua",
    "device-name",
    "mac",
)
VIRTUALBROWSER_CN_LANGUAGE = {"mode": 1, "language": "zh-CN", "value": "zh-CN,zh"}
VIRTUALBROWSER_CN_TIME_ZONE = {
    "mode": 1,
    "zone": "(UTC+08:00) Asia/Shanghai",
    "utc": "Asia/Shanghai",
    "locale": "zh-CN",
    "value": 8,
}
VIRTUALBROWSER_LANGUAGE_BY_COUNTRY = {
    "AU": {"mode": 1, "language": "en-AU", "value": "en-AU,en"},
    "BR": {"mode": 1, "language": "pt-BR", "value": "pt-BR,pt"},
    "CA": {"mode": 1, "language": "en-CA", "value": "en-CA,en"},
    "CN": VIRTUALBROWSER_CN_LANGUAGE,
    "DE": {"mode": 1, "language": "de-DE", "value": "de-DE,de"},
    "ES": {"mode": 1, "language": "es-ES", "value": "es-ES,es"},
    "FR": {"mode": 1, "language": "fr-FR", "value": "fr-FR,fr"},
    "GB": {"mode": 1, "language": "en-GB", "value": "en-GB,en"},
    "HK": {"mode": 1, "language": "zh-HK", "value": "zh-HK,zh"},
    "ID": {"mode": 1, "language": "id-ID", "value": "id-ID,id"},
    "IN": {"mode": 1, "language": "en-IN", "value": "en-IN,en"},
    "IT": {"mode": 1, "language": "it-IT", "value": "it-IT,it"},
    "JP": {"mode": 1, "language": "ja-JP", "value": "ja-JP,ja"},
    "KR": {"mode": 1, "language": "ko-KR", "value": "ko-KR,ko"},
    "MY": {"mode": 1, "language": "en-MY", "value": "en-MY,en"},
    "NL": {"mode": 1, "language": "nl-NL", "value": "nl-NL,nl"},
    "PH": {"mode": 1, "language": "en-PH", "value": "en-PH,en"},
    "RU": {"mode": 1, "language": "ru-RU", "value": "ru-RU,ru"},
    "SG": {"mode": 1, "language": "en-SG", "value": "en-SG,en"},
    "TH": {"mode": 1, "language": "th-TH", "value": "th-TH,th"},
    "TW": {"mode": 1, "language": "zh-TW", "value": "zh-TW,zh"},
    "US": {"mode": 1, "language": "en-US", "value": "en-US,en"},
    "VN": {"mode": 1, "language": "vi-VN", "value": "vi-VN,vi"},
}
VIRTUALBROWSER_FALLBACK_LANGUAGE = {"mode": 1, "language": "en-US", "value": "en-US,en"}
VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS = (
    (1366, 768),
    (1600, 900),
    (1680, 1050),
    (1920, 1080),
    (2560, 1440),
)
VIRTUALBROWSER_COMMON_HARDWARE_PROFILES = (
    (4, 8),
    (6, 16),
    (8, 16),
    (8, 32),
    (12, 32),
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


def build_virtualbrowser_random_fingerprint_defaults(
    geo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成随机指纹托管模式的最小自洽默认值。"""
    width, height = secrets.choice(VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS)
    cpu, memory = secrets.choice(VIRTUALBROWSER_COMMON_HARDWARE_PROFILES)
    defaults = {
        "ua-language": dict(VIRTUALBROWSER_CN_LANGUAGE),
        "time-zone": dict(VIRTUALBROWSER_CN_TIME_ZONE),
        "screen": {
            "mode": 1,
            "width": width,
            "height": height,
            "_value": f"{width} x {height}",
        },
        "fonts": {"mode": 1},
        "canvas": {"mode": 1},
        "webgl-img": {"mode": 1},
        "audio-context": {"mode": 1},
        "client-rects": {"mode": 1},
        "speech_voices": {"mode": 1},
        "webrtc": {"mode": 0},
        "location": {"mode": 2, "enable": 0},
        "cpu": {"mode": 1, "value": cpu},
        "memory": {"mode": 1, "value": memory},
    }
    defaults.update(build_virtualbrowser_geo_fingerprint_overrides(geo))
    return defaults


def build_virtualbrowser_geo_fingerprint_overrides(
    geo: dict[str, Any] | None,
) -> dict[str, Any]:
    """按出口地理信息生成语言和时区覆盖值。"""
    if not isinstance(geo, dict):
        return {}
    country_code = str(geo.get("country_code") or "").strip().upper()
    timezone = str(geo.get("timezone") or "").strip()
    overrides: dict[str, Any] = {}
    language = _language_for_country(country_code) if country_code else None
    if language:
        overrides["ua-language"] = dict(language)
    if timezone:
        locale = str((language or VIRTUALBROWSER_CN_LANGUAGE).get("language") or "zh-CN")
        time_zone = _build_time_zone_profile(timezone, locale=locale)
        if time_zone:
            overrides["time-zone"] = time_zone
    return overrides


def _language_for_country(country_code: str) -> dict[str, Any]:
    return VIRTUALBROWSER_LANGUAGE_BY_COUNTRY.get(country_code, VIRTUALBROWSER_FALLBACK_LANGUAGE)


def _build_time_zone_profile(timezone: str, *, locale: str) -> dict[str, Any] | None:
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return None
    offset = datetime.now(zone).utcoffset()
    if offset is None:
        return None
    offset_hours = offset.total_seconds() / 3600
    value = int(offset_hours) if offset_hours.is_integer() else round(offset_hours, 2)
    return {
        "mode": 1,
        "zone": f"({_format_utc_offset(offset_hours)}) {timezone}",
        "utc": timezone,
        "locale": locale,
        "value": value,
    }


def _format_utc_offset(offset_hours: float) -> str:
    sign = "+" if offset_hours >= 0 else "-"
    total_minutes = int(round(abs(offset_hours) * 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def materialize_virtualbrowser_fingerprint(
    fingerprint: dict[str, Any] | None,
    *,
    default_chrome_version: int,
    geo: dict[str, Any] | None = None,
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
        for key in VIRTUALBROWSER_RANDOM_IDENTITY_KEYS:
            payload.pop(key, None)
        defaults = build_virtualbrowser_random_fingerprint_defaults(geo)
        defaults.update(payload)
        return secrets.choice(VIRTUALBROWSER_RANDOM_CHROME_VERSIONS), defaults

    return chrome_version, payload
