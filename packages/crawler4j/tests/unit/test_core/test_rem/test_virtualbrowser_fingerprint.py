from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS,
    VIRTUALBROWSER_CN_LANGUAGE,
    VIRTUALBROWSER_FALLBACK_LANGUAGE,
    VIRTUALBROWSER_LANGUAGE_BY_COUNTRY,
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    VIRTUALBROWSER_UA_TEMPLATES,
    build_virtualbrowser_randomized_fingerprint_patch,
    build_virtualbrowser_speech_voices_override,
    materialize_virtualbrowser_fingerprint,
)


def test_virtualbrowser_common_screen_resolutions_use_modern_weighted_pool():
    assert VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS == (
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


def test_materialize_virtualbrowser_fingerprint_defers_random_fields_to_virtualbrowser():
    chrome_version, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
            "fonts": {"mode": 1},
            "canvas": {"mode": 1},
            "webgl-img": {"mode": 1},
        },
        default_chrome_version=145,
    )

    assert chrome_version == 145
    assert payload == {}


def test_randomized_fingerprint_patch_only_repairs_invalid_or_required_fields(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        lambda _items: (8, 16),
    )
    expected = {
        "ua-language": {"mode": 1, "language": "zh-CN", "value": "zh-CN,zh"},
        "time-zone": {"mode": 1, "utc": "Asia/Shanghai", "value": 8},
        "location": {
            "mode": 1,
            "enable": 1,
            "longitude": "121.6489",
            "latitude": "42.0117",
            "precision": 1500,
        },
        "speech_voices": {"mode": 1, "value": [{"name": "Google UK English Male"}]},
    }

    patch = build_virtualbrowser_randomized_fingerprint_patch(
        {
            "ua": {
                "mode": 0,
                "value": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/145.0.0.0",
            },
            "ua-full-version": {"mode": 1, "value": "145.0.7632.109"},
            "sec-ch-ua": {"mode": 0, "value": [{"brand": "Chromium", "version": 145}]},
            "cpu": {"mode": 1, "value": 2},
            "memory": {"mode": 1, "value": 8},
            "screen": {"mode": 0, "width": 1920, "height": 1080, "_value": "1920 x 1080"},
        },
        expected,
    )

    assert patch == {
        "ua": {
            "mode": 1,
            "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0",
        },
        "cpu": {"mode": 1, "value": 8},
        "memory": {"mode": 1, "value": 16},
        "screen": {"mode": 1, "width": 1920, "height": 1080, "_value": "1920 x 1080"},
        **expected,
    }
    assert "ua-full-version" not in patch
    assert "sec-ch-ua" not in patch


def test_virtualbrowser_random_user_agent_templates_match_supported_host_systems():
    assert "WOW64" not in VIRTUALBROWSER_UA_TEMPLATES["Windows"]
    assert "Win64; x64" in VIRTUALBROWSER_UA_TEMPLATES["Windows"]
    assert "Macintosh; Intel Mac OS X" in VIRTUALBROWSER_UA_TEMPLATES["Darwin"]
    assert "X11; Linux x86_64" in VIRTUALBROWSER_UA_TEMPLATES["Linux"]


def test_virtualbrowser_speech_voices_override_uses_native_macos_voices():
    """macOS VirtualBrowser 不支持注入 Windows/Google 语音列表。"""
    assert build_virtualbrowser_speech_voices_override(system="Darwin") is None

    windows_override = build_virtualbrowser_speech_voices_override(system="Windows")
    assert windows_override is not None
    assert windows_override["mode"] == 1
    assert windows_override["value"]


def test_materialize_virtualbrowser_fingerprint_strips_manual_random_identity_fields():
    _, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
        },
        default_chrome_version=145,
    )

    assert payload == {}


def test_materialize_virtualbrowser_fingerprint_omits_randomized_identity_fields():
    _, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
            "ua": {"mode": 1, "value": "Mozilla/5.0 Test"},
            "sec-ch-ua": {"mode": 1, "value": '"Chromium";v="145"'},
            "device-name": {"mode": 1, "value": "Q7M2P9X4K3A1B5C6D"},
            "mac": {"mode": 1, "value": "02-76-66-51-39-C9"},
        },
        default_chrome_version=145,
    )

    assert payload == {}


def test_materialize_virtualbrowser_fingerprint_uses_proxy_geo(monkeypatch):
    chrome_version, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
        },
        default_chrome_version=145,
        geo={
            "country_code": "JP",
            "timezone": "Asia/Tokyo",
            "latitude": 35.6895,
            "longitude": 139.6917,
        },
    )

    assert chrome_version == 145
    assert payload["ua-language"] == {"mode": 1, "language": "ja-JP", "value": "ja"}
    assert payload["time-zone"] == {
        "mode": 1,
        "zone": "(UTC+09:00) Asia/Tokyo",
        "utc": "Asia/Tokyo",
        "locale": "ja-JP",
        "value": 9,
    }
    assert payload["location"] | {"precision": 0} == {
        "mode": 1,
        "enable": 1,
        "longitude": "139.6917",
        "latitude": "35.6895",
        "precision": 0,
    }
    assert 1000 <= payload["location"]["precision"] <= 2000


def test_materialize_virtualbrowser_fingerprint_applies_geo_without_randomize():
    _, payload = materialize_virtualbrowser_fingerprint(
        {"fonts": {"mode": 1}},
        default_chrome_version=145,
        geo={
            "latitude": 39.9072,
            "longitude": 116.357,
        },
    )

    assert payload["fonts"] == {"mode": 1}
    assert payload["location"] | {"precision": 0} == {
        "mode": 1,
        "enable": 1,
        "longitude": "116.357",
        "latitude": "39.9072",
        "precision": 0,
    }


def test_materialize_virtualbrowser_fingerprint_ignores_legacy_post_create_marker():
    chrome_version, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 144,
            "__randomize_after_create__": True,
            "fonts": {"mode": 1},
        },
        default_chrome_version=145,
    )

    assert chrome_version == 144
    assert payload == {"fonts": {"mode": 1}}


def test_virtualbrowser_language_value_does_not_duplicate_primary_language():
    profiles = [
        VIRTUALBROWSER_CN_LANGUAGE,
        VIRTUALBROWSER_FALLBACK_LANGUAGE,
        *VIRTUALBROWSER_LANGUAGE_BY_COUNTRY.values(),
    ]

    for profile in profiles:
        language = profile["language"]
        value_parts = [part.strip() for part in str(profile["value"]).split(",") if part.strip()]

        assert language not in value_parts
