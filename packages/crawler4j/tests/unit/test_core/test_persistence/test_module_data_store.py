from __future__ import annotations

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def test_module_data_store_reads_and_writes_only_data_db(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()

    records = [
        {"id": "u1", "phone": "13800138000"},
        {"id": "u2", "phone": "13900139000"},
    ]

    assert store.write_dataset("demo_module", "accounts", records) is True
    assert store.write_data_table_schema(
        "demo_module",
        "accounts",
        {"title": "账号管理", "dataset": "accounts", "columns": [{"key": "phone", "label": "手机号"}]},
    ) is True

    assert store.read_dataset("demo_module", "accounts") == records
    assert store.read_data_table_schema("demo_module", "accounts") == {
        "title": "账号管理",
        "dataset": "accounts",
        "columns": [{"key": "phone", "label": "手机号"}],
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
        schema_row = conn.execute(
            "SELECT schema_json FROM module_data_table_views WHERE module_name = ? AND view_id = ?",
            ("demo_module", "accounts"),
        ).fetchone()

    assert [row["record_index"] for row in dataset_rows] == [0, 1]
    assert [json.loads(row["record_json"]) for row in dataset_rows] == records
    assert schema_row is not None


def test_init_database_migrates_legacy_module_dataset_rows(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection
    from src.core.persistence.database import init_database
    from src.core.persistence.module_data_store import ModuleDataStore

    legacy_records = [
        {"id": "u1", "phone": "13800138000"},
        {"id": "u2", "phone": "13900139000"},
    ]

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
            ("demo_module", "accounts", json.dumps(legacy_records, ensure_ascii=False), 100, 200),
        )

    init_database()

    store = ModuleDataStore()
    assert store.read_dataset("demo_module", "accounts") == legacy_records

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

    assert [row["record_index"] for row in dataset_rows] == [0, 1]
    assert [json.loads(row["record_json"]) for row in dataset_rows] == legacy_records
    assert [row["created_at"] for row in dataset_rows] == [100, 100]
    assert [row["updated_at"] for row in dataset_rows] == [200, 200]


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
    kv.set("module:demo_module:ui:data_table:legacy_accounts", {"title": "旧账号"})

    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
    store.write_data_table_schema("demo_module", "accounts", {"title": "账号管理", "dataset": "accounts"})
    store.append_audit_event(
        "demo_module",
        "account_events",
        {"entity_key": "13800138000", "event_type": "created", "payload": {"source": "import"}},
    )

    assert store.clear_module_data("demo_module") is True
    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_data_table_schema("demo_module", "accounts") == {}
    assert store.query_audit_events("demo_module", "account_events") == []
    assert kv.get("module:demo_module:dataset:legacy_accounts") == [{"id": "legacy"}]
    assert kv.get("module:demo_module:ui:data_table:legacy_accounts") == {"title": "旧账号"}


def test_module_data_store_ignores_legacy_kv_rows(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set("module:demo_module:dataset:accounts", [{"id": "legacy"}])
    kv.set("module:demo_module:ui:data_table:accounts", {"title": "旧账号"})

    store = ModuleDataStore()

    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_data_table_schema("demo_module", "accounts") == {}
    assert kv.get("module:demo_module:dataset:accounts") == [{"id": "legacy"}]
    assert kv.get("module:demo_module:ui:data_table:accounts") == {"title": "旧账号"}
