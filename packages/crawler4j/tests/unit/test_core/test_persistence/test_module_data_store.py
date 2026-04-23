from __future__ import annotations

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
    queries: list[dict[str, object]] | None = None,
    seeds: list[dict[str, object]] | None = None,
) -> bool:
    from src.core.mms.data_contract import normalize_manifest_data

    (module_root / "data" / "sql" / "views").mkdir(parents=True, exist_ok=True)
    (module_root / "data" / "sql" / "queries").mkdir(parents=True, exist_ok=True)
    (module_root / "data" / "seeds").mkdir(parents=True, exist_ok=True)

    raw_resources = [dict(item) for item in (resources or [])]
    raw_views = [dict(item) for item in (views or [])]
    raw_queries = [dict(item) for item in (queries or [])]
    raw_seeds = [dict(item) for item in (seeds or [])]

    for view in raw_views:
        view_id = str(view["id"])
        sql_file = str(view.get("sql_file") or f"data/sql/views/{view_id}.sql")
        (module_root / sql_file).write_text(str(view.pop("sql", "")).strip() + "\n", encoding="utf-8")
        view["sql_file"] = sql_file

    for query in raw_queries:
        query_id = str(query["id"])
        sql_file = str(query.get("sql_file") or f"data/sql/queries/{query_id}.sql")
        (module_root / sql_file).write_text(str(query.pop("sql", "")).strip() + "\n", encoding="utf-8")
        query["sql_file"] = sql_file

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
            "queries": raw_queries,
            "seeds": raw_seeds,
        }
    )
    return store.sync_manifest_data(module_name, module_root, manifest_data)


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
                {"name": "entry_id", "type": "text", "nullable": True, "filterable": True, "sortable": True},
            ],
            ensure_ascii=False,
        ),
        1,
        cleanup_policy,
        100,
        200,
    )


