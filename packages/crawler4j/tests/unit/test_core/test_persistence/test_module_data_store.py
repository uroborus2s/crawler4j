from __future__ import annotations

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

    assert store.write_dataset("demo_module", "accounts", [{"id": "u1", "phone": "13800138000"}]) is True
    assert store.write_data_table_schema(
        "demo_module",
        "accounts",
        {"title": "账号管理", "dataset": "accounts", "columns": [{"key": "phone", "label": "手机号"}]},
    ) is True

    assert store.read_dataset("demo_module", "accounts") == [{"id": "u1", "phone": "13800138000"}]
    assert store.read_data_table_schema("demo_module", "accounts") == {
        "title": "账号管理",
        "dataset": "accounts",
        "columns": [{"key": "phone", "label": "手机号"}],
    }
    assert store.append_audit_event(
        "demo_module",
        event_type="status.changed",
        entity_type="account",
        entity_key="u1",
        summary="切换到 active",
        payload={"before": "new", "after": "active"},
        created_at=1700000000,
    ) == {
        "id": 1,
        "module_name": "demo_module",
        "event_type": "status.changed",
        "entity_type": "account",
        "entity_key": "u1",
        "summary": "切换到 active",
        "payload": {"before": "new", "after": "active"},
        "created_at": 1700000000,
    }
    assert store.query_audit_events("demo_module", entity_type="account", entity_key="u1") == [
        {
            "id": 1,
            "module_name": "demo_module",
            "event_type": "status.changed",
            "entity_type": "account",
            "entity_key": "u1",
            "summary": "切换到 active",
            "payload": {"before": "new", "after": "active"},
            "created_at": 1700000000,
        }
    ]

    with get_connection(DATA_DB) as conn:
        dataset_row = conn.execute(
            "SELECT records_json FROM module_datasets WHERE module_name = ? AND dataset_name = ?",
            ("demo_module", "accounts"),
        ).fetchone()
        schema_row = conn.execute(
            "SELECT schema_json FROM module_data_table_views WHERE module_name = ? AND view_id = ?",
            ("demo_module", "accounts"),
        ).fetchone()
        audit_row = conn.execute(
            """
            SELECT event_type, entity_type, entity_key, summary, payload_json
            FROM module_audit_events
            WHERE module_name = ? AND entity_key = ?
            """,
            ("demo_module", "u1"),
        ).fetchone()

    assert dataset_row is not None
    assert schema_row is not None
    assert audit_row is not None


def test_module_data_store_clear_module_data_removes_data_db_rows_only(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set("module:demo_module:dataset:legacy_accounts", [{"id": "legacy"}])
    kv.set("module:demo_module:ui:data_table:legacy_accounts", {"title": "旧账号"})

    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
    store.write_data_table_schema("demo_module", "accounts", {"title": "账号管理", "dataset": "accounts"})
    store.append_audit_event("demo_module", event_type="status.changed", entity_key="u1", payload={"after": "active"})

    assert store.clear_module_data("demo_module") is True
    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_data_table_schema("demo_module", "accounts") == {}
    assert store.query_audit_events("demo_module") == []
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


def test_module_data_store_query_audit_events_supports_filters_and_order(temp_data_dir):
    from src.core.persistence.module_data_store import ModuleDataStore

    store = ModuleDataStore()
    store.append_audit_event(
        "demo_module",
        event_type="status.changed",
        entity_type="account",
        entity_key="u1",
        payload={"after": "new"},
        created_at=1700000000,
    )
    store.append_audit_event(
        "demo_module",
        event_type="status.changed",
        entity_type="account",
        entity_key="u1",
        payload={"after": "active"},
        created_at=1700000010,
    )
    store.append_audit_event(
        "demo_module",
        event_type="sync.completed",
        entity_type="job",
        entity_key="job-1",
        payload={"ok": True},
        created_at=1700000020,
    )

    latest_first = store.query_audit_events("demo_module", entity_type="account", entity_key="u1")
    assert [event["payload"] for event in latest_first] == [{"after": "active"}, {"after": "new"}]

    oldest_first = store.query_audit_events(
        "demo_module",
        entity_type="account",
        entity_key="u1",
        order="asc",
        limit=1,
    )
    assert [event["payload"] for event in oldest_first] == [{"after": "new"}]

    filtered = store.query_audit_events("demo_module", event_type="sync.completed")
    assert len(filtered) == 1
    assert filtered[0]["entity_key"] == "job-1"
