from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_CN_LANGUAGE,
    VIRTUALBROWSER_FALLBACK_LANGUAGE,
    VIRTUALBROWSER_LANGUAGE_BY_COUNTRY,
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    build_virtualbrowser_ip_auto_fingerprint_overrides,
    build_virtualbrowser_randomized_fingerprint_patch,
    materialize_virtualbrowser_fingerprint,
)


def test_virtualbrowser_ip_auto_fingerprint_uses_vendor_default_modes():
    overrides = build_virtualbrowser_ip_auto_fingerprint_overrides()

    assert overrides["ua"] == {"mode": 0}
    assert overrides["screen"] == {"mode": 0}
    assert overrides["ua-language"] == {"mode": 2}
    assert overrides["time-zone"] == {"mode": 2}
    assert overrides["location"] == {"mode": 2, "enable": 1}
    assert overrides["speech_voices"] == {"mode": 1, "value": {}}


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


def test_randomized_fingerprint_patch_keeps_hardware_in_common_pool(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        lambda _items: (8, 16),
    )
    expected = build_virtualbrowser_ip_auto_fingerprint_overrides()

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
        "cpu": {"mode": 1, "value": 8},
        "memory": {"mode": 1, "value": 16},
        "ua-language": {"mode": 2},
        "time-zone": {"mode": 2},
        "location": {"mode": 2, "enable": 1},
        "speech_voices": {"mode": 1, "value": {}},
    }
    assert "ua-full-version" not in patch
    assert "sec-ch-ua" not in patch


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
