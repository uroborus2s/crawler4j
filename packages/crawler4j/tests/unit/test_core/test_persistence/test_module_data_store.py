from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _recreate_legacy_module_db_views_table(conn) -> None:
    conn.execute("DROP TABLE module_db_views")
    conn.execute(
        """
        CREATE TABLE module_db_views (
            module_name TEXT NOT NULL,
            view_id TEXT NOT NULL,
            view_kind TEXT NOT NULL CHECK (view_kind IN ('sql_view', 'materialized_view')),
            physical_view_name TEXT NOT NULL,
            source_resource_ids_json TEXT NOT NULL DEFAULT '[]',
            select_sql_template TEXT NOT NULL,
            columns_json TEXT NOT NULL DEFAULT '[]',
            schema_version INTEGER NOT NULL DEFAULT 1,
            cleanup_policy TEXT NOT NULL CHECK (cleanup_policy IN ('drop_view', 'drop_table', 'keep')),
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (module_name, view_id)
        )
        """
    )


def _sync_manifest_data(
    store,
    module_root: Path,
    *,
    module_name: str = "demo_module",
    resources: list[dict[str, object]] | None = None,
    views: list[dict[str, object]] | None = None,
    seeds: list[dict[str, object]] | None = None,
) -> bool:
    from src.core.mms.data_contract import normalize_manifest_data

    (module_root / "data" / "sql" / "views").mkdir(parents=True, exist_ok=True)
    (module_root / "data" / "seeds").mkdir(parents=True, exist_ok=True)

    raw_resources = [dict(item) for item in (resources or [])]
    raw_views = [dict(item) for item in (views or [])]
    raw_seeds = [dict(item) for item in (seeds or [])]

    for view in raw_views:
        view_id = str(view["id"])
        sql_file = str(view.get("sql_file") or f"data/sql/views/{view_id}.sql")
        (module_root / sql_file).write_text(str(view.pop("sql", "")).strip() + "\n", encoding="utf-8")
        view["sql_file"] = sql_file

    for seed in raw_seeds:
        seed_id = str(seed["id"])
        seed_file = str(seed.get("file") or f"data/seeds/{seed_id}.json")
        payload = seed.pop("records", [])
        (module_root / seed_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        seed["file"] = seed_file

    manifest_data = normalize_manifest_data(
        {
            "resources": raw_resources,
            "views": raw_views,
            "seeds": raw_seeds,
        }
    )
    return store.sync_manifest_data(module_name, module_root, manifest_data)


def _declare_managed_dataset(
    store,
    module_root: Path,
    *,
    module_name: str = "demo_module",
    resource_id: str = "accounts",
    record_key_field: str = "id",
    include_status: bool = False,
) -> bool:
    columns = [
        {"name": record_key_field, "type": "text", "required": True},
        {"name": "phone", "type": "text"},
    ]
    if include_status:
        columns.append({"name": "status", "type": "text"})
    return _sync_manifest_data(
        store,
        module_root,
        module_name=module_name,
        resources=[
            {
                "id": resource_id,
                "storage_mode": "managed_dataset",
                "record_key_field": record_key_field,
                "schema": {
                    "version": 1,
                    "columns": columns,
                },
            }
        ],
    )


def _query_records_for_assertion(
    store,
    *,
    module_name: str = "demo_module",
    resource_id: str = "accounts",
    where=None,
    order_by: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    resources = {item["resource_id"]: item for item in store.list_data_resources(module_name)}
    resource = resources[resource_id]
    if order_by is None:
        if resource["storage_mode"] == "managed_dataset":
            order_by = [{"field": "record_index", "direction": "asc"}]
        else:
            order_by = [{"field": resource.get("record_key_field") or "id", "direction": "asc"}]
    rows = store.query_resource_records(
        module_name,
        resource_id,
        select=["*"],
        where=where,
        order_by=order_by,
        limit=2_147_483_647,
        offset=0,
    )
    return [{key: value for key, value in row.items() if key not in {"created_at", "updated_at"}} for row in rows]


def _declare_custom_accounts(
    store,
    module_root: Path,
    *,
    module_name: str = "demo_module",
    resource_id: str = "accounts",
) -> bool:
    return _sync_manifest_data(
        store,
        module_root,
        module_name=module_name,
        resources=[
            {
                "id": resource_id,
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "id", "type": "text", "required": True},
                        {"name": "phone", "type": "text"},
                        {"name": "status", "type": "text"},
                        {"name": "balance", "type": "number"},
                    ],
                },
            }
        ],
    )


def _legacy_db_view_row(*, cleanup_policy: str = "drop_table", view_kind: str = "materialized_view") -> tuple:
    return (
        "demo_module",
        "billing_stats",
        view_kind,
        "demo_module_view_billing_stats",
        json.dumps(["billing_entries"], ensure_ascii=False),
        "SELECT entry_id FROM {{resource:billing_entries}}",
        json.dumps(
            [
                {"name": "entry_id", "type": "text", "nullable": True},
            ],
            ensure_ascii=False,
        ),
        1,
        cleanup_policy,
        100,
        200,
    )


def test_module_data_store_legacy_read_wrappers_are_removed():
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    for method_name in ("get_record", "list_records", "read_resource_records", "query_db_view"):
        assert not hasattr(store, method_name)


