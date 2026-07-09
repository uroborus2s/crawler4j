from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_COMMON_HARDWARE_PROFILES,
    VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS,
    VIRTUALBROWSER_CN_LANGUAGE,
    VIRTUALBROWSER_CN_TIME_ZONE,
    VIRTUALBROWSER_FALLBACK_LANGUAGE,
    VIRTUALBROWSER_LANGUAGE_BY_COUNTRY,
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    VIRTUALBROWSER_UA_TEMPLATES,
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


def test_materialize_virtualbrowser_fingerprint_randomizes_chrome_version(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )

    def pick_random_value(options):
        if options == tuple(range(139, 146)):
            return 142
        if options == VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS:
            return (1920, 1080)
        if options == VIRTUALBROWSER_COMMON_HARDWARE_PROFILES:
            return (6, 16)
        raise AssertionError(f"unexpected options: {options!r}")

    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        pick_random_value,
    )

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

    assert chrome_version == 142
    assert payload["os"] == "Win 11"
    assert "WOW64" not in payload["ua"]["value"]
    assert "Win64; x64" in payload["ua"]["value"]
    assert payload["ua-full-version"] == {"mode": 1, "value": "142.0.0.0"}
    assert payload["sec-ch-ua"]["value"][0] == {"brand": "Chromium", "version": 142}
    assert payload["ua-language"] == VIRTUALBROWSER_CN_LANGUAGE
    assert payload["time-zone"] == VIRTUALBROWSER_CN_TIME_ZONE
    assert payload["screen"] == {"mode": 1, "width": 1920, "height": 1080, "_value": "1920 x 1080"}
    assert payload["fonts"]["value"]
    assert set(("r", "g", "b", "a")).issubset(payload["canvas"])
    assert set(("r", "g", "b", "a")).issubset(payload["webgl-img"])
    assert set(("channel", "analyer")).issubset(payload["audio-context"])
    assert set(("width", "height")).issubset(payload["client-rects"])
    assert payload["speech_voices"]["value"]
    assert payload["device-name"]["value"].startswith("DESKTOP-")
    assert payload["mac"]["value"].count("-") == 5
    assert payload["webrtc"] == {"mode": 0}
    assert payload["cpu"] == {"mode": 1, "value": 6}
    assert payload["memory"] == {"mode": 1, "value": 16}
    assert "location" not in payload


def test_virtualbrowser_random_user_agent_templates_match_supported_host_systems():
    assert "WOW64" not in VIRTUALBROWSER_UA_TEMPLATES["Windows"]
    assert "Win64; x64" in VIRTUALBROWSER_UA_TEMPLATES["Windows"]
    assert "Macintosh; Intel Mac OS X" in VIRTUALBROWSER_UA_TEMPLATES["Darwin"]
    assert "X11; Linux x86_64" in VIRTUALBROWSER_UA_TEMPLATES["Linux"]


def test_materialize_virtualbrowser_fingerprint_uses_host_system_profile(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Darwin",
    )
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        lambda options: options[0],
    )

    _, payload = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
        },
        default_chrome_version=145,
    )

    assert payload["os"] == "Mac OS"
    assert "Macintosh; Intel Mac OS X" in payload["ua"]["value"]
    assert "Win64; x64" not in payload["ua"]["value"]
    assert "PingFang SC" in payload["fonts"]["value"]
    assert payload["speech_voices"]["value"][0]["name"] == "Ting-Ting"
    assert payload["device-name"]["value"].startswith("MacBook-Pro-")


def test_materialize_virtualbrowser_fingerprint_omits_randomized_identity_fields(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        lambda options: options[0],
    )

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

    assert payload["ua"]["value"] != "Mozilla/5.0 Test"
    assert payload["sec-ch-ua"]["value"] != '"Chromium";v="145"'
    assert payload["device-name"]["value"] != "Q7M2P9X4K3A1B5C6D"
    assert payload["mac"]["value"] != "02-76-66-51-39-C9"
    assert payload["ua-language"] == VIRTUALBROWSER_CN_LANGUAGE
    assert payload["time-zone"] == VIRTUALBROWSER_CN_TIME_ZONE
    assert payload["screen"]["mode"] == 1
    assert payload["fonts"]["value"]
    assert "r" in payload["canvas"]
    assert "value" in payload["speech_voices"]


def test_materialize_virtualbrowser_fingerprint_uses_proxy_geo(monkeypatch):
    def pick_random_value(options):
        if options == tuple(range(139, 146)):
            return 142
        if options == VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS:
            return (1920, 1080)
        if options == VIRTUALBROWSER_COMMON_HARDWARE_PROFILES:
            return (6, 16)
        raise AssertionError(f"unexpected options: {options!r}")

    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        pick_random_value,
    )

    _, payload = materialize_virtualbrowser_fingerprint(
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

    assert payload["ua-language"] == {"mode": 1, "language": "ja-JP", "value": "ja"}
    assert payload["time-zone"] == {
        "mode": 1,
        "zone": "(UTC+09:00) Asia/Tokyo",
        "utc": "Asia/Tokyo",
        "locale": "ja-JP",
        "value": 9,
    }
    assert payload["location"] | {"precision": 0} == {
        "mode": 2,
        "enable": 1,
        "longitude": "139.6917",
        "latitude": "35.6895",
        "precision": 0,
    }
    assert 1600 <= payload["location"]["precision"] <= 5600


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
        "mode": 2,
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
