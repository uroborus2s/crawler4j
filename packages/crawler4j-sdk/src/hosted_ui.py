"""Shared hosted UI schema normalization helpers."""

from __future__ import annotations

import re
from typing import Any

MANAGED_VIEW_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HOSTED_PAGE_ENTRY_RE = re.compile(r"^core:(page|data_table):([a-z][a-z0-9_]*)$")
ALLOWED_TABLE_SCHEMA_KEYS = {
    "title",
    "dataset",
    "primary_key",
    "lock_scope",
    "lock_key",
    "display_fields",
    "create_fields",
    "update_fields",
    "create_handler",
    "update_handler",
    "columns",
}
ALLOWED_TABLE_COLUMN_KEYS = {
    "key",
    "label",
    "visible",
    "required",
    "type",
    "options",
    "default",
}
ALLOWED_TABLE_COLUMN_TYPES = {"text", "number", "int", "bool", "select"}
BUSINESS_OCCUPANCY_COLUMN_KEYS = {
    "occupied",
    "occupied_label",
    "is_occupied",
    "lock_status",
    "lock_status_label",
}
BUSINESS_OCCUPANCY_COLUMN_LABELS = {"占用中", "占用状态"}
ALLOWED_PAGE_LAYOUT_KEYS = {"direction", "kind", "columns", "gap"}
ALLOWED_PAGE_SCHEMA_KEYS = {"type", "title", "load_handler", "children", "layout"}
ALLOWED_SECTION_SCHEMA_KEYS = {"type", "title", "children", "variant", "layout"}
ALLOWED_TEXT_SCHEMA_KEYS = {"type", "text", "binding", "style"}
ALLOWED_BUTTON_SCHEMA_KEYS = {"type", "label", "action"}
ALLOWED_BUTTON_ACTION_KEYS = {"type", "entry", "page_id", "view_id"}
ALLOWED_INLINE_TABLE_SCHEMA_KEYS = {"type", "title", "binding", "rows", "columns", "empty_text"}
ALLOWED_LAYOUT_DIRECTIONS = {"column", "row"}
ALLOWED_LAYOUT_KINDS = {"grid"}
ALLOWED_TEXT_STYLES = {"title", "subtitle", "body", "meta"}


