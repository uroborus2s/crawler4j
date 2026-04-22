"""模块业务数据与数据表元数据存储。"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from src.core.persistence.database import DATA_DB, get_connection


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _normalize_records_for_write(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("dataset records must be a list of objects")

    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"dataset records[{index}] must be an object")
        records.append(dict(item))
    return records


def _normalize_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _normalize_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _normalize_timestamp(raw: Any) -> int:
    if raw is None:
        return int(time.time())
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(time.time())


class ModuleDataStore:
    """模块数据与 `core:data_table` 视图元数据持久化。

    当前唯一事实源为 `data.db`。
    """

    def _read_dataset_manifest_timestamps(self, module_name: str, dataset_name: str) -> tuple[int | None, int | None]:
        with get_connection(DATA_DB) as conn:
            row = conn.execute(
                """
                SELECT created_at, updated_at
                FROM module_dataset_manifests
                WHERE module_name = ? AND dataset_name = ?
                """,
                (module_name, dataset_name),
            ).fetchone()
            if not row:
                row = conn.execute(
                    """
                    SELECT MIN(created_at) AS created_at, MAX(updated_at) AS updated_at
                    FROM module_datasets
                    WHERE module_name = ? AND dataset_name = ?
                    """,
                    (module_name, dataset_name),
                ).fetchone()
        if not row:
            return None, None
        if row["created_at"] is None or row["updated_at"] is None:
            return None, None
        return int(row["created_at"]), int(row["updated_at"])

    def _write_dataset_manifest_row(
        self,
        conn,
        module_name: str,
        dataset_name: str,
        *,
        created_at: int,
        updated_at: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO module_dataset_manifests (
                module_name,
                dataset_name,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(module_name, dataset_name) DO UPDATE SET
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (module_name, dataset_name, created_at, updated_at),
        )

    def _write_dataset_row(self, module_name: str, dataset_name: str, records: list[dict[str, Any]]) -> bool:
        now = int(time.time())
        normalized_records = [dict(record) for record in records]
        created_at, _ = self._read_dataset_manifest_timestamps(module_name, dataset_name)
        created_at = created_at if created_at is not None else now
        with get_connection(DATA_DB) as conn:
            conn.execute(
                """
                DELETE FROM module_datasets
                WHERE module_name = ? AND dataset_name = ?
                """,
                (module_name, dataset_name),
            )
            if normalized_records:
                conn.executemany(
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
                    [
                        (
                            module_name,
                            dataset_name,
                            record_index,
                            json.dumps(record, ensure_ascii=False),
                            created_at,
                            now,
                        )
                        for record_index, record in enumerate(normalized_records)
                    ],
                )
            self._write_dataset_manifest_row(
                conn,
                module_name,
                dataset_name,
                created_at=created_at,
                updated_at=now,
            )
        return True

    def _read_dataset_row(self, module_name: str, dataset_name: str) -> list[dict[str, Any]] | None:
        with get_connection(DATA_DB) as conn:
            rows = conn.execute(
                """
                SELECT record_json
                FROM module_datasets
                WHERE module_name = ? AND dataset_name = ?
                ORDER BY record_index ASC
                """,
                (module_name, dataset_name),
            ).fetchall()
        if not rows:
            return None
        return _normalize_records([json.loads(row["record_json"]) for row in rows])

    def _append_audit_event_row(
        self,
        module_name: str,
        dataset_name: str,
        event: dict[str, Any],
    ) -> str:
        event_id = _normalize_text(event.get("id")) or str(uuid.uuid4())
        payload = _normalize_payload(event.get("payload"))
        created_at = _normalize_timestamp(event.get("created_at"))
        with get_connection(DATA_DB) as conn:
            conn.execute(
                """
                INSERT INTO module_audit_events (
                    id,
                    module_name,
                    dataset_name,
                    entity_key,
                    event_type,
                    run_id,
                    previous_status,
                    next_status,
                    result,
                    reason,
                    payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    module_name,
                    dataset_name,
                    _normalize_text(event.get("entity_key")),
                    _normalize_text(event.get("event_type")) or "event",
                    _normalize_text(event.get("run_id")),
                    _normalize_text(event.get("previous_status")),
                    _normalize_text(event.get("next_status")),
                    _normalize_text(event.get("result")),
                    _normalize_text(event.get("reason")),
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                ),
            )
        return event_id

    def _query_audit_event_rows(
        self,
        module_name: str,
        dataset_name: str,
        *,
        entity_key: str | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        clauses = ["module_name = ?", "dataset_name = ?"]
        params: list[Any] = [module_name, dataset_name]

        if entity_key:
            clauses.append("entity_key = ?")
            params.append(entity_key)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if run_id:
            clauses.append("run_id = ?")
            params.append(run_id)
        if start_at is not None:
            clauses.append("created_at >= ?")
            params.append(int(start_at))
        if end_at is not None:
            clauses.append("created_at <= ?")
            params.append(int(end_at))

        direction = "ASC" if str(order).lower() == "asc" else "DESC"
        normalized_limit = max(int(limit), 1)
        normalized_offset = max(int(offset), 0)
        params.extend([normalized_limit, normalized_offset])

        query = f"""
            SELECT
                id,
                module_name,
                dataset_name,
                entity_key,
                event_type,
                run_id,
                previous_status,
                next_status,
                result,
                reason,
                payload_json,
                created_at
            FROM module_audit_events
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at {direction}, id {direction}
            LIMIT ? OFFSET ?
        """

        with get_connection(DATA_DB) as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return [
            {
                "id": row["id"],
                "module_name": row["module_name"],
                "dataset_name": row["dataset_name"],
                "entity_key": row["entity_key"],
                "event_type": row["event_type"],
                "run_id": row["run_id"],
                "previous_status": row["previous_status"],
                "next_status": row["next_status"],
                "result": row["result"],
                "reason": row["reason"],
                "payload": _normalize_payload(json.loads(row["payload_json"])),
                "created_at": int(row["created_at"]),
            }
            for row in rows
        ]

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
        return self._write_dataset_row(module_name, dataset_name, _normalize_records_for_write(records))

    def append_audit_event(
        self,
        module_name: str,
        dataset_name: str,
        event: dict[str, Any],
    ) -> str:
        return self._append_audit_event_row(module_name, dataset_name, dict(event or {}))

    def query_audit_events(
        self,
        module_name: str,
        dataset_name: str,
        *,
        entity_key: str | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        return self._query_audit_event_rows(
            module_name,
            dataset_name,
            entity_key=entity_key,
            event_type=event_type,
            run_id=run_id,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
            order=order,
        )

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
                "DELETE FROM module_dataset_manifests WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

            cursor = conn.execute(
                "DELETE FROM module_audit_events WHERE module_name = ?",
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