def test_module_data_store_reads_and_writes_only_data_db(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    records = [
        {"id": "u1", "phone": "13800138000"},
        {"id": "u2", "phone": "13900139000"},
    ]

    assert store.write_dataset("demo_module", "accounts", records) is True
    assert store.write_page_schema(
        "demo_module",
        "dashboard",
        {"type": "Page", "title": "账号管理", "load_handler": "load_dashboard_page", "children": []},
    ) is True

    assert store.read_dataset("demo_module", "accounts") == [
        {"id": "u1", "phone": "13800138000", "record_key": "u1", "run_status": "不占用", "record_status": ""},
        {"id": "u2", "phone": "13900139000", "record_key": "u2", "run_status": "不占用", "record_status": ""},
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
        manifest_row = conn.execute(
            """
            SELECT created_at, updated_at
            FROM module_dataset_manifests
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()
        page_row = conn.execute(
            "SELECT schema_json FROM module_pages WHERE module_name = ? AND page_id = ?",
            ("demo_module", "dashboard"),
        ).fetchone()

    assert [row["record_index"] for row in dataset_rows] == [0, 1]
    assert [json.loads(row["record_json"]) for row in dataset_rows] == records
    assert manifest_row is not None
    assert page_row is not None


def test_init_database_creates_module_data_resources_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection

    with get_connection(DATA_DB) as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(module_data_resources)").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(module_data_resources)").fetchall()
        }

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
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(module_db_views)").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(module_db_views)").fetchall()
        }
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


def test_init_database_normalizes_legacy_module_db_view_metadata(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database
    from src.core.persistence.module_data_store import ModuleDataStore

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

    init_database()

    store = ModuleDataStore()
    assert store.list_db_views("demo_module") == [
        {
            "module_name": "demo_module",
            "view_id": "billing_stats",
            "view_kind": "sql_view",
            "physical_view_name": "demo_module_view_billing_stats",
            "source_resource_ids": ["billing_entries"],
            "select_sql_template": "SELECT entry_id FROM {{resource:billing_entries}}",
            "columns": [
                {"name": "entry_id", "type": "text", "nullable": True, "filterable": True, "sortable": True},
            ],
            "schema_version": 1,
            "cleanup_policy": "drop_view",
        }
    ]

    with get_connection(DATA_DB) as conn:
        row = conn.execute(
            """
            SELECT view_kind, cleanup_policy, created_at, updated_at
            FROM module_db_views
            WHERE module_name = ? AND view_id = ?
            """,
            ("demo_module", "billing_stats"),
        ).fetchone()
        create_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'module_db_views'
            """
        ).fetchone()["sql"]

    assert dict(row) == {
        "view_kind": "sql_view",
        "cleanup_policy": "drop_view",
        "created_at": 100,
        "updated_at": 200,
    }
    assert "materialized_view" not in create_sql
    assert "drop_table" not in create_sql


def test_init_database_upgrades_v2_module_dataset_schema_to_v3(temp_data_dir):
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

    init_database()

    with get_connection(DATA_DB) as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(module_datasets)").fetchall()
        }
        row = conn.execute(
            """
            SELECT record_index, record_key, run_status, record_status, record_json, created_at, updated_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()

    assert {"record_key", "run_status", "record_status"}.issubset(columns)
    assert row is not None
    assert row["record_index"] == 0
    assert row["record_key"] is None
    assert row["run_status"] == "不占用"
    assert row["record_status"] == ""
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

    with pytest.raises(RuntimeError, match="Legacy module_datasets schema is no longer supported"):
        init_database()

    with get_connection(DATA_DB) as conn:
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(module_datasets)").fetchall()
        }
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

    with pytest.raises(RuntimeError, match="Legacy module_datasets schema is no longer supported"):
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
                    {"name": "execution_date", "type": "text", "filterable": True, "sortable": True},
                    {"name": "labor_account", "type": "text", "filterable": True, "sortable": True},
                    {"name": "bill_batch", "type": "text", "filterable": True, "sortable": True},
                    {"name": "total_count", "type": "int", "sortable": True},
                    {"name": "total_amount", "type": "number", "sortable": True},
                ],
            }
        ],
    )
    store.write_dataset(
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

    queried = store.query_db_view(
        "demo_module",
        "labor_billing_stats",
        filters={
            "execution_date": "2026-04-23",
            "bill_batch": "batch-001",
        },
        sort=[{"field": "total_count", "direction": "desc"}],
        limit=10,
        offset=0,
    )

    assert queried == {
        "rows": [
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
        ],
        "total": 2,
        "limit": 10,
        "offset": 0,
    }

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
            resources=[{"id": "accounts", "storage_mode": "managed_dataset"}],
            views=[
                {
                    "id": "account_stats",
                    "source_resource_ids": ["accounts"],
                    "sql": """
SELECT phone
FROM {{resource:accounts}}
""",
                    "columns": [
                        {"name": "phone", "type": "text", "filterable": True, "sortable": True},
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
                            {"name": "entry_id", "type": "text", "filterable": True, "sortable": True},
                        ],
                        **kwargs,
                    }
                ],
                "queries": [],
                "seeds": [],
            }
        )


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
                    {"name": "execution_date", "type": "text", "filterable": True, "sortable": True},
                ],
            }
        ],
    )
    store.write_dataset(
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


def test_module_data_store_clear_module_data_treats_legacy_drop_table_view_as_view(temp_data_dir):
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
                "schema": {"columns": [{"name": "entry_id", "type": "text", "required": True}]},
            }
        ],
        views=[
            {
                "id": "billing_stats",
                "source_resource_ids": ["billing_entries"],
                "sql": "SELECT entry_id FROM {{resource:billing_entries}}",
                "columns": [
                    {"name": "entry_id", "type": "text", "filterable": True, "sortable": True},
                ],
            }
        ],
    )

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
            _legacy_db_view_row(cleanup_policy="drop_table", view_kind="sql_view"),
        )
        sqlite_view = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'view' AND name = ?
            """,
            ("demo_module_view_billing_stats",),
        ).fetchone()

    assert sqlite_view is not None
    assert store.clear_module_data("demo_module") is True

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


def test_module_data_store_rewrite_preserves_manifest_created_at_and_reindexes_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    with patch("src.core.persistence.module_data_store.time.time", side_effect=[100, 200]):
        assert store.write_dataset(
            "demo_module",
            "accounts",
            [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}],
        ) is True
        assert store.write_dataset("demo_module", "accounts", [{"id": "u9"}]) is True

    assert store.read_dataset("demo_module", "accounts") == [
        {"id": "u9", "record_key": "u9", "run_status": "不占用", "record_status": ""}
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
        manifest_row = conn.execute(
            """
            SELECT created_at, updated_at
            FROM module_dataset_manifests
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()

    assert len(dataset_rows) == 1
    assert dataset_rows[0]["record_index"] == 0
    assert json.loads(dataset_rows[0]["record_json"]) == {"id": "u9"}
    assert dataset_rows[0]["created_at"] == 100
    assert dataset_rows[0]["updated_at"] == 200
    assert manifest_row is not None
    assert dict(manifest_row) == {"created_at": 100, "updated_at": 200}


def test_module_data_store_roundtrips_record_key_and_status_columns(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    records = [
        {
            "record_key": "account:1",
            "run_status": "queued",
            "record_status": "active",
            "phone": "13800138000",
        },
        {
            "record_key": "account:2",
            "run_status": "done",
            "record_status": "blocked",
            "phone": "13900139000",
        },
    ]

    assert store.write_dataset("demo_module", "accounts", records) is True

    assert store.read_dataset("demo_module", "accounts") == records
    with get_connection(DATA_DB) as conn:
        rows = conn.execute(
            """
            SELECT record_key, run_status, record_status
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            ("demo_module", "accounts"),
        ).fetchall()

    assert [dict(row) for row in rows] == [
        {"record_key": "account:1", "run_status": "queued", "record_status": "active"},
        {"record_key": "account:2", "run_status": "done", "record_status": "blocked"},
    ]


def test_module_data_store_write_empty_dataset_keeps_manifest_and_clears_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    with patch("src.core.persistence.module_data_store.time.time", side_effect=[100, 200]):
        assert store.write_dataset("demo_module", "accounts", [{"id": "u1"}]) is True
        assert store.write_dataset("demo_module", "accounts", []) is True

    assert store.read_dataset("demo_module", "accounts") == []

    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            """
            SELECT record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchall()
        manifest_row = conn.execute(
            """
            SELECT created_at, updated_at
            FROM module_dataset_manifests
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()

    assert dataset_rows == []
    assert manifest_row is not None
    assert dict(manifest_row) == {"created_at": 100, "updated_at": 200}


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
    assert store.write_dataset("demo_module", "accounts", [{"id": "u1"}]) is True

    with pytest.raises(ValueError, match=r"records\[1\]"):
        store.write_dataset("demo_module", "accounts", [{"id": "u2"}, "bad"])

    assert store.read_dataset("demo_module", "accounts") == [
        {"id": "u1", "record_key": "u1", "run_status": "不占用", "record_status": ""}
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
    assert store.write_dataset("demo_module", "accounts", records) is True

    assert store.read_dataset("demo_module", "accounts") == records
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


def test_module_data_store_lists_registered_data_resources(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
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
                "queries": [],
                "seeds": [],
            }
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

    with pytest.raises(RuntimeError, match="Unexpected module_datasets schema definition"):
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
    from src.core.persistence import DATA_DB, get_connection, get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set("module:demo_module:dataset:legacy_accounts", [{"id": "legacy"}])

    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
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
    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_page_schema("demo_module", "dashboard") == {}
    assert store.query_audit_events("demo_module", "account_events") == []

    with get_connection(DATA_DB) as conn:
        manifest_row = conn.execute(
            """
            SELECT 1
            FROM module_dataset_manifests
            WHERE module_name = ? AND dataset_name = ?
            """,
            ("demo_module", "accounts"),
        ).fetchone()

    assert manifest_row is None
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
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])

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
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])

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

    assert store.read_dataset("demo_module", "accounts") == []
    assert kv.get("module:demo_module:dataset:accounts") == [{"id": "legacy"}]
