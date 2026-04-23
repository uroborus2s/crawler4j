from __future__ import annotations

import pytest

from crawler4j_contracts.hosted_ui import normalize_page_schema


def test_normalize_page_schema_supports_card_component():
    schema = normalize_page_schema(
        "dashboard",
        {
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "children": [
                {
                    "type": "Card",
                    "title": "活跃账号",
                    "layout": {"direction": "column", "gap": 8},
                    "children": [
                        {"type": "Text", "style": "subtitle", "binding": "summary.active_count"},
                        {"type": "Text", "style": "meta", "text": "较昨日 +12.5%"},
                    ],
                }
            ],
        },
    )

    assert schema["children"] == [
        {
            "type": "Card",
            "title": "活跃账号",
            "layout": {"direction": "column", "gap": 8},
            "children": [
                {"type": "Text", "style": "subtitle", "binding": "summary.active_count"},
                {"type": "Text", "style": "meta", "text": "较昨日 +12.5%"},
            ],
        }
    ]


def test_normalize_page_schema_rejects_unsupported_card_fields():
    with pytest.raises(ValueError, match="children\\[0\\] 包含不支持的字段"):
        normalize_page_schema(
            "dashboard",
            {
                "type": "Page",
                "load_handler": "load_dashboard_page",
                "children": [
                    {
                        "type": "Card",
                        "title": "活跃账号",
                        "accent_color": "#facc15",
                    }
                ],
            },
        )