def _validate_managed_identifier(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not MANAGED_VIEW_ID_RE.match(normalized):
        raise ValueError(f"{field_name} 必须是以小写字母开头、只包含字母数字下划线的标识符")
    return normalized


def _normalize_table_field_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是字符串数组")

    values: list[str] = []
    for item in raw:
        values.append(_validate_managed_identifier(str(item), field_name=field_name))
    return values


def _validate_lock_key_usage(schema: dict[str, Any]) -> None:
    if not schema.get("lock_key"):
        return

    conflicts: list[str] = []
    for column in schema.get("columns", []):
        if not isinstance(column, dict):
            continue
        key = str(column.get("key", "")).strip()
        label = str(column.get("label", "")).strip()
        if key in BUSINESS_OCCUPANCY_COLUMN_KEYS or label in BUSINESS_OCCUPANCY_COLUMN_LABELS:
            conflicts.append(key or label)

    if conflicts:
        rendered = ", ".join(dict.fromkeys(conflicts))
        raise ValueError(
            f"lock_key 只用于 Core 临时锁，不能与业务占用列同时声明；请删除这些列或移除 lock_key: {rendered}"
        )


def _normalize_table_column(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("数据表 columns 中的每一项都必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_TABLE_COLUMN_KEYS)
    if unknown_keys:
        raise ValueError(f"数据表列定义包含不支持的字段: {', '.join(unknown_keys)}")

    key = _validate_managed_identifier(str(raw.get("key", "")), field_name="column.key")
    label = str(raw.get("label") or key).strip()
    if not label:
        raise ValueError("数据表列定义必须提供 label")

    col_type = str(raw.get("type") or "text").strip().lower()
    if col_type not in ALLOWED_TABLE_COLUMN_TYPES:
        raise ValueError(f"不支持的数据表列类型: {col_type}")

    column: dict[str, Any] = {
        "key": key,
        "label": label,
    }
    if raw.get("visible") is not None:
        column["visible"] = bool(raw["visible"])
    if raw.get("required") is not None:
        column["required"] = bool(raw["required"])
    if col_type != "text":
        column["type"] = col_type
    if raw.get("default") is not None:
        column["default"] = raw["default"]
    if col_type == "select":
        options = raw.get("options")
        if not isinstance(options, list) or not options:
            raise ValueError("select 列必须提供非空 options 数组")
        column["options"] = [str(option) for option in options]
    elif raw.get("options") is not None:
        raise ValueError("只有 select 列允许配置 options")

    return column


def normalize_table_schema(view_id: str, schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError("数据表 schema 必须是对象")

    unknown_keys = sorted(set(schema) - ALLOWED_TABLE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"数据表 schema 包含不支持的字段: {', '.join(unknown_keys)}")

    dataset = str(schema.get("dataset") or view_id).strip()
    if dataset != view_id:
        raise ValueError("数据表 dataset 必须与 view_id 保持一致，由宿主统一管理")

    raw_columns = schema.get("columns", [])
    if not isinstance(raw_columns, list):
        raise ValueError("数据表 columns 必须是数组")

    normalized = {
        "title": str(schema.get("title") or view_id).strip() or view_id,
        "dataset": view_id,
        "primary_key": _validate_managed_identifier(
            str(schema.get("primary_key") or "id"),
            field_name="primary_key",
        ),
        "columns": [_normalize_table_column(column) for column in raw_columns],
    }

    if schema.get("lock_scope") is not None:
        normalized["lock_scope"] = _validate_managed_identifier(
            str(schema.get("lock_scope")),
            field_name="lock_scope",
        )
    if schema.get("lock_key") is not None:
        normalized["lock_key"] = _validate_managed_identifier(
            str(schema.get("lock_key")),
            field_name="lock_key",
        )
    for list_field in ("display_fields", "create_fields", "update_fields"):
        values = _normalize_table_field_list(schema.get(list_field), field_name=list_field)
        if values:
            normalized[list_field] = values
    for handler_field in ("create_handler", "update_handler"):
        if schema.get(handler_field) is not None:
            normalized[handler_field] = _validate_managed_identifier(
                str(schema.get(handler_field)),
                field_name=handler_field,
            )

    _validate_lock_key_usage(normalized)
    return normalized


def _normalize_binding(raw: Any, *, field_name: str) -> str:
    binding = str(raw or "").strip()
    if not binding:
        raise ValueError(f"{field_name} 不能为空")
    return binding


def _normalize_layout(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_PAGE_LAYOUT_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    layout: dict[str, Any] = {}
    direction = str(raw.get("direction") or "").strip().lower()
    if direction:
        if direction not in ALLOWED_LAYOUT_DIRECTIONS:
            raise ValueError(f"{field_name}.direction 不受支持: {direction}")
        layout["direction"] = direction

    kind = str(raw.get("kind") or "").strip().lower()
    if kind:
        if kind not in ALLOWED_LAYOUT_KINDS:
            raise ValueError(f"{field_name}.kind 不受支持: {kind}")
        layout["kind"] = kind

    if raw.get("columns") is not None:
        columns = int(raw.get("columns"))
        if columns < 1:
            raise ValueError(f"{field_name}.columns 必须 >= 1")
        layout["columns"] = columns

    if raw.get("gap") is not None:
        gap = int(raw.get("gap"))
        if gap < 0:
            raise ValueError(f"{field_name}.gap 必须 >= 0")
        layout["gap"] = gap

    if layout.get("kind") == "grid" and "columns" not in layout:
        raise ValueError(f"{field_name}.kind=grid 时必须提供 columns")

    return layout


def _normalize_hosted_entry(entry: str, *, field_name: str) -> str:
    if not HOSTED_PAGE_ENTRY_RE.match(entry):
        raise ValueError(f"{field_name} 必须使用 core:page:<page_id> 或 core:data_table:<view_id>")
    return entry


def _normalize_button_action(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_BUTTON_ACTION_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    action_type = str(raw.get("type") or "").strip()
    if action_type not in {"reload", "open_page"}:
        raise ValueError(f"{field_name}.type 只支持 reload / open_page")

    action: dict[str, Any] = {"type": action_type}
    if action_type == "open_page":
        entry = str(raw.get("entry") or "").strip()
        if not entry:
            page_id = str(raw.get("page_id") or "").strip()
            view_id = str(raw.get("view_id") or "").strip()
            if page_id:
                entry = f"core:page:{page_id}"
            elif view_id:
                entry = f"core:data_table:{view_id}"
        action["entry"] = _normalize_hosted_entry(entry, field_name=f"{field_name}.entry")
    elif any(raw.get(key) is not None for key in ("entry", "page_id", "view_id")):
        raise ValueError(f"{field_name}.type=reload 时不能再传 entry/page_id/view_id")

    return action


def _normalize_inline_table_schema(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_INLINE_TABLE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    binding = str(raw.get("binding") or "").strip()
    rows = raw.get("rows")
    if not binding and rows is None:
        raise ValueError(f"{field_name} 必须提供 binding 或 rows")
    if binding and rows is not None:
        raise ValueError(f"{field_name} 不能同时提供 binding 和 rows")

    columns = raw.get("columns", [])
    if not isinstance(columns, list):
        raise ValueError(f"{field_name}.columns 必须是数组")

    normalized: dict[str, Any] = {"type": "DataTable"}
    if raw.get("title") is not None:
        normalized["title"] = str(raw.get("title") or "").strip()
    if binding:
        normalized["binding"] = _normalize_binding(binding, field_name=f"{field_name}.binding")
    if rows is not None:
        if not isinstance(rows, list):
            raise ValueError(f"{field_name}.rows 必须是数组")
        normalized["rows"] = [dict(item) for item in rows if isinstance(item, dict)]
    if columns:
        normalized["columns"] = [_normalize_table_column(column) for column in columns]
    if raw.get("empty_text") is not None:
        normalized["empty_text"] = str(raw.get("empty_text") or "").strip()
    return normalized


def _normalize_page_children(raw: Any, *, field_name: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是数组")

    children: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        children.append(_normalize_page_component(item, field_name=f"{field_name}[{index}]"))
    return children


def _normalize_page_component(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    component_type = str(raw.get("type") or "").strip()
    if component_type == "Section":
        unknown_keys = sorted(set(raw) - ALLOWED_SECTION_SCHEMA_KEYS)
        if unknown_keys:
            raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
        section: dict[str, Any] = {
            "type": "Section",
            "children": _normalize_page_children(raw.get("children"), field_name=f"{field_name}.children"),
        }
        if raw.get("title") is not None:
            section["title"] = str(raw.get("title") or "").strip()
        if raw.get("variant") is not None:
            section["variant"] = str(raw.get("variant") or "").strip().lower()
        layout = _normalize_layout(raw.get("layout"), field_name=f"{field_name}.layout")
        if layout:
            section["layout"] = layout
        return section

    if component_type == "Text":
        unknown_keys = sorted(set(raw) - ALLOWED_TEXT_SCHEMA_KEYS)
        if unknown_keys:
            raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
        text = str(raw.get("text") or "").strip()
        binding = str(raw.get("binding") or "").strip()
        if not text and not binding:
            raise ValueError(f"{field_name} 必须提供 text 或 binding")
        if text and binding:
            raise ValueError(f"{field_name} 不能同时提供 text 和 binding")
        item: dict[str, Any] = {"type": "Text"}
        if text:
            item["text"] = text
        if binding:
            item["binding"] = _normalize_binding(binding, field_name=f"{field_name}.binding")
        if raw.get("style") is not None:
            style = str(raw.get("style") or "").strip().lower()
            if style not in ALLOWED_TEXT_STYLES:
                raise ValueError(f"{field_name}.style 不受支持: {style}")
            item["style"] = style
        return item

    if component_type == "Button":
        unknown_keys = sorted(set(raw) - ALLOWED_BUTTON_SCHEMA_KEYS)
        if unknown_keys:
            raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
        label = str(raw.get("label") or "").strip()
        if not label:
            raise ValueError(f"{field_name}.label 不能为空")
        return {
            "type": "Button",
            "label": label,
            "action": _normalize_button_action(raw.get("action"), field_name=f"{field_name}.action"),
        }

    if component_type == "DataTable":
        return _normalize_inline_table_schema(raw, field_name=field_name)

    raise ValueError(f"{field_name}.type 不受支持: {component_type or '<empty>'}")


def normalize_page_schema(page_id: str, schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError("宿主页 schema 必须是对象")

    unknown_keys = sorted(set(schema) - ALLOWED_PAGE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"宿主页 schema 包含不支持的字段: {', '.join(unknown_keys)}")

    schema_type = str(schema.get("type") or "").strip()
    if schema_type != "Page":
        raise ValueError("宿主页 schema.type 必须是 Page")

    load_handler = str(schema.get("load_handler") or "").strip()
    if not load_handler:
        raise ValueError("宿主页 schema 必须提供 load_handler")
    _validate_managed_identifier(load_handler, field_name="load_handler")

    normalized = {
        "type": "Page",
        "title": str(schema.get("title") or page_id).strip() or page_id,
        "load_handler": load_handler,
        "children": _normalize_page_children(schema.get("children"), field_name="children"),
    }
    layout = _normalize_layout(schema.get("layout"), field_name="layout")
    if layout:
        normalized["layout"] = layout
    return normalized


__all__ = ["normalize_page_schema", "normalize_table_schema"]
