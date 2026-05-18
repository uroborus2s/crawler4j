from __future__ import annotations

import pytest
from typing import TypedDict

from crawler4j_contracts.hosted_ui import (
    QueryCallback,
    HostedDataTableQuery,
    HostedDataTableQueryResult,
    PageSchema,
    normalize_db_view_schema,
    normalize_page_schema,
)
from crawler4j_contracts import DatabaseClient


class AccountTableRow(TypedDict):
    account_id: str
    status: str


class _FakeDbExecutor:
    def __init__(self) -> None:
        self.plans: list[dict] = []

    def describe_source(self, source: str) -> dict:
        return {"source": source, "storage_mode": "custom_table", "record_key_field": "account_id"}

    def execute_plan(self, plan: dict):
        self.plans.append(plan)
        return []


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


def test_hosted_data_table_query_uses_fixed_contract_shape():
    query = HostedDataTableQuery.from_mapping(
        {
            "search_text": " ready ",
            "search_fields": ["account_id", "status"],
            "sort": [{"field": "status", "direction": "desc"}],
            "page": 3,
            "page_size": 25,
            "params": {"account_id": "A001"},
        }
    )

    assert query.search_text == " ready "
    assert query.search_fields == ("account_id", "status")
    assert query.sort[0].field == "status"
    assert query.sort[0].direction == "desc"
    assert query.limit == 25
    assert query.offset == 50
    assert query.params == {"account_id": "A001"}


def test_hosted_data_table_query_removes_legacy_callback_helpers():
    query = HostedDataTableQuery()

    assert not hasattr(query, "to_query_callback")
    assert not hasattr(query, "to_count_query_callback")


def test_hosted_data_table_query_executes_rows_and_count_callbacks():
    executor = _FakeDbExecutor()
    query = HostedDataTableQuery.from_mapping(
        {
            "search_text": " ready ",
            "search_fields": ["account_id", "status", "unmapped_search", "blocked_search"],
            "sort": [
                {"field": "createdAt", "direction": "desc"},
                {"field": "blocked_sort", "direction": "asc"},
                {"field": "unmapped_sort", "direction": "asc"},
            ],
            "page": 2,
            "page_size": 10,
            "params": {
                "account_id": "A001",
                "blocked_eq": "nope",
                "unmapped_param": "kept",
            },
        }
    )

    def rows_query(callback: QueryCallback):
        return callback(DatabaseClient(executor).from_("accounts")).execute()

    def count_query(callback: QueryCallback) -> int:
        callback(DatabaseClient(executor).from_("accounts")).count(alias="total").execute()
        return 42

    total, rows = query.to_query(
        rows_query,
        count_query,
        search_transform=lambda field: {
            "account_id": "account_id",
            "status": "account_status",
            "unmapped_search": "unmapped_search",
        }.get(field),
        sort_transform=lambda field: {
            "createdAt": "created_at",
            "unmapped_sort": "unmapped_sort",
        }.get(field),
        filter_transform=lambda key, value: {
            "account_id": "account_id",
            "unmapped_param": (key, value),
        }.get(key),
    )

    assert rows == []
    assert total == 42
    assert executor.plans[0] == {
        "kind": "select",
        "base": {"source": "accounts"},
        "joins": [],
        "select": [],
        "where": [
            {
                "kind": "group",
                "operator": "or",
                "conditions": [
                    {"field": "account_id", "op": "like", "value": "%ready%"},
                    {"field": "account_status", "op": "like", "value": "%ready%"},
                    {"field": "unmapped_search", "op": "like", "value": "%ready%"},
                ],
            },
            {"field": "account_id", "op": "eq", "value": "A001"},
            {"field": "unmapped_param", "op": "eq", "value": "kept"},
        ],
        "group_by": [],
        "order_by": [
            {"field": "created_at", "direction": "desc"},
            {"field": "unmapped_sort", "direction": "asc"},
        ],
        "limit": 10,
        "offset": 10,
    }
    assert executor.plans[1] == {
        "kind": "select",
        "base": {"source": "accounts"},
        "joins": [],
        "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "total"}],
        "where": [
            {
                "kind": "group",
                "operator": "or",
                "conditions": [
                    {"field": "account_id", "op": "like", "value": "%ready%"},
                    {"field": "account_status", "op": "like", "value": "%ready%"},
                    {"field": "unmapped_search", "op": "like", "value": "%ready%"},
                ],
            },
            {"field": "account_id", "op": "eq", "value": "A001"},
            {"field": "unmapped_param", "op": "eq", "value": "kept"},
        ],
        "group_by": [],
        "order_by": [],
        "limit": None,
        "offset": None,
    }


def test_hosted_data_table_query_without_transforms_preserves_fields():
    executor = _FakeDbExecutor()
    query = HostedDataTableQuery.from_mapping(
        {
            "search_text": " ready ",
            "search_fields": ["account_id"],
            "sort": [{"field": "created_at", "direction": "desc"}],
            "page": 1,
            "page_size": 5,
            "params": {"status": "ready"},
        }
    )

    query.to_query(
        lambda callback: callback(DatabaseClient(executor).from_("accounts")).execute(),
        lambda callback: 0,
    )

    assert executor.plans == [
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "joins": [],
            "select": [],
            "where": [
                {"field": "account_id", "op": "like", "value": "%ready%"},
                {"field": "status", "op": "eq", "value": "ready"},
            ],
            "group_by": [],
            "order_by": [
                {"field": "created_at", "direction": "desc"},
            ],
            "limit": 5,
            "offset": 0,
        }
    ]


