from __future__ import annotations

import pytest

from crawler4j_contracts.hosted_ui import normalize_db_view_schema, normalize_page_schema


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
                    "title_align": "center",
                    "content_align": "center",
                    "content_vertical_align": "center",
                    "min_height": 180,
                    "padding": 24,
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
            "title_align": "center",
            "content_align": "center",
            "content_vertical_align": "center",
            "min_height": 180,
            "padding": 24,
            "layout": {"direction": "column", "gap": 8},
            "children": [
                {"type": "Text", "style": "subtitle", "binding": "summary.active_count"},
                {"type": "Text", "style": "meta", "text": "较昨日 +12.5%"},
            ],
        }
    ]


@pytest.mark.parametrize("removed_key", ["filterable", "sortable"])
def test_normalize_db_view_schema_rejects_removed_query_flags(removed_key):
    with pytest.raises(ValueError, match=f"不支持的字段: {removed_key}"):
        normalize_db_view_schema(
            "billing_stats",
            {
                "view_kind": "sql_view",
                "source_resource_ids": ["billing_entries"],
                "select_sql_template": "SELECT entry_id FROM {{resource:billing_entries}}",
                "columns": [{"name": "entry_id", "type": "text", removed_key: True}],
            },
        )


def test_normalize_page_schema_rejects_invalid_card_vertical_alignment():
    with pytest.raises(ValueError, match="children\\[0\\]\\.content_vertical_align 不受支持"):
        normalize_page_schema(
            "dashboard",
            {
                "type": "Page",
                "load_handler": "load_dashboard_page",
                "children": [
                    {
                        "type": "Card",
                        "title": "活跃账号",
                        "content_vertical_align": "middle-ish",
                    }
                ],
            },
        )


def test_normalize_page_schema_supports_page_scroll_vertical_hidden():
    schema = normalize_page_schema(
        "dashboard",
        {
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "scroll": {"vertical": "hidden"},
            "children": [
                {"type": "Text", "style": "title", "text": "今日运营看板"},
            ],
        },
    )

    assert schema["scroll"] == {"vertical": "hidden"}


def test_normalize_page_schema_rejects_invalid_page_scroll_vertical_value():
    with pytest.raises(ValueError, match="scroll\\.vertical 不受支持"):
        normalize_page_schema(
            "dashboard",
            {
                "type": "Page",
                "load_handler": "load_dashboard_page",
                "scroll": {"vertical": "overlay"},
                "children": [],
            },
        )


def test_normalize_page_schema_supports_parameterized_icon_button():
    schema = normalize_page_schema(
        "detail",
        {
            "type": "Page",
            "load_handler": "load_detail_page",
            "children": [
                {
                    "type": "Button",
                    "icon": "←",
                    "aria_label": "返回",
                    "size": "icon",
                    "variant": "ghost",
                    "action": {"type": "open_page", "page_id": "accounts"},
                },
            ],
        },
    )

    assert schema["children"][0] == {
        "type": "Button",
        "icon": "←",
        "aria_label": "返回",
        "size": "icon",
        "variant": "ghost",
        "action": {"type": "open_page", "page_id": "accounts"},
    }


def test_normalize_page_schema_supports_page_action_button():
    schema = normalize_page_schema(
        "dashboard",
        {
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "children": [
                {
                    "type": "Button",
                    "label": "创建账号",
                    "action": {
                        "type": "page_action",
                        "name": "create_account_from_ui",
                        "params": {
                            "account_id": {"binding": "selected.id"},
                            "source": {"value": "dashboard"},
                        },
                    },
                },
            ],
        },
    )

    assert schema["children"][0]["action"] == {
        "type": "page_action",
        "name": "create_account_from_ui",
        "params": {
            "account_id": {"binding": "selected.id"},
            "source": {"value": "dashboard"},
        },
    }


def test_normalize_page_schema_supports_ui_action_button():
    schema = normalize_page_schema(
        "dashboard",
        {
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "children": [
                {
                    "type": "Button",
                    "label": "创建账号",
                    "action": {
                        "type": "ui_action",
                        "name": "create_account_from_ui",
                        "params": {
                            "account_id": {"binding": "selected.id"},
                            "source": {"value": "dashboard"},
                        },
                    },
                },
            ],
        },
    )

    assert schema["children"][0]["action"] == {
        "type": "ui_action",
        "name": "create_account_from_ui",
        "params": {
            "account_id": {"binding": "selected.id"},
            "source": {"value": "dashboard"},
        },
    }


def test_normalize_page_schema_requires_accessible_label_for_icon_button():
    with pytest.raises(ValueError, match="aria_label"):
        normalize_page_schema(
            "detail",
            {
                "type": "Page",
                "load_handler": "load_detail_page",
                "children": [
                    {
                        "type": "Button",
                        "icon": "←",
                        "size": "icon",
                        "action": {"type": "open_page", "page_id": "accounts"},
                    }
                ],
            },
        )
