"""VirtualBrowser 指纹模板的创建期展开。"""

from __future__ import annotations

import platform
import secrets
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


def _language_profile(locale: str) -> dict[str, Any]:
    return {"mode": 1, "language": locale, "value": locale.split("-", 1)[0]}


VIRTUALBROWSER_CN_LANGUAGE = _language_profile("zh-CN")
VIRTUALBROWSER_CN_TIME_ZONE = {
    "mode": 1,
    "zone": "(UTC+08:00) Asia/Shanghai",
    "utc": "Asia/Shanghai",
    "locale": "zh-CN",
    "value": 8,
}
VIRTUALBROWSER_LANGUAGE_BY_COUNTRY = {
    "AU": _language_profile("en-AU"),
    "BR": _language_profile("pt-BR"),
    "CA": _language_profile("en-CA"),
    "CN": VIRTUALBROWSER_CN_LANGUAGE,
    "DE": _language_profile("de-DE"),
    "ES": _language_profile("es-ES"),
    "FR": _language_profile("fr-FR"),
    "GB": _language_profile("en-GB"),
    "HK": _language_profile("zh-HK"),
    "ID": _language_profile("id-ID"),
    "IN": _language_profile("en-IN"),
    "IT": _language_profile("it-IT"),
    "JP": _language_profile("ja-JP"),
    "KR": _language_profile("ko-KR"),
    "MY": _language_profile("en-MY"),
    "NL": _language_profile("nl-NL"),
    "PH": _language_profile("en-PH"),
    "RU": _language_profile("ru-RU"),
    "SG": _language_profile("en-SG"),
    "TH": _language_profile("th-TH"),
    "TW": _language_profile("zh-TW"),
    "US": _language_profile("en-US"),
    "VN": _language_profile("vi-VN"),
}
VIRTUALBROWSER_FALLBACK_LANGUAGE = _language_profile("en-US")
VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS = (
    (1920, 1080),
    (1920, 1080),
    (1920, 1080),
    (1536, 864),
    (1536, 864),
    (2560, 1440),
    (1920, 1200),
    (1440, 900),
    (1680, 1050),
    (1366, 768),
)
VIRTUALBROWSER_COMMON_HARDWARE_PROFILES = (
    (4, 8),
    (6, 16),
    (8, 16),
    (8, 32),
    (12, 32),
)
VIRTUALBROWSER_UA_TEMPLATES = {
    "Windows": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
    ),
    "Darwin": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
    ),
    "Linux": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
    ),
}
VIRTUALBROWSER_OS_BY_SYSTEM = {
    "Windows": "Win 11",
    "Darwin": "Mac OS",
    "Linux": "Linux",
}
VIRTUALBROWSER_WINDOWS_FONTS = (
    "Microsoft YaHei",
    "SimSun",
    "SimHei",
    "NSimSun",
)
VIRTUALBROWSER_MACOS_FONTS = (
    "PingFang SC",
    "Hiragino Sans GB",
    "Helvetica Neue",
    "Arial",
)
VIRTUALBROWSER_LINUX_FONTS = (
    "Noto Sans CJK SC",
    "WenQuanYi Micro Hei",
    "DejaVu Sans",
    "Arial",
)
VIRTUALBROWSER_FONTS_BY_SYSTEM = {
    "Windows": VIRTUALBROWSER_WINDOWS_FONTS,
    "Darwin": VIRTUALBROWSER_MACOS_FONTS,
    "Linux": VIRTUALBROWSER_LINUX_FONTS,
}
VIRTUALBROWSER_WINDOWS_SPEECH_VOICES = (
    {
        "default": True,
        "lang": "zh-CN",
        "localService": True,
        "name": "Microsoft Huihui - Chinese (Simplified, PRC)",
        "voiceURI": "Microsoft Huihui - Chinese (Simplified, PRC)",
    },
    {
        "default": False,
        "lang": "zh-CN",
        "localService": True,
        "name": "Microsoft Yaoyao - Chinese (Simplified, PRC)",
        "voiceURI": "Microsoft Yaoyao - Chinese (Simplified, PRC)",
    },
)
VIRTUALBROWSER_MACOS_SPEECH_VOICES = (
    {
        "default": True,
        "lang": "zh-CN",
        "localService": True,
        "name": "Ting-Ting",
        "voiceURI": "Ting-Ting",
    },
)
VIRTUALBROWSER_LINUX_SPEECH_VOICES = (
    {
        "default": True,
        "lang": "zh-CN",
        "localService": False,
        "name": "Google 普通话（中国大陆）",
        "voiceURI": "Google 普通话（中国大陆）",
    },
)
VIRTUALBROWSER_SPEECH_VOICES_BY_SYSTEM = {
    "Windows": VIRTUALBROWSER_WINDOWS_SPEECH_VOICES,
    "Darwin": VIRTUALBROWSER_MACOS_SPEECH_VOICES,
    "Linux": VIRTUALBROWSER_LINUX_SPEECH_VOICES,
}
VIRTUALBROWSER_CN_SPEECH_VOICES = VIRTUALBROWSER_WINDOWS_SPEECH_VOICES


