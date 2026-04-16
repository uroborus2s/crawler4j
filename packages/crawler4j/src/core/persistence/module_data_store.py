"""模块业务数据与数据表元数据存储。"""

from __future__ import annotations

import json
import time
from typing import Any

from src.core.persistence.database import DATA_DB, get_connection
from src.core.persistence.kv_store import KVStore, get_kv_store


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _normalize_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


class ModuleDataStore:
    """模块数据与 `core:data_table` 视图元数据持久化。

    当前事实源为 `data.db`。历史 `state.db.kv_store` 中的
    `module:{module}:dataset:*` / `module:{module}:ui:data_table:*`
    会在首次访问时自动迁移并删除旧 key。
    """

    def __init__(self, kv_store: KVStore | None = None):
        self._kv = kv_store or get_kv_store()
        self._legacy_migrated = False

    def _dataset_key(self, module_name: str, dataset_name: str) -> str:
        return f"module:{module_name}:dataset:{dataset_name}"

    def _view_key(self, module_name: str, view_id: str) -> str:
        return f"module:{module_name}:ui:data_table:{view_id}"

    def _ensure_legacy_migrated(self) -> None:
        if self._legacy_migrated:
            return
        self._migrate_all_legacy_entries()
        self._legacy_migrated = True

    def _migrate_all_legacy_entries(self) -> None:
        for key in self._kv.keys("module:%"):
            parts = key.split(":")
            if len(parts) >= 4 and parts[0] == "module" and parts[2] == "dataset":
                module_name = parts[1]
                dataset_name = ":".join(parts[3:])
                raw = self._kv.get(key)
                records = _normalize_records(raw)
                self._write_dataset_row(module_name, dataset_name, records)
                self._kv.delete(key)
                continue

            if len(parts) >= 5 and parts[0] == "module" and parts[2] == "ui" and parts[3] == "data_table":
                module_name = parts[1]
                view_id = ":".join(parts[4:])
                raw = self._kv.get(key)
                schema = _normalize_schema(raw)
                self._write_view_row(module_name, view_id, schema)
                self._kv.delete(key)

    def _write_dataset_row(self, module_name: str, dataset_name: str, records: list[dict[str, Any]]) -> bool:
        now = int(time.time())
        with get_connection(DATA_DB) as conn:
            conn.execute(
                """
                INSERT INTO module_datasets (module_name, dataset_name, records_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(module_name, dataset_name) DO UPDATE SET
                    records_json = excluded.records_json,
                    updated_at = excluded.updated_at
                """,
                (
                    module_name,
                    dataset_name,
                    json.dumps(records, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return True

    def _read_dataset_row(self, module_name: str, dataset_name: str) -> list[dict[str, Any]] | None:
        with get_connection(DATA_DB) as conn:
            row = conn.execute(
                """
                SELECT records_json
                FROM module_datasets
                WHERE module_name = ? AND dataset_name = ?
                """,
                (module_name, dataset_name),
            ).fetchone()
        if not row:
            return None
        return _normalize_records(json.loads(row["records_json"]))

    def _write_view_row(self, module_name: str, view_id: str, schema: dict[str, Any]) -> bool:
        now = int(time.time())
        with get_connection(DATA_DB) as conn:
            conn.execute(
                """
                INSERT INTO module_data_table_views (module_name, view_id, schema_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(module_name, view_id) DO UPDATE SET
                    schema_json = excluded.schema_json,
                    updated_at = excluded.updated_at
                """,
                (
                    module_name,
                    view_id,
                    json.dumps(schema, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return True

    def _read_view_row(self, module_name: str, view_id: str) -> dict[str, Any] | None:
        with get_connection(DATA_DB) as conn:
            row = conn.execute(
                """
                SELECT schema_json
                FROM module_data_table_views
                WHERE module_name = ? AND view_id = ?
                """,
                (module_name, view_id),
            ).fetchone()
        if not row:
            return None
        return _normalize_schema(json.loads(row["schema_json"]))

    def read_dataset(self, module_name: str, dataset_name: str) -> list[dict[str, Any]]:
        self._ensure_legacy_migrated()
        records = self._read_dataset_row(module_name, dataset_name)
        if records is not None:
            self._kv.delete(self._dataset_key(module_name, dataset_name))
            return records

        legacy_key = self._dataset_key(module_name, dataset_name)
        legacy_value = self._kv.get(legacy_key)
        if legacy_value is None:
            return []

        records = _normalize_records(legacy_value)
        self._write_dataset_row(module_name, dataset_name, records)
        self._kv.delete(legacy_key)
        return records

    def write_dataset(self, module_name: str, dataset_name: str, records: list[dict[str, Any]]) -> bool:
        self._ensure_legacy_migrated()
        ok = self._write_dataset_row(module_name, dataset_name, _normalize_records(records))
        self._kv.delete(self._dataset_key(module_name, dataset_name))
        return ok

    def read_data_table_schema(self, module_name: str, view_id: str) -> dict[str, Any]:
        self._ensure_legacy_migrated()
        schema = self._read_view_row(module_name, view_id)
        if schema is not None:
            self._kv.delete(self._view_key(module_name, view_id))
            return schema

        legacy_key = self._view_key(module_name, view_id)
        legacy_value = self._kv.get(legacy_key)
        if legacy_value is None:
            return {}

        schema = _normalize_schema(legacy_value)
        self._write_view_row(module_name, view_id, schema)
        self._kv.delete(legacy_key)
        return schema

    def write_data_table_schema(self, module_name: str, view_id: str, schema: dict[str, Any]) -> bool:
        self._ensure_legacy_migrated()
        ok = self._write_view_row(module_name, view_id, _normalize_schema(schema))
        self._kv.delete(self._view_key(module_name, view_id))
        return ok

    def clear_module_data(self, module_name: str) -> bool:
        self._ensure_legacy_migrated()
        changed = False

        with get_connection(DATA_DB) as conn:
            cursor = conn.execute(
                "DELETE FROM module_datasets WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

            cursor = conn.execute(
                "DELETE FROM module_data_table_views WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

        for legacy_key in self._kv.keys(f"module:{module_name}:dataset:%"):
            changed = self._kv.delete(legacy_key) or changed
        for legacy_key in self._kv.keys(f"module:{module_name}:ui:data_table:%"):
            changed = self._kv.delete(legacy_key) or changed

        return changed


_module_data_store: ModuleDataStore | None = None


def get_module_data_store() -> ModuleDataStore:
    global _module_data_store
    if _module_data_store is None:
        _module_data_store = ModuleDataStore()
    return _module_data_store