def test_module_data_store_reads_and_writes_only_data_db(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    records = [
        {"id": "u1", "phone": "13800138000"},
        {"id": "u2", "phone": "13900139000"},
    ]

    assert store.replace_resource_records("demo_module", "accounts", records) is True
    assert (
        store.write_page_schema(
            "demo_module",
            "dashboard",
            {"type": "Page", "title": "账号管理", "load_handler": "load_dashboard_page", "children": []},
        )
        is True
    )

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13800138000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        },
        {
            "id": "u2",
            "phone": "13900139000",
            "record_index": 1,
            "record_key": "u2",
            "run_status": "不占用",
            "record_status": "",
        },
    ]
    assert store.read_page_schema("demo_module", "dashboard") == {
        "type": "Page",
        "title": "账号管理",
        "load_handler": "load_dashboard_page",
        "children": [],
    }

    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            """
            SELECT record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()
        page_row = conn.execute(
            "SELECT schema_json FROM module_pages WHERE module_name = ? AND page_id = ?",
            ("demo_module", "dashboard"),
        ).fetchone()

    assert [row["record_index"] for row in dataset_rows] == [0, 1]
    assert [json.loads(row["record_json"]) for row in dataset_rows] == records
    assert page_row is not None


def test_module_data_store_rejects_access_to_undeclared_resource(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}])

    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        store.query_resource_records("demo_module", "accounts")


def test_module_data_store_describes_managed_dataset_write_contract(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "accounts",
                "storage_mode": "managed_dataset",
                "record_key_field": "phone",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "account_id", "type": "int"},
                        {"name": "phone", "type": "text", "required": True},
                        {"name": "status_reason", "type": "text"},
                    ],
                },
                "indexes": {"by_account_id": ["account_id"]},
                "cleanup_policy": "delete_rows",
            }
        ],
    )

    descriptor = store.describe_data_source("demo_module", "accounts")

    assert descriptor["kind"] == "data_table"
    assert descriptor["source_kind"] == "snapshot"
    assert descriptor["storage_mode"] == "managed_dataset"
    assert descriptor["record_key_field"] == "phone"
    assert descriptor["columns"] == [
        {
            "name": "account_id",
            "type": "int",
            "nullable": True,
            "required": False,
            "writable": True,
        },
        {
            "name": "phone",
            "type": "text",
            "nullable": False,
            "required": True,
            "writable": True,
        },
        {
            "name": "status_reason",
            "type": "text",
            "nullable": True,
            "required": False,
            "writable": True,
        },
    ]
    assert descriptor["system_fields"] == [
        {"name": "record_index", "type": "int", "writable": False, "generated": True},
        {"name": "record_key", "type": "text", "writable": False, "generated": True},
        {"name": "run_status", "type": "text", "writable": True, "generated": False},
        {"name": "record_status", "type": "text", "writable": True, "generated": False},
        {"name": "created_at", "type": "int", "writable": False, "generated": True},
        {"name": "updated_at", "type": "int", "writable": False, "generated": True},
    ]
    assert descriptor["writable_fields"] == [
        "account_id",
        "phone",
        "status_reason",
        "run_status",
        "record_status",
    ]
    assert descriptor["required_fields"] == ["phone"]
    assert descriptor["read_only_fields"] == ["record_index", "record_key", "created_at", "updated_at"]
    assert descriptor["indexes"] == {"by_account_id": ["account_id"]}


def test_module_data_store_describes_custom_table_auto_increment_write_contract(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "ctrip_account_daily_audits",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "id", "type": "int", "auto_increment": True},
                        {"name": "ctrip_account_id", "type": "int"},
                        {"name": "ctrip_account", "type": "text", "required": True},
                        {"name": "audit_date", "type": "text", "required": True},
                    ],
                },
                "indexes": {
                    "by_ctrip_account": ["ctrip_account"],
                    "by_audit_date": ["audit_date"],
                },
                "cleanup_policy": "drop_table",
            }
        ],
    )

    descriptor = store.describe_data_source("demo_module", "ctrip_account_daily_audits")

    assert descriptor["kind"] == "data_table"
    assert descriptor["source_kind"] == "relation"
    assert descriptor["storage_mode"] == "custom_table"
    assert descriptor["record_key_field"] == "id"
    assert descriptor["columns"][0] == {
        "name": "id",
        "type": "int",
        "nullable": False,
        "required": False,
        "writable": False,
        "auto_increment": True,
    }
    assert descriptor["writable_fields"] == ["ctrip_account_id", "ctrip_account", "audit_date"]
    assert descriptor["required_fields"] == ["ctrip_account", "audit_date"]
    assert descriptor["read_only_fields"] == ["id", "created_at", "updated_at"]
    assert descriptor["system_fields"] == [
        {"name": "created_at", "type": "int", "writable": False, "generated": True},
        {"name": "updated_at", "type": "int", "writable": False, "generated": True},
    ]
    assert descriptor["indexes"] == {
        "by_ctrip_account": ["ctrip_account"],
        "by_audit_date": ["audit_date"],
    }


def test_module_data_store_describes_custom_table_manual_key_as_required_writable(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_custom_accounts(store, temp_data_dir)

    descriptor = store.describe_data_source("demo_module", "accounts")

    assert descriptor["columns"][0] == {
        "name": "id",
        "type": "text",
        "nullable": False,
        "required": True,
        "writable": True,
    }
    assert descriptor["writable_fields"] == ["id", "phone", "status", "balance"]
    assert descriptor["required_fields"] == ["id"]
    assert descriptor["read_only_fields"] == ["created_at", "updated_at"]


def test_module_data_store_executes_managed_dataset_query_plan(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    store.replace_resource_records(
        "demo_module",
        "accounts",
        [
            {"id": "u1", "phone": "13800138000", "status": "ready"},
            {"id": "u2", "phone": "13900139000", "status": "blocked"},
        ],
    )
    descriptor = {
        "source": "accounts",
        "source_kind": "snapshot",
        "columns": [
            {"name": "id", "type": "text"},
            {"name": "phone", "type": "text"},
            {"name": "status", "type": "text"},
        ],
        "joins": [],
    }

    rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "select": [{"kind": "column", "field": "phone"}],
            "where": ["status", "=", "ready"],
            "order_by": [{"field": "phone", "direction": "desc"}],
            "limit": 10,
            "offset": 0,
        },
        describe_source=lambda source: descriptor,
    )

    assert rows == [{"phone": "13800138000"}]


def test_module_data_store_executes_managed_dataset_count_plan_after_where(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    store.replace_resource_records(
        "demo_module",
        "accounts",
        [
            {"id": "u1", "phone": "13800138000", "status": "ready"},
            {"id": "u2", "phone": "13900139000", "status": "ready", "run_status": "占用中"},
            {"id": "u3", "phone": "13700137000", "status": "blocked", "run_status": "占用中"},
        ],
    )
    descriptor = {
        "source": "accounts",
        "source_kind": "snapshot",
        "columns": [
            {"name": "id", "type": "text"},
            {"name": "phone", "type": "text"},
            {"name": "status", "type": "text"},
        ],
        "joins": [],
    }

    rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "total"}],
            "where": ["status", "=", "ready"],
            "order_by": [{"field": "phone", "direction": "desc"}],
            "limit": 1,
            "offset": 1,
        },
        describe_source=lambda source: descriptor,
    )
    occupied_rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "occupied_total"}],
            "where": ["run_status", "=", "占用中"],
        },
        describe_source=lambda source: descriptor,
    )
    empty_rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "total"}],
            "where": ["status", "=", "missing"],
        },
        describe_source=lambda source: descriptor,
    )

    assert rows == [{"total": 2}]
    assert occupied_rows == [{"occupied_total": 2}]
    assert empty_rows == [{"total": 0}]


def test_module_data_store_rejects_managed_dataset_non_count_aggregate_plan(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    descriptor = {
        "source": "accounts",
        "source_kind": "snapshot",
        "columns": [
            {"name": "id", "type": "text"},
            {"name": "phone", "type": "text"},
            {"name": "status", "type": "text"},
        ],
        "joins": [],
    }

    with pytest.raises(ValueError, match="managed_dataset\\(snapshot\\).*only supports count"):
        store.execute_query_plan(
            "demo_module",
            {
                "kind": "select",
                "base": {"source": "accounts"},
                "select": [
                    {"kind": "column", "field": "status"},
                    {"kind": "aggregate", "func": "count", "field": "*", "alias": "total"},
                ],
            },
            describe_source=lambda source: descriptor,
        )

    with pytest.raises(ValueError, match="managed_dataset\\(snapshot\\).*group_by is not supported"):
        store.execute_query_plan(
            "demo_module",
            {
                "kind": "select",
                "base": {"source": "accounts"},
                "select": [{"kind": "aggregate", "func": "count", "field": "*", "alias": "total"}],
                "group_by": ["status"],
            },
            describe_source=lambda source: descriptor,
        )

    with pytest.raises(ValueError, match="managed_dataset\\(snapshot\\).*only supports count"):
        store.execute_query_plan(
            "demo_module",
            {
                "kind": "select",
                "base": {"source": "accounts"},
                "select": [{"kind": "aggregate", "func": "sum", "field": "phone", "alias": "total"}],
            },
            describe_source=lambda source: descriptor,
        )


def test_module_data_store_executes_managed_dataset_physical_and_json_filters(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    store.replace_resource_records(
        "demo_module",
        "accounts",
        [
            {"id": "u1", "phone": "13800138000", "status": "ready"},
            {"id": "u2", "phone": "13900139000", "status": "ready", "run_status": "占用中"},
            {"id": "u3", "phone": "13700137000", "status": "blocked", "run_status": "占用中"},
        ],
    )
    descriptor = {
        "source": "accounts",
        "source_kind": "snapshot",
        "columns": [
            {"name": "id", "type": "text"},
            {"name": "phone", "type": "text"},
            {"name": "status", "type": "text"},
        ],
        "joins": [],
    }

    rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "accounts"},
            "select": [
                {"kind": "column", "field": "record_index"},
                {"kind": "column", "field": "record_key"},
                {"kind": "column", "field": "status"},
                {"kind": "column", "field": "run_status"},
            ],
            "where": [
                "and",
                ["record_key", "in", ["u1", "u2"]],
                ["or", ["status", "=", "ready"], ["phone", "=", "000"]],
            ],
            "order_by": [{"field": "phone", "direction": "desc"}],
            "limit": 10,
            "offset": 0,
        },
        describe_source=lambda source: descriptor,
    )

    assert rows == [
        {"record_index": 1, "record_key": "u2", "status": "ready", "run_status": "占用中"},
        {"record_index": 0, "record_key": "u1", "status": "ready", "run_status": "不占用"},
    ]


def test_module_data_store_queries_resource_records_with_managed_dataset_json_and_physical_fields(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    store.replace_resource_records(
        "demo_module",
        "accounts",
        [
            {"id": "u1", "phone": "13800138000", "status": "ready"},
            {"id": "u2", "phone": "13900139000", "status": "blocked", "run_status": "占用中"},
        ],
    )

    assert store.query_resource_records(
        "demo_module",
        "accounts",
        select=["record_key", "id", "status", "run_status"],
        where=["status", "=", "ready"],
        order_by=[{"field": "phone", "direction": "desc"}],
        limit=10,
        offset=0,
    ) == [{"record_key": "u1", "id": "u1", "status": "ready", "run_status": "不占用"}]

    wildcard_rows = store.query_resource_records(
        "demo_module",
        "accounts",
        select=["*"],
        order_by=[{"field": "record_index", "direction": "asc"}],
        limit=1,
        offset=0,
    )
    assert wildcard_rows == [
        {
            "id": "u1",
            "phone": "13800138000",
            "status": "ready",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
            "created_at": wildcard_rows[0]["created_at"],
            "updated_at": wildcard_rows[0]["updated_at"],
        }
    ]


def test_module_data_store_query_resource_records_keeps_json_field_filter_and_sort(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir, include_status=True)
    store.replace_resource_records(
        "demo_module",
        "accounts",
        [
            {"id": "u1", "phone": "13800138000", "status": "ready"},
            {"id": "u2", "phone": "13900139000", "status": "blocked"},
            {"id": "u3", "phone": "13700137000", "status": "ready"},
        ],
    )

    assert _query_records_for_assertion(
        store,
        where={"status": "ready"},
        order_by=[{"field": "phone", "direction": "asc"}],
    ) == [
        {
            "id": "u3",
            "phone": "13700137000",
            "status": "ready",
            "record_index": 2,
            "record_key": "u3",
            "run_status": "不占用",
            "record_status": "",
        },
        {
            "id": "u1",
            "phone": "13800138000",
            "status": "ready",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        },
    ]


def test_module_data_store_rejects_managed_dataset_join_plan(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    with pytest.raises(ValueError, match="managed_dataset\\(snapshot\\).*join"):
        store.execute_query_plan(
            "demo_module",
            {
                "kind": "select",
                "base": {"source": "accounts"},
                "joins": [{"target": "billing_entries", "type": "inner", "on": []}],
            },
            describe_source=lambda source: {"source": source, "source_kind": "snapshot", "columns": [], "joins": []},
        )


def test_module_data_store_executes_custom_table_join_aggregate_plan(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "billing_entries",
                "storage_mode": "custom_table",
                "record_key_field": "entry_id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "entry_id", "type": "text", "required": True},
                        {"name": "account_id", "type": "text", "required": True},
                        {"name": "amount", "type": "number"},
                        {"name": "status", "type": "text"},
                    ],
                },
                "joins": [
                    {
                        "target": "account_profiles",
                        "on": {"account_id": "account_id"},
                    }
                ],
            },
            {
                "id": "account_profiles",
                "storage_mode": "custom_table",
                "record_key_field": "account_id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "account_id", "type": "text", "required": True},
                        {"name": "owner_name", "type": "text"},
                    ],
                },
            },
        ],
    )
    store.replace_resource_records(
        "demo_module",
        "billing_entries",
        [
            {"entry_id": "e1", "account_id": "A001", "amount": 10.5, "status": "done"},
            {"entry_id": "e2", "account_id": "A001", "amount": 20.0, "status": "done"},
            {"entry_id": "e3", "account_id": "A002", "amount": 1.0, "status": "pending"},
        ],
    )
    store.replace_resource_records(
        "demo_module",
        "account_profiles",
        [
            {"account_id": "A001", "owner_name": "alice"},
            {"account_id": "A002", "owner_name": "bob"},
        ],
    )
    descriptors = {
        "billing_entries": {
            "source": "billing_entries",
            "source_kind": "relation",
            "columns": [
                {"name": "entry_id", "type": "text"},
                {"name": "account_id", "type": "text"},
                {"name": "amount", "type": "number"},
                {"name": "status", "type": "text"},
            ],
            "joins": [
                {
                    "target": "account_profiles",
                    "types": ["inner"],
                    "on": [{"left": "account_id", "right": "account_id"}],
                }
            ],
        },
        "account_profiles": {
            "source": "account_profiles",
            "source_kind": "relation",
            "columns": [
                {"name": "account_id", "type": "text"},
                {"name": "owner_name", "type": "text"},
            ],
            "joins": [],
        },
    }

    rows = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "billing_entries"},
            "joins": [
                {
                    "target": "account_profiles",
                    "type": "inner",
                    "on": [{"left": "account_id", "right": "account_id"}],
                }
            ],
            "where": ["and", ["status", "=", "done"], ["or", ["account_id", "=", "A001"], ["account_id", "=", "A002"]]],
            "group_by": ["account_id"],
            "select": [
                {"kind": "aggregate", "func": "sum", "field": "amount", "alias": "total_amount"},
                {"kind": "aggregate", "func": "count", "field": "*", "alias": "total_count"},
            ],
            "order_by": [{"field": "total_amount", "direction": "desc"}],
            "limit": 10,
            "offset": 0,
        },
        describe_source=lambda source: descriptors[source],
    )

    assert rows == [{"account_id": "A001", "total_amount": 30.5, "total_count": 2}]


def test_init_database_creates_module_data_resources_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection

    with get_connection(DATA_DB) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(module_data_resources)").fetchall()}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(module_data_resources)").fetchall()}

    assert {
        "module_name",
        "resource_id",
        "storage_mode",
        "logical_name",
        "physical_table_name",
        "record_key_field",
        "schema_version",
        "schema_json",
        "indexes_json",
        "cleanup_policy",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert "idx_module_data_resources_module" in indexes
    assert "idx_module_data_resources_module_mode" in indexes


def test_init_database_creates_module_db_views_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection

    with get_connection(DATA_DB) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(module_db_views)").fetchall()}
        indexes = {row["name"] for row in conn.execute("PRAGMA index_list(module_db_views)").fetchall()}
        create_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'module_db_views'
            """
        ).fetchone()["sql"]

    assert {
        "module_name",
        "view_id",
        "view_kind",
        "physical_view_name",
        "source_resource_ids_json",
        "select_sql_template",
        "columns_json",
        "schema_version",
        "cleanup_policy",
        "created_at",
        "updated_at",
    }.issubset(columns)
    assert "idx_module_db_views_module" in indexes
    assert "materialized_view" not in create_sql
    assert "drop_table" not in create_sql
    assert "'sql_view'" in create_sql
    assert "'drop_view'" in create_sql
    assert "'keep'" in create_sql