def test_hosted_data_table_query_preserves_falsey_filter_values():
    executor = _FakeDbExecutor()
    query = HostedDataTableQuery(params={"enabled": False, "priority": 0})

    query.to_query(
        lambda callback: callback(DatabaseClient(executor).from_("accounts")).execute(),
        lambda callback: 0,
        filter_transform=lambda key, value: {"enabled": "is_enabled", "priority": "priority"}.get(key),
    )

    assert executor.plans[0]["where"] == [
        {"field": "is_enabled", "op": "eq", "value": False},
        {"field": "priority", "op": "eq", "value": 0},
    ]


def test_hosted_data_table_query_count_callback_omits_order_and_pagination():
    executor = _FakeDbExecutor()
    query = HostedDataTableQuery.from_mapping(
        {
            "search_text": " ready ",
            "search_fields": ["account_id", "status", "blocked_search"],
            "sort": [{"field": "createdAt", "direction": "desc"}],
            "page": 3,
            "page_size": 15,
            "params": {"account_id": "A001", "blocked_eq": "nope"},
        }
    )

    query.to_query(
        lambda callback: [],
        lambda callback: callback(DatabaseClient(executor).from_("accounts")).count(alias="total").execute() or 7,
        search_transform=lambda field: {
            "account_id": "account_id",
            "status": "account_status",
        }.get(field),
        sort_transform=lambda field: {
            "createdAt": "created_at",
        }.get(field),
        filter_transform=lambda key, value: {
            "account_id": "account_id",
        }.get(key),
    )

    assert executor.plans == [
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "joins": [],
            "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "total"}],
            "where": [
                {
                    "kind": "group",
                    "operator": "or",
                    "conditions": [
                        {"field": "account_id", "op": "like", "value": "%ready%"},
                        {"field": "account_status", "op": "like", "value": "%ready%"},
                    ],
                },
                {"field": "account_id", "op": "eq", "value": "A001"},
            ],
            "group_by": [],
            "order_by": [],
            "limit": None,
            "offset": None,
        }
    ]


def test_hosted_data_table_query_result_from_query_transforms_rows():
    query = HostedDataTableQuery(page=2, page_size=10)

    result = HostedDataTableQueryResult.from_query(
        query,
        (
            3,
            [
                {"account_id": "A001", "status": "ready"},
                {"account_id": "A002", "status": "hidden"},
            ],
        ),
        lambda row: (
            {"accountId": row["account_id"], "status": row["status"]}
            if row["status"] != "hidden"
            else None
        ),
    )

    assert result.rows == ({"accountId": "A001", "status": "ready"},)
    assert result.total == 3
    assert result.page == 2
    assert result.page_size == 10


def test_hosted_data_table_query_to_result_combines_query_and_row_transform():
    query = HostedDataTableQuery(page=3, page_size=20)

    result = query.to_result(
        lambda callback: [{"account_id": "A001", "status": "ready"}],
        lambda callback: 9,
        lambda row: {"accountId": row["account_id"], "status": row["status"]},
    )

    assert result.to_dict() == {
        "rows": [{"accountId": "A001", "status": "ready"}],
        "total": 9,
        "page": 3,
        "page_size": 20,
    }


def test_hosted_data_table_query_result_uses_fixed_contract_shape():
    result = HostedDataTableQueryResult[AccountTableRow](
        rows=[{"account_id": "A001", "status": "ready"}],
        page=2,
        page_size=10,
    )

    assert result.rows == ({"account_id": "A001", "status": "ready"},)
    assert result.total == 1
    assert result.page == 2
    assert result.page_size == 10
    assert result.to_dict() == {
        "rows": [{"account_id": "A001", "status": "ready"}],
        "total": 1,
        "page": 2,
        "page_size": 10,
    }


def test_hosted_data_table_query_result_rejects_non_mapping_rows():
    with pytest.raises(ValueError, match="rows items must be mappings"):
        HostedDataTableQueryResult(rows=[{"account_id": "A001"}, "bad-row"])  # type: ignore[list-item]


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


def test_normalize_page_schema_rejects_page_action_button():
    with pytest.raises(ValueError, match="reload / open_page / ui_action"):
        normalize_page_schema(
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
                        },
                    },
                ],
            },
        )


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


def test_page_schema_type_documents_crud_ui_action_fields():
    schema: PageSchema = {
        "type": "Page",
        "load_handler": "load_accounts_page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "accounts",
                "data_source": {"type": "managed_resource", "resource_id": "accounts"},
                "columns": [{"key": "account_id"}, {"key": "name", "sortable": True}],
                "crud": {
                    "mode": "handlers",
                    "render": "row_actions",
                    "primary_key": "account_id",
                    "form": {
                        "create_columns": ["name"],
                        "update_columns": ["name"],
                    },
                    "create_handler": "create_account",
                    "update_handler": "update_account",
                    "delete_handler": "delete_account",
                },
            }
        ],
    }

    normalized = normalize_page_schema("accounts", schema)

    assert normalized["children"][0]["crud"] == {
        "mode": "handlers",
        "render": "row_actions",
        "toolbar": {},
        "primary_key": "account_id",
        "form": {
            "create_columns": ["name"],
            "update_columns": ["name"],
        },
        "create_handler": "create_account",
        "update_handler": "update_account",
        "delete_handler": "delete_account",
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
