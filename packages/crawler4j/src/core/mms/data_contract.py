"""Module data contract normalization and validation helpers."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any


_IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RESOURCE_STORAGE_MODES = {"managed_dataset", "custom_table"}
_RESOURCE_CLEANUP_POLICIES = {"delete_rows", "drop_table", "keep"}
_VIEW_CLEANUP_POLICIES = {"drop_view", "keep"}
_COLUMN_TYPES = {"text", "int", "number", "bool", "json"}
_BLOCKED_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|attach|detach|pragma|create|replace)\b",
    re.IGNORECASE,
)
_RESOURCE_REF_RE = re.compile(r"\{\{resource:([a-z][a-z0-9_]*)\}\}")
_SQL_REF_RE = re.compile(r"\b(?:from|join)\s+([^\s,()]+)", re.IGNORECASE)


def _normalize_identifier(raw: Any, *, field_name: str) -> str:
    value = str(raw or "").strip()
    if not _IDENT_RE.fullmatch(value):
        raise ValueError(f"{field_name} 必须是 snake_case 标识符")
    return value


def _normalize_mapping(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是 YAML 映射对象")
    return dict(raw)


def _normalize_list(raw: Any, *, field_name: str) -> list[Any]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是数组")
    return list(raw)


def _normalize_column(raw: Any, *, field_name: str, allow_auto_increment: bool = False) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 中的每一项都必须是对象")
    allowed_keys = {"name", "key", "type", "nullable", "required"}
    if allow_auto_increment:
        allowed_keys.add("auto_increment")
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
    name = _normalize_identifier(raw.get("name") or raw.get("key"), field_name=f"{field_name}.name")
    column_type = str(raw.get("type") or "text").strip().lower()
    if column_type not in _COLUMN_TYPES:
        raise ValueError(f"{field_name}.{name}.type 不支持: {column_type}")
    column = {
        "name": name,
        "type": column_type,
        "nullable": bool(raw.get("nullable")) if "nullable" in raw else not bool(raw.get("required")),
    }
    if allow_auto_increment and bool(raw.get("auto_increment")):
        column["auto_increment"] = True
    return column


def _normalize_custom_table_schema(raw: Any, *, record_key_field: str) -> dict[str, Any]:
    schema = _normalize_mapping(raw, field_name="data.resources[].schema")
    raw_columns = _normalize_list(schema.get("columns"), field_name="data.resources[].schema.columns")
    columns = [
        _normalize_column(item, field_name="data.resources[].schema.columns", allow_auto_increment=True)
        for item in raw_columns
    ]
    if not columns:
        raise ValueError("custom_table 资源必须声明 schema.columns")
    column_names = {column["name"] for column in columns}
    if record_key_field not in column_names:
        raise ValueError(f"custom_table 资源必须包含主键列: {record_key_field}")
    auto_increment_columns = [column for column in columns if column.get("auto_increment")]
    if auto_increment_columns:
        if len(auto_increment_columns) > 1:
            raise ValueError("custom_table 资源最多只能声明一个 auto_increment 字段")
        auto_increment_column = auto_increment_columns[0]
        if auto_increment_column["name"] != record_key_field:
            raise ValueError("custom_table auto_increment 字段必须是 record_key_field")
        if auto_increment_column["type"] != "int":
            raise ValueError("custom_table auto_increment record_key_field 必须是 int")
    normalized_columns: list[dict[str, Any]] = []
    for column in columns:
        payload = dict(column)
        if payload["name"] == record_key_field:
            payload["nullable"] = False
        normalized_columns.append(payload)
    version = schema.get("version") or schema.get("schema_version") or 1
    try:
        version_value = int(version)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"data.resources[].schema.version 不是合法整数: {version}") from exc
    if version_value < 1:
        raise ValueError("data.resources[].schema.version 必须 >= 1")
    return {"version": version_value, "columns": normalized_columns}


def _normalize_resource_schema(raw: Any, *, record_key_field: str) -> dict[str, Any]:
    schema = _normalize_mapping(raw, field_name="data.resources[].schema")
    raw_columns = _normalize_list(schema.get("columns"), field_name="data.resources[].schema.columns")
    columns = [
        _normalize_column(item, field_name="data.resources[].schema.columns", allow_auto_increment=True)
        for item in raw_columns
    ]
    if not columns:
        raise ValueError("data.resources[].schema.columns 不能为空")
    column_names = {column["name"] for column in columns}
    if record_key_field not in column_names:
        raise ValueError(f"data.resources[].schema.columns 必须包含主键列: {record_key_field}")
    if any(column.get("auto_increment") for column in columns):
        raise ValueError("managed_dataset 不支持 auto_increment 字段")
    normalized_columns: list[dict[str, Any]] = []
    for column in columns:
        payload = dict(column)
        if payload["name"] == record_key_field:
            payload["nullable"] = False
        normalized_columns.append(payload)
    version = schema.get("version") or schema.get("schema_version") or 1
    try:
        version_value = int(version)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"data.resources[].schema.version 不是合法整数: {version}") from exc
    if version_value < 1:
        raise ValueError("data.resources[].schema.version 必须 >= 1")
    return {"version": version_value, "columns": normalized_columns}


def _normalize_join_entry(raw: Any, *, resource_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"data.resources[{resource_id}].joins 中的每一项都必须是对象")
    allowed_keys = {"target", "on", "type", "types"}
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"data.resources[{resource_id}].joins 包含不支持的字段: " + ", ".join(unknown_keys))
    target = _normalize_identifier(raw.get("target"), field_name=f"data.resources[{resource_id}].joins[].target")
    on = _normalize_mapping(raw.get("on"), field_name=f"data.resources[{resource_id}].joins[{target}].on")
    if not on:
        raise ValueError(f"data.resources[{resource_id}].joins[{target}].on 不能为空")
    normalized_on = [
        {
            "left": _normalize_identifier(left, field_name=f"data.resources[{resource_id}].joins[{target}].on.left"),
            "right": _normalize_identifier(right, field_name=f"data.resources[{resource_id}].joins[{target}].on.right"),
        }
        for left, right in on.items()
    ]
    raw_types = raw.get("types")
    if raw_types is None:
        raw_types = [raw.get("type") or "inner"]
    join_types = [
        str(item or "").strip().lower()
        for item in _normalize_list(raw_types, field_name=f"data.resources[{resource_id}].joins[{target}].types")
    ]
    if not join_types or any(item not in {"inner", "left"} for item in join_types):
        raise ValueError(f"data.resources[{resource_id}].joins[{target}].types 只支持 inner/left")
    return {"target": target, "types": sorted(set(join_types)), "on": normalized_on}


def _normalize_indexes(raw: Any, *, field_name: str, column_names: set[str]) -> dict[str, list[str]]:
    indexes = _normalize_mapping(raw, field_name=field_name)
    normalized: dict[str, list[str]] = {}
    for raw_name, raw_columns in indexes.items():
        index_name = _normalize_identifier(raw_name, field_name=f"{field_name}.<index>")
        columns = _normalize_list(raw_columns, field_name=f"{field_name}.{index_name}")
        if not columns:
            raise ValueError(f"{field_name}.{index_name} 必须声明至少一个字段")
        resolved: list[str] = []
        for raw_column in columns:
            column_name = _normalize_identifier(raw_column, field_name=f"{field_name}.{index_name}.<column>")
            if column_name not in column_names:
                raise ValueError(f"{field_name}.{index_name} 引用了未声明字段: {column_name}")
            resolved.append(column_name)
        normalized[index_name] = resolved
    return normalized


def _normalize_resource_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("data.resources 中的每一项都必须是对象")
    allowed_keys = {"id", "storage_mode", "record_key_field", "schema", "indexes", "cleanup_policy", "joins"}
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError("data.resources 包含不支持的字段: " + ", ".join(unknown_keys))

    resource_id = _normalize_identifier(raw.get("id"), field_name="data.resources[].id")
    storage_mode = str(raw.get("storage_mode") or "managed_dataset").strip().lower()
    if storage_mode not in _RESOURCE_STORAGE_MODES:
        raise ValueError(f"data.resources[{resource_id}].storage_mode 不支持: {storage_mode}")
    record_key_field = _normalize_identifier(
        raw.get("record_key_field") or "id",
        field_name=f"data.resources[{resource_id}].record_key_field",
    )
    cleanup_policy = (
        str(raw.get("cleanup_policy") or ("delete_rows" if storage_mode == "managed_dataset" else "drop_table"))
        .strip()
        .lower()
    )
    if cleanup_policy not in _RESOURCE_CLEANUP_POLICIES:
        raise ValueError(f"data.resources[{resource_id}].cleanup_policy 不支持: {cleanup_policy}")

    if storage_mode == "custom_table":
        schema = _normalize_custom_table_schema(raw.get("schema"), record_key_field=record_key_field)
        indexes = _normalize_indexes(
            raw.get("indexes"),
            field_name=f"data.resources[{resource_id}].indexes",
            column_names={column["name"] for column in schema["columns"]},
        )
        joins = [
            _normalize_join_entry(item, resource_id=resource_id)
            for item in _normalize_list(raw.get("joins"), field_name=f"data.resources[{resource_id}].joins")
        ]
    else:
        schema = _normalize_resource_schema(raw.get("schema"), record_key_field=record_key_field)
        indexes = _normalize_mapping(raw.get("indexes"), field_name=f"data.resources[{resource_id}].indexes")
        joins = _normalize_list(raw.get("joins"), field_name=f"data.resources[{resource_id}].joins")
        if joins:
            raise ValueError(f"data.resources[{resource_id}].joins 只允许 custom_table 声明")

    return {
        "resource_id": resource_id,
        "storage_mode": storage_mode,
        "record_key_field": record_key_field,
        "schema": schema,
        "indexes": indexes,
        "joins": joins,
        "cleanup_policy": cleanup_policy,
    }


def _normalize_view_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("data.views 中的每一项都必须是对象")
    allowed_keys = {
        "id",
        "view_kind",
        "source_resource_ids",
        "sql_file",
        "sql",
        "columns",
        "cleanup_policy",
        "schema_version",
    }
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError("data.views 包含不支持的字段: " + ", ".join(unknown_keys))

    view_id = _normalize_identifier(raw.get("id"), field_name="data.views[].id")
    view_kind = str(raw.get("view_kind") or "sql_view").strip().lower()
    if view_kind != "sql_view":
        raise ValueError(f"data.views[{view_id}].view_kind 只支持 sql_view")
    source_resource_ids = [
        _normalize_identifier(item, field_name=f"data.views[{view_id}].source_resource_ids")
        for item in _normalize_list(
            raw.get("source_resource_ids"), field_name=f"data.views[{view_id}].source_resource_ids"
        )
    ]
    if not source_resource_ids:
        raise ValueError(f"data.views[{view_id}].source_resource_ids 不能为空")
    sql_file = str(raw.get("sql_file") or "").strip()
    sql = str(raw.get("sql") or "").strip()
    if not sql_file and not sql:
        raise ValueError(f"data.views[{view_id}].sql_file 或 sql 不能为空")
    columns = [
        _normalize_column(item, field_name=f"data.views[{view_id}].columns")
        for item in _normalize_list(raw.get("columns"), field_name=f"data.views[{view_id}].columns")
    ]
    if not columns:
        raise ValueError(f"data.views[{view_id}].columns 不能为空")
    cleanup_policy = str(raw.get("cleanup_policy") or "drop_view").strip().lower()
    if cleanup_policy not in _VIEW_CLEANUP_POLICIES:
        raise ValueError(f"data.views[{view_id}].cleanup_policy 只支持 drop_view/keep")
    try:
        schema_version = int(raw.get("schema_version") or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"data.views[{view_id}].schema_version 不是合法整数") from exc
    if schema_version < 1:
        raise ValueError(f"data.views[{view_id}].schema_version 必须 >= 1")
    return {
        "view_id": view_id,
        "view_kind": view_kind,
        "source_resource_ids": source_resource_ids,
        "sql_file": sql_file,
        "sql": sql,
        "columns": columns,
        "cleanup_policy": cleanup_policy,
        "schema_version": schema_version,
    }


def _normalize_seed_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("data.seeds 中的每一项都必须是对象")
    allowed_keys = {"id", "resource_id", "file", "format", "mode"}
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError("data.seeds 包含不支持的字段: " + ", ".join(unknown_keys))
    seed_id = _normalize_identifier(raw.get("id"), field_name="data.seeds[].id")
    resource_id = _normalize_identifier(raw.get("resource_id"), field_name=f"data.seeds[{seed_id}].resource_id")
    file_path = str(raw.get("file") or "").strip()
    if not file_path:
        raise ValueError(f"data.seeds[{seed_id}].file 不能为空")
    seed_format = str(raw.get("format") or "json").strip().lower()
    if seed_format != "json":
        raise ValueError(f"data.seeds[{seed_id}].format 目前只支持 json")
    mode = str(raw.get("mode") or "replace_if_empty").strip().lower()
    if mode not in {"replace", "replace_if_empty"}:
        raise ValueError(f"data.seeds[{seed_id}].mode 只支持 replace/replace_if_empty")
    return {
        "seed_id": seed_id,
        "resource_id": resource_id,
        "file": file_path,
        "format": seed_format,
        "mode": mode,
    }


def normalize_manifest_data(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {"resources": [], "views": [], "seeds": []}
    if not isinstance(raw, dict):
        raise ValueError("data 必须是 YAML 映射对象")
    allowed_keys = {"resources", "views", "seeds"}
    unknown_keys = sorted(set(raw) - allowed_keys)
    if unknown_keys:
        raise ValueError("data 包含不支持的字段: " + ", ".join(unknown_keys))

    resources = [
        _normalize_resource_entry(item) for item in _normalize_list(raw.get("resources"), field_name="data.resources")
    ]
    views = [_normalize_view_entry(item) for item in _normalize_list(raw.get("views"), field_name="data.views")]
    seeds = [_normalize_seed_entry(item) for item in _normalize_list(raw.get("seeds"), field_name="data.seeds")]

    resource_ids = {item["resource_id"] for item in resources}
    view_ids = {item["view_id"] for item in views}
    seed_ids = {item["seed_id"] for item in seeds}
    if len(resource_ids) != len(resources):
        raise ValueError("data.resources[].id 不能重复")
    if len(view_ids) != len(views):
        raise ValueError("data.views[].id 不能重复")
    if len(seed_ids) != len(seeds):
        raise ValueError("data.seeds[].id 不能重复")
    duplicated_sources = sorted(resource_ids & view_ids)
    if duplicated_sources:
        raise ValueError("data.resources[].id 与 data.views[].id 不能重复: " + ", ".join(duplicated_sources))

    resource_map = {item["resource_id"]: item for item in resources}
    for resource in resources:
        for join in resource.get("joins", []):
            target = resource_map.get(join["target"])
            if target is None:
                raise ValueError(f"data.resources[{resource['resource_id']}].joins 引用了未声明资源: {join['target']}")
            if target["storage_mode"] != "custom_table":
                raise ValueError(
                    f"data.resources[{resource['resource_id']}].joins 只允许连接 custom_table: {join['target']}"
                )
            left_columns = {column["name"] for column in resource["schema"]["columns"]}
            right_columns = {column["name"] for column in target["schema"]["columns"]}
            for pair in join["on"]:
                if pair["left"] not in left_columns:
                    raise ValueError(
                        f"data.resources[{resource['resource_id']}].joins 引用了未声明字段: {pair['left']}"
                    )
                if pair["right"] not in right_columns:
                    raise ValueError(
                        f"data.resources[{resource['resource_id']}].joins 引用了目标未声明字段: {pair['right']}"
                    )

    for view in views:
        for resource_id in view["source_resource_ids"]:
            if resource_id not in resource_ids:
                raise ValueError(f"data.views[{view['view_id']}] 引用了未声明资源: {resource_id}")
            if resource_map[resource_id]["storage_mode"] != "custom_table":
                raise ValueError(f"data.views[{view['view_id']}] 只允许引用 custom_table: {resource_id}")
    for seed in seeds:
        if seed["resource_id"] not in resource_ids:
            raise ValueError(f"data.seeds[{seed['seed_id']}] 引用了未声明资源: {seed['resource_id']}")

    return {
        "resources": resources,
        "views": views,
        "seeds": seeds,
    }


def load_sql_file(module_root: Path, relative_path: str, *, expected_prefix: str) -> str:
    normalized = str(relative_path or "").strip()
    if not normalized:
        raise ValueError("SQL 文件路径不能为空")
    if not normalized.startswith(expected_prefix):
        raise ValueError(f"SQL 文件必须位于 {expected_prefix}")
    root = module_root.resolve()
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"SQL 文件路径越界: {relative_path}") from exc
    if not target.is_file():
        raise ValueError(f"找不到 SQL 文件: {relative_path}")
    sql = target.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError(f"SQL 文件为空: {relative_path}")
    if ";" in sql:
        raise ValueError(f"SQL 文件必须只包含单条语句: {relative_path}")
    if _BLOCKED_SQL_RE.search(sql):
        raise ValueError(f"SQL 文件包含被禁止的关键字: {relative_path}")
    if not re.match(r"^\s*(with\b|select\b)", sql, flags=re.IGNORECASE):
        raise ValueError(f"SQL 文件必须以 SELECT / WITH 开头: {relative_path}")
    return sql


def validate_resource_sql(sql: str, *, source_resource_ids: list[str], owner_label: str) -> None:
    placeholders = _RESOURCE_REF_RE.findall(sql)
    if not placeholders:
        raise ValueError(f"{owner_label} 必须至少引用一个 {{resource:<id>}} 占位符")
    for token in _SQL_REF_RE.findall(sql):
        if not _RESOURCE_REF_RE.fullmatch(token):
            raise ValueError(f"{owner_label} 的 FROM/JOIN 只允许引用 {{resource:<id>}} 占位符")
    if set(placeholders) != set(source_resource_ids):
        raise ValueError(f"{owner_label} 的 SQL 占位符必须与 source_resource_ids 完全一致")


def validate_seed_file(module_root: Path, relative_path: str) -> list[dict[str, Any]]:
    normalized = str(relative_path or "").strip()
    if not normalized:
        raise ValueError("种子文件路径不能为空")
    if not normalized.startswith("data/seeds/"):
        raise ValueError("种子文件必须位于 data/seeds/")
    root = module_root.resolve()
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"种子文件路径越界: {relative_path}") from exc
    if not target.is_file():
        raise ValueError(f"找不到种子文件: {relative_path}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError(f"种子文件必须是对象数组 JSON: {relative_path}")
    return [dict(item) for item in payload]
