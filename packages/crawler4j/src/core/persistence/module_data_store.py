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
_CUSTOM_TABLE_BOOL_TRUE_STRINGS = {"true", "1", "yes", "on"}
_CUSTOM_TABLE_BOOL_FALSE_STRINGS = {"false", "0", "no", "off"}
_LEGACY_CUSTOM_TABLE_COLUMNS = {
    "record_key",
    "run_status",
    "record_status",
    "record_json",
    "created_at",
    "updated_at",
}
_MANAGED_DATASET_PHYSICAL_COLUMN_TYPES = {
    "record_index": "int",
    "record_key": "text",
    "run_status": "text",
    "record_status": "text",
    "created_at": "int",
    "updated_at": "int",
}
_CUSTOM_TABLE_SYSTEM_COLUMN_TYPES = {
    "created_at": "int",
    "updated_at": "int",
}
_MANAGED_DATASET_RESERVED_WRITE_FIELDS = set(_MANAGED_DATASET_PHYSICAL_COLUMN_TYPES)
_MANAGED_DATASET_STATUS_WRITE_FIELDS = {"run_status", "record_status"}
_MANAGED_DATASET_GENERATED_WRITE_FIELDS = _MANAGED_DATASET_RESERVED_WRITE_FIELDS - _MANAGED_DATASET_STATUS_WRITE_FIELDS
_FILTER_OP_ALIASES = {
    "=": "eq",
    "==": "eq",
    "eq": "eq",
    "in": "in",
    ">": "gt",
    "gt": "gt",
    ">=": "gte",
    "gte": "gte",
    "<": "lt",
    "lt": "lt",
    "<=": "lte",
    "lte": "lte",
    "between": "between",
    "like": "like",
    "is_null": "is_null",
}
_SQL_FILTER_OPS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "like": "LIKE"}
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


def _data_source_column_descriptor(
    raw: dict[str, Any],
    *,
    storage_mode: str,
    record_key_field: str | None,
    writable: bool = True,
) -> dict[str, Any]:
    name = _validate_snake_case_identifier(str(raw.get("name") or raw.get("key") or ""))
    column_type = str(raw.get("type") or "text").strip() or "text"
    auto_increment = bool(raw.get("auto_increment"))
    nullable = bool(raw.get("nullable")) if "nullable" in raw else not bool(raw.get("required"))
    if storage_mode == "custom_table" and record_key_field and name == record_key_field:
        nullable = False
    if auto_increment:
        nullable = False
    required = (bool(raw.get("required")) or nullable is False) and not auto_increment
    column = {
        "name": name,
        "type": column_type,
        "nullable": nullable,
        "required": required,
        "writable": bool(writable and not auto_increment),
    }
    if auto_increment:
        column["auto_increment"] = True
    return column


def _read_only_column_descriptor(raw: dict[str, Any]) -> dict[str, Any]:
    name = _validate_snake_case_identifier(str(raw.get("name") or raw.get("key") or ""))
    nullable = bool(raw.get("nullable")) if "nullable" in raw else not bool(raw.get("required"))
    return {
        "name": name,
        "type": str(raw.get("type") or "text").strip() or "text",
        "nullable": nullable,
        "required": False,
        "writable": False,
    }


def _system_field_descriptor(
    name: str,
    column_type: str,
    *,
    writable: bool,
    generated: bool,
) -> dict[str, Any]:
    return {
        "name": _validate_snake_case_identifier(name),
        "type": column_type,
        "writable": writable,
        "generated": generated,
    }


def _managed_dataset_system_fields() -> list[dict[str, Any]]:
    return [
        _system_field_descriptor(
            name,
            column_type,
            writable=name in _MANAGED_DATASET_STATUS_WRITE_FIELDS,
            generated=name in _MANAGED_DATASET_GENERATED_WRITE_FIELDS,
        )
        for name, column_type in _MANAGED_DATASET_PHYSICAL_COLUMN_TYPES.items()
    ]


def _custom_table_system_fields() -> list[dict[str, Any]]:
    return [
        _system_field_descriptor(name, column_type, writable=False, generated=True)
        for name, column_type in _CUSTOM_TABLE_SYSTEM_COLUMN_TYPES.items()
    ]


def _with_data_source_write_contract(descriptor: dict[str, Any]) -> dict[str, Any]:
    columns = [dict(column) for column in descriptor.get("columns", []) if isinstance(column, dict)]
    system_fields = [dict(field) for field in descriptor.get("system_fields", []) if isinstance(field, dict)]
    descriptor["columns"] = columns
    descriptor["system_fields"] = system_fields
    descriptor["writable_fields"] = [
        str(item["name"])
        for item in [*columns, *system_fields]
        if item.get("writable") is True and item.get("name")
    ]
    descriptor["required_fields"] = [
        str(column["name"])
        for column in columns
        if column.get("required") is True and column.get("name")
    ]
    descriptor["read_only_fields"] = [
        str(item["name"])
        for item in [*columns, *system_fields]
        if item.get("writable") is not True and item.get("name")
    ]
    return descriptor


def _db_view_name(module_name: str, view_id: str) -> str:
    _validate_snake_case_identifier(module_name)
    _validate_snake_case_identifier(view_id)
    return _validate_snake_case_identifier(f"{module_name}_view_{view_id}")


def _record_status_columns(record: dict[str, Any]) -> tuple[str, str]:
    return (
        _normalize_text(record.get("run_status")) or _DEFAULT_RUN_STATUS,
        _normalize_text(record.get("record_status")) or _DEFAULT_RECORD_STATUS,
    )


def _record_json_payload(record: dict[str, Any], *, json_column_names: set[str]) -> dict[str, Any]:
    return {
        field: value
        for field, value in record.items()
        if _validate_snake_case_identifier(str(field)) in json_column_names
    }


def _record_key_for_write(
    record: dict[str, Any],
    _record_index: int,
    *,
    record_key_field: str | None,
    require_key: bool,
) -> str | None:
    candidate_fields = [field for field in (record_key_field, "record_key", "id") if field]
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
    }
    return column


