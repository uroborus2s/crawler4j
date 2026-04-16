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


def test_module_data_store_migrates_legacy_kv_records_and_schema(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection, get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    kv.set(
        "module:demo_module:dataset:accounts",
        [{"id": "u1", "phone": "13800138000"}],
    )
    kv.set(
        "module:demo_module:ui:data_table:accounts",
        {"title": "账号管理", "dataset": "accounts", "columns": [{"key": "phone"}]},
    )

    store = ModuleDataStore()

    assert store.read_dataset("demo_module", "accounts") == [{"id": "u1", "phone": "13800138000"}]
    assert store.read_data_table_schema("demo_module", "accounts") == {
        "title": "账号管理",
        "dataset": "accounts",
        "columns": [{"key": "phone"}],
    }
    assert kv.get("module:demo_module:dataset:accounts") is None
    assert kv.get("module:demo_module:ui:data_table:accounts") is None

    with get_connection(DATA_DB) as conn:
        dataset_row = conn.execute(
            "SELECT records_json FROM module_datasets WHERE module_name = ? AND dataset_name = ?",
            ("demo_module", "accounts"),
        ).fetchone()
        schema_row = conn.execute(
            "SELECT schema_json FROM module_data_table_views WHERE module_name = ? AND view_id = ?",
            ("demo_module", "accounts"),
        ).fetchone()

    assert dataset_row is not None
    assert schema_row is not None


def test_module_data_store_clear_module_data_removes_new_and_legacy_rows(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
    store.write_data_table_schema("demo_module", "accounts", {"title": "账号管理", "dataset": "accounts"})

    kv.set("module:demo_module:dataset:legacy_accounts", [{"id": "legacy"}])
    kv.set("module:demo_module:ui:data_table:legacy_accounts", {"title": "旧账号"})

    assert store.clear_module_data("demo_module") is True
    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_data_table_schema("demo_module", "accounts") == {}
    assert kv.get("module:demo_module:dataset:legacy_accounts") is None
    assert kv.get("module:demo_module:ui:data_table:legacy_accounts") is None


def test_module_data_store_keeps_explicit_empty_new_rows_over_legacy_kv(temp_data_dir):
    from src.core.persistence import get_kv_store
    from src.core.persistence.module_data_store import ModuleDataStore

    kv = get_kv_store()
    store = ModuleDataStore()
    store.write_dataset("demo_module", "accounts", [])
    store.write_data_table_schema("demo_module", "accounts", {})

    kv.set("module:demo_module:dataset:accounts", [{"id": "legacy"}])
    kv.set("module:demo_module:ui:data_table:accounts", {"title": "旧账号"})

    assert store.read_dataset("demo_module", "accounts") == []
    assert store.read_data_table_schema("demo_module", "accounts") == {}
    assert kv.get("module:demo_module:dataset:accounts") is None
    assert kv.get("module:demo_module:ui:data_table:accounts") is None