def test_init_database_does_not_create_module_dataset_manifests_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection

    with get_connection(DATA_DB) as conn:
        table_row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'module_dataset_manifests'
            """
        ).fetchone()

    assert table_row is None


def test_init_database_rejects_legacy_module_db_view_schema(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database

    with get_connection(DATA_DB) as conn:
        _recreate_legacy_module_db_views_table(conn)
        conn.execute(
            """
            INSERT INTO module_db_views (
                module_name,
                view_id,
                view_kind,
                physical_view_name,
                source_resource_ids_json,
                select_sql_template,
                columns_json,
                schema_version,
                cleanup_policy,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _legacy_db_view_row(),
        )

    with pytest.raises(RuntimeError, match="0.4.0 module_db_views schema"):
        init_database()

    with get_connection(DATA_DB) as conn:
        create_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'module_db_views'
            """
        ).fetchone()["sql"]

    assert "materialized_view" in create_sql
    assert "drop_table" in create_sql


def test_init_database_rejects_v2_module_dataset_schema(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database

    with get_connection(DATA_DB) as conn:
        conn.execute("DROP TABLE module_datasets")
        conn.execute(
            """
            CREATE TABLE module_datasets (
                module_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                record_index INTEGER NOT NULL,
                record_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, dataset_name, record_index)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO module_datasets (
                module_name,
                dataset_name,
                record_index,
                record_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("demo_module", "accounts", 0, json.dumps({"id": "legacy"}, ensure_ascii=False), 100, 200),
        )

    with pytest.raises(RuntimeError, match="0.4.0 module_datasets schema"):
        init_database()

    with get_connection(DATA_DB) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(module_datasets)").fetchall()}
        row = conn.execute(
            """
            SELECT record_index, record_json, created_at, updated_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()

    assert "record_key" not in columns
    assert row is not None
    assert row["record_index"] == 0
    assert json.loads(row["record_json"]) == {"id": "legacy"}
    assert row["created_at"] == 100
    assert row["updated_at"] == 200


def test_init_database_rejects_legacy_module_dataset_schema(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database

    with get_connection(DATA_DB) as conn:
        conn.execute("DROP TABLE module_datasets")
        conn.execute(
            """
            CREATE TABLE module_datasets (
                module_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                records_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, dataset_name)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO module_datasets (module_name, dataset_name, records_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("demo_module", "legacy_accounts", json.dumps([{"id": "legacy"}], ensure_ascii=False), 100, 200),
        )

    with pytest.raises(RuntimeError, match="0.4.0 module_datasets schema"):
        init_database()

    with get_connection(DATA_DB) as conn:
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(module_datasets)").fetchall()}
        legacy_row = conn.execute(
            """
            SELECT records_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "legacy_accounts"),
        ).fetchone()

    assert "records_json" in existing_columns
    assert legacy_row is not None
    assert legacy_row["records_json"] == json.dumps([{"id": "legacy"}], ensure_ascii=False)


def test_init_database_rejects_hybrid_module_dataset_schema_with_legacy_column(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database

    with get_connection(DATA_DB) as conn:
        conn.execute("DROP TABLE module_datasets")
        conn.execute(
            """
            CREATE TABLE module_datasets (
                module_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                record_index INTEGER NOT NULL,
                record_json TEXT NOT NULL,
                records_json TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, dataset_name, record_index)
            )
            """
        )

    with pytest.raises(RuntimeError, match="0.4.0 module_datasets schema"):
        init_database()


def test_module_data_store_declares_db_view_and_queries_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "billing_entries",
                "storage_mode": "custom_table",
                "record_key_field": "entry_id",
                "schema": {
                    "columns": [
                        {"name": "entry_id", "type": "text", "required": True},
                        {"name": "execution_date", "type": "text", "required": True},
                        {"name": "labor_account", "type": "text", "required": True},
                        {"name": "bill_batch", "type": "text", "required": True},
                        {"name": "amount", "type": "number", "required": True},
                    ]
                },
                "indexes": {
                    "execution_account_batch": ["execution_date", "labor_account", "bill_batch"],
                },
            }
        ],
        views=[
            {
                "id": "labor_billing_stats",
                "source_resource_ids": ["billing_entries"],
                "sql": """
SELECT
  execution_date,
  labor_account,
  bill_batch,
  COUNT(*) AS total_count,
  SUM(amount) AS total_amount
FROM {{resource:billing_entries}}
GROUP BY execution_date, labor_account, bill_batch
""",
                "columns": [
                    {"name": "execution_date", "type": "text"},
                    {"name": "labor_account", "type": "text"},
                    {"name": "bill_batch", "type": "text"},
                    {"name": "total_count", "type": "int"},
                    {"name": "total_amount", "type": "number"},
                ],
            }
        ],
    )
    store.replace_resource_records(
        "demo_module",
        "billing_entries",
        [
            {
                "entry_id": "e-1",
                "execution_date": "2026-04-23",
                "labor_account": "acct-001",
                "bill_batch": "batch-001",
                "amount": 3.0,
            },
            {
                "entry_id": "e-2",
                "execution_date": "2026-04-23",
                "labor_account": "acct-001",
                "bill_batch": "batch-001",
                "amount": 2.5,
            },
            {
                "entry_id": "e-3",
                "execution_date": "2026-04-23",
                "labor_account": "acct-002",
                "bill_batch": "batch-001",
                "amount": 1.5,
            },
        ],
    )

    declared = store.list_db_views("demo_module")[0]

    assert declared["physical_view_name"] == "demo_module_view_labor_billing_stats"
    assert declared["view_kind"] == "sql_view"
    assert declared["source_resource_ids"] == ["billing_entries"]

    queried = store.execute_query_plan(
        "demo_module",
        {
            "kind": "select",
            "base": {"source": "labor_billing_stats"},
            "select": [{"kind": "column", "field": "*"}],
            "where": [
                ["execution_date", "=", "2026-04-23"],
                ["bill_batch", "=", "batch-001"],
            ],
            "order_by": [{"field": "total_count", "direction": "desc"}],
            "limit": 10,
            "offset": 0,
        },
        describe_source=lambda source: store.describe_data_source("demo_module", source),
    )

    assert queried == [
        {
            "execution_date": "2026-04-23",
            "labor_account": "acct-001",
            "bill_batch": "batch-001",
            "total_count": 2,
            "total_amount": 5.5,
        },
        {
            "execution_date": "2026-04-23",
            "labor_account": "acct-002",
            "bill_batch": "batch-001",
            "total_count": 1,
            "total_amount": 1.5,
        },
    ]

    with get_connection(DATA_DB) as conn:
        manifest_row = conn.execute(
            """
            SELECT physical_view_name, source_resource_ids_json, columns_json
            FROM module_db_views
            WHERE module_name = ? AND view_id = ?
            """,
            ("demo_module", "labor_billing_stats"),
        ).fetchone()
        sqlite_view = conn.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type = 'view' AND name = ?
            """,
            ("demo_module_view_labor_billing_stats",),
        ).fetchone()

    assert manifest_row is not None
    assert json.loads(manifest_row["source_resource_ids_json"]) == ["billing_entries"]
    assert json.loads(manifest_row["columns_json"])[-1]["name"] == "total_amount"
    assert dict(sqlite_view) == {"name": "demo_module_view_labor_billing_stats", "type": "view"}


