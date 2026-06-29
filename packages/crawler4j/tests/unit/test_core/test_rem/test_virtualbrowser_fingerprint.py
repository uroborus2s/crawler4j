from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_COMMON_HARDWARE_PROFILES,
    VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS,
    VIRTUALBROWSER_CN_LANGUAGE,
    VIRTUALBROWSER_CN_TIME_ZONE,
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    materialize_virtualbrowser_fingerprint,
)


def test_materialize_virtualbrowser_fingerprint_randomizes_chrome_version(monkeypatch):
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
    assert payload == {
        "ua-language": VIRTUALBROWSER_CN_LANGUAGE,
        "time-zone": VIRTUALBROWSER_CN_TIME_ZONE,
        "screen": {"mode": 1, "width": 1920, "height": 1080, "_value": "1920 x 1080"},
        "fonts": {"mode": 1},
        "canvas": {"mode": 1},
        "webgl-img": {"mode": 1},
        "audio-context": {"mode": 1},
        "client-rects": {"mode": 1},
        "speech_voices": {"mode": 1},
        "webrtc": {"mode": 0},
        "location": {"mode": 2, "enable": 0},
        "cpu": {"mode": 1, "value": 6},
        "memory": {"mode": 1, "value": 16},
    }


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

    assert "ua" not in payload
    assert "sec-ch-ua" not in payload
    assert "device-name" not in payload
    assert "mac" not in payload
    assert payload["ua-language"] == VIRTUALBROWSER_CN_LANGUAGE
    assert payload["time-zone"] == VIRTUALBROWSER_CN_TIME_ZONE
    assert payload["screen"]["mode"] == 1


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
