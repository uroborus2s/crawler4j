"""模块业务数据与数据表元数据存储。"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from src.core.mms.data_contract import load_sql_file, validate_resource_sql, validate_seed_file
from src.core.persistence.database import DATA_DB, get_connection

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_STORAGE_MODES = {"managed_dataset", "custom_table"}
_CLEANUP_POLICIES = {"delete_rows", "drop_table", "keep"}
_DB_VIEW_KINDS = {"sql_view"}
_DB_VIEW_CLEANUP_POLICIES = {"drop_view", "keep"}
_DEFAULT_RUN_STATUS = "不占用"
_DEFAULT_RECORD_STATUS = ""
_DB_VIEW_COLUMN_TYPES = {"text", "int", "number", "bool", "json"}
_DB_VIEW_SORT_DIRECTIONS = {"asc", "desc"}
_CUSTOM_TABLE_TYPE_MAP = {
    "text": "TEXT",
    "int": "INTEGER",
    "integer": "INTEGER",
    "number": "REAL",
    "real": "REAL",
    "bool": "INTEGER",
    "json": "TEXT",
}
_LEGACY_CUSTOM_TABLE_COLUMNS = {
    "record_key",
    "run_status",
    "record_status",
    "record_json",
    "created_at",
    "updated_at",
}
_DB_VIEW_RESOURCE_PLACEHOLDER_RE = re.compile(r"\{\{resource:([a-z][a-z0-9_]*)\}\}")
_DB_VIEW_SQL_REF_RE = re.compile(r"\b(?:from|join)\s+([^\s,()]+)", re.IGNORECASE)
_DB_VIEW_BLOCKED_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|create|replace)\b",
    re.IGNORECASE,
)


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


def _normalize_resource_json(raw: Any) -> Any:
    if raw in (None, ""):
        return {}
    try:
        loaded = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, (dict, list)) else {}


def _normalize_resource_json_for_write(raw: Any) -> Any:
    if raw is None:
        return {}
    return raw if isinstance(raw, (dict, list)) else {}


def _normalize_schema_version(raw: Any) -> int:
    if raw in (None, ""):
        return 1
    try:
        version = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid schema version: {raw}") from exc
    if version < 1:
        raise ValueError(f"invalid schema version: {raw}")
    return version


def _validate_storage_mode(storage_mode: str) -> str:
    if storage_mode not in _STORAGE_MODES:
        raise ValueError(f"unsupported storage_mode: {storage_mode}")
    return storage_mode


def _validate_cleanup_policy(cleanup_policy: str) -> str:
    if cleanup_policy not in _CLEANUP_POLICIES:
        raise ValueError(f"unsupported cleanup_policy: {cleanup_policy}")
    return cleanup_policy


def _validate_db_view_kind(view_kind: str) -> str:
    if view_kind not in _DB_VIEW_KINDS:
        raise ValueError(f"unsupported view_kind: {view_kind}")
    return view_kind


def _validate_db_view_cleanup_policy(cleanup_policy: str) -> str:
    if cleanup_policy not in _DB_VIEW_CLEANUP_POLICIES:
        raise ValueError(f"unsupported db view cleanup_policy: {cleanup_policy}")
    return cleanup_policy


def _validate_snake_case_identifier(name: str) -> str:
    if not _SNAKE_CASE_RE.fullmatch(name):
        raise ValueError(f"custom table identifiers must be snake_case: {name}")
    return name


def _quote_identifier(name: str) -> str:
    return f'"{_validate_snake_case_identifier(name)}"'


def _custom_table_name(module_name: str, resource_id: str) -> str:
    _validate_snake_case_identifier(module_name)
    _validate_snake_case_identifier(resource_id)
    return _validate_snake_case_identifier(f"{module_name}_{resource_id}")


def _db_view_name(module_name: str, view_id: str) -> str:
    _validate_snake_case_identifier(module_name)
    _validate_snake_case_identifier(view_id)
    return _validate_snake_case_identifier(f"{module_name}_view_{view_id}")


def _record_status_columns(record: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalize_text(record.get("run_status")) or _DEFAULT_RUN_STATUS,
        _normalize_text(record.get("record_status")) or _DEFAULT_RECORD_STATUS,
    )


def _record_from_storage_row(row) -> dict[str, Any]:
    record = _normalize_records([json.loads(row["record_json"])])
    payload = record[0] if record else {}
    record_key = _normalize_text(row["record_key"])
    if record_key is not None:
        payload.setdefault("record_key", record_key)
    payload["run_status"] = _normalize_text(row["run_status"]) or _DEFAULT_RUN_STATUS
    payload["record_status"] = _normalize_text(row["record_status"]) or _DEFAULT_RECORD_STATUS
    return payload


def _record_key_for_write(
    record: dict[str, Any],
    _record_index: int,
    *,
    record_key_field: str | None,
    require_key: bool,
) -> str | None:
    candidate_fields = [
        field
        for field in (record_key_field, "record_key", "id")
        if field
    ]
    for field in dict.fromkeys(candidate_fields):
        if field in record:
            record_key = _normalize_text(record.get(field))
            if record_key is not None:
                return record_key
    if require_key:
        return None
    return None


def _normalize_custom_table_type(raw: Any) -> str:
    column_type = str(raw or "text").strip().lower()
    if column_type not in _CUSTOM_TABLE_TYPE_MAP:
        raise ValueError(f"unsupported custom table column type: {column_type}")
    return column_type


def _normalize_db_view_column_type(raw: Any) -> str:
    column_type = str(raw or "text").strip().lower()
    if column_type not in _DB_VIEW_COLUMN_TYPES:
        raise ValueError(f"unsupported db view column type: {column_type}")
    return column_type


def _normalize_db_view_column(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("db view columns must be objects")

    name = _validate_snake_case_identifier(str(raw.get("name") or ""))
    column = {
        "name": name,
        "type": _normalize_db_view_column_type(raw.get("type")),
        "nullable": bool(raw.get("nullable")) if "nullable" in raw else True,
        "filterable": bool(raw.get("filterable")),
        "sortable": bool(raw.get("sortable")),
    }
    return column


def _normalize_db_view_columns(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("db view columns must be a non-empty list")
    return [_normalize_db_view_column(item) for item in raw]


def _normalize_db_view_source_resource_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("db view source_resource_ids must be a non-empty list")
    return [
        _validate_snake_case_identifier(str(item))
        for item in raw
    ]


def _normalize_db_view_schema_version(raw: Any) -> int:
    if raw in (None, ""):
        return 1
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid db view schema version: {raw}") from exc
    if value < 1:
        raise ValueError(f"invalid db view schema version: {raw}")
    return value


def _normalize_db_view_sort(raw: Any) -> list[dict[str, str]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("db view sort must be a list")
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"db view sort[{index}] must be an object")
        field = _validate_snake_case_identifier(str(item.get("field") or ""))
        direction = str(item.get("direction") or "asc").strip().lower()
        if direction not in _DB_VIEW_SORT_DIRECTIONS:
            raise ValueError(f"unsupported db view sort direction: {direction}")
        normalized.append({"field": field, "direction": direction})
    return normalized


def _apply_record_query(
    records: list[dict[str, Any]] | None,
    *,
    filters: dict[str, Any] | None = None,
    sort: list[dict[str, Any]] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    filtered = list(records or [])
    for field, value in dict(filters or {}).items():
        normalized_field = _validate_snake_case_identifier(str(field))
        if value is None:
            filtered = [item for item in filtered if item.get(normalized_field) is None]
        else:
            filtered = [item for item in filtered if item.get(normalized_field) == value]

    for item in reversed(_normalize_db_view_sort(sort or [])):
        filtered.sort(
            key=lambda row: row.get(item["field"]),
            reverse=item["direction"] == "desc",
        )

    normalized_offset = max(int(offset), 0)
    normalized_limit = max(int(limit), 1)
    return filtered[normalized_offset : normalized_offset + normalized_limit]


def _normalize_db_view_sql_template(raw: Any) -> str:
    sql = str(raw or "").strip()
    if not sql:
        raise ValueError("db view select_sql_template is required")
    if ";" in sql:
        raise ValueError("db view select_sql_template must be a single statement")
    if _DB_VIEW_BLOCKED_SQL_RE.search(sql):
        raise ValueError("db view select_sql_template contains blocked SQL keywords")
    if not re.match(r"^\s*(with\b|select\b)", sql, flags=re.IGNORECASE):
        raise ValueError("db view select_sql_template must start with SELECT or WITH")
    return sql


def _normalize_custom_table_column(raw: Any, *, record_key_field: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("custom table schema columns must be objects")

    name = _validate_snake_case_identifier(
        str(raw.get("name") or raw.get("key") or ""),
    )
    column_type = _normalize_custom_table_type(raw.get("type"))
    nullable = bool(raw.get("nullable")) if "nullable" in raw else not bool(raw.get("required"))
    if record_key_field and name == record_key_field:
        nullable = False
    return {
        "name": name,
        "type": column_type,
        "nullable": nullable,
    }


def _normalize_custom_table_schema(raw: Any, *, record_key_field: str | None) -> dict[str, Any]:
    schema = _normalize_schema(raw)
    version = _normalize_schema_version(schema.get("version") or schema.get("schema_version"))
    raw_columns = schema.get("columns", [])
    if raw_columns is None:
        raw_columns = []
    if not isinstance(raw_columns, list):
        raise ValueError("custom table schema columns must be a list")

    columns = [
        _normalize_custom_table_column(column, record_key_field=record_key_field)
        for column in raw_columns
    ]
    if record_key_field and columns:
        names = {column["name"] for column in columns}
        if record_key_field not in names:
            raise ValueError(f"custom table schema must include record_key_field column: {record_key_field}")
    return {
        "version": version,
        "columns": columns,
    }


def _normalize_custom_table_resource_metadata(
    *,
    schema: Any,
    indexes: Any,
    record_key_field: str | None,
) -> tuple[int, dict[str, Any], dict[str, list[str]]]:
    normalized_schema = _normalize_custom_table_schema(schema, record_key_field=record_key_field)
    if not normalized_schema["columns"]:
        raise ValueError("custom table resource schema must declare columns")
    normalized_indexes = _normalize_custom_table_indexes(
        indexes,
        column_names={column["name"] for column in normalized_schema["columns"]},
    )
    return normalized_schema["version"], normalized_schema, normalized_indexes


def _normalize_custom_table_indexes(raw: Any, *, column_names: set[str]) -> dict[str, list[str]]:
    indexes = _normalize_schema(raw)
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_columns in indexes.items():
        index_name = _validate_snake_case_identifier(str(raw_name))
        if not isinstance(raw_columns, list) or not raw_columns:
            raise ValueError(f"custom table index {index_name} must declare a non-empty column list")
        columns = [
            _validate_snake_case_identifier(str(column))
            for column in raw_columns
        ]
        missing_columns = [column for column in columns if column not in column_names]
        if missing_columns:
            raise ValueError(
                f"custom table index {index_name} references unknown columns: {', '.join(missing_columns)}"
            )
        normalized[index_name] = columns
    return normalized


def _merge_inferred_column_type(existing_type: str, new_type: str) -> str:
    if existing_type == new_type:
        return existing_type
    if {existing_type, new_type}.issubset({"int", "number"}):
        return "number"
    if "json" in {existing_type, new_type}:
        return "json"
    return "text"


def _infer_custom_table_column_type(value: Any) -> str:
    if value is None:
        return "text"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    if isinstance(value, (dict, list)):
        return "json"
    return "text"


def _infer_custom_table_schema_from_records(
    records: list[dict[str, Any]],
    *,
    record_key_field: str | None,
) -> dict[str, Any]:
    column_order: list[str] = []
    column_types: dict[str, str] = {}
    nullable_columns: set[str] = set()
    for record in records:
        for key, value in record.items():
            if key not in column_types:
                _validate_snake_case_identifier(key)
                column_order.append(key)
                column_types[key] = _infer_custom_table_column_type(value)
            else:
                column_types[key] = _merge_inferred_column_type(
                    column_types[key],
                    _infer_custom_table_column_type(value),
                )
            if value is None:
                nullable_columns.add(key)

    if record_key_field and record_key_field not in column_types:
        column_order.insert(0, record_key_field)
        column_types[record_key_field] = "text"
        nullable_columns.add(record_key_field)

    columns = [
        {
            "name": column_name,
            "type": column_types[column_name],
            "nullable": column_name != record_key_field and column_name in nullable_columns,
        }
        for column_name in column_order
    ]
    return {
        "version": 1,
        "columns": columns,
    }


def _sqlite_value_for_custom_table_column(value: Any, *, column_type: str) -> Any:
    if value is None:
        return None
    if column_type == "bool":
        return 1 if bool(value) else 0
    if column_type in {"int", "integer"}:
        return int(value)
    if column_type in {"number", "real"}:
        return float(value)
    if column_type == "json":
        return json.dumps(value, ensure_ascii=False)
    return value


def _python_value_for_custom_table_column(value: Any, *, column_type: str) -> Any:
    if value is None:
        return None
    if column_type == "bool":
        return bool(value)
    if column_type == "json":
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


class ModuleDataStore:
    """模块数据与宿主页 schema 持久化。

    当前唯一事实源为 `data.db`。
    """

    def _resource_from_row(self, row) -> dict[str, Any]:
        return {
            "module_name": row["module_name"],
            "resource_id": row["resource_id"],
            "storage_mode": row["storage_mode"],
            "logical_name": row["logical_name"],
            "physical_table_name": row["physical_table_name"],
            "record_key_field": row["record_key_field"],
            "schema_version": int(row["schema_version"]) if row["schema_version"] is not None else 1,
            "schema": _normalize_resource_json(row["schema_json"]),
            "indexes": _normalize_resource_json(row["indexes_json"]),
            "cleanup_policy": row["cleanup_policy"],
        }

    def _read_resource_row_with_conn(self, conn, module_name: str, resource_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                module_name,
                resource_id,
                storage_mode,
                logical_name,
                physical_table_name,
                record_key_field,
                schema_version,
                schema_json,
                indexes_json,
                cleanup_policy
            FROM module_data_resources
            WHERE module_name = ? AND resource_id = ?
            """,
            (module_name, resource_id),
        ).fetchone()
        return self._resource_from_row(row) if row else None

    def _list_resource_rows_with_conn(self, conn, module_name: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                module_name,
                resource_id,
                storage_mode,
                logical_name,
                physical_table_name,
                record_key_field,
                schema_version,
                schema_json,
                indexes_json,
                cleanup_policy
            FROM module_data_resources
            WHERE module_name = ?
            ORDER BY resource_id ASC
            """,
            (module_name,),
        ).fetchall()
        return [self._resource_from_row(row) for row in rows]

    def _db_view_from_row(self, row) -> dict[str, Any]:
        raw_source_resource_ids = _normalize_resource_json(row["source_resource_ids_json"])
        if not isinstance(raw_source_resource_ids, list):
            raw_source_resource_ids = []
        raw_columns = _normalize_resource_json(row["columns_json"])
        if not isinstance(raw_columns, list):
            raw_columns = []
        cleanup_policy = "keep" if str(row["cleanup_policy"] or "").strip() == "keep" else "drop_view"
        return {
            "module_name": row["module_name"],
            "view_id": row["view_id"],
            "view_kind": "sql_view",
            "physical_view_name": row["physical_view_name"],
            "source_resource_ids": [
                _validate_snake_case_identifier(str(item))
                for item in raw_source_resource_ids
            ],
            "select_sql_template": str(row["select_sql_template"] or "").strip(),
            "columns": _normalize_db_view_columns(raw_columns),
            "schema_version": _normalize_db_view_schema_version(row["schema_version"]),
            "cleanup_policy": cleanup_policy,
        }

    def _read_db_view_row_with_conn(self, conn, module_name: str, view_id: str) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT
                module_name,
                view_id,
                view_kind,
                physical_view_name,
                source_resource_ids_json,
                select_sql_template,
                columns_json,
                schema_version,
                cleanup_policy
            FROM module_db_views
            WHERE module_name = ? AND view_id = ?
            """,
            (module_name, view_id),
        ).fetchone()
        return self._db_view_from_row(row) if row else None

    def _list_db_view_rows_with_conn(self, conn, module_name: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                module_name,
                view_id,
                view_kind,
                physical_view_name,
                source_resource_ids_json,
                select_sql_template,
                columns_json,
                schema_version,
                cleanup_policy
            FROM module_db_views
            WHERE module_name = ?
            ORDER BY view_id ASC
            """,
            (module_name,),
        ).fetchall()
        return [self._db_view_from_row(row) for row in rows]

    def _write_resource_row_with_conn(
        self,
        conn,
        module_name: str,
        resource_id: str,
        *,
        storage_mode: str,
        logical_name: str,
        physical_table_name: str,
        record_key_field: str | None,
        schema: Any | None,
        indexes: Any | None,
        cleanup_policy: str,
        now: int,
    ) -> dict[str, Any]:
        _validate_storage_mode(storage_mode)
        _validate_cleanup_policy(cleanup_policy)
        if storage_mode == "custom_table":
            schema_version, normalized_schema, normalized_indexes = _normalize_custom_table_resource_metadata(
                schema=schema,
                indexes=indexes,
                record_key_field=record_key_field,
            )
        else:
            normalized_schema = _normalize_resource_json_for_write(schema)
            normalized_indexes = _normalize_resource_json_for_write(indexes)
            schema_version = _normalize_schema_version(
                normalized_schema.get("version") if isinstance(normalized_schema, dict) else 1
            )
        conn.execute(
            """
            INSERT INTO module_data_resources (
                module_name,
                resource_id,
                storage_mode,
                logical_name,
                physical_table_name,
                record_key_field,
                schema_version,
                schema_json,
                indexes_json,
                cleanup_policy,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(module_name, resource_id) DO UPDATE SET
                storage_mode = excluded.storage_mode,
                logical_name = excluded.logical_name,
                physical_table_name = excluded.physical_table_name,
                record_key_field = excluded.record_key_field,
                schema_version = excluded.schema_version,
                schema_json = excluded.schema_json,
                indexes_json = excluded.indexes_json,
                cleanup_policy = excluded.cleanup_policy,
                updated_at = excluded.updated_at
            """,
            (
                module_name,
                resource_id,
                storage_mode,
                logical_name,
                physical_table_name,
                record_key_field,
                schema_version,
                json.dumps(normalized_schema, ensure_ascii=False),
                json.dumps(normalized_indexes, ensure_ascii=False),
                cleanup_policy,
                now,
                now,
            ),
        )
        resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
        if resource is None:
            raise RuntimeError("module data resource registration failed")
        return resource

    def _ensure_managed_dataset_resource_with_conn(
        self,
        conn,
        module_name: str,
        dataset_name: str,
        *,
        now: int,
    ) -> dict[str, Any]:
        existing = self._read_resource_row_with_conn(conn, module_name, dataset_name)
        if existing is not None:
            if existing["storage_mode"] == "managed_dataset":
                return self._write_resource_row_with_conn(
                    conn,
                    module_name,
                    dataset_name,
                    storage_mode="managed_dataset",
                    logical_name=existing["logical_name"],
                    physical_table_name="module_datasets",
                    record_key_field=existing["record_key_field"],
                    schema=existing["schema"],
                    indexes=existing["indexes"],
                    cleanup_policy=existing["cleanup_policy"],
                    now=now,
                )
            return existing
        return self._write_resource_row_with_conn(
            conn,
            module_name,
            dataset_name,
            storage_mode="managed_dataset",
            logical_name=dataset_name,
            physical_table_name="module_datasets",
            record_key_field=None,
            schema={},
            indexes={},
            cleanup_policy="delete_rows",
            now=now,
        )

    def _read_dataset_manifest_timestamps_with_conn(
        self,
        conn,
        module_name: str,
        dataset_name: str,
    ) -> tuple[int | None, int | None]:
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

    def _write_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        dataset_name: str,
        records: list[dict[str, Any]],
        *,
        record_key_field: str | None,
        now: int,
    ) -> None:
        normalized_records = [dict(record) for record in records]
        created_at, _ = self._read_dataset_manifest_timestamps_with_conn(conn, module_name, dataset_name)
        created_at = created_at if created_at is not None else now
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
                    record_key,
                    run_status,
                    record_status,
                    record_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        module_name,
                        dataset_name,
                        record_index,
                        _record_key_for_write(
                            record,
                            record_index,
                            record_key_field=record_key_field,
                            require_key=False,
                        ),
                        *_record_status_columns(record),
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

    def _read_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        dataset_name: str,
    ) -> list[dict[str, Any]] | None:
        rows = conn.execute(
            """
            SELECT record_key, run_status, record_status, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            (module_name, dataset_name),
        ).fetchall()
        if not rows:
            return None
        return [_record_from_storage_row(row) for row in rows]

    def _custom_table_schema_columns(self, resource: dict[str, Any]) -> list[dict[str, Any]]:
        schema = _normalize_custom_table_schema(
            resource.get("schema") or {},
            record_key_field=resource.get("record_key_field"),
        )
        if not schema["columns"]:
            raise ValueError(f"custom table resource {resource['resource_id']} missing schema columns")
        return schema["columns"]

    def _expected_custom_table_column_map(self, resource: dict[str, Any]) -> dict[str, tuple[str, bool, bool]]:
        expected: dict[str, tuple[str, bool, bool]] = {}
        record_key_field = resource.get("record_key_field")
        for column in self._custom_table_schema_columns(resource):
            expected[column["name"]] = (
                _CUSTOM_TABLE_TYPE_MAP[column["type"]],
                bool(column["nullable"]),
                column["name"] == record_key_field,
            )
        expected["created_at"] = ("INTEGER", True, False)
        expected["updated_at"] = ("INTEGER", True, False)
        return expected

    def _assert_custom_table_matches_resource(self, conn, resource: dict[str, Any]) -> None:
        physical_table_name = resource["physical_table_name"]
        table_info = conn.execute(f"PRAGMA table_info({_quote_identifier(physical_table_name)})").fetchall()
        existing = {
            row["name"]: (
                str(row["type"] or "").upper(),
                not bool(row["notnull"]),
                bool(row["pk"]),
            )
            for row in table_info
        }
        if set(existing) == _LEGACY_CUSTOM_TABLE_COLUMNS:
            raise RuntimeError(
                f"legacy generic custom table schema is no longer supported: {physical_table_name}"
            )
        expected = self._expected_custom_table_column_map(resource)
        if set(existing) != set(expected):
            raise RuntimeError(
                f"custom table schema mismatch for {physical_table_name}: "
                f"expected_columns={sorted(expected)}, existing_columns={sorted(existing)}"
            )
        for column_name, (expected_type, expected_nullable, expected_pk) in expected.items():
            existing_type, existing_nullable, existing_pk = existing[column_name]
            if existing_type != expected_type or existing_nullable != expected_nullable or existing_pk != expected_pk:
                raise RuntimeError(
                    f"custom table column mismatch for {physical_table_name}.{column_name}: "
                    f"expected={(expected_type, expected_nullable, expected_pk)}, "
                    f"existing={(existing_type, existing_nullable, existing_pk)}"
                )

    def _ensure_custom_table_indexes_with_conn(self, conn, resource: dict[str, Any]) -> None:
        physical_table_name = resource["physical_table_name"]
        table_identifier = _quote_identifier(physical_table_name)
        normalized_indexes = _normalize_custom_table_indexes(
            resource.get("indexes") or {},
            column_names={column["name"] for column in self._custom_table_schema_columns(resource)},
        )
        for index_name, columns in normalized_indexes.items():
            rendered_columns = ", ".join(_quote_identifier(column) for column in columns)
            conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {_quote_identifier(f'idx_{physical_table_name}_{index_name}')}
                ON {table_identifier}({rendered_columns})
                """
            )

    def _ensure_custom_table_with_conn(self, conn, resource: dict[str, Any]) -> None:
        physical_table_name = resource["physical_table_name"]
        table_identifier = _quote_identifier(physical_table_name)
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (physical_table_name,),
        ).fetchone()
        if not table_exists:
            column_defs: list[str] = []
            record_key_field = resource.get("record_key_field")
            for column in self._custom_table_schema_columns(resource):
                sqlite_type = _CUSTOM_TABLE_TYPE_MAP[column["type"]]
                rendered = f"{_quote_identifier(column['name'])} {sqlite_type}"
                if column["name"] == record_key_field:
                    rendered += " NOT NULL PRIMARY KEY"
                elif not column["nullable"]:
                    rendered += " NOT NULL"
                column_defs.append(rendered)
            column_defs.extend(
                [
                    "created_at INTEGER DEFAULT (strftime('%s', 'now'))",
                    "updated_at INTEGER DEFAULT (strftime('%s', 'now'))",
                ]
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_identifier} (
                    {", ".join(column_defs)}
                )
                """
            )
        self._assert_custom_table_matches_resource(conn, resource)
        self._ensure_custom_table_indexes_with_conn(conn, resource)

    def _validate_db_view_resource_refs(self, sql_template: str) -> list[str]:
        placeholders = _DB_VIEW_RESOURCE_PLACEHOLDER_RE.findall(sql_template)
        if not placeholders:
            raise ValueError("db view select_sql_template must reference at least one {{resource:<id>}} placeholder")
        for token in _DB_VIEW_SQL_REF_RE.findall(sql_template):
            if not _DB_VIEW_RESOURCE_PLACEHOLDER_RE.fullmatch(token):
                raise ValueError("db view table references must use {{resource:<resource_id>}} placeholders")
        return placeholders

    def _resolve_db_view_sql_with_conn(
        self,
        conn,
        module_name: str,
        *,
        source_resource_ids: list[str],
        select_sql_template: str,
    ) -> str:
        placeholders = self._validate_db_view_resource_refs(select_sql_template)
        if set(placeholders) != set(source_resource_ids):
            raise ValueError(
                "db view placeholders must exactly match source_resource_ids"
            )

        resolved_sql = select_sql_template
        for resource_id in source_resource_ids:
            resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
            if resource is None:
                raise ValueError(f"db view source resource not found: {resource_id}")
            if resource["storage_mode"] != "custom_table":
                raise ValueError(f"db view source resources must be custom_table: {resource_id}")
            self._ensure_custom_table_with_conn(conn, resource)
            resolved_sql = resolved_sql.replace(
                f"{{{{resource:{resource_id}}}}}",
                _quote_identifier(resource["physical_table_name"]),
            )
        return resolved_sql

    def _validate_db_view_columns_with_conn(
        self,
        conn,
        *,
        temp_view_name: str,
        columns: list[dict[str, Any]],
    ) -> None:
        cursor = conn.execute(
            f"SELECT * FROM {_quote_identifier(temp_view_name)} LIMIT 0"
        )
        actual_columns = [str(item[0]) for item in cursor.description or []]
        expected_columns = [column["name"] for column in columns]
        if actual_columns != expected_columns:
            raise ValueError(
                f"db view declared columns do not match query output: expected={expected_columns}, actual={actual_columns}"
            )

    def _recreate_db_view_with_conn(
        self,
        conn,
        *,
        physical_view_name: str,
        resolved_sql: str,
        columns: list[dict[str, Any]],
    ) -> None:
        temp_view_name = _validate_snake_case_identifier(f"tmp_{uuid.uuid4().hex[:20]}")
        temp_identifier = _quote_identifier(temp_view_name)
        conn.execute(f"DROP VIEW IF EXISTS {temp_identifier}")
        try:
            conn.execute(f"CREATE TEMP VIEW {temp_identifier} AS {resolved_sql}")
            self._validate_db_view_columns_with_conn(conn, temp_view_name=temp_view_name, columns=columns)
        finally:
            conn.execute(f"DROP VIEW IF EXISTS {temp_identifier}")

        view_identifier = _quote_identifier(physical_view_name)
        conn.execute(f"DROP VIEW IF EXISTS {view_identifier}")
        conn.execute(f"CREATE VIEW {view_identifier} AS {resolved_sql}")

    def _write_db_view_row_with_conn(
        self,
        conn,
        module_name: str,
        view_id: str,
        *,
        view_kind: str,
        source_resource_ids: list[str],
        select_sql_template: str,
        columns: list[dict[str, Any]],
        cleanup_policy: str,
        schema_version: int,
        now: int,
    ) -> dict[str, Any]:
        normalized_view_kind = _validate_db_view_kind(view_kind)
        normalized_source_resource_ids = _normalize_db_view_source_resource_ids(source_resource_ids)
        normalized_sql = _normalize_db_view_sql_template(select_sql_template)
        normalized_columns = _normalize_db_view_columns(columns)
        normalized_cleanup_policy = _validate_db_view_cleanup_policy(cleanup_policy)
        normalized_schema_version = _normalize_db_view_schema_version(schema_version)
        physical_view_name = _db_view_name(module_name, view_id)
        resolved_sql = self._resolve_db_view_sql_with_conn(
            conn,
            module_name,
            source_resource_ids=normalized_source_resource_ids,
            select_sql_template=normalized_sql,
        )
        self._recreate_db_view_with_conn(
            conn,
            physical_view_name=physical_view_name,
            resolved_sql=resolved_sql,
            columns=normalized_columns,
        )
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
            ON CONFLICT(module_name, view_id) DO UPDATE SET
                view_kind = excluded.view_kind,
                physical_view_name = excluded.physical_view_name,
                source_resource_ids_json = excluded.source_resource_ids_json,
                select_sql_template = excluded.select_sql_template,
                columns_json = excluded.columns_json,
                schema_version = excluded.schema_version,
                cleanup_policy = excluded.cleanup_policy,
                updated_at = excluded.updated_at
            """,
            (
                module_name,
                view_id,
                normalized_view_kind,
                physical_view_name,
                json.dumps(normalized_source_resource_ids, ensure_ascii=False),
                normalized_sql,
                json.dumps(normalized_columns, ensure_ascii=False),
                normalized_schema_version,
                normalized_cleanup_policy,
                now,
                now,
            ),
        )
        manifest = self._read_db_view_row_with_conn(conn, module_name, view_id)
        if manifest is None:
            raise RuntimeError("module db view registration failed")
        return manifest

    def _ensure_db_view_with_conn(self, conn, module_name: str, view_id: str) -> dict[str, Any]:
        manifest = self._read_db_view_row_with_conn(conn, module_name, view_id)
        if manifest is None:
            raise ValueError(f"db view not found: {view_id}")
        view_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'view' AND name = ?
            """,
            (manifest["physical_view_name"],),
        ).fetchone()
        if not view_exists:
            self._write_db_view_row_with_conn(
                conn,
                module_name,
                view_id,
                view_kind=manifest["view_kind"],
                source_resource_ids=manifest["source_resource_ids"],
                select_sql_template=manifest["select_sql_template"],
                columns=manifest["columns"],
                cleanup_policy=manifest["cleanup_policy"],
                schema_version=manifest["schema_version"],
                now=int(time.time()),
            )
            manifest = self._read_db_view_row_with_conn(conn, module_name, view_id)
            if manifest is None:
                raise ValueError(f"db view not found: {view_id}")
        return manifest

    def _write_custom_table_rows_with_conn(
        self,
        conn,
        resource: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> None:
        physical_table_name = resource["physical_table_name"]
        table_identifier = _quote_identifier(physical_table_name)
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        column_names = [column["name"] for column in column_defs]
        record_key_field = resource["record_key_field"]
        existing_rows = conn.execute(
            f"SELECT {_quote_identifier(record_key_field)}, created_at FROM {table_identifier}"
        ).fetchall()
        existing_created_at = {
            _normalize_text(row[record_key_field]): int(row["created_at"])
            for row in existing_rows
            if row["created_at"] is not None and _normalize_text(row[record_key_field]) is not None
        }
        prepared_rows: list[tuple[Any, ...]] = []
        seen_keys: set[str] = set()
        for record_index, original_record in enumerate(records):
            record = dict(original_record)
            record_key = _record_key_for_write(
                record,
                record_index,
                record_key_field=record_key_field,
                require_key=True,
            )
            if record_key is None:
                raise ValueError("custom table records require a record_key")
            if record_key in seen_keys:
                raise ValueError(f"duplicate custom table record_key: {record_key}")
            seen_keys.add(record_key)
            if record_key_field not in record:
                record[record_key_field] = record_key

            unexpected_fields = sorted(set(record) - set(column_names))
            if unexpected_fields:
                raise ValueError(
                    f"custom table records contain undefined columns for {physical_table_name}: "
                    f"{', '.join(unexpected_fields)}"
                )

            row_values: list[Any] = []
            for column in column_defs:
                column_name = column["name"]
                if column_name not in record:
                    if not column["nullable"]:
                        raise ValueError(
                            f"custom table records missing required column {column_name} for {physical_table_name}"
                        )
                    row_values.append(None)
                    continue
                row_values.append(
                    _sqlite_value_for_custom_table_column(record[column_name], column_type=column["type"])
                )
            prepared_rows.append(
                tuple(
                    row_values
                    + [
                        existing_created_at.get(record_key, now),
                        now,
                    ]
                )
            )
        conn.execute(f"DELETE FROM {table_identifier}")
        if prepared_rows:
            insert_columns = ", ".join(
                [_quote_identifier(column) for column in column_names] + ["created_at", "updated_at"]
            )
            insert_params = ", ".join(["?"] * (len(column_names) + 2))
            conn.executemany(
                f"""
                INSERT INTO {table_identifier} ({insert_columns})
                VALUES ({insert_params})
                """,
                prepared_rows,
            )

    def _read_custom_table_rows_with_conn(
        self,
        conn,
        resource: dict[str, Any],
    ) -> list[dict[str, Any]]:
        table_identifier = _quote_identifier(resource["physical_table_name"])
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        select_columns = ", ".join(_quote_identifier(column["name"]) for column in column_defs)
        rows = conn.execute(
            f"""
            SELECT {select_columns}
            FROM {table_identifier}
            ORDER BY rowid ASC
            """
        ).fetchall()
        rendered_rows: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] = {}
            for column in column_defs:
                payload[column["name"]] = _python_value_for_custom_table_column(
                    row[column["name"]],
                    column_type=column["type"],
                )
            rendered_rows.append(payload)
        return rendered_rows

    def _write_dataset_row(self, module_name: str, dataset_name: str, records: list[dict[str, Any]]) -> bool:
        now = int(time.time())
        with get_connection(DATA_DB) as conn:
            resource = self._ensure_managed_dataset_resource_with_conn(
                conn,
                module_name,
                dataset_name,
                now=now,
            )
            if resource["storage_mode"] == "custom_table":
                self._write_custom_table_rows_with_conn(conn, resource, records, now=now)
            else:
                self._write_managed_dataset_rows_with_conn(
                    conn,
                    module_name,
                    resource["logical_name"],
                    records,
                    record_key_field=resource["record_key_field"],
                    now=now,
                )
        return True

    def _read_dataset_row(self, module_name: str, dataset_name: str) -> list[dict[str, Any]] | None:
        with get_connection(DATA_DB) as conn:
            resource = self._read_resource_row_with_conn(conn, module_name, dataset_name)
            if resource is None:
                return self._read_managed_dataset_rows_with_conn(conn, module_name, dataset_name)
            if resource["storage_mode"] == "custom_table":
                return self._read_custom_table_rows_with_conn(conn, resource)
            return self._read_managed_dataset_rows_with_conn(conn, module_name, resource["logical_name"])

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

    def _write_page_row(self, module_name: str, page_id: str, schema: dict[str, Any]) -> bool:
        now = int(time.time())
        with get_connection(DATA_DB) as conn:
            self._write_page_row_with_conn(conn, module_name, page_id, schema, now=now)
        return True

    def _write_page_row_with_conn(
        self,
        conn,
        module_name: str,
        page_id: str,
        schema: dict[str, Any],
        *,
        now: int,
    ) -> None:
        conn.execute(
            """
            INSERT INTO module_pages (module_name, page_id, schema_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(module_name, page_id) DO UPDATE SET
                schema_json = excluded.schema_json,
                updated_at = excluded.updated_at
            """,
            (
                module_name,
                page_id,
                json.dumps(schema, ensure_ascii=False),
                now,
                now,
            ),
        )

    def _read_page_row(self, module_name: str, page_id: str) -> dict[str, Any] | None:
        with get_connection(DATA_DB) as conn:
            row = conn.execute(
                """
                SELECT schema_json
                FROM module_pages
                WHERE module_name = ? AND page_id = ?
                """,
                (module_name, page_id),
            ).fetchone()
        if not row:
            return None
        return _normalize_schema(json.loads(row["schema_json"]))

    def list_data_resources(self, module_name: str) -> list[dict[str, Any]]:
        with get_connection(DATA_DB) as conn:
            return self._list_resource_rows_with_conn(conn, module_name)

    def list_db_views(self, module_name: str) -> list[dict[str, Any]]:
        with get_connection(DATA_DB) as conn:
            return self._list_db_view_rows_with_conn(conn, module_name)

    def query_db_view(
        self,
        module_name: str,
        view_id: str,
        *,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        normalized_filters = dict(filters or {})
        normalized_sort = _normalize_db_view_sort(sort or [])
        normalized_limit = max(int(limit), 1)
        normalized_offset = max(int(offset), 0)

        with get_connection(DATA_DB) as conn:
            manifest = self._ensure_db_view_with_conn(conn, module_name, view_id)
            physical_view_name = manifest["physical_view_name"]
            view_identifier = _quote_identifier(physical_view_name)
            column_defs = manifest["columns"]
            column_map = {column["name"]: column for column in column_defs}
            rendered_columns = ", ".join(_quote_identifier(column["name"]) for column in column_defs)

            where_clauses: list[str] = []
            params: list[Any] = []
            for field, value in normalized_filters.items():
                normalized_field = _validate_snake_case_identifier(str(field))
                column = column_map.get(normalized_field)
                if column is None:
                    raise ValueError(f"db view filter field not found: {normalized_field}")
                if not column.get("filterable"):
                    raise ValueError(f"db view field is not filterable: {normalized_field}")
                if value is None:
                    where_clauses.append(f"{_quote_identifier(normalized_field)} IS NULL")
                    continue
                where_clauses.append(f"{_quote_identifier(normalized_field)} = ?")
                params.append(value)

            order_by = ""
            if normalized_sort:
                order_parts: list[str] = []
                for item in normalized_sort:
                    column = column_map.get(item["field"])
                    if column is None:
                        raise ValueError(f"db view sort field not found: {item['field']}")
                    if not column.get("sortable"):
                        raise ValueError(f"db view field is not sortable: {item['field']}")
                    order_parts.append(f"{_quote_identifier(item['field'])} {item['direction'].upper()}")
                order_by = f" ORDER BY {', '.join(order_parts)}"

            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            rows = conn.execute(
                f"""
                SELECT {rendered_columns}
                FROM {view_identifier}
                {where_sql}
                {order_by}
                LIMIT ? OFFSET ?
                """,
                tuple(params + [normalized_limit, normalized_offset]),
            ).fetchall()
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS total FROM {view_identifier}{where_sql}",
                    tuple(params),
                ).fetchone()["total"]
            )

        rendered_rows: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] = {}
            for column in column_defs:
                payload[column["name"]] = _python_value_for_custom_table_column(
                    row[column["name"]],
                    column_type=column["type"],
                )
            rendered_rows.append(payload)
        return {
            "rows": rendered_rows,
            "total": total,
            "limit": normalized_limit,
            "offset": normalized_offset,
        }

    def _list_custom_table_records_with_conn(
        self,
        conn,
        resource: dict[str, Any],
        *,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        column_map = {column["name"]: column for column in column_defs}
        table_identifier = _quote_identifier(resource["physical_table_name"])
        rendered_columns = ", ".join(_quote_identifier(column["name"]) for column in column_defs)

        where_clauses: list[str] = []
        params: list[Any] = []
        for field, value in dict(filters or {}).items():
            normalized_field = _validate_snake_case_identifier(str(field))
            if normalized_field not in column_map:
                raise ValueError(f"resource filter field not found: {normalized_field}")
            if value is None:
                where_clauses.append(f"{_quote_identifier(normalized_field)} IS NULL")
            else:
                where_clauses.append(f"{_quote_identifier(normalized_field)} = ?")
                params.append(value)

        order_by = ""
        normalized_sort = _normalize_db_view_sort(sort or [])
        if normalized_sort:
            order_by = " ORDER BY " + ", ".join(
                f"{_quote_identifier(item['field'])} {item['direction'].upper()}"
                for item in normalized_sort
            )
        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        rows = conn.execute(
            f"""
            SELECT {rendered_columns}
            FROM {table_identifier}
            {where_sql}
            {order_by}
            LIMIT ? OFFSET ?
            """,
            tuple(params + [max(int(limit), 1), max(int(offset), 0)]),
        ).fetchall()
        rendered: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] = {}
            for column in column_defs:
                payload[column["name"]] = _python_value_for_custom_table_column(
                    row[column["name"]],
                    column_type=column["type"],
                )
            rendered.append(payload)
        return rendered

    def get_record(self, module_name: str, resource_id: str, key: Any) -> dict[str, Any] | None:
        normalized_key = _normalize_text(key)
        if normalized_key is None:
            return None
        with get_connection(DATA_DB) as conn:
            resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
            if resource is None:
                rows = self._read_managed_dataset_rows_with_conn(conn, module_name, resource_id)
                for row in rows:
                    row_key = _normalize_text(row.get("record_key") or row.get("id"))
                    if row_key == normalized_key:
                        return row
                return None

            record_key_field = resource.get("record_key_field") or "id"
            if resource["storage_mode"] == "custom_table":
                rows = self._list_custom_table_records_with_conn(
                    conn,
                    resource,
                    filters={record_key_field: normalized_key},
                    limit=1,
                    offset=0,
                )
                return rows[0] if rows else None

            rows = self._read_managed_dataset_rows_with_conn(conn, module_name, resource["logical_name"])
            for row in rows:
                row_key = _normalize_text(row.get(record_key_field) or row.get("record_key") or row.get("id"))
                if row_key == normalized_key:
                    return row
        return None

    def list_records(
        self,
        module_name: str,
        resource_id: str,
        *,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with get_connection(DATA_DB) as conn:
            resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
            if resource is None:
                rows = self._read_managed_dataset_rows_with_conn(conn, module_name, resource_id)
                return _apply_record_query(rows, filters=filters, sort=sort, limit=limit, offset=offset)
            if resource["storage_mode"] == "custom_table":
                return self._list_custom_table_records_with_conn(
                    conn,
                    resource,
                    filters=filters,
                    sort=sort,
                    limit=limit,
                    offset=offset,
                )
            rows = self._read_managed_dataset_rows_with_conn(conn, module_name, resource["logical_name"])
            return _apply_record_query(rows, filters=filters, sort=sort, limit=limit, offset=offset)

    def run_registered_query(
        self,
        module_name: str,
        *,
        source_resource_ids: list[str],
        sql_template: str,
        columns: list[dict[str, Any]],
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_sql = _normalize_db_view_sql_template(sql_template)
        normalized_columns = _normalize_db_view_columns(columns)
        normalized_params = dict(params or {})

        with get_connection(DATA_DB) as conn:
            resolved_sql = self._resolve_db_view_sql_with_conn(
                conn,
                module_name,
                source_resource_ids=source_resource_ids,
                select_sql_template=normalized_sql,
            )
            cursor = conn.execute(resolved_sql, normalized_params)
            actual_columns = [str(item[0]) for item in cursor.description or []]
            expected_columns = [column["name"] for column in normalized_columns]
            if actual_columns != expected_columns:
                raise ValueError(
                    f"registered query columns do not match query output: expected={expected_columns}, actual={actual_columns}"
                )
            rows = cursor.fetchall()

        rendered_rows: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] = {}
            for column in normalized_columns:
                payload[column["name"]] = _python_value_for_custom_table_column(
                    row[column["name"]],
                    column_type=column["type"],
                )
            rendered_rows.append(payload)
        return rendered_rows

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

    def read_page_schema(self, module_name: str, page_id: str) -> dict[str, Any]:
        schema = self._read_page_row(module_name, page_id)
        return schema if schema is not None else {}

    def write_page_schema(self, module_name: str, page_id: str, schema: dict[str, Any]) -> bool:
        return self._write_page_row(module_name, page_id, _normalize_schema(schema))

    def sync_manifest_data(self, module_name: str, module_root, manifest_data: dict[str, Any]) -> bool:
        module_root_path = getattr(module_root, "resolve", None)
        if callable(module_root_path):
            module_root = module_root.resolve()

        changed = False
        now = int(time.time())
        resource_ids = {item["resource_id"] for item in manifest_data["resources"]}
        view_ids = {item["view_id"] for item in manifest_data["views"]}

        with get_connection(DATA_DB) as conn:
            for resource in manifest_data["resources"]:
                current = self._read_resource_row_with_conn(conn, module_name, resource["resource_id"])
                updated = self._write_resource_row_with_conn(
                    conn,
                    module_name,
                    resource["resource_id"],
                    storage_mode=resource["storage_mode"],
                    logical_name=resource["resource_id"],
                    physical_table_name=(
                        _custom_table_name(module_name, resource["resource_id"])
                        if resource["storage_mode"] == "custom_table"
                        else "module_datasets"
                    ),
                    record_key_field=resource["record_key_field"],
                    schema=resource["schema"],
                    indexes=resource["indexes"],
                    cleanup_policy=resource["cleanup_policy"],
                    now=now,
                )
                if resource["storage_mode"] == "custom_table":
                    self._ensure_custom_table_with_conn(conn, updated)
                changed = current != updated or changed

            existing_views = self._list_db_view_rows_with_conn(conn, module_name)
            for db_view in existing_views:
                if db_view["view_id"] in view_ids:
                    continue
                physical_view_name = db_view["physical_view_name"]
                if db_view.get("cleanup_policy") != "keep":
                    conn.execute(f"DROP VIEW IF EXISTS {_quote_identifier(physical_view_name)}")
                cursor = conn.execute(
                    "DELETE FROM module_db_views WHERE module_name = ? AND view_id = ?",
                    (module_name, db_view["view_id"]),
                )
                changed = bool(cursor.rowcount) or changed

            existing_resources = self._list_resource_rows_with_conn(conn, module_name)
            for resource in existing_resources:
                if resource["resource_id"] in resource_ids:
                    continue
                if resource["storage_mode"] == "custom_table":
                    physical_table_name = resource["physical_table_name"]
                    if resource["cleanup_policy"] == "drop_table":
                        conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(physical_table_name)}")
                    elif resource["cleanup_policy"] == "delete_rows":
                        conn.execute(f"DELETE FROM {_quote_identifier(physical_table_name)}")
                else:
                    conn.execute(
                        "DELETE FROM module_datasets WHERE module_name = ? AND dataset_name = ?",
                        (module_name, resource["logical_name"]),
                    )
                    conn.execute(
                        "DELETE FROM module_dataset_manifests WHERE module_name = ? AND dataset_name = ?",
                        (module_name, resource["logical_name"]),
                    )
                cursor = conn.execute(
                    "DELETE FROM module_data_resources WHERE module_name = ? AND resource_id = ?",
                    (module_name, resource["resource_id"]),
                )
                changed = bool(cursor.rowcount) or changed

            for view in manifest_data["views"]:
                sql = load_sql_file(module_root, view["sql_file"], expected_prefix="data/sql/views/")
                validate_resource_sql(
                    sql,
                    source_resource_ids=view["source_resource_ids"],
                    owner_label=f"data.views[{view['view_id']}]",
                )
                current = self._read_db_view_row_with_conn(conn, module_name, view["view_id"])
                updated = self._write_db_view_row_with_conn(
                    conn,
                    module_name,
                    view["view_id"],
                    view_kind=view["view_kind"],
                    source_resource_ids=view["source_resource_ids"],
                    select_sql_template=sql,
                    columns=view["columns"],
                    cleanup_policy=view["cleanup_policy"],
                    schema_version=view["schema_version"],
                    now=now,
                )
                changed = current != updated or changed

            for seed in manifest_data["seeds"]:
                records = validate_seed_file(module_root, seed["file"])
                current_resource = self._read_resource_row_with_conn(conn, module_name, seed["resource_id"])
                if current_resource and current_resource["storage_mode"] == "custom_table":
                    current_rows = self._list_custom_table_records_with_conn(
                        conn,
                        current_resource,
                        limit=1,
                        offset=0,
                    )
                else:
                    logical_name = current_resource["logical_name"] if current_resource else seed["resource_id"]
                    current_rows = _apply_record_query(
                        self._read_managed_dataset_rows_with_conn(conn, module_name, logical_name),
                        limit=1,
                        offset=0,
                )
                if seed["mode"] == "replace_if_empty" and current_rows:
                    continue
                target_resource = current_resource or self._read_resource_row_with_conn(conn, module_name, seed["resource_id"])
                if target_resource is None:
                    raise ValueError(f"seed target resource not found: {seed['resource_id']}")
                if target_resource["storage_mode"] == "custom_table":
                    self._write_custom_table_rows_with_conn(conn, target_resource, records, now=now)
                else:
                    self._write_managed_dataset_rows_with_conn(
                        conn,
                        module_name,
                        target_resource["logical_name"],
                        records,
                        record_key_field=target_resource["record_key_field"],
                        now=now,
                    )
                changed = bool(records) or changed

        return changed

    def replace_declared_ui(
        self,
        module_name: str,
        *,
        page_schemas: dict[str, dict[str, Any]],
    ) -> bool:
        normalized_pages = {
            str(page_id): _normalize_schema(schema)
            for page_id, schema in dict(page_schemas or {}).items()
        }

        changed = bool(normalized_pages)
        now = int(time.time())
        with get_connection(DATA_DB) as conn:
            cursor = conn.execute(
                "DELETE FROM module_pages WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

            for page_id, schema in normalized_pages.items():
                self._write_page_row_with_conn(conn, module_name, page_id, schema, now=now)

        return changed

    def clear_module_data(self, module_name: str) -> bool:
        changed = False

        with get_connection(DATA_DB) as conn:
            for db_view in self._list_db_view_rows_with_conn(conn, module_name):
                physical_view_name = db_view["physical_view_name"]
                cleanup_policy = str(db_view.get("cleanup_policy") or "")
                if cleanup_policy == "keep":
                    continue
                existing_view = conn.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'view' AND name = ?
                    """,
                    (physical_view_name,),
                ).fetchone()
                identifier = _quote_identifier(physical_view_name)
                conn.execute(f"DROP VIEW IF EXISTS {identifier}")
                changed = bool(existing_view) or changed

            for resource in self._list_resource_rows_with_conn(conn, module_name):
                if resource["storage_mode"] == "custom_table":
                    physical_table_name = resource["physical_table_name"]
                    table_identifier = _quote_identifier(physical_table_name)
                    table_exists = conn.execute(
                        """
                        SELECT 1
                        FROM sqlite_master
                        WHERE type = 'table' AND name = ?
                        """,
                        (physical_table_name,),
                    ).fetchone()
                    if resource["cleanup_policy"] == "drop_table":
                        conn.execute(f"DROP TABLE IF EXISTS {table_identifier}")
                        changed = bool(table_exists) or changed
                    elif resource["cleanup_policy"] == "delete_rows" and table_exists:
                        cursor = conn.execute(f"DELETE FROM {table_identifier}")
                        changed = bool(cursor.rowcount) or changed
                    continue

                cursor = conn.execute(
                    """
                    DELETE FROM module_datasets
                    WHERE module_name = ? AND dataset_name = ?
                    """,
                    (module_name, resource["logical_name"]),
                )
                changed = bool(cursor.rowcount) or changed

                cursor = conn.execute(
                    """
                    DELETE FROM module_dataset_manifests
                    WHERE module_name = ? AND dataset_name = ?
                    """,
                    (module_name, resource["logical_name"]),
                )
                changed = bool(cursor.rowcount) or changed

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
                "DELETE FROM module_data_resources WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

            cursor = conn.execute(
                "DELETE FROM module_db_views WHERE module_name = ?",
                (module_name,),
            )
            changed = bool(cursor.rowcount) or changed

            cursor = conn.execute(
                "DELETE FROM module_pages WHERE module_name = ?",
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