def test_module_data_store_rejects_db_view_over_managed_dataset(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    with pytest.raises(ValueError, match="custom_table"):
        _sync_manifest_data(
            store,
            temp_data_dir,
            resources=[
                {
                    "id": "accounts",
                    "storage_mode": "managed_dataset",
                    "schema": {
                        "version": 1,
                        "columns": [
                            {"name": "id", "type": "text", "required": True},
                            {"name": "phone", "type": "text"},
                        ],
                    },
                }
            ],
            views=[
                {
                    "id": "account_stats",
                    "source_resource_ids": ["accounts"],
                    "sql": """
SELECT phone
FROM {{resource:accounts}}
""",
                    "columns": [
                        {"name": "phone", "type": "text"},
                    ],
                }
            ],
        )


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"view_kind": "materialized_view"}, r"view_kind 只支持 sql_view"),
        ({"cleanup_policy": "drop_table"}, r"cleanup_policy 只支持 drop_view/keep"),
    ],
)
def test_module_data_store_rejects_legacy_db_view_v1_options(temp_data_dir, kwargs, match):
    from src.core.mms.data_contract import normalize_manifest_data

    with pytest.raises(ValueError, match=match):
        normalize_manifest_data(
            {
                "resources": [
                    {
                        "id": "billing_entries",
                        "storage_mode": "custom_table",
                        "record_key_field": "entry_id",
                        "schema": {"columns": [{"name": "entry_id", "type": "text", "required": True}]},
                    }
                ],
                "views": [
                    {
                        "id": "billing_stats",
                        "source_resource_ids": ["billing_entries"],
                        "sql_file": "data/sql/views/billing_stats.sql",
                        "columns": [
                            {"name": "entry_id", "type": "text"},
                        ],
                        **kwargs,
                    }
                ],
                "seeds": [],
            }
        )


