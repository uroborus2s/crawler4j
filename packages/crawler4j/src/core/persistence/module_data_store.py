"""模块业务数据与数据表元数据存储。"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from typing import Any

from src.core.mms.data_contract import load_sql_file, validate_resource_sql, validate_seed_file
from src.core.persistence.database import DATA_DB, get_connection
from src.core.persistence.write_coordinator import get_db_write_coordinator

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


def _execute_with_read_authorizer(
    conn,
    sql: str,
    params: Any = (),
    *,
    allowed_tables: set[str],
):
    denied_table: list[str] = []

    def authorize(action_code, arg1, arg2, db_name, trigger_name):
        del arg2, db_name, trigger_name
        if action_code == sqlite3.SQLITE_READ and arg1 not in allowed_tables:
            denied_table.append(str(arg1 or ""))
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(authorize)
    try:
        return conn.execute(sql, params)
    except sqlite3.DatabaseError as exc:
        if denied_table:
            raise ValueError(f"SQL 只能读取已声明的数据资源: {denied_table[0]}") from exc
        raise
    finally:
        conn.set_authorizer(None)


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _normalize_records_for_write(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError("resource records must be a list of objects")

    records: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"resource records[{index}] must be an object")
        records.append(dict(item))
    return records


def _normalize_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _normalize_text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


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


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _normalize_timestamp(raw: Any) -> int:
    if raw is None:
        return int(time.time())
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(time.time())


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


def _record_json_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    payload.pop("run_status", None)
    payload.pop("record_status", None)
    return payload


def _record_from_storage_row(row, *, include_system_fields: bool = False) -> dict[str, Any]:
    record = _normalize_records([json.loads(row["record_json"])])
    payload = record[0] if record else {}
    record_key = _normalize_text(row["record_key"])
    if record_key is not None:
        payload.setdefault("record_key", record_key)
    payload["run_status"] = _normalize_text(row["run_status"]) or _DEFAULT_RUN_STATUS
    payload["record_status"] = _normalize_text(row["record_status"]) or _DEFAULT_RECORD_STATUS
    if include_system_fields:
        payload["created_at"] = row["created_at"]
        payload["updated_at"] = row["updated_at"]
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


def _normalize_plan_where(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("query plan where must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"query plan where[{index}] must be an object")
        field = _validate_snake_case_identifier(str(item.get("field") or ""))
        op = str(item.get("op") or "eq").strip().lower()
        if op not in {"eq", "in", "gt", "gte", "lt", "lte", "between", "like", "is_null"}:
            raise ValueError(f"unsupported query filter op: {op}")
        payload = {"field": field, "op": op}
        if op != "is_null":
            payload["value"] = item.get("value")
        normalized.append(payload)
    return normalized


def _normalize_plan_limit(raw: Any) -> int:
    if raw in (None, ""):
        return 100
    value = int(raw)
    if value < 1:
        raise ValueError("query plan limit must be >= 1")
    return value


def _normalize_plan_offset(raw: Any) -> int:
    if raw in (None, ""):
        return 0
    value = int(raw)
    if value < 0:
        raise ValueError("query plan offset must be >= 0")
    return value


def _normalize_write_fields(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("write fields must be a non-empty object")
    return {
        _validate_snake_case_identifier(str(field)): value
        for field, value in raw.items()
    }


def _render_custom_table_where_clause(
    column_map: dict[str, dict[str, Any]],
    where: Any,
    *,
    require_where: bool,
) -> tuple[str, list[Any]]:
    normalized_where = _normalize_plan_where(where)
    if require_where and not normalized_where:
        raise ValueError("write where must not be empty")

    clauses: list[str] = []
    params: list[Any] = []
    for item in normalized_where:
        field = item["field"]
        column = column_map.get(field)
        if column is None:
            raise ValueError(f"write where field not found: {field}")
        field_sql = _quote_identifier(field)
        op = item["op"]
        if op == "is_null":
            clauses.append(f"{field_sql} IS NULL")
        elif op == "eq":
            clauses.append(f"{field_sql} = ?")
            params.append(_sqlite_value_for_custom_table_column(item.get("value"), column_type=column["type"]))
        elif op == "in":
            values = list(item.get("value") or [])
            if not values:
                clauses.append("1 = 0")
            else:
                clauses.append(f"{field_sql} IN ({', '.join(['?'] * len(values))})")
                params.extend(
                    _sqlite_value_for_custom_table_column(value, column_type=column["type"])
                    for value in values
                )
        elif op == "between":
            values = list(item.get("value") or [])
            if len(values) != 2:
                raise ValueError("between filter value must contain two items")
            clauses.append(f"{field_sql} BETWEEN ? AND ?")
            params.extend(
                _sqlite_value_for_custom_table_column(value, column_type=column["type"])
                for value in values
            )
        else:
            sql_op = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "like": "LIKE"}[op]
            clauses.append(f"{field_sql} {sql_op} ?")
            params.append(_sqlite_value_for_custom_table_column(item.get("value"), column_type=column["type"]))

    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


def _plan_has_aggregate(select_items: list[dict[str, Any]]) -> bool:
    return any(item.get("kind") == "aggregate" for item in select_items)


def _filter_record_value(current: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return current == expected
    if op == "in":
        return current in list(expected or [])
    if op == "gt":
        return current is not None and current > expected
    if op == "gte":
        return current is not None and current >= expected
    if op == "lt":
        return current is not None and current < expected
    if op == "lte":
        return current is not None and current <= expected
    if op == "between":
        bounds = list(expected or [])
        if len(bounds) != 2:
            raise ValueError("between filter value must contain two items")
        return current is not None and bounds[0] <= current <= bounds[1]
    if op == "like":
        return expected is not None and str(expected) in str(current or "")
    if op == "is_null":
        return current is None
    raise ValueError(f"unsupported query filter op: {op}")


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


def _resource_write_lock_key(module_name: str, resource_id: str) -> str:
    return f"data:{module_name}:{resource_id}"


def _audit_write_lock_key(module_name: str, dataset_name: str) -> str:
    return f"audit:{module_name}:{dataset_name}"


def _module_write_lock_key(module_name: str) -> str:
    return f"module:{module_name}"


def _page_write_lock_key(module_name: str, page_id: str) -> str:
    return f"page:{module_name}:{page_id}"


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

    def _require_resource_row_with_conn(self, conn, module_name: str, resource_id: str) -> dict[str, Any]:
        resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
        if resource is None:
            raise ValueError(f"未注册的数据资源: {resource_id}")
        return resource

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
        row = conn.execute(
            """
            SELECT MIN(created_at) AS created_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            """,
            (module_name, dataset_name),
        ).fetchone()
        created_at = int(row["created_at"]) if row and row["created_at"] is not None else None
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
                        json.dumps(_record_json_payload(record), ensure_ascii=False),
                        created_at,
                        now,
                    )
                    for record_index, record in enumerate(normalized_records)
                ],
            )

    def _read_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        dataset_name: str,
        *,
        include_system_fields: bool = False,
    ) -> list[dict[str, Any]] | None:
        rows = conn.execute(
            """
            SELECT record_key, run_status, record_status, record_json, created_at, updated_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            (module_name, dataset_name),
        ).fetchall()
        if not rows:
            return None
        return [_record_from_storage_row(row, include_system_fields=include_system_fields) for row in rows]

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
    ) -> tuple[str, set[str]]:
        placeholders = self._validate_db_view_resource_refs(select_sql_template)
        if set(placeholders) != set(source_resource_ids):
            raise ValueError(
                "db view placeholders must exactly match source_resource_ids"
            )

        resolved_sql = select_sql_template
        allowed_tables: set[str] = set()
        for resource_id in source_resource_ids:
            resource = self._read_resource_row_with_conn(conn, module_name, resource_id)
            if resource is None:
                raise ValueError(f"db view source resource not found: {resource_id}")
            if resource["storage_mode"] != "custom_table":
                raise ValueError(f"db view source resources must be custom_table: {resource_id}")
            self._ensure_custom_table_with_conn(conn, resource)
            allowed_tables.add(resource["physical_table_name"])
            resolved_sql = resolved_sql.replace(
                f"{{{{resource:{resource_id}}}}}",
                _quote_identifier(resource["physical_table_name"]),
            )
        return resolved_sql, allowed_tables

    def _validate_db_view_columns_with_conn(
        self,
        conn,
        *,
        temp_view_name: str,
        columns: list[dict[str, Any]],
        allowed_tables: set[str],
    ) -> None:
        cursor = _execute_with_read_authorizer(
            conn,
            f"SELECT * FROM {_quote_identifier(temp_view_name)} LIMIT 0",
            allowed_tables=allowed_tables | {temp_view_name},
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
        allowed_tables: set[str],
    ) -> None:
        temp_view_name = _validate_snake_case_identifier(f"tmp_{uuid.uuid4().hex[:20]}")
        temp_identifier = _quote_identifier(temp_view_name)
        conn.execute(f"DROP VIEW IF EXISTS {temp_identifier}")
        try:
            conn.execute(f"CREATE TEMP VIEW {temp_identifier} AS {resolved_sql}")
            self._validate_db_view_columns_with_conn(
                conn,
                temp_view_name=temp_view_name,
                columns=columns,
                allowed_tables=allowed_tables,
            )
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
        resolved_sql, allowed_tables = self._resolve_db_view_sql_with_conn(
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
            allowed_tables=allowed_tables,
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

    def _upsert_custom_table_rows_with_conn(
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
        seen_keys: set[str] = set()
        prepared_rows: list[tuple[Any, ...]] = []
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
            prepared_rows.append(tuple(row_values + [now, now]))

        if not prepared_rows:
            return

        insert_columns = [_quote_identifier(column) for column in column_names] + ["created_at", "updated_at"]
        insert_params = ", ".join(["?"] * (len(column_names) + 2))
        update_columns = [
            f"{_quote_identifier(column)} = excluded.{_quote_identifier(column)}"
            for column in column_names
            if column != record_key_field
        ]
        update_columns.append("updated_at = excluded.updated_at")
        conn.executemany(
            f"""
            INSERT INTO {table_identifier} ({", ".join(insert_columns)})
            VALUES ({insert_params})
            ON CONFLICT({_quote_identifier(record_key_field)}) DO UPDATE SET
                {", ".join(update_columns)}
            """,
            prepared_rows,
        )

    def _update_custom_table_rows_with_conn(
        self,
        conn,
        resource: dict[str, Any],
        fields: dict[str, Any],
        *,
        where: Any,
        now: int,
    ) -> int:
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        column_map = {column["name"]: column for column in column_defs}
        record_key_field = resource["record_key_field"]
        normalized_fields = _normalize_write_fields(fields)
        if record_key_field in normalized_fields:
            raise ValueError(f"custom table record key cannot be updated: {record_key_field}")
        unexpected_fields = sorted(set(normalized_fields) - set(column_map))
        if unexpected_fields:
            raise ValueError(
                f"custom table update contains undefined columns for {resource['physical_table_name']}: "
                f"{', '.join(unexpected_fields)}"
            )

        assignments: list[str] = []
        params: list[Any] = []
        for field, value in normalized_fields.items():
            column = column_map[field]
            assignments.append(f"{_quote_identifier(field)} = ?")
            params.append(_sqlite_value_for_custom_table_column(value, column_type=column["type"]))
        assignments.append("updated_at = ?")
        params.append(now)
        where_sql, where_params = _render_custom_table_where_clause(column_map, where, require_where=True)
        table_identifier = _quote_identifier(resource["physical_table_name"])
        cursor = conn.execute(
            f"""
            UPDATE {table_identifier}
            SET {", ".join(assignments)}
            {where_sql}
            """,
            tuple(params + where_params),
        )
        return int(cursor.rowcount or 0)

    def _delete_custom_table_rows_with_conn(
        self,
        conn,
        resource: dict[str, Any],
        *,
        where: Any,
    ) -> int:
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        column_map = {column["name"]: column for column in column_defs}
        where_sql, where_params = _render_custom_table_where_clause(column_map, where, require_where=True)
        table_identifier = _quote_identifier(resource["physical_table_name"])
        cursor = conn.execute(
            f"""
            DELETE FROM {table_identifier}
            {where_sql}
            """,
            tuple(where_params),
        )
        return int(cursor.rowcount or 0)

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

    def _replace_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> bool:
        now = int(time.time())
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_resource_write_lock_key(module_name, resource_id)],
            operation=lambda conn: self._replace_resource_records_with_conn(
                conn,
                module_name,
                resource_id,
                records,
                now=now,
            ),
        )

    def _replace_resource_records_with_conn(
        self,
        conn,
        module_name: str,
        resource_id: str,
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> bool:
        resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
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

    def _upsert_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> bool:
        now = int(time.time())
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_resource_write_lock_key(module_name, resource_id)],
            operation=lambda conn: self._upsert_resource_records_with_conn(
                conn,
                module_name,
                resource_id,
                records,
                now=now,
            ),
        )

    def _upsert_resource_records_with_conn(
        self,
        conn,
        module_name: str,
        resource_id: str,
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> bool:
        resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
        if resource["storage_mode"] != "custom_table":
            raise ValueError(f"upsert only supports custom_table resources: {resource_id}")
        self._upsert_custom_table_rows_with_conn(conn, resource, records, now=now)
        return True

    def _update_resource_records(
        self,
        module_name: str,
        resource_id: str,
        fields: dict[str, Any],
        *,
        where: Any,
    ) -> int:
        now = int(time.time())
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_resource_write_lock_key(module_name, resource_id)],
            operation=lambda conn: self._update_resource_records_with_conn(
                conn,
                module_name,
                resource_id,
                fields,
                where=where,
                now=now,
            ),
        )

    def _update_resource_records_with_conn(
        self,
        conn,
        module_name: str,
        resource_id: str,
        fields: dict[str, Any],
        *,
        where: Any,
        now: int,
    ) -> int:
        resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
        if resource["storage_mode"] != "custom_table":
            raise ValueError(f"update_where only supports custom_table resources: {resource_id}")
        return self._update_custom_table_rows_with_conn(conn, resource, fields, where=where, now=now)

    def _delete_resource_records(self, module_name: str, resource_id: str, *, where: Any) -> int:
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_resource_write_lock_key(module_name, resource_id)],
            operation=lambda conn: self._delete_resource_records_with_conn(
                conn,
                module_name,
                resource_id,
                where=where,
            ),
        )

    def _delete_resource_records_with_conn(self, conn, module_name: str, resource_id: str, *, where: Any) -> int:
        resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
        if resource["storage_mode"] != "custom_table":
            raise ValueError(f"delete_where only supports custom_table resources: {resource_id}")
        return self._delete_custom_table_rows_with_conn(conn, resource, where=where)

    def _execute_write_operation_with_conn(
        self,
        conn,
        module_name: str,
        operation: dict[str, Any],
        *,
        now: int,
    ) -> Any:
        kind = str(operation.get("kind") or "")
        if kind == "replace_records":
            return self._replace_resource_records_with_conn(
                conn,
                module_name,
                str(operation.get("resource") or ""),
                _normalize_records_for_write(operation.get("records")),
                now=now,
            )
        if kind == "upsert_records":
            return self._upsert_resource_records_with_conn(
                conn,
                module_name,
                str(operation.get("resource") or ""),
                _normalize_records_for_write(operation.get("records")),
                now=now,
            )
        if kind == "update_records":
            return self._update_resource_records_with_conn(
                conn,
                module_name,
                str(operation.get("resource") or ""),
                _normalize_write_fields(operation.get("fields")),
                where=operation.get("where"),
                now=now,
            )
        if kind == "delete_records":
            return self._delete_resource_records_with_conn(
                conn,
                module_name,
                str(operation.get("resource") or ""),
                where=operation.get("where"),
            )
        if kind == "append_audit_event":
            return self._append_audit_event_row_with_conn(
                conn,
                module_name,
                str(operation.get("dataset") or ""),
                dict(operation.get("event") or {}),
            )
        raise ValueError(f"unsupported write operation kind: {kind}")

    def _execute_write_batch(self, module_name: str, operations: list[dict[str, Any]]) -> list[Any]:
        now = int(time.time())
        lock_keys = [_module_write_lock_key(module_name)]
        for operation in operations:
            lock_keys.extend(self._write_operation_lock_keys(module_name, operation))
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=lock_keys,
            operation=lambda conn: [
                self._execute_write_operation_with_conn(conn, module_name, operation, now=now)
                for operation in operations
            ],
        )

    def _write_operation_lock_keys(self, module_name: str, operation: dict[str, Any]) -> list[str]:
        kind = str(operation.get("kind") or "")
        if kind in {"replace_records", "upsert_records", "update_records", "delete_records"}:
            return [_resource_write_lock_key(module_name, str(operation.get("resource") or ""))]
        if kind == "append_audit_event":
            return [_audit_write_lock_key(module_name, str(operation.get("dataset") or ""))]
        return [_module_write_lock_key(module_name)]

    def _read_resource_records(self, module_name: str, resource_id: str) -> list[dict[str, Any]] | None:
        with get_connection(DATA_DB) as conn:
            resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
            if resource["storage_mode"] == "custom_table":
                return self._read_custom_table_rows_with_conn(conn, resource)
            return self._read_managed_dataset_rows_with_conn(conn, module_name, resource["logical_name"])

    def _append_audit_event_row(self, module_name: str, dataset_name: str, event: dict[str, Any]) -> str:
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_audit_write_lock_key(module_name, dataset_name)],
            operation=lambda conn: self._append_audit_event_row_with_conn(conn, module_name, dataset_name, event),
        )

    def _append_audit_event_row_with_conn(self, conn, module_name: str, dataset_name: str, event: dict[str, Any]) -> str:
        event_type = _normalize_text(event.get("event_type"))
        if event_type is None:
            raise ValueError("audit event_type is required")

        event_id = _normalize_text(event.get("id")) or str(uuid.uuid4())
        payload = _normalize_payload(event.get("payload"))
        created_at = _normalize_timestamp(event.get("created_at"))
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
                event_type,
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
        normalized_limit = int(limit)
        if normalized_limit < 1:
            raise ValueError("audit query limit must be >= 1")
        normalized_offset = int(offset)
        if normalized_offset < 0:
            raise ValueError("audit query offset must be >= 0")
        direction = str(order or "desc").strip().lower()
        if direction not in {"asc", "desc"}:
            raise ValueError(f"unsupported audit query order: {direction}")

        clauses = ["module_name = ?", "dataset_name = ?"]
        params: list[Any] = [module_name, dataset_name]
        if entity_key is not None:
            clauses.append("entity_key = ?")
            params.append(entity_key)
        if event_type is not None:
            clauses.append("event_type = ?")
            params.append(event_type)
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if start_at is not None:
            clauses.append("created_at >= ?")
            params.append(int(start_at))
        if end_at is not None:
            clauses.append("created_at <= ?")
            params.append(int(end_at))

        params.extend([normalized_limit, normalized_offset])
        with get_connection(DATA_DB) as conn:
            rows = conn.execute(
                f"""
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
                ORDER BY created_at {direction.upper()}, id {direction.upper()}
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload_json = json.loads(row["payload_json"])
            except (TypeError, ValueError):
                payload_json = {}
            events.append(
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
                    "payload": _normalize_payload(payload_json),
                    "created_at": row["created_at"],
                }
            )
        return events

    def _write_page_row(self, module_name: str, page_id: str, schema: dict[str, Any]) -> bool:
        now = int(time.time())
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_page_write_lock_key(module_name, page_id)],
            operation=lambda conn: self._write_page_row_with_conn(conn, module_name, page_id, schema, now=now) or True,
        )

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

    def execute_query_plan(
        self,
        module_name: str,
        plan: dict[str, Any],
        *,
        describe_source,
    ) -> list[dict[str, Any]]:
        base = plan.get("base")
        if not isinstance(base, dict):
            raise ValueError("query plan base must be an object")
        source_id = _validate_snake_case_identifier(str(base.get("source") or ""))
        descriptor = describe_source(source_id)
        source_kind = str(descriptor.get("source_kind") or "")
        joins = [dict(item) for item in plan.get("joins") or [] if isinstance(item, dict)]
        select_items = [dict(item) for item in plan.get("select") or [] if isinstance(item, dict)]
        group_by = [_validate_snake_case_identifier(str(item)) for item in plan.get("group_by") or []]
        has_aggregate = _plan_has_aggregate(select_items)
        if source_kind != "relation" and (joins or group_by or has_aggregate):
            label = "managed_dataset(snapshot)" if source_kind == "snapshot" else "view(read_model)"
            if joins:
                raise ValueError(f"source '{source_id}' is {label}; join is only supported for custom_table(relation)")
            if group_by:
                raise ValueError(f"source '{source_id}' is {label}; group_by is not supported")
            raise ValueError(f"source '{source_id}' is {label}; aggregate is not supported")
        if source_kind == "snapshot":
            return self._execute_snapshot_plan(module_name, source_id, descriptor, plan)
        if source_kind == "read_model":
            return self._execute_view_plan(module_name, source_id, descriptor, plan)
        if source_kind != "relation":
            raise ValueError(f"unsupported source_kind: {source_kind}")
        return self._execute_relation_plan(module_name, source_id, descriptor, plan, describe_source=describe_source)

    def _execute_snapshot_plan(
        self,
        module_name: str,
        source_id: str,
        descriptor: dict[str, Any],
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        column_names = {column["name"] for column in descriptor["columns"]}
        where = _normalize_plan_where(plan.get("where"))
        order_by = _normalize_db_view_sort(plan.get("order_by") or [])
        select_items = [dict(item) for item in plan.get("select") or [] if isinstance(item, dict)]
        selected_fields = [
            _validate_snake_case_identifier(str(item.get("field") or ""))
            for item in select_items
            if item.get("kind", "column") == "column"
        ]
        for field in selected_fields:
            if field not in column_names:
                raise ValueError(f"query select field not found: {field}")
        for item in where:
            if item["field"] not in column_names:
                raise ValueError(f"query filter field not found: {item['field']}")
        for item in order_by:
            if item["field"] not in column_names:
                raise ValueError(f"query sort field not found: {item['field']}")

        with get_connection(DATA_DB) as conn:
            resource = self._require_resource_row_with_conn(conn, module_name, source_id)
            rows = (
                self._read_managed_dataset_rows_with_conn(
                    conn,
                    module_name,
                    resource["logical_name"],
                    include_system_fields=True,
                )
                or []
            )

        filtered = rows
        for item in where:
            filtered = [
                row
                for row in filtered
                if _filter_record_value(row.get(item["field"]), item["op"], item.get("value"))
            ]
        for item in reversed(order_by):
            filtered.sort(key=lambda row: row.get(item["field"]), reverse=item["direction"] == "desc")
        offset = _normalize_plan_offset(plan.get("offset"))
        limit = _normalize_plan_limit(plan.get("limit"))
        page = filtered[offset : offset + limit]
        if not selected_fields:
            selected_fields = [column["name"] for column in descriptor["columns"]]
        return [{field: row.get(field) for field in selected_fields} for row in page]

    def _execute_view_plan(
        self,
        module_name: str,
        source_id: str,
        descriptor: dict[str, Any],
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        with get_connection(DATA_DB) as conn:
            view = self._ensure_db_view_with_conn(conn, module_name, source_id)
            return self._execute_sql_source_plan_with_conn(
                conn,
                source_identifier=_quote_identifier(view["physical_view_name"]),
                descriptor=descriptor,
                plan=plan,
            )

    def _execute_relation_plan(
        self,
        module_name: str,
        source_id: str,
        descriptor: dict[str, Any],
        plan: dict[str, Any],
        *,
        describe_source,
    ) -> list[dict[str, Any]]:
        joins = [dict(item) for item in plan.get("joins") or [] if isinstance(item, dict)]
        declared_joins = {item["target"]: item for item in descriptor.get("joins", []) if isinstance(item, dict)}
        with get_connection(DATA_DB) as conn:
            base_resource = self._require_resource_row_with_conn(conn, module_name, source_id)
            if base_resource["storage_mode"] != "custom_table":
                raise ValueError(f"source '{source_id}' is not custom_table(relation)")
            self._ensure_custom_table_with_conn(conn, base_resource)
            join_sources: list[dict[str, Any]] = []
            for index, join in enumerate(joins):
                target = _validate_snake_case_identifier(str(join.get("target") or ""))
                declared = declared_joins.get(target)
                if declared is None:
                    raise ValueError(f"join target '{target}' is not declared in joins")
                join_type = str(join.get("type") or "inner").strip().lower()
                if join_type not in set(declared.get("types") or ["inner"]):
                    raise ValueError(f"join target '{target}' does not allow {join_type} join")
                target_descriptor = describe_source(target)
                if target_descriptor.get("source_kind") != "relation":
                    raise ValueError(f"join target '{target}' is not custom_table(relation)")
                target_resource = self._require_resource_row_with_conn(conn, module_name, target)
                self._ensure_custom_table_with_conn(conn, target_resource)
                declared_on = {(item["left"], item["right"]) for item in declared.get("on", [])}
                actual_on = []
                for pair in join.get("on") or []:
                    left = _validate_snake_case_identifier(str(pair.get("left") or ""))
                    right = _validate_snake_case_identifier(str(pair.get("right") or ""))
                    if (left, right) not in declared_on:
                        raise ValueError(f"join target '{target}' uses undeclared on pair: {left}={right}")
                    actual_on.append({"left": left, "right": right})
                if not actual_on:
                    raise ValueError(f"join target '{target}' requires on pairs")
                join_sources.append(
                    {
                        "alias": f"j{index}",
                        "type": join_type,
                        "resource": target_resource,
                        "descriptor": target_descriptor,
                        "on": actual_on,
                    }
                )
            return self._execute_sql_source_plan_with_conn(
                conn,
                source_identifier=_quote_identifier(base_resource["physical_table_name"]),
                descriptor=descriptor,
                plan=plan,
                join_sources=join_sources,
            )

    def _execute_sql_source_plan_with_conn(
        self,
        conn,
        *,
        source_identifier: str,
        descriptor: dict[str, Any],
        plan: dict[str, Any],
        join_sources: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        join_sources = list(join_sources or [])
        source_columns = {
            "base": {column["name"]: column for column in descriptor["columns"]},
            **{
                join["alias"]: {column["name"]: column for column in join["descriptor"]["columns"]}
                for join in join_sources
            },
        }

        def resolve_field(field: str) -> str:
            normalized = _validate_snake_case_identifier(field)
            if normalized in source_columns["base"]:
                return f"base.{_quote_identifier(normalized)}"
            matches = [alias for alias, columns in source_columns.items() if alias != "base" and normalized in columns]
            if len(matches) == 1:
                return f"{matches[0]}.{_quote_identifier(normalized)}"
            if matches:
                raise ValueError(f"query field is ambiguous: {normalized}")
            raise ValueError(f"query field not found: {normalized}")

        where = _normalize_plan_where(plan.get("where"))
        order_by = _normalize_db_view_sort(plan.get("order_by") or [])
        select_items = [dict(item) for item in plan.get("select") or [] if isinstance(item, dict)]
        group_by = [_validate_snake_case_identifier(str(item)) for item in plan.get("group_by") or []]
        params: list[Any] = []

        select_sql: list[str] = []
        for field in group_by:
            select_sql.append(f"{resolve_field(field)} AS {_quote_identifier(field)}")
        if not select_items and not group_by:
            select_sql = [
                f"base.{_quote_identifier(column['name'])} AS {_quote_identifier(column['name'])}"
                for column in descriptor["columns"]
            ]
        for item in select_items:
            kind = str(item.get("kind") or "column")
            if kind == "column":
                field = _validate_snake_case_identifier(str(item.get("field") or ""))
                if field in group_by:
                    continue
                select_sql.append(f"{resolve_field(field)} AS {_quote_identifier(field)}")
                continue
            if kind != "aggregate":
                raise ValueError(f"unsupported select item kind: {kind}")
            func = str(item.get("func") or "").strip().lower()
            if func not in {"count", "sum", "avg", "min", "max"}:
                raise ValueError(f"unsupported aggregate function: {func}")
            alias = _validate_snake_case_identifier(str(item.get("alias") or f"{func}_value"))
            field = str(item.get("field") or "*")
            if func == "count" and field == "*":
                select_sql.append(f"COUNT(*) AS {_quote_identifier(alias)}")
            else:
                select_sql.append(f"{func.upper()}({resolve_field(_validate_snake_case_identifier(field))}) AS {_quote_identifier(alias)}")
        if not select_sql:
            raise ValueError("query plan select cannot be empty")

        join_sql: list[str] = []
        for join in join_sources:
            table_identifier = _quote_identifier(join["resource"]["physical_table_name"])
            on_sql = " AND ".join(
                f"base.{_quote_identifier(pair['left'])} = {join['alias']}.{_quote_identifier(pair['right'])}"
                for pair in join["on"]
            )
            join_keyword = "LEFT JOIN" if join["type"] == "left" else "JOIN"
            join_sql.append(f"{join_keyword} {table_identifier} AS {join['alias']} ON {on_sql}")

        where_sql_parts: list[str] = []
        for item in where:
            field_sql = resolve_field(item["field"])
            op = item["op"]
            if op == "is_null":
                where_sql_parts.append(f"{field_sql} IS NULL")
            elif op == "eq":
                where_sql_parts.append(f"{field_sql} = ?")
                params.append(item.get("value"))
            elif op == "in":
                values = list(item.get("value") or [])
                if not values:
                    where_sql_parts.append("1 = 0")
                else:
                    where_sql_parts.append(f"{field_sql} IN ({', '.join(['?'] * len(values))})")
                    params.extend(values)
            elif op == "between":
                values = list(item.get("value") or [])
                if len(values) != 2:
                    raise ValueError("between filter value must contain two items")
                where_sql_parts.append(f"{field_sql} BETWEEN ? AND ?")
                params.extend(values)
            else:
                sql_op = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "like": "LIKE"}[op]
                where_sql_parts.append(f"{field_sql} {sql_op} ?")
                params.append(item.get("value"))

        group_sql = ""
        if group_by:
            group_sql = " GROUP BY " + ", ".join(resolve_field(field) for field in group_by)
        rendered_select_aliases = {
            str(item.get("alias") or item.get("field") or "")
            for item in select_items
        } | set(group_by)
        order_sql = ""
        if order_by:
            parts = []
            for item in order_by:
                field = item["field"]
                if field in rendered_select_aliases:
                    parts.append(f"{_quote_identifier(field)} {item['direction'].upper()}")
                else:
                    parts.append(f"{resolve_field(field)} {item['direction'].upper()}")
            order_sql = " ORDER BY " + ", ".join(parts)
        limit = _normalize_plan_limit(plan.get("limit"))
        offset = _normalize_plan_offset(plan.get("offset"))
        params.extend([limit, offset])

        rows = conn.execute(
            f"""
            SELECT {", ".join(select_sql)}
            FROM {source_identifier} AS base
            {" ".join(join_sql)}
            {"WHERE " + " AND ".join(where_sql_parts) if where_sql_parts else ""}
            {group_sql}
            {order_sql}
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

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
            resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
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

            rows = self._read_managed_dataset_rows_with_conn(conn, module_name, resource["logical_name"]) or []
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
            resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
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
            resolved_sql, allowed_tables = self._resolve_db_view_sql_with_conn(
                conn,
                module_name,
                source_resource_ids=source_resource_ids,
                select_sql_template=normalized_sql,
            )
            cursor = _execute_with_read_authorizer(
                conn,
                resolved_sql,
                normalized_params,
                allowed_tables=allowed_tables,
            )
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

    def read_resource_records(self, module_name: str, resource_id: str) -> list[dict[str, Any]]:
        records = self._read_resource_records(module_name, resource_id)
        return records if records is not None else []

    def replace_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> bool:
        return self._replace_resource_records(module_name, resource_id, _normalize_records_for_write(records))

    def upsert_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> bool:
        return self._upsert_resource_records(module_name, resource_id, _normalize_records_for_write(records))

    def update_resource_records(
        self,
        module_name: str,
        resource_id: str,
        fields: dict[str, Any],
        *,
        where: Any,
    ) -> int:
        return self._update_resource_records(module_name, resource_id, fields, where=where)

    def delete_resource_records(self, module_name: str, resource_id: str, *, where: Any) -> int:
        return self._delete_resource_records(module_name, resource_id, where=where)

    def execute_write_batch(self, module_name: str, operations: list[dict[str, Any]]) -> list[Any]:
        if not isinstance(operations, list):
            raise ValueError("write batch operations must be a list")
        return self._execute_write_batch(
            module_name,
            [dict(operation) for operation in operations if isinstance(operation, dict)],
        )

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
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
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
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
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
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")
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
                "DELETE FROM module_datasets WHERE module_name = ?",
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
