"""模块业务数据与数据表元数据存储。"""

from __future__ import annotations

import json
import time
from typing import Any

from src.core.persistence.database import DATA_DB, get_connection


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

    当前唯一事实源为 `data.db`。
    """

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
        records = self._read_dataset_row(module_name, dataset_name)
        return records if records is not None else []

    def write_dataset(self, module_name: str, dataset_name: str, records: list[dict[str, Any]]) -> bool:
        return self._write_dataset_row(module_name, dataset_name, _normalize_records(records))

    def read_data_table_schema(self, module_name: str, view_id: str) -> dict[str, Any]:
        schema = self._read_view_row(module_name, view_id)
        return schema if schema is not None else {}

    def write_data_table_schema(self, module_name: str, view_id: str, schema: dict[str, Any]) -> bool:
        return self._write_view_row(module_name, view_id, _normalize_schema(schema))

    def clear_module_data(self, module_name: str) -> bool:
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

        return changed


_module_data_store: ModuleDataStore | None = None


def get_module_data_store() -> ModuleDataStore:
    global _module_data_store
    if _module_data_store is None:
        _module_data_store = ModuleDataStore()
    return _module_data_store