def _normalize_db_view_columns(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("db view columns must be a non-empty list")
    return [_normalize_db_view_column(item) for item in raw]


def _normalize_db_view_source_resource_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("db view source_resource_ids must be a non-empty list")
    return [_validate_snake_case_identifier(str(item)) for item in raw]


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


def _normalize_filter_op(raw: Any) -> str:
    normalized = str(raw or "eq").strip().lower()
    if normalized not in _FILTER_OP_ALIASES:
        raise ValueError(f"unsupported query filter op: {normalized}")
    return _FILTER_OP_ALIASES[normalized]


def _normalize_plan_where(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if isinstance(raw, (list, tuple)) and not raw:
        return []
    if isinstance(raw, dict):
        if "field" in raw or "operator" in raw or "conditions" in raw:
            return [_normalize_plan_condition(raw)]
        if not raw:
            return []
        return [
            {"field": _validate_snake_case_identifier(str(field)), "op": "eq", "value": value}
            for field, value in raw.items()
        ]
    condition = _normalize_plan_condition(raw)
    if condition.get("kind") == "group" and condition.get("operator") == "and":
        return list(condition["conditions"])
    return [condition]


def _normalize_plan_condition(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        if "operator" in raw or "conditions" in raw:
            operator = str(raw.get("operator") or "and").strip().lower()
            if operator not in {"and", "or"}:
                raise ValueError(f"unsupported query filter group operator: {operator}")
            conditions = [_normalize_plan_condition(item) for item in raw.get("conditions") or []]
            if not conditions:
                raise ValueError("query filter group must contain conditions")
            return {"kind": "group", "operator": operator, "conditions": conditions}
        field = _validate_snake_case_identifier(str(raw.get("field") or ""))
        op = _normalize_filter_op(raw.get("op"))
        item: dict[str, Any] = {"field": field, "op": op}
        if op != "is_null":
            item["value"] = raw.get("value")
        return item
    if not isinstance(raw, (list, tuple)):
        raise ValueError("query plan where must be a condition list")
    items = list(raw)
    if not items:
        raise ValueError("query filter condition must be non-empty")
    first = items[0]
    if isinstance(first, str) and first.strip().lower() in {"and", "or"}:
        operator = first.strip().lower()
        conditions = [_normalize_plan_condition(item) for item in items[1:]]
        if not conditions:
            raise ValueError("query filter group must contain conditions")
        return {"kind": "group", "operator": operator, "conditions": conditions}
    if len(items) >= 2 and isinstance(items[0], str):
        field = _validate_snake_case_identifier(str(items[0]))
        op = _normalize_filter_op(items[1])
        item: dict[str, Any] = {"field": field, "op": op}
        if op == "between":
            if len(items) == 4:
                item["value"] = [items[2], items[3]]
            elif len(items) == 3:
                item["value"] = items[2]
            else:
                raise ValueError("between filter value must contain two items")
        elif op != "is_null":
            if len(items) < 3:
                raise ValueError(f"{op} filter requires a value")
            item["value"] = items[2]
        return item
    if all(isinstance(item, (dict, list, tuple)) for item in items):
        return {
            "kind": "group",
            "operator": "and",
            "conditions": [_normalize_plan_condition(item) for item in items],
        }
    raise ValueError("invalid query filter condition")


def _iter_where_predicates(where: list[dict[str, Any]]):
    for item in where:
        if item.get("kind") == "group":
            yield from _iter_where_predicates(item["conditions"])
        else:
            yield item


def _render_where_conditions(
    where: list[dict[str, Any]],
    render_predicate,
    *,
    require_where: bool = False,
) -> tuple[str, list[Any]]:
    if require_where and not where:
        raise ValueError("write where must not be empty")
    clauses: list[str] = []
    params: list[Any] = []
    for item in where:
        clause, clause_params = _render_where_condition(item, render_predicate)
        clauses.append(clause)
        params.extend(clause_params)
    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


def _render_where_condition(condition: dict[str, Any], render_predicate) -> tuple[str, list[Any]]:
    if condition.get("kind") == "group":
        operator = str(condition.get("operator") or "and").strip().lower()
        if operator not in {"and", "or"}:
            raise ValueError(f"unsupported query filter group operator: {operator}")
        parts: list[str] = []
        params: list[Any] = []
        for item in condition.get("conditions") or []:
            part, item_params = _render_where_condition(item, render_predicate)
            parts.append(part)
            params.extend(item_params)
        if not parts:
            raise ValueError("query filter group must contain conditions")
        joiner = f" {operator.upper()} "
        return f"({joiner.join(parts)})", params
    return render_predicate(condition)


def _normalize_plan_limit(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    value = int(raw)
    if value < 1:
        raise ValueError("query plan limit must be >= 1")
    return value


def _normalize_plan_offset(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    value = int(raw)
    if value < 0:
        raise ValueError("query plan offset must be >= 0")
    return value


def _render_plan_pagination(raw_limit: Any, raw_offset: Any) -> tuple[str, list[Any]]:
    limit = _normalize_plan_limit(raw_limit)
    offset = _normalize_plan_offset(raw_offset)
    if limit is None and offset is None:
        return "", []
    if limit is None:
        return " LIMIT -1 OFFSET ?", [offset]
    if offset is None:
        return " LIMIT ?", [limit]
    return " LIMIT ? OFFSET ?", [limit, offset]


def _normalize_resource_query_select(raw: Any) -> list[dict[str, str]]:
    if raw in (None, ""):
        return []
    if raw == "*":
        return [{"kind": "column", "field": "*"}]
    if not isinstance(raw, (list, tuple)):
        raise ValueError("resource query select must be a list")
    select_items: list[dict[str, str]] = []
    for item in raw:
        field = str(item or "")
        if field == "*":
            select_items.append({"kind": "column", "field": "*"})
            continue
        select_items.append({"kind": "column", "field": _validate_snake_case_identifier(field)})
    return select_items


def _normalize_write_fields(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("write fields must be a non-empty object")
    return {_validate_snake_case_identifier(str(field)): value for field, value in raw.items()}


def _render_custom_table_where_clause(
    column_map: dict[str, dict[str, Any]],
    where: Any,
    *,
    require_where: bool,
) -> tuple[str, list[Any]]:
    normalized_where = _normalize_plan_where(where)

    def render_predicate(item: dict[str, Any]) -> tuple[str, list[Any]]:
        field = item["field"]
        column = column_map.get(field)
        if column is None:
            raise ValueError(f"write where field not found: {field}")
        field_sql = _quote_identifier(field)
        op = item["op"]
        if op == "is_null":
            return f"{field_sql} IS NULL", []
        if op == "eq":
            return f"{field_sql} = ?", [
                _sqlite_value_for_custom_table_column(item.get("value"), column_type=column["type"])
            ]
        if op == "in":
            values = list(item.get("value") or [])
            if not values:
                return "1 = 0", []
            return f"{field_sql} IN ({', '.join(['?'] * len(values))})", [
                *(_sqlite_value_for_custom_table_column(value, column_type=column["type"]) for value in values)
            ]
        if op == "between":
            values = list(item.get("value") or [])
            if len(values) != 2:
                raise ValueError("between filter value must contain two items")
            return f"{field_sql} BETWEEN ? AND ?", [
                *(_sqlite_value_for_custom_table_column(value, column_type=column["type"]) for value in values)
            ]
        sql_op = _SQL_FILTER_OPS[op]
        return f"{field_sql} {sql_op} ?", [
            _sqlite_value_for_custom_table_column(item.get("value"), column_type=column["type"])
        ]

    return _render_where_conditions(normalized_where, render_predicate, require_where=require_where)


def _plan_has_aggregate(select_items: list[dict[str, Any]]) -> bool:
    return any(item.get("kind") == "aggregate" for item in select_items)


def _managed_dataset_count_alias(select_items: list[dict[str, Any]]) -> str | None:
    if len(select_items) != 1:
        return None
    item = select_items[0]
    if item.get("kind") != "aggregate":
        return None
    func = str(item.get("func") or "").strip().lower()
    field = str(item.get("field") or "*")
    if func != "count" or field != "*":
        return None
    return _validate_snake_case_identifier(str(item.get("alias") or "count"))


def _collect_plan_column_fields(
    select_items: list[dict[str, Any]],
    where: list[dict[str, Any]],
    order_by: list[dict[str, Any]],
) -> list[str]:
    fields: list[str] = []

    def add(raw_field: Any) -> None:
        if str(raw_field or "") == "*":
            return
        field = _validate_snake_case_identifier(str(raw_field or ""))
        if field in _MANAGED_DATASET_RESERVED_WRITE_FIELDS or field in fields:
            return
        fields.append(field)

    for item in select_items:
        if item.get("kind", "column") == "column":
            add(item.get("field"))
    for item in _iter_where_predicates(where):
        add(item.get("field"))
    for item in order_by:
        add(item.get("field"))
    return fields


def _managed_dataset_json_column_names(descriptor: dict[str, Any]) -> set[str]:
    return {
        str(column.get("name") or "")
        for column in descriptor.get("columns", [])
        if isinstance(column, dict) and str(column.get("name") or "") not in _MANAGED_DATASET_PHYSICAL_COLUMN_TYPES
    }


def _managed_dataset_all_fields(descriptor: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for column in descriptor.get("columns", []):
        if not isinstance(column, dict):
            continue
        name = str(column.get("name") or "")
        if name and name not in fields:
            fields.append(name)
    for field in _MANAGED_DATASET_PHYSICAL_COLUMN_TYPES:
        if field not in fields:
            fields.append(field)
    return fields


def _managed_dataset_field_mode(field: str, *, json_column_names: set[str]) -> str | None:
    if field in _MANAGED_DATASET_PHYSICAL_COLUMN_TYPES:
        return "physical"
    if field in json_column_names:
        return "json"
    return None


def _managed_dataset_field_sql(field: str, *, json_column_names: set[str]) -> str:
    mode = _managed_dataset_field_mode(field, json_column_names=json_column_names)
    if mode == "physical":
        return _quote_identifier(field)
    if mode == "json":
        return f"json_extract(record_json, '$.{field}')"
    raise ValueError(f"query field not found: {field}")


def _render_managed_dataset_where_clause(
    where: list[dict[str, Any]],
    *,
    json_column_names: set[str],
    require_where: bool = False,
) -> tuple[str, list[Any]]:
    def render_predicate(item: dict[str, Any]) -> tuple[str, list[Any]]:
        field_sql = _managed_dataset_field_sql(item["field"], json_column_names=json_column_names)
        op = item["op"]
        if op == "is_null":
            return f"{field_sql} IS NULL", []
        if op == "eq":
            return f"{field_sql} = ?", [item.get("value")]
        if op == "in":
            values = list(item.get("value") or [])
            if not values:
                return "1 = 0", []
            return f"{field_sql} IN ({', '.join(['?'] * len(values))})", values
        if op == "between":
            values = list(item.get("value") or [])
            if len(values) != 2:
                raise ValueError("between filter value must contain two items")
            return f"{field_sql} BETWEEN ? AND ?", values
        sql_op = _SQL_FILTER_OPS[op]
        return f"{field_sql} {sql_op} ?", [item.get("value")]

    return _render_where_conditions(where, render_predicate, require_where=require_where)


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
    auto_increment = bool(raw.get("auto_increment"))
    if auto_increment:
        if name != record_key_field:
            raise ValueError("custom table auto_increment column must be the record_key_field")
        if column_type not in {"int", "integer"}:
            raise ValueError("custom table auto_increment record_key_field must be integer")
        nullable = False
    if record_key_field and name == record_key_field:
        nullable = False
    column = {
        "name": name,
        "type": column_type,
        "nullable": nullable,
    }
    if auto_increment:
        column["auto_increment"] = True
    return column


def _normalize_custom_table_schema(raw: Any, *, record_key_field: str | None) -> dict[str, Any]:
    schema = _normalize_schema(raw)
    version = _normalize_schema_version(schema.get("version") or schema.get("schema_version"))
    raw_columns = schema.get("columns", [])
    if raw_columns is None:
        raw_columns = []
    if not isinstance(raw_columns, list):
        raise ValueError("custom table schema columns must be a list")

    columns = [_normalize_custom_table_column(column, record_key_field=record_key_field) for column in raw_columns]
    if record_key_field and columns:
        names = {column["name"] for column in columns}
        if record_key_field not in names:
            raise ValueError(f"custom table schema must include record_key_field column: {record_key_field}")
    auto_increment_columns = [column for column in columns if column.get("auto_increment")]
    if len(auto_increment_columns) > 1:
        raise ValueError("custom table schema can only declare one auto_increment column")
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
        columns = [_validate_snake_case_identifier(str(column)) for column in raw_columns]
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
        return _sqlite_bool_value_for_custom_table_column(value)
    if column_type in {"int", "integer"}:
        return int(value)
    if column_type in {"number", "real"}:
        return float(value)
    if column_type == "json":
        return json.dumps(value, ensure_ascii=False)
    return value


def _sqlite_bool_value_for_custom_table_column(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _CUSTOM_TABLE_BOOL_TRUE_STRINGS:
            return 1
        if normalized in _CUSTOM_TABLE_BOOL_FALSE_STRINGS:
            return 0
        raise ValueError(f"invalid custom table bool value: {value!r}")
    if isinstance(value, int) and value in {0, 1}:
        return int(value)
    if isinstance(value, float) and value in {0.0, 1.0}:
        return int(value)
    raise ValueError(f"invalid custom table bool value: {value!r}")


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


def _custom_table_record_key_column(
    columns: list[dict[str, Any]],
    *,
    record_key_field: str,
) -> dict[str, Any]:
    for column in columns:
        if column["name"] == record_key_field:
            return column
    raise ValueError(f"custom table schema must include record_key_field column: {record_key_field}")


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
            "source_resource_ids": [_validate_snake_case_identifier(str(item)) for item in raw_source_resource_ids],
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
        resource: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> None:
        dataset_name = resource["logical_name"]
        record_key_field = resource.get("record_key_field")
        normalized_records = [dict(record) for record in records]
        json_column_names = self._managed_dataset_json_column_names_from_resource(resource)
        for record in normalized_records:
            self._validate_managed_dataset_schema_write_fields(
                resource,
                record,
                operation="records",
                ignore_generated_fields=True,
            )
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
                        json.dumps(
                            _record_json_payload(record, json_column_names=json_column_names),
                            ensure_ascii=False,
                        ),
                        created_at,
                        now,
                    )
                    for record_index, record in enumerate(normalized_records)
                ],
            )

    def _managed_dataset_json_column_names_from_resource(self, resource: dict[str, Any]) -> set[str]:
        schema = _normalize_schema(resource.get("schema") or {})
        columns = schema.get("columns") or []
        names = {
            _validate_snake_case_identifier(str(column.get("name") or ""))
            for column in columns
            if isinstance(column, dict)
        }
        return names - _MANAGED_DATASET_RESERVED_WRITE_FIELDS

    def _validate_managed_dataset_schema_write_fields(
        self,
        resource: dict[str, Any],
        fields: dict[str, Any],
        *,
        operation: str,
        allow_status_fields: bool = True,
        ignore_generated_fields: bool = False,
    ) -> None:
        allowed_physical_fields = _MANAGED_DATASET_STATUS_WRITE_FIELDS if allow_status_fields else set()
        ignored_physical_fields = _MANAGED_DATASET_GENERATED_WRITE_FIELDS if ignore_generated_fields else set()
        reserved_fields = sorted(
            field
            for field in (_validate_snake_case_identifier(str(raw_field)) for raw_field in fields)
            if field in _MANAGED_DATASET_RESERVED_WRITE_FIELDS
            and field not in allowed_physical_fields
            and field not in ignored_physical_fields
        )
        if reserved_fields:
            raise ValueError(
                f"managed_dataset {operation} contains reserved host fields for "
                f"{resource['resource_id']}: {', '.join(reserved_fields)}"
            )
        allowed_fields = (
            self._managed_dataset_json_column_names_from_resource(resource)
            | allowed_physical_fields
            | ignored_physical_fields
        )
        unknown_fields = sorted(
            field
            for field in (_validate_snake_case_identifier(str(raw_field)) for raw_field in fields)
            if field not in allowed_fields
        )
        if unknown_fields:
            raise ValueError(
                f"managed_dataset {operation} contains fields outside schema for "
                f"{resource['resource_id']}: {', '.join(unknown_fields)}"
            )

    def _managed_dataset_resource_columns_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        *,
        extra_fields: list[str] | None = None,
        include_schema_fields: bool = True,
    ) -> list[dict[str, Any]]:
        del conn, module_name, extra_fields
        schema = _normalize_schema(resource.get("schema") or {})
        schema_columns = [column for column in schema.get("columns") or [] if isinstance(column, dict)]
        schema_types: dict[str, str] = {}
        schema_flags: dict[str, dict[str, Any]] = {}
        ordered_fields: list[str] = []

        def add_json_field(
            raw_field: Any,
            *,
            column_type: str = "text",
            nullable: bool = True,
            required: bool = False,
        ) -> None:
            try:
                field = _validate_snake_case_identifier(str(raw_field or ""))
            except ValueError:
                return
            if field in _MANAGED_DATASET_RESERVED_WRITE_FIELDS:
                return
            schema_types.setdefault(field, column_type)
            schema_flags.setdefault(field, {"nullable": nullable, "required": required})
            if field not in ordered_fields:
                ordered_fields.append(field)

        if include_schema_fields:
            for column in schema_columns:
                nullable = bool(column.get("nullable")) if "nullable" in column else not bool(column.get("required"))
                add_json_field(
                    column.get("name"),
                    column_type=str(column.get("type") or "text"),
                    nullable=nullable,
                    required=bool(column.get("required")),
                )

        return [
            _data_source_column_descriptor(
                {
                    "name": field,
                    "type": schema_types.get(field, "text"),
                    **schema_flags.get(field, {}),
                },
                storage_mode="managed_dataset",
                record_key_field=resource.get("record_key_field"),
            )
            for field in ordered_fields
        ]

    def _upsert_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> None:
        dataset_name = resource["logical_name"]
        record_key_field = resource.get("record_key_field")
        existing_rows = conn.execute(
            """
            SELECT record_index, record_key, run_status, record_status, record_json, created_at
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            ORDER BY record_index ASC
            """,
            (module_name, dataset_name),
        ).fetchall()
        existing_by_key = {
            _normalize_text(row["record_key"]): row
            for row in existing_rows
            if _normalize_text(row["record_key"]) is not None
        }
        json_column_names = self._managed_dataset_json_column_names_from_resource(resource)
        next_record_index = max([int(row["record_index"]) for row in existing_rows] or [-1]) + 1
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
                raise ValueError("managed_dataset records require a record_key")
            if record_key in seen_keys:
                raise ValueError(f"duplicate managed_dataset record_key: {record_key}")
            seen_keys.add(record_key)
            if record_key_field and record_key_field not in record:
                record[record_key_field] = record_key
            self._validate_managed_dataset_schema_write_fields(
                resource,
                record,
                operation="records",
                ignore_generated_fields=True,
            )

            existing = existing_by_key.get(record_key)
            payload = _record_json_payload(record, json_column_names=json_column_names)
            if existing is not None:
                try:
                    existing_payload = json.loads(existing["record_json"])
                except (TypeError, ValueError):
                    existing_payload = {}
                if not isinstance(existing_payload, dict):
                    existing_payload = {}
                existing_payload = {
                    field: value for field, value in existing_payload.items() if field in json_column_names
                }
                existing_payload.update(payload)
                run_status = _normalize_text(record.get("run_status")) or existing["run_status"] or _DEFAULT_RUN_STATUS
                record_status = (
                    _normalize_text(record.get("record_status")) or existing["record_status"] or _DEFAULT_RECORD_STATUS
                )
                conn.execute(
                    """
                    UPDATE module_datasets
                    SET run_status = ?,
                        record_status = ?,
                        record_json = ?,
                        updated_at = ?
                    WHERE module_name = ?
                      AND dataset_name = ?
                      AND record_index = ?
                    """,
                    (
                        run_status,
                        record_status,
                        json.dumps(existing_payload, ensure_ascii=False),
                        now,
                        module_name,
                        dataset_name,
                        existing["record_index"],
                    ),
                )
                continue

            conn.execute(
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
                (
                    module_name,
                    dataset_name,
                    next_record_index,
                    record_key,
                    *_record_status_columns(record),
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            next_record_index += 1

    def _update_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        fields: dict[str, Any],
        *,
        where: Any,
        now: int,
    ) -> int:
        normalized_fields = _normalize_write_fields(fields)
        reserved_fields = sorted(set(normalized_fields) & _MANAGED_DATASET_GENERATED_WRITE_FIELDS)
        if reserved_fields:
            raise ValueError(f"managed_dataset update contains reserved host fields: {', '.join(reserved_fields)}")
        self._validate_managed_dataset_schema_write_fields(
            resource,
            normalized_fields,
            operation="update",
            allow_status_fields=True,
        )
        normalized_where = _normalize_plan_where(where)
        json_column_names = self._managed_dataset_json_column_names_from_resource(resource)
        where_sql, where_params = _render_managed_dataset_where_clause(
            normalized_where,
            json_column_names=json_column_names,
            require_where=True,
        )
        filter_sql = f" AND {where_sql.removeprefix(' WHERE ')}"
        if set(normalized_fields).issubset(_MANAGED_DATASET_STATUS_WRITE_FIELDS):
            set_clauses: list[str] = []
            set_params: list[Any] = []
            if "run_status" in normalized_fields:
                set_clauses.append("run_status = ?")
                set_params.append(_normalize_text(normalized_fields["run_status"]) or _DEFAULT_RUN_STATUS)
            if "record_status" in normalized_fields:
                set_clauses.append("record_status = ?")
                set_params.append(_normalize_text(normalized_fields["record_status"]) or _DEFAULT_RECORD_STATUS)
            set_clauses.append("updated_at = ?")
            set_params.append(now)
            cursor = conn.execute(
                f"""
                UPDATE module_datasets
                SET {", ".join(set_clauses)}
                WHERE module_name = ? AND dataset_name = ?
                {filter_sql}
                """,
                (*set_params, module_name, resource["logical_name"], *where_params),
            )
            return int(cursor.rowcount or 0)

        rows = conn.execute(
            f"""
            SELECT record_index, record_json
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            {filter_sql}
            """,
            (module_name, resource["logical_name"], *where_params),
        ).fetchall()
        for row in rows:
            try:
                payload = json.loads(row["record_json"])
            except (TypeError, ValueError):
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            payload = {field: value for field, value in payload.items() if field in json_column_names}
            json_updates = {field: value for field, value in normalized_fields.items() if field in json_column_names}
            payload.update(json_updates)
            set_clauses: list[str] = []
            set_params: list[Any] = []
            if "run_status" in normalized_fields:
                set_clauses.append("run_status = ?")
                set_params.append(_normalize_text(normalized_fields["run_status"]) or _DEFAULT_RUN_STATUS)
            if "record_status" in normalized_fields:
                set_clauses.append("record_status = ?")
                set_params.append(_normalize_text(normalized_fields["record_status"]) or _DEFAULT_RECORD_STATUS)
            if json_updates:
                set_clauses.append("record_json = ?")
                set_params.append(json.dumps(payload, ensure_ascii=False))
            set_clauses.append("updated_at = ?")
            set_params.append(now)
            conn.execute(
                f"""
                UPDATE module_datasets
                SET {", ".join(set_clauses)}
                WHERE module_name = ?
                  AND dataset_name = ?
                  AND record_index = ?
                """,
                (*set_params, module_name, resource["logical_name"], row["record_index"]),
            )
        return len(rows)

    def _delete_managed_dataset_rows_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        *,
        where: Any,
    ) -> int:
        normalized_where = _normalize_plan_where(where)
        json_column_names = self._managed_dataset_json_column_names_from_resource(resource)
        where_sql, where_params = _render_managed_dataset_where_clause(
            normalized_where,
            json_column_names=json_column_names,
            require_where=True,
        )
        filter_sql = f" AND {where_sql.removeprefix(' WHERE ')}"
        cursor = conn.execute(
            f"""
            DELETE FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            {filter_sql}
            """,
            (module_name, resource["logical_name"], *where_params),
        )
        return int(cursor.rowcount or 0)

    def _custom_table_schema_columns(self, resource: dict[str, Any]) -> list[dict[str, Any]]:
        schema = _normalize_custom_table_schema(
            resource.get("schema") or {},
            record_key_field=resource.get("record_key_field"),
        )
        if not schema["columns"]:
            raise ValueError(f"custom table resource {resource['resource_id']} missing schema columns")
        return schema["columns"]

    def _resource_query_descriptor_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        *,
        extra_fields: list[str] | None = None,
        joins: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if resource["storage_mode"] == "custom_table":
            self._ensure_custom_table_with_conn(conn, resource)
            columns = [
                _data_source_column_descriptor(
                    column,
                    storage_mode="custom_table",
                    record_key_field=resource.get("record_key_field") or "id",
                )
                for column in self._custom_table_schema_columns(resource)
            ]
            return _with_data_source_write_contract(
                {
                    "source": resource["resource_id"],
                    "kind": "data_table",
                    "source_kind": "relation",
                    "storage_mode": resource["storage_mode"],
                    "record_key_field": resource.get("record_key_field") or "id",
                    "columns": columns,
                    "system_fields": _custom_table_system_fields(),
                    "writable_fields": [],
                    "required_fields": [],
                    "read_only_fields": [],
                    "indexes": dict(resource.get("indexes") or {}),
                    "joins": [dict(item) for item in joins or [] if isinstance(item, dict)],
                }
            )
        return _with_data_source_write_contract(
            {
                "source": resource["resource_id"],
                "kind": "data_table",
                "source_kind": "snapshot",
                "storage_mode": resource["storage_mode"],
                "record_key_field": resource.get("record_key_field") or "id",
                "columns": self._managed_dataset_resource_columns_with_conn(
                    conn,
                    module_name,
                    resource,
                    extra_fields=extra_fields,
                ),
                "system_fields": _managed_dataset_system_fields(),
                "writable_fields": [],
                "required_fields": [],
                "read_only_fields": [],
                "indexes": dict(resource.get("indexes") or {}),
                "joins": [],
            }
        )

    def _coerce_custom_table_query_rows(
        self,
        resource: dict[str, Any],
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        column_map = {column["name"]: column for column in self._custom_table_schema_columns(resource)}
        rendered: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any] = {}
            for field, value in row.items():
                column = column_map.get(field)
                if column is None:
                    payload[field] = value
                    continue
                payload[field] = _python_value_for_custom_table_column(value, column_type=column["type"])
            rendered.append(payload)
        return rendered

    def _resource_has_records_with_conn(self, conn, module_name: str, resource: dict[str, Any]) -> bool:
        if resource["storage_mode"] == "custom_table":
            self._ensure_custom_table_with_conn(conn, resource)
            table_identifier = _quote_identifier(resource["physical_table_name"])
            row = conn.execute(f"SELECT 1 FROM {table_identifier} LIMIT 1").fetchone()
            return row is not None
        row = conn.execute(
            """
            SELECT 1
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            LIMIT 1
            """,
            (module_name, resource["logical_name"]),
        ).fetchone()
        return row is not None

    def _expected_custom_table_column_map(self, resource: dict[str, Any]) -> dict[str, tuple[str, bool, bool, bool]]:
        expected: dict[str, tuple[str, bool, bool, bool]] = {}
        record_key_field = resource.get("record_key_field")
        for column in self._custom_table_schema_columns(resource):
            expected[column["name"]] = (
                _CUSTOM_TABLE_TYPE_MAP[column["type"]],
                bool(column["nullable"]),
                column["name"] == record_key_field,
                bool(column.get("auto_increment")),
            )
        expected["created_at"] = ("INTEGER", True, False, False)
        expected["updated_at"] = ("INTEGER", True, False, False)
        return expected

    def _assert_custom_table_matches_resource(self, conn, resource: dict[str, Any]) -> None:
        physical_table_name = resource["physical_table_name"]
        table_info = conn.execute(f"PRAGMA table_info({_quote_identifier(physical_table_name)})").fetchall()
        table_sql_row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (physical_table_name,),
        ).fetchone()
        table_sql = str(table_sql_row["sql"] or "").upper() if table_sql_row else ""
        existing = {
            row["name"]: (
                str(row["type"] or "").upper(),
                not bool(row["notnull"]),
                bool(row["pk"]),
                bool(row["pk"]) and "AUTOINCREMENT" in table_sql,
            )
            for row in table_info
        }
        if set(existing) == _LEGACY_CUSTOM_TABLE_COLUMNS:
            raise RuntimeError(f"legacy generic custom table schema is no longer supported: {physical_table_name}")
        expected = self._expected_custom_table_column_map(resource)
        if set(existing) != set(expected):
            raise RuntimeError(
                f"custom table schema mismatch for {physical_table_name}: "
                f"expected_columns={sorted(expected)}, existing_columns={sorted(existing)}"
            )
        for column_name, (expected_type, expected_nullable, expected_pk, expected_auto_increment) in expected.items():
            existing_type, existing_nullable, existing_pk, existing_auto_increment = existing[column_name]
            if (
                existing_type != expected_type
                or existing_nullable != expected_nullable
                or existing_pk != expected_pk
                or existing_auto_increment != expected_auto_increment
            ):
                raise RuntimeError(
                    f"custom table column mismatch for {physical_table_name}.{column_name}: "
                    f"expected={(expected_type, expected_nullable, expected_pk, expected_auto_increment)}, "
                    f"existing={(existing_type, existing_nullable, existing_pk, existing_auto_increment)}"
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
                CREATE INDEX IF NOT EXISTS {_quote_identifier(f"idx_{physical_table_name}_{index_name}")}
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
                    if column.get("auto_increment"):
                        rendered += " AUTOINCREMENT"
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
            raise ValueError("db view placeholders must exactly match source_resource_ids")

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

    def _add_custom_table_rows_with_conn(
        self,
        conn,
        resource: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> list[Any]:
        physical_table_name = resource["physical_table_name"]
        table_identifier = _quote_identifier(physical_table_name)
        self._ensure_custom_table_with_conn(conn, resource)
        column_defs = self._custom_table_schema_columns(resource)
        column_names = [column["name"] for column in column_defs]
        record_key_field = resource["record_key_field"]
        record_key_column = _custom_table_record_key_column(column_defs, record_key_field=record_key_field)
        auto_increment_key = bool(record_key_column.get("auto_increment"))
        seen_keys: set[str] = set()
        inserted_keys: list[Any] = []

        for record_index, original_record in enumerate(records):
            record = dict(original_record)
            if auto_increment_key and _normalize_text(record.get(record_key_field)) is None:
                record.pop(record_key_field, None)

            record_key = _record_key_for_write(
                record,
                record_index,
                record_key_field=record_key_field,
                require_key=not auto_increment_key,
            )
            generated_record_key = auto_increment_key and record_key is None
            if record_key is None and not auto_increment_key:
                raise ValueError("custom table records require a record_key")
            if record_key is not None:
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

            insert_column_names: list[str] = []
            row_values: list[Any] = []
            for column in column_defs:
                column_name = column["name"]
                if generated_record_key and column_name == record_key_field:
                    continue
                insert_column_names.append(column_name)
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

            insert_columns = ", ".join(
                [_quote_identifier(column) for column in insert_column_names] + ["created_at", "updated_at"]
            )
            insert_params = ", ".join(["?"] * (len(insert_column_names) + 2))
            cursor = conn.execute(
                f"""
                INSERT INTO {table_identifier} ({insert_columns})
                VALUES ({insert_params})
                """,
                tuple(row_values + [now, now]),
            )
            if generated_record_key:
                inserted_keys.append(cursor.lastrowid)
            else:
                inserted_keys.append(
                    _sqlite_value_for_custom_table_column(
                        record[record_key_field], column_type=record_key_column["type"]
                    )
                )

        return inserted_keys

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
                resource,
                records,
                now=now,
            )
        return True

    def _add_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> list[Any]:
        now = int(time.time())
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_resource_write_lock_key(module_name, resource_id)],
            operation=lambda conn: self._add_resource_records_with_conn(
                conn,
                module_name,
                resource_id,
                records,
                now=now,
            ),
        )

    def _add_resource_records_with_conn(
        self,
        conn,
        module_name: str,
        resource_id: str,
        records: list[dict[str, Any]],
        *,
        now: int,
    ) -> list[Any]:
        resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
        if resource["storage_mode"] != "custom_table":
            raise ValueError("add_records only supports custom_table resources")
        return self._add_custom_table_rows_with_conn(conn, resource, records, now=now)

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
        if resource["storage_mode"] == "custom_table":
            self._upsert_custom_table_rows_with_conn(conn, resource, records, now=now)
        else:
            self._upsert_managed_dataset_rows_with_conn(conn, module_name, resource, records, now=now)
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
        if resource["storage_mode"] == "custom_table":
            return self._update_custom_table_rows_with_conn(conn, resource, fields, where=where, now=now)
        return self._update_managed_dataset_rows_with_conn(conn, module_name, resource, fields, where=where, now=now)

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
        if resource["storage_mode"] == "custom_table":
            return self._delete_custom_table_rows_with_conn(conn, resource, where=where)
        return self._delete_managed_dataset_rows_with_conn(conn, module_name, resource, where=where)

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
        if kind == "add_records":
            return self._add_resource_records_with_conn(
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
        if kind in {"replace_records", "add_records", "upsert_records", "update_records", "delete_records"}:
            return [_resource_write_lock_key(module_name, str(operation.get("resource") or ""))]
        if kind == "append_audit_event":
            return [_audit_write_lock_key(module_name, str(operation.get("dataset") or ""))]
        return [_module_write_lock_key(module_name)]

    def _append_audit_event_row(self, module_name: str, dataset_name: str, event: dict[str, Any]) -> str:
        return get_db_write_coordinator().run_write(
            DATA_DB,
            lock_keys=[_audit_write_lock_key(module_name, dataset_name)],
            operation=lambda conn: self._append_audit_event_row_with_conn(conn, module_name, dataset_name, event),
        )

    def _append_audit_event_row_with_conn(
        self, conn, module_name: str, dataset_name: str, event: dict[str, Any]
    ) -> str:
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

    def describe_data_source(
        self,
        module_name: str,
        source_id: str,
        *,
        extra_fields: list[str] | None = None,
        joins: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_source_id = _validate_snake_case_identifier(str(source_id or ""))
        with get_connection(DATA_DB) as conn:
            resource = self._read_resource_row_with_conn(conn, module_name, normalized_source_id)
            if resource is not None:
                return self._resource_query_descriptor_with_conn(
                    conn,
                    module_name,
                    resource,
                    extra_fields=extra_fields,
                    joins=joins,
                )
            view = self._read_db_view_row_with_conn(conn, module_name, normalized_source_id)
            if view is not None:
                view = self._ensure_db_view_with_conn(conn, module_name, normalized_source_id)
                return _with_data_source_write_contract(
                    {
                        "source": normalized_source_id,
                        "kind": "data_view",
                        "source_kind": "read_model",
                        "columns": [_read_only_column_descriptor(dict(column)) for column in view["columns"]],
                        "system_fields": [],
                        "writable_fields": [],
                        "required_fields": [],
                        "read_only_fields": [],
                        "joins": [],
                    }
                )
        raise ValueError(f"未注册的数据源: {normalized_source_id}")

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
        managed_dataset_count_alias = (
            _managed_dataset_count_alias(select_items) if source_kind == "snapshot" and has_aggregate else None
        )
        if source_kind != "relation" and (joins or group_by or has_aggregate):
            label = "managed_dataset(snapshot)" if source_kind == "snapshot" else "view(read_model)"
            if joins:
                raise ValueError(f"source '{source_id}' is {label}; join is only supported for custom_table(relation)")
            if group_by:
                raise ValueError(f"source '{source_id}' is {label}; group_by is not supported")
            if managed_dataset_count_alias is None:
                if source_kind == "snapshot":
                    raise ValueError(f"source '{source_id}' is {label}; only supports count(*) aggregate")
                raise ValueError(f"source '{source_id}' is {label}; aggregate is not supported")
        if source_kind == "snapshot":
            descriptor = self.describe_data_source(module_name, source_id)
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
        with get_connection(DATA_DB) as conn:
            return self._execute_snapshot_plan_with_conn(conn, module_name, source_id, descriptor, plan)

    def _execute_snapshot_plan_with_conn(
        self,
        conn,
        module_name: str,
        source_id: str,
        descriptor: dict[str, Any],
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        json_column_names = _managed_dataset_json_column_names(descriptor)
        where = _normalize_plan_where(plan.get("where"))
        order_by = _normalize_db_view_sort(plan.get("order_by") or [])
        select_items = [dict(item) for item in plan.get("select") or [] if isinstance(item, dict)]
        count_alias = _managed_dataset_count_alias(select_items)
        if count_alias is not None:
            for item in _iter_where_predicates(where):
                if _managed_dataset_field_mode(item["field"], json_column_names=json_column_names) is None:
                    raise ValueError(f"query filter field not found: {item['field']}")
            resource = self._require_resource_row_with_conn(conn, module_name, source_id)
            where_sql, params = _render_managed_dataset_where_clause(where, json_column_names=json_column_names)
            filter_sql = f" AND {where_sql.removeprefix(' WHERE ')}" if where_sql else ""
            row = conn.execute(
                f"""
                SELECT COUNT(*) AS {_quote_identifier(count_alias)}
                FROM module_datasets
                WHERE module_name = ? AND dataset_name = ?
                {filter_sql}
                """,
                (
                    module_name,
                    resource["logical_name"],
                    *params,
                ),
            ).fetchone()
            return [{count_alias: int(row[count_alias] if row else 0)}]

        selected_fields: list[str] = []
        has_wildcard_select = False
        for item in select_items:
            if item.get("kind", "column") != "column":
                continue
            raw_field = str(item.get("field") or "")
            if raw_field == "*":
                has_wildcard_select = True
                continue
            selected_fields.append(_validate_snake_case_identifier(raw_field))
        if has_wildcard_select:
            selected_fields = _managed_dataset_all_fields(descriptor)
        for field in selected_fields:
            if _managed_dataset_field_mode(field, json_column_names=json_column_names) is None:
                raise ValueError(f"query select field not found: {field}")
        for item in _iter_where_predicates(where):
            if _managed_dataset_field_mode(item["field"], json_column_names=json_column_names) is None:
                raise ValueError(f"query filter field not found: {item['field']}")
        for item in order_by:
            if _managed_dataset_field_mode(item["field"], json_column_names=json_column_names) is None:
                raise ValueError(f"query sort field not found: {item['field']}")

        resource = self._require_resource_row_with_conn(conn, module_name, source_id)
        if not selected_fields:
            selected_fields = _managed_dataset_all_fields(descriptor)
        select_sql = ", ".join(
            f"{_managed_dataset_field_sql(field, json_column_names=json_column_names)} AS {_quote_identifier(field)}"
            for field in selected_fields
        )
        where_sql, params = _render_managed_dataset_where_clause(where, json_column_names=json_column_names)
        filter_sql = f" AND {where_sql.removeprefix(' WHERE ')}" if where_sql else ""
        order_sql = ""
        if order_by:
            order_sql = " ORDER BY " + ", ".join(
                f"{_managed_dataset_field_sql(item['field'], json_column_names=json_column_names)} {item['direction'].upper()}"
                for item in order_by
            )
        pagination_sql, pagination_params = _render_plan_pagination(plan.get("limit"), plan.get("offset"))
        rows = conn.execute(
            f"""
            SELECT {select_sql}
            FROM module_datasets
            WHERE module_name = ? AND dataset_name = ?
            {filter_sql}
            {order_sql}
            {pagination_sql}
            """,
            (
                module_name,
                resource["logical_name"],
                *params,
                *pagination_params,
            ),
        ).fetchall()

        return [dict(row) for row in rows]

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

        select_sql: list[str] = []
        selected_aliases: set[str] = set()
        for field in group_by:
            select_sql.append(f"{resolve_field(field)} AS {_quote_identifier(field)}")
            selected_aliases.add(field)
        if not select_items and not group_by:
            select_sql = [
                f"base.{_quote_identifier(column['name'])} AS {_quote_identifier(column['name'])}"
                for column in descriptor["columns"]
            ]
            selected_aliases.update(column["name"] for column in descriptor["columns"])
        for item in select_items:
            kind = str(item.get("kind") or "column")
            if kind == "column":
                raw_field = str(item.get("field") or "")
                if raw_field == "*":
                    for column in descriptor["columns"]:
                        field = column["name"]
                        if field not in selected_aliases:
                            select_sql.append(f"{resolve_field(field)} AS {_quote_identifier(field)}")
                            selected_aliases.add(field)
                    continue
                field = _validate_snake_case_identifier(raw_field)
                if field in group_by:
                    continue
                select_sql.append(f"{resolve_field(field)} AS {_quote_identifier(field)}")
                selected_aliases.add(field)
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
                select_sql.append(
                    f"{func.upper()}({resolve_field(_validate_snake_case_identifier(field))}) AS {_quote_identifier(alias)}"
                )
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

        def render_predicate(item: dict[str, Any]) -> tuple[str, list[Any]]:
            field_sql = resolve_field(item["field"])
            op = item["op"]
            if op == "is_null":
                return f"{field_sql} IS NULL", []
            if op == "eq":
                return f"{field_sql} = ?", [item.get("value")]
            if op == "in":
                values = list(item.get("value") or [])
                if not values:
                    return "1 = 0", []
                return f"{field_sql} IN ({', '.join(['?'] * len(values))})", values
            if op == "between":
                values = list(item.get("value") or [])
                if len(values) != 2:
                    raise ValueError("between filter value must contain two items")
                return f"{field_sql} BETWEEN ? AND ?", values
            sql_op = _SQL_FILTER_OPS[op]
            return f"{field_sql} {sql_op} ?", [item.get("value")]

        where_sql, params = _render_where_conditions(where, render_predicate)

        group_sql = ""
        if group_by:
            group_sql = " GROUP BY " + ", ".join(resolve_field(field) for field in group_by)
        rendered_select_aliases = {str(item.get("alias") or item.get("field") or "") for item in select_items} | set(
            group_by
        )
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
        pagination_sql, pagination_params = _render_plan_pagination(plan.get("limit"), plan.get("offset"))
        params.extend(pagination_params)

        rows = conn.execute(
            f"""
            SELECT {", ".join(select_sql)}
            FROM {source_identifier} AS base
            {" ".join(join_sql)}
            {where_sql}
            {group_sql}
            {order_sql}
            {pagination_sql}
            """,
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]

    def _query_resource_records_with_conn(
        self,
        conn,
        module_name: str,
        resource: dict[str, Any],
        *,
        select: Any = None,
        where: Any = None,
        order_by: list[dict[str, Any]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        select_items = _normalize_resource_query_select(select)
        normalized_where = _normalize_plan_where(where)
        normalized_order_by = _normalize_db_view_sort(order_by or [])
        descriptor = self._resource_query_descriptor_with_conn(
            conn,
            module_name,
            resource,
        )
        plan = {
            "kind": "select",
            "base": {"source": resource["resource_id"]},
            "select": select_items,
            "where": normalized_where,
            "order_by": normalized_order_by,
            "limit": limit,
            "offset": offset,
        }
        if resource["storage_mode"] == "managed_dataset":
            return self._execute_snapshot_plan_with_conn(
                conn,
                module_name,
                resource["resource_id"],
                descriptor,
                plan,
            )
        rows = self._execute_sql_source_plan_with_conn(
            conn,
            source_identifier=_quote_identifier(resource["physical_table_name"]),
            descriptor=descriptor,
            plan=plan,
        )
        return self._coerce_custom_table_query_rows(resource, rows)

    def query_resource_records(
        self,
        module_name: str,
        resource_id: str,
        *,
        select: Any = None,
        where: Any = None,
        order_by: list[dict[str, Any]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(DATA_DB) as conn:
            resource = self._require_resource_row_with_conn(conn, module_name, resource_id)
            return self._query_resource_records_with_conn(
                conn,
                module_name,
                resource,
                select=select,
                where=where,
                order_by=order_by,
                limit=limit,
                offset=offset,
            )

    def replace_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> bool:
        return self._replace_resource_records(module_name, resource_id, _normalize_records_for_write(records))

    def add_resource_records(self, module_name: str, resource_id: str, records: list[dict[str, Any]]) -> list[Any]:
        return self._add_resource_records(module_name, resource_id, _normalize_records_for_write(records))

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
                sql = str(view.get("sql") or "").strip()
                if not sql:
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
                target_resource = self._read_resource_row_with_conn(conn, module_name, seed["resource_id"])
                if target_resource is None:
                    raise ValueError(f"seed target resource not found: {seed['resource_id']}")
                if seed["mode"] == "replace_if_empty" and self._resource_has_records_with_conn(
                    conn,
                    module_name,
                    target_resource,
                ):
                    continue
                if target_resource["storage_mode"] == "custom_table":
                    self._write_custom_table_rows_with_conn(conn, target_resource, records, now=now)
                else:
                    self._write_managed_dataset_rows_with_conn(
                        conn,
                        module_name,
                        target_resource,
                        records,
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
            str(page_id): _normalize_schema(schema) for page_id, schema in dict(page_schemas or {}).items()
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