@pytest.mark.parametrize("removed_key", ["filterable", "sortable"])
def test_module_data_store_rejects_removed_column_query_flags(temp_data_dir, removed_key):
    from src.core.mms.data_contract import normalize_manifest_data

    with pytest.raises(ValueError, match=f"不支持的字段: {removed_key}"):
        normalize_manifest_data(
            {
                "resources": [
                    {
                        "id": "billing_entries",
                        "storage_mode": "custom_table",
                        "record_key_field": "entry_id",
                        "schema": {"columns": [{"name": "entry_id", "type": "text", "required": True}]},
                    }
                ],
                "views": [
                    {
                        "id": "billing_stats",
                        "source_resource_ids": ["billing_entries"],
                        "sql_file": "data/sql/views/billing_stats.sql",
                        "columns": [{"name": "entry_id", "type": "text", removed_key: True}],
                    }
                ],
            }
        )


def test_module_data_store_rejects_db_view_reading_undeclared_table(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    with pytest.raises(ValueError, match="只能读取已声明的数据资源"):
        _sync_manifest_data(
            store,
            temp_data_dir,
            resources=[
                {
                    "id": "accounts",
                    "storage_mode": "custom_table",
                    "record_key_field": "id",
                    "schema": {"columns": [{"name": "id", "type": "text", "required": True}]},
                }
            ],
            views=[
                {
                    "id": "account_stats",
                    "source_resource_ids": ["accounts"],
                    "sql": "SELECT id FROM {{resource:accounts}}, module_datasets",
                    "columns": [{"name": "id", "type": "text"}],
                }
            ],
        )


def test_data_contract_rejects_data_view_over_managed_dataset(temp_data_dir):
    from src.core.mms.data_contract import normalize_manifest_data

    with pytest.raises(ValueError, match="只允许引用 custom_table"):
        normalize_manifest_data(
            {
                "resources": [
                    {
                        "id": "accounts",
                        "storage_mode": "managed_dataset",
                        "record_key_field": "id",
                        "schema": {"columns": [{"name": "id", "type": "text", "required": True}]},
                    }
                ],
                "views": [
                    {
                        "id": "account_stats",
                        "source_resource_ids": ["accounts"],
                        "sql": "SELECT id FROM {{resource:accounts}}",
                        "columns": [{"name": "id", "type": "text"}],
                    }
                ],
            }
        )


def test_data_contract_rejects_sibling_prefix_sql_and_seed_paths(temp_data_dir):
    from src.core.mms.data_contract import load_sql_file, validate_seed_file

    module_root = temp_data_dir / "demo"
    sibling = temp_data_dir / "demo_evil"
    (module_root / "data" / "sql" / "views").mkdir(parents=True)
    sibling.mkdir()
    (sibling / "query.sql").write_text("SELECT 1\n", encoding="utf-8")
    (sibling / "seed.json").write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="路径越界"):
        load_sql_file(
            module_root,
            "data/sql/views/../../../../demo_evil/query.sql",
            expected_prefix="data/sql/views/",
        )
    with pytest.raises(ValueError, match="路径越界"):
        validate_seed_file(module_root, "data/seeds/../../../demo_evil/seed.json")


def test_module_data_store_clear_module_data_drops_registered_db_views(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "billing_entries",
                "storage_mode": "custom_table",
                "record_key_field": "entry_id",
                "schema": {
                    "columns": [
                        {"name": "entry_id", "type": "text", "required": True},
                        {"name": "execution_date", "type": "text", "required": True},
                    ]
                },
            }
        ],
        views=[
            {
                "id": "billing_stats",
                "source_resource_ids": ["billing_entries"],
                "sql": """
SELECT execution_date
FROM {{resource:billing_entries}}
""",
                "columns": [
                    {"name": "execution_date", "type": "text"},
                ],
            }
        ],
    )
    store.replace_resource_records(
        "demo_module",
        "billing_entries",
        [{"entry_id": "e-1", "execution_date": "2026-04-23"}],
    )

    assert store.clear_module_data("demo_module") is True
    assert store.list_db_views("demo_module") == []

    with get_connection(DATA_DB) as conn:
        sqlite_view = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'view' AND name = ?
            """,
            ("demo_module_view_billing_stats",),
        ).fetchone()

    assert sqlite_view is None


def test_module_data_store_rewrite_preserves_created_at_and_reindexes_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    with patch("src.core.persistence.module_data_store.time.time", side_effect=[100, 200]):
        assert (
            store.replace_resource_records(
                "demo_module",
                "accounts",
                [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}],
            )
            is True
        )
        assert store.replace_resource_records("demo_module", "accounts", [{"id": "u9"}]) is True

    assert _query_records_for_assertion(store) == [
        {
            "id": "u9",
            "phone": None,
            "record_index": 0,
            "record_key": "u9",
            "run_status": "不占用",
            "record_status": "",
        },
    ]

    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            """
            SELECT record_index, record_json, created_at, updated_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert len(dataset_rows) == 1
    assert dataset_rows[0]["record_index"] == 0
    assert json.loads(dataset_rows[0]["record_json"]) == {"id": "u9"}
    assert dataset_rows[0]["created_at"] == 100
    assert dataset_rows[0]["updated_at"] == 200