def normalize_chrome_version(value: Any, *, default: int) -> int:
    """把浏览器版本归一为合法整数。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _fingerprint_system(system: str | None = None) -> str:
    name = str(system or platform.system()).strip()
    return name if name in VIRTUALBROWSER_UA_TEMPLATES else "Windows"


def generate_random_user_agent(chrome_version: int, *, system: str | None = None) -> str:
    """按宿主系统生成 UA。"""
    return VIRTUALBROWSER_UA_TEMPLATES[_fingerprint_system(system)].format(version=chrome_version)


def generate_device_name(system: str | None = None) -> str:
    """按宿主系统生成设备名。"""
    token = uuid.uuid4().hex[:8].upper()
    current_system = _fingerprint_system(system)
    if current_system == "Darwin":
        return f"MacBook-Pro-{token[:6]}"
    if current_system == "Linux":
        return f"linux-{token.lower()}"
    return f"DESKTOP-{token}"


def generate_mac_address() -> str:
    """生成本地管理的随机 MAC。"""
    octets = bytearray(secrets.token_bytes(6))
    octets[0] = (octets[0] & 0b11111100) | 0b00000010
    return "-".join(f"{octet:02X}" for octet in octets)


def _channel_delta(max_abs: int = 10) -> int:
    return secrets.randbelow(max_abs * 2 + 1) - max_abs


def _unit_noise() -> float:
    return round((secrets.randbelow(900_000) + 100_000) / 1_000_000, 12)


def _rgba_noise() -> dict[str, int]:
    return {channel: _channel_delta() for channel in ("r", "g", "b", "a")}


def _random_mode_placeholder(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"mode"} and value.get("mode") == 1


def build_virtualbrowser_random_fingerprint_defaults(
    geo: dict[str, Any] | None = None,
    *,
    chrome_version: int = 145,
) -> dict[str, Any]:
    """生成随机指纹托管模式的一次性稳定默认值。"""
    width, height = secrets.choice(VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS)
    cpu, memory = secrets.choice(VIRTUALBROWSER_COMMON_HARDWARE_PROFILES)
    current_system = _fingerprint_system()
    defaults = {
        "os": VIRTUALBROWSER_OS_BY_SYSTEM[current_system],
        "ua": {"mode": 0, "value": generate_random_user_agent(chrome_version, system=current_system)},
        "ua-full-version": {"mode": 1, "value": f"{chrome_version}.0.0.0"},
        "sec-ch-ua": {
            "mode": 0,
            "value": [
                {"brand": "Chromium", "version": chrome_version},
                {"brand": "Not=A?Brand", "version": "99"},
            ],
        },
        "ua-language": dict(VIRTUALBROWSER_CN_LANGUAGE),
        "time-zone": dict(VIRTUALBROWSER_CN_TIME_ZONE),
        "screen": {
            "mode": 1,
            "width": width,
            "height": height,
            "_value": f"{width} x {height}",
        },
        "fonts": {"mode": 1, "value": list(VIRTUALBROWSER_FONTS_BY_SYSTEM[current_system])},
        "canvas": {"mode": 1, **_rgba_noise()},
        "webgl-img": {"mode": 1, **_rgba_noise()},
        "audio-context": {"mode": 1, "channel": _unit_noise(), "analyer": _unit_noise()},
        "client-rects": {"mode": 1, "width": _unit_noise(), "height": _unit_noise()},
        "speech_voices": {
            "mode": 1,
            "value": [dict(voice) for voice in VIRTUALBROWSER_SPEECH_VOICES_BY_SYSTEM[current_system]],
        },
        "device-name": {"mode": 1, "value": generate_device_name(current_system)},
        "mac": {"mode": 1, "value": generate_mac_address()},
        "webrtc": {"mode": 0},
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
        for key in VIRTUALBROWSER_RANDOM_MODE_KEYS:
            if _random_mode_placeholder(payload.get(key)):
                payload.pop(key, None)
        chrome_version = secrets.choice(VIRTUALBROWSER_RANDOM_CHROME_VERSIONS)
        defaults = build_virtualbrowser_random_fingerprint_defaults(
            geo,
            chrome_version=chrome_version,
        )
        defaults.update(payload)
        return chrome_version, defaults

    return chrome_version, payload
