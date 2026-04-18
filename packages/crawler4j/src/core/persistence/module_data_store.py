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


def _normalize_entity_token(raw: Any) -> str:
    return str(raw or "").strip()


def _normalize_event_type(raw: Any) -> str:
    normalized = str(raw or "").strip()
    if not normalized:
        raise ValueError("event_type 不能为空")
    return normalized


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

    def append_audit_event(
        self,
        module_name: str,
        *,
        event_type: str,
        payload: Any = None,
        entity_type: str | None = None,
        entity_key: str | None = None,
        summary: str | None = None,
        created_at: int | None = None,
    ) -> dict[str, Any]:
        normalized_event_type = _normalize_event_type(event_type)
        now = int(created_at) if created_at is not None else int(time.time())
        payload_json = json.dumps(payload, ensure_ascii=False)

        with get_connection(DATA_DB) as conn:
            cursor = conn.execute(
                """
                INSERT INTO module_audit_events (
                    module_name,
                    event_type,
                    entity_type,
                    entity_key,
                    summary,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    module_name,
                    normalized_event_type,
                    _normalize_entity_token(entity_type),
                    _normalize_entity_token(entity_key),
                    str(summary or "").strip(),
                    payload_json,
                    now,
                ),
            )
            event_id = int(cursor.lastrowid)

        return {
            "id": event_id,
            "module_name": module_name,
            "event_type": normalized_event_type,
            "entity_type": _normalize_entity_token(entity_type),
            "entity_key": _normalize_entity_token(entity_key),
            "summary": str(summary or "").strip(),
            "payload": payload,
            "created_at": now,
        }

    def query_audit_events(
        self,
        module_name: str,
        *,
        event_type: str | None = None,
        entity_type: str | None = None,
        entity_key: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        normalized_limit = max(int(limit), 0)
        normalized_offset = max(int(offset), 0)
        normalized_order = "ASC" if str(order or "").strip().lower() == "asc" else "DESC"
        if normalized_limit == 0:
            return []

        clauses = ["module_name = ?"]
        params: list[Any] = [module_name]

        if event_type is not None and str(event_type).strip():
            clauses.append("event_type = ?")
            params.append(_normalize_event_type(event_type))
        if entity_type is not None and str(entity_type).strip():
            clauses.append("entity_type = ?")
            params.append(_normalize_entity_token(entity_type))
        if entity_key is not None and str(entity_key).strip():
            clauses.append("entity_key = ?")
            params.append(_normalize_entity_token(entity_key))

        sql = f"""
            SELECT id, module_name, event_type, entity_type, entity_key, summary, payload_json, created_at
            FROM module_audit_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at {normalized_order}, id {normalized_order}
            LIMIT ? OFFSET ?
        """
        params.extend([normalized_limit, normalized_offset])

        with get_connection(DATA_DB) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "id": int(row["id"]),
                "module_name": str(row["module_name"]),
                "event_type": str(row["event_type"]),
                "entity_type": str(row["entity_type"] or ""),
                "entity_key": str(row["entity_key"] or ""),
                "summary": str(row["summary"] or ""),
                "payload": json.loads(row["payload_json"]),
                "created_at": int(row["created_at"]),
            }
            for row in rows
        ]

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

            cursor = conn.execute(
                "DELETE FROM module_audit_events WHERE module_name = ?",
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