def test_module_data_store_roundtrips_status_columns_without_record_json_leakage(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    records = [
        {
            "id": "account:1",
            "run_status": "queued",
            "record_status": "active",
            "phone": "13800138000",
        },
        {
            "id": "account:2",
            "run_status": "done",
            "record_status": "blocked",
            "phone": "13900139000",
        },
    ]

    assert store.replace_resource_records("demo_module", "accounts", records) is True

    assert _query_records_for_assertion(store) == [
        {
            "id": "account:1",
            "phone": "13800138000",
            "record_index": 0,
            "record_key": "account:1",
            "run_status": "queued",
            "record_status": "active",
        },
        {
            "id": "account:2",
            "phone": "13900139000",
            "record_index": 1,
            "record_key": "account:2",
            "run_status": "done",
            "record_status": "blocked",
        },
    ]
    with get_connection(DATA_DB) as conn:
        rows = conn.execute(
            """
            SELECT record_key, run_status, record_status, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert [
        {
            "record_key": row["record_key"],
            "run_status": row["run_status"],
            "record_status": row["record_status"],
            "record_json": json.loads(row["record_json"]),
        }
        for row in rows
    ] == [
        {
            "record_key": "account:1",
            "run_status": "queued",
            "record_status": "active",
            "record_json": {"id": "account:1", "phone": "13800138000"},
        },
        {
            "record_key": "account:2",
            "run_status": "done",
            "record_status": "blocked",
            "record_json": {"id": "account:2", "phone": "13900139000"},
        },
    ]


@pytest.mark.parametrize("field_name", ["record_key", "record_index", "created_at", "updated_at"])
def test_module_data_store_ignores_managed_dataset_generated_host_fields_on_replace_and_upsert(
    temp_data_dir,
    field_name,
):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    assert (
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13800138000", field_name: "host-owned"}],
        )
        is True
    )
    assert (
        store.upsert_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13900139000", field_name: "host-owned"}],
        )
        is True
    )

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13900139000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        }
    ]
    with get_connection(DATA_DB) as conn:
        row = conn.execute(
            """
            SELECT record_key, record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()
    assert row is not None
    assert row["record_key"] == "u1"
    assert row["record_index"] == 0
    assert json.loads(row["record_json"]) == {"id": "u1", "phone": "13900139000"}


def test_module_data_store_write_empty_dataset_clears_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    with patch("src.core.persistence.module_data_store.time.time", side_effect=[100, 200]):
        assert store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}]) is True
        assert store.replace_resource_records("demo_module", "accounts", []) is True

    assert _query_records_for_assertion(store) == []

    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            """
            SELECT record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert dataset_rows == []


def test_module_data_store_replace_declared_ui_replaces_stale_pages(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    store.write_page_schema(
        "demo_module",
        "legacy_page",
        {"type": "Page", "title": "旧页面", "load_handler": "load_legacy_page", "children": []},
    )

    assert store.replace_declared_ui(
        "demo_module",
        page_schemas={
            "dashboard": {
                "type": "Page",
                "title": "新页面",
                "load_handler": "load_dashboard_page",
                "children": [],
            }
        },
    )

    assert store.read_page_schema("demo_module", "legacy_page") == {}
    assert store.read_page_schema("demo_module", "dashboard") == {
        "type": "Page",
        "title": "新页面",
        "load_handler": "load_dashboard_page",
        "children": [],
    }


def test_module_data_store_rejects_invalid_write_dataset_without_clobbering_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    assert store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}]) is True

    with pytest.raises(ValueError, match=r"records\[1\]"):
        store.replace_resource_records("demo_module", "accounts", [{"id": "u2"}, "bad"])

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": None,
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        }
    ]

    with get_connection(DATA_DB) as conn:
        rows = conn.execute(
            """
            SELECT record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert len(rows) == 1
    assert rows[0]["record_index"] == 0
    assert json.loads(rows[0]["record_json"]) == {"id": "u1"}


def test_module_data_store_rejects_managed_dataset_schema_extra_fields_without_clobbering_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    assert (
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13800138000"}],
        )
        is True
    )

    with pytest.raises(ValueError, match="fields outside schema.*phone_masked"):
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13800138000", "phone_masked": "138****8000"}],
        )

    with pytest.raises(ValueError, match="fields outside schema.*phone_masked"):
        store.upsert_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u2", "phone": "13900139000", "phone_masked": "139****9000"}],
        )

    with pytest.raises(ValueError, match="fields outside schema.*phone_masked"):
        store.update_resource_records(
            "demo_module",
            "accounts",
            {"phone_masked": "138****8000"},
            where=["id", "=", "u1"],
        )

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13800138000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        }
    ]

    with get_connection(DATA_DB) as conn:
        rows = conn.execute(
            """
            SELECT record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert [json.loads(row["record_json"]) for row in rows] == [
        {"id": "u1", "phone": "13800138000"},
    ]


def test_module_data_store_does_not_implicit_record_key_field_into_managed_schema(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    assert (
        store.sync_manifest_data(
            "demo_module",
            temp_data_dir,
            {
                "resources": [
                    {
                        "resource_id": "accounts",
                        "storage_mode": "managed_dataset",
                        "record_key_field": "id",
                        "schema": {"version": 1, "columns": [{"name": "phone", "type": "text"}]},
                        "indexes": {},
                        "cleanup_policy": "delete_rows",
                    }
                ],
                "views": [],
                "seeds": [],
            },
        )
        is True
    )

    descriptor = store.describe_data_source("demo_module", "accounts")
    assert "id" not in {column["name"] for column in descriptor["columns"]}

    with pytest.raises(ValueError, match="fields outside schema.*id"):
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13800138000"}],
        )

    assert (
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"record_key": "u1", "phone": "13800138000"}],
        )
        is True
    )

    descriptor = store.describe_data_source("demo_module", "accounts")
    assert "id" not in {column["name"] for column in descriptor["columns"]}
    assert store.query_resource_records("demo_module", "accounts", select=["record_key", "phone"]) == [
        {"record_key": "u1", "phone": "13800138000"}
    ]
    with pytest.raises(ValueError, match="query select field not found: id"):
        store.query_resource_records("demo_module", "accounts", select=["id"])

    with get_connection(DATA_DB) as conn:
        row = conn.execute(
            """
            SELECT record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()
    assert json.loads(row["record_json"]) == {"phone": "13800138000"}


def test_module_data_store_ignores_historical_undeclared_json_fields_in_managed_dataset_queries(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    assert (
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [{"id": "u1", "phone": "13800138000"}],
        )
        is True
    )

    with get_connection(DATA_DB) as conn:
        conn.execute(
            """
            UPDATE module_datasets
            SET record_json = ?
            WHERE module_name = ? AND dataset_name = ? AND record_index = 0
            """,
            (
                json.dumps({"id": "u1", "phone": "13800138000", "phone_masked": "138****8000"}),
                "demo_module",
                "accounts",
            ),
        )

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13800138000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "不占用",
            "record_status": "",
        }
    ]

    with pytest.raises(ValueError, match="query select field not found: phone_masked"):
        store.query_resource_records("demo_module", "accounts", select=["phone_masked"])
    with pytest.raises(ValueError, match="query filter field not found: phone_masked"):
        store.query_resource_records("demo_module", "accounts", where=["phone_masked", "=", "138****8000"])
    with pytest.raises(ValueError, match="query sort field not found: phone_masked"):
        store.query_resource_records(
            "demo_module",
            "accounts",
            select=["id"],
            order_by=[{"field": "phone_masked", "direction": "asc"}],
        )

    assert (
        store.update_resource_records(
            "demo_module",
            "accounts",
            {"phone": "13800138001"},
            where=["id", "=", "u1"],
        )
        == 1
    )
    with get_connection(DATA_DB) as conn:
        row = conn.execute(
            """
            SELECT record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ? AND record_index = 0
            """,
            ("demo_module", "accounts"),
        ).fetchone()
    assert json.loads(row["record_json"]) == {"id": "u1", "phone": "13800138001"}


