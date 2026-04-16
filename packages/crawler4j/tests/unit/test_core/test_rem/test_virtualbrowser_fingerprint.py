import re

from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    materialize_virtualbrowser_fingerprint,
)


def test_materialize_virtualbrowser_fingerprint_generates_create_time_random_values():
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
    assert payload["fonts"] == {"mode": 1}
    assert payload["canvas"] == {"mode": 1}
    assert payload["webgl-img"] == {"mode": 1}
    assert payload["ua"]["mode"] == 1
    assert "Chrome/145.0.0.0" in payload["ua"]["value"]
    assert re.fullmatch(r"[A-Z0-9]{18}", payload["device-name"]["value"])
    assert re.fullmatch(r"(?:[0-9A-F]{2}-){5}[0-9A-F]{2}", payload["mac"]["value"])


def test_materialize_virtualbrowser_fingerprint_generates_new_values_for_each_create():
    _, first = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
        },
        default_chrome_version=145,
    )
    _, second = materialize_virtualbrowser_fingerprint(
        {
            "chrome_version": 145,
            VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True,
        },
        default_chrome_version=145,
    )

    assert first["device-name"]["value"] != second["device-name"]["value"]
    assert first["mac"]["value"] != second["mac"]["value"]


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