def test_module_data_store_creates_and_routes_custom_table_resources(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "accounts",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {
                    "columns": [
                        {"key": "id", "type": "text"},
                        {"key": "phone", "type": "text"},
                        {"key": "status", "type": "text", "nullable": True},
                    ]
                },
                "cleanup_policy": "drop_table",
            }
        ],
    )
    assert store.list_data_resources("demo_module")[0] == {
        "module_name": "demo_module",
        "resource_id": "accounts",
        "storage_mode": "custom_table",
        "logical_name": "accounts",
        "physical_table_name": "demo_module_accounts",
        "record_key_field": "id",
        "schema_version": 1,
        "schema": {
            "version": 1,
            "columns": [
                {"name": "id", "type": "text", "nullable": False},
                {"name": "phone", "type": "text", "nullable": True},
                {"name": "status", "type": "text", "nullable": True},
            ],
        },
        "indexes": {},
        "cleanup_policy": "drop_table",
    }

    records = [
        {
            "id": "u1",
            "status": "active",
            "phone": "13800138000",
        }
    ]
    assert store.replace_resource_records("demo_module", "accounts", records) is True

    assert _query_records_for_assertion(store) == records
    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            """
            SELECT 1
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchall()
        custom_rows = conn.execute(
            """
            SELECT id, phone, status
            FROM demo_module_accounts
            """
        ).fetchall()

    assert dataset_rows == []
    assert len(custom_rows) == 1
    assert dict(custom_rows[0]) == {
        "id": "u1",
        "phone": "13800138000",
        "status": "active",
    }


def test_module_data_store_adds_custom_table_rows_with_auto_increment_key(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "accounts",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {
                    "columns": [
                        {"name": "id", "type": "int", "auto_increment": True},
                        {"name": "phone", "type": "text"},
                        {"name": "status", "type": "text"},
                    ]
                },
                "cleanup_policy": "drop_table",
            }
        ],
    )

    assert store.list_data_resources("demo_module")[0]["schema"]["columns"][0] == {
        "name": "id",
        "type": "int",
        "nullable": False,
        "auto_increment": True,
    }

    inserted_ids = store.add_resource_records(
        "demo_module",
        "accounts",
        [
            {"phone": "13800138000", "status": "new"},
            {"phone": "13900139000", "status": "ready"},
        ],
    )

    assert inserted_ids == [1, 2]
    assert _query_records_for_assertion(store) == [
        {"id": 1, "phone": "13800138000", "status": "new"},
        {"id": 2, "phone": "13900139000", "status": "ready"},
    ]
    with get_connection(DATA_DB) as conn:
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("demo_module_accounts",),
        ).fetchone()["sql"]
    assert "AUTOINCREMENT" in table_sql

    with pytest.raises(ValueError, match="custom table records require a record_key"):
        store.upsert_resource_records("demo_module", "accounts", [{"phone": "13700137000"}])


def test_module_data_store_upserts_updates_and_deletes_custom_table_rows(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_custom_accounts(store, temp_data_dir)

    assert (
        store.upsert_resource_records(
            "demo_module",
            "accounts",
            [
                {"id": "u1", "phone": "13800138000", "status": "new", "balance": 1.5},
                {"id": "u2", "phone": "13900139000", "status": "expired", "balance": 2.0},
            ],
        )
        is True
    )
    assert (
        store.upsert_resource_records(
            "demo_module",
            "accounts",
            [
                {"id": "u1", "phone": "13800138001", "status": "ready", "balance": 3.5},
                {"id": "u3", "phone": "13700137000", "status": "ready", "balance": 4.0},
            ],
        )
        is True
    )

    assert (
        store.update_resource_records(
            "demo_module",
            "accounts",
            {"status": "used"},
            where=["id", "=", "u1"],
        )
        == 1
    )
    assert (
        store.delete_resource_records(
            "demo_module",
            "accounts",
            where=["status", "=", "expired"],
        )
        == 1
    )

    assert _query_records_for_assertion(store) == [
        {"id": "u1", "phone": "13800138001", "status": "used", "balance": 3.5},
        {"id": "u3", "phone": "13700137000", "status": "ready", "balance": 4.0},
    ]


def test_module_data_store_upserts_updates_and_deletes_managed_dataset_rows(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    assert (
        store.replace_resource_records(
            "demo_module",
            "accounts",
            [
                {"id": "u1", "phone": "13800138000"},
                {"id": "u2", "phone": "13900139000"},
            ],
        )
        is True
    )
    assert (
        store.upsert_resource_records(
            "demo_module",
            "accounts",
            [
                {"id": "u2", "phone": "13999999999"},
                {"id": "u3", "phone": "13700137000"},
            ],
        )
        is True
    )
    assert (
        store.update_resource_records(
            "demo_module",
            "accounts",
            {"phone": "13600136000", "run_status": "占用中", "record_status": "active"},
            where=["id", "=", "u1"],
        )
        == 1
    )
    assert store.delete_resource_records("demo_module", "accounts", where=["id", "=", "u3"]) == 1

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13600136000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "占用中",
            "record_status": "active",
        },
        {
            "id": "u2",
            "phone": "13999999999",
            "record_index": 1,
            "record_key": "u2",
            "run_status": "不占用",
            "record_status": "",
        },
    ]


@pytest.mark.parametrize(
    "field_name",
    ["record_key", "record_index", "created_at", "updated_at"],
)
def test_module_data_store_rejects_managed_dataset_reserved_update_fields(temp_data_dir, field_name):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    store.replace_resource_records("demo_module", "accounts", [{"id": "u1", "phone": "13800138000"}])

    with pytest.raises(ValueError, match=f"reserved host fields.*{field_name}"):
        store.update_resource_records("demo_module", "accounts", {field_name: "u9"}, where=["id", "=", "u1"])


def test_module_data_store_update_where_updates_status_columns_without_record_json_leakage(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    store.replace_resource_records("demo_module", "accounts", [{"id": "u1", "phone": "13800138000"}])

    assert (
        store.update_resource_records(
            "demo_module",
            "accounts",
            {"run_status": "占用中", "record_status": "active"},
            where=["id", "=", "u1"],
        )
        == 1
    )

    assert _query_records_for_assertion(store) == [
        {
            "id": "u1",
            "phone": "13800138000",
            "record_index": 0,
            "record_key": "u1",
            "run_status": "占用中",
            "record_status": "active",
        }
    ]

    with get_connection(DATA_DB) as conn:
        row = conn.execute(
            """
            SELECT run_status, record_status, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ? AND record_key = ?
            """,
            ("demo_module", "accounts", "u1"),
        ).fetchone()

    assert row["run_status"] == "占用中"
    assert row["record_status"] == "active"
    assert json.loads(row["record_json"]) == {"id": "u1", "phone": "13800138000"}


def test_module_data_store_batch_write_is_atomic(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_custom_accounts(store, temp_data_dir)

    with pytest.raises(ValueError, match="未注册的数据资源: missing"):
        store.execute_write_batch(
            "demo_module",
            [
                {
                    "kind": "upsert_records",
                    "resource": "accounts",
                    "records": [{"id": "u1", "phone": "13800138000", "status": "ready"}],
                },
                {
                    "kind": "upsert_records",
                    "resource": "missing",
                    "records": [{"id": "u2"}],
                },
            ],
        )
    assert _query_records_for_assertion(store) == []

    results = store.execute_write_batch(
        "demo_module",
        [
            {
                "kind": "upsert_records",
                "resource": "accounts",
                "records": [{"id": "u1", "phone": "13800138000", "status": "ready"}],
            },
            {
                "kind": "append_audit_event",
                "dataset": "account_events",
                "event": {"entity_key": "u1", "event_type": "created", "created_at": 100},
            },
        ],
    )

    assert results[0] is True
    assert isinstance(results[1], str)
    assert _query_records_for_assertion(store) == [
        {"id": "u1", "phone": "13800138000", "status": "ready", "balance": None}
    ]
    assert store.query_audit_events("demo_module", "account_events", limit=10) == [
        {
            "id": results[1],
            "module_name": "demo_module",
            "dataset_name": "account_events",
            "entity_key": "u1",
            "event_type": "created",
            "run_id": None,
            "previous_status": None,
            "next_status": None,
            "result": None,
            "reason": None,
            "payload": {},
            "created_at": 100,
        }
    ]


def test_module_data_store_serializes_concurrent_audit_appends(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    def append_event(index: int) -> str:
        return store.append_audit_event(
            "demo_module",
            "account_events",
            {
                "entity_key": f"u{index}",
                "event_type": "created",
                "created_at": index,
            },
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        event_ids = list(executor.map(append_event, range(30)))

    events = store.query_audit_events("demo_module", "account_events", limit=100, order="asc")
    assert [event["id"] for event in events] == event_ids
    assert [event["created_at"] for event in events] == list(range(30))


def test_module_data_store_lists_registered_data_resources(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "billing_audit",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {"columns": [{"key": "id", "type": "text"}]},
                "cleanup_policy": "drop_table",
            }
        ],
    )

    resources = store.list_data_resources("demo_module")

    assert [resource["resource_id"] for resource in resources] == ["billing_audit"]
    assert [resource["storage_mode"] for resource in resources] == ["custom_table"]


def test_module_data_store_rejects_unsafe_custom_table_names(temp_data_dir):
    from src.core.mms.data_contract import normalize_manifest_data

    with pytest.raises(ValueError, match="snake_case"):
        normalize_manifest_data(
            {
                "resources": [{"id": "accounts;drop", "storage_mode": "custom_table"}],
                "views": [],
                "seeds": [],
            }
        )


def test_module_data_store_query_returns_empty_for_missing_managed_dataset_record(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)

    assert (
        store.query_resource_records(
            "demo_module",
            "accounts",
            where=["record_key", "=", "missing"],
            limit=1,
            offset=0,
        )
        == []
    )


@pytest.mark.parametrize(
    "create_sql",
    [
        """
        CREATE TABLE module_datasets (
            module_name TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            unexpected_column TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE module_datasets (
            module_name TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            record_json TEXT NOT NULL,
            PRIMARY KEY (module_name, dataset_name, record_index)
        )
        """,
        """
        CREATE TABLE module_datasets (
            module_name TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            record_json TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (module_name, dataset_name)
        )
        """,
    ],
)
def test_init_database_rejects_incompatible_module_dataset_schema(temp_data_dir, create_sql):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database

    with get_connection(DATA_DB) as conn:
        conn.execute("DROP TABLE module_datasets")
        conn.execute(create_sql)

    with pytest.raises(RuntimeError, match="0.4.0 module_datasets schema"):
        init_database()


def test_module_data_store_appends_and_queries_audit_events(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    first_event_id = store.append_audit_event(
        "demo_module",
        "account_events",
        {
            "entity_key": "13800138000",
            "event_type": "created",
            "next_status": "active",
            "payload": {"source": "import"},
            "created_at": 100,
        },
    )
    second_event_id = store.append_audit_event(
        "demo_module",
        "account_events",
        {
            "entity_key": "13800138000",
            "event_type": "status_changed",
            "previous_status": "active",
            "next_status": "blocked",
            "result": "success",
            "reason": "risk_control",
            "payload": {"operator": "system"},
            "created_at": 200,
        },
    )

    assert first_event_id
    assert second_event_id
    assert first_event_id != second_event_id

    all_events = store.query_audit_events("demo_module", "account_events")
    created_only = store.query_audit_events(
        "demo_module",
        "account_events",
        entity_key="13800138000",
        event_type="created",
    )

    assert [event["event_type"] for event in all_events] == ["status_changed", "created"]
    assert created_only == [
        {
            "id": first_event_id,
            "module_name": "demo_module",
            "dataset_name": "account_events",
            "entity_key": "13800138000",
            "event_type": "created",
            "run_id": None,
            "previous_status": None,
            "next_status": "active",
            "result": None,
            "reason": None,
            "payload": {"source": "import"},
            "created_at": 100,
        }
    ]

    with get_connection(DATA_DB) as conn:
        rows = conn.execute(
            """
            SELECT id, module_name, dataset_name, event_type, payload_json, created_at
            FROM module_audit_events
            WHERE module_name = ?
            ORDER BY created_at ASC
            """,
            ("demo_module",),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["id"] == first_event_id
    assert rows[0]["dataset_name"] == "account_events"


def test_module_data_store_queries_audit_events_with_filters_and_paging(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    store.append_audit_event(
        "demo_module",
        "account_events",
        {
            "entity_key": "u1",
            "event_type": "created",
            "run_id": "run-1",
            "payload": {"seq": 1},
            "created_at": 100,
        },
    )
    store.append_audit_event(
        "demo_module",
        "account_events",
        {
            "entity_key": "u1",
            "event_type": "status_changed",
            "run_id": "run-2",
            "payload": {"seq": 2},
            "created_at": 200,
        },
    )
    store.append_audit_event(
        "demo_module",
        "account_events",
        {
            "entity_key": "u2",
            "event_type": "status_changed",
            "run_id": "run-2",
            "payload": {"seq": 3},
            "created_at": 300,
        },
    )

    filtered = store.query_audit_events(
        "demo_module",
        "account_events",
        entity_key="u1",
        run_id="run-2",
        start_at=150,
        end_at=250,
    )
    paged = store.query_audit_events(
        "demo_module",
        "account_events",
        order="asc",
        limit=1,
        offset=1,
    )

    assert [event["payload"]["seq"] for event in filtered] == [2]
    assert [event["payload"]["seq"] for event in paged] == [2]


def test_module_data_store_clear_module_data_removes_data_db_rows_only(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set("module:demo_module:dataset:legacy_accounts", [{"id": "legacy"}])

    store = ModuleDataStore()
    _declare_managed_dataset(store, temp_data_dir)
    store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}])
    store.write_page_schema(
        "demo_module",
        "dashboard",
        {"type": "Page", "title": "账号管理", "load_handler": "load_dashboard_page", "children": []},
    )
    store.append_audit_event(
        "demo_module",
        "account_events",
        {"entity_key": "13800138000", "event_type": "created", "payload": {"source": "import"}},
    )

    assert store.clear_module_data("demo_module") is True
    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        store.query_resource_records("demo_module", "accounts")
    assert store.read_page_schema("demo_module", "dashboard") == {}
    assert store.query_audit_events("demo_module", "account_events") == []
    assert kv.get("module:demo_module:dataset:legacy_accounts") == [{"id": "legacy"}]


def test_module_data_store_clear_module_data_drops_custom_tables(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "accounts",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {"columns": [{"key": "id", "type": "text"}]},
                "cleanup_policy": "drop_table",
            }
        ],
    )
    store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}])

    assert store.clear_module_data("demo_module") is True

    with get_connection(DATA_DB) as conn:
        table_row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            ("demo_module_accounts",),
        ).fetchone()
        resource_rows = conn.execute(
            """
            SELECT 1
            FROM module_data_resources
            WHERE module_name = ?
            """,
            ("demo_module",),
        ).fetchall()

    assert table_row is None
    assert resource_rows == []


def test_module_data_store_clear_module_data_keep_policy_preserves_custom_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    _sync_manifest_data(
        store,
        temp_data_dir,
        resources=[
            {
                "id": "accounts",
                "storage_mode": "custom_table",
                "record_key_field": "id",
                "schema": {"columns": [{"key": "id", "type": "text"}]},
                "cleanup_policy": "keep",
            }
        ],
    )
    store.replace_resource_records("demo_module", "accounts", [{"id": "u1"}])

    assert store.clear_module_data("demo_module") is True

    with get_connection(DATA_DB) as conn:
        rows = conn.execute("SELECT id FROM demo_module_accounts").fetchall()
        resource_rows = conn.execute(
            """
            SELECT 1
            FROM module_data_resources
            WHERE module_name = ?
            """,
            ("demo_module",),
        ).fetchall()

    assert [dict(row) for row in rows] == [{"id": "u1"}]
    assert resource_rows == []


def test_module_data_store_ignores_legacy_kv_rows(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set("module:demo_module:dataset:accounts", [{"id": "legacy"}])

    store = ModuleDataStore()

    _declare_managed_dataset(store, temp_data_dir)

    assert _query_records_for_assertion(store) == []
    assert kv.get("module:demo_module:dataset:accounts") == [{"id": "legacy"}]
