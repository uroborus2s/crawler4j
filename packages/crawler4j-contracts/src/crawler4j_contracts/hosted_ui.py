"""Shared hosted UI schema normalization helpers."""

from __future__ import annotations

import re
from typing import Any

MANAGED_VIEW_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

ALLOWED_INLINE_TABLE_SCHEMA_KEYS = {
    "type",
    "table_id",
    "title",
    "columns",
    "features",
    "data_source",
    "row_action",
    "empty_text",
    "crud",
}
ALLOWED_TABLE_COLUMN_KEYS = {
    "key",
    "label",
    "visible",
    "required",
    "readonly",
    "type",
    "options",
    "default",
    "sortable",
    "searchable",
    "width",
    "stretch",
    "align",
}
ALLOWED_TABLE_COLUMN_TYPES = {"text", "number", "int", "bool", "select", "badge", "actions"}
ALLOWED_DATA_STORAGE_MODES = {"managed_dataset", "custom_table"}
ALLOWED_DATA_CLEANUP_POLICIES = {"delete_rows", "drop_table", "keep"}
ALLOWED_DATA_RESOURCE_KEYS = {
    "storage_mode",
    "record_key_field",
    "schema",
    "indexes",
    "cleanup_policy",
}
ALLOWED_PAGE_LAYOUT_KEYS = {"direction", "kind", "columns", "gap"}
ALLOWED_PAGE_SCHEMA_KEYS = {"type", "title", "load_handler", "children", "layout", "scroll"}
ALLOWED_PAGE_SCROLL_KEYS = {"vertical"}
ALLOWED_PAGE_SCROLL_VERTICAL_VALUES = {"auto", "hidden"}
ALLOWED_SECTION_SCHEMA_KEYS = {"type", "title", "children", "variant", "layout"}
ALLOWED_CARD_SCHEMA_KEYS = {
    "type",
    "title",
    "children",
    "layout",
    "title_align",
    "content_align",
    "content_vertical_align",
    "min_height",
    "padding",
}
ALLOWED_TEXT_SCHEMA_KEYS = {"type", "text", "binding", "style"}
ALLOWED_BUTTON_SCHEMA_KEYS = {"type", "label", "icon", "aria_label", "size", "variant", "action"}
ALLOWED_BUTTON_SIZES = {"md", "sm", "icon"}
ALLOWED_BUTTON_VARIANTS = {"primary", "secondary", "ghost"}
ALLOWED_BUTTON_ACTION_KEYS = {"type", "page_id", "name", "params"}
ALLOWED_ACTION_PARAM_SPEC_KEYS = {"binding", "value"}
ALLOWED_FEATURES_KEYS = {"search", "sort", "pagination"}
ALLOWED_SEARCH_FEATURE_KEYS = {"enabled", "placeholder"}
ALLOWED_SORT_FEATURE_KEYS = {"enabled", "default"}
ALLOWED_PAGINATION_FEATURE_KEYS = {"enabled", "page_size", "page_size_options"}
ALLOWED_SORT_SPEC_KEYS = {"field", "direction"}
ALLOWED_DATA_SOURCE_KEYS = {"type", "handler", "binding", "rows", "resource_id"}
ALLOWED_INLINE_DATA_SOURCE_TYPES = {"binding", "rows", "query_handler", "managed_resource"}
ALLOWED_TABLE_CRUD_KEYS = {
    "mode",
    "render",
    "toolbar",
    "primary_key",
    "form",
    "create_handler",
    "update_handler",
    "delete_handler",
}
ALLOWED_TABLE_CRUD_FORM_KEYS = {"create_columns", "update_columns"}
ALLOWED_TABLE_CRUD_RENDER_MODES = {"toolbar", "row_actions"}
ALLOWED_TABLE_CRUD_TOOLBAR_KEYS = {"create", "update", "delete"}
ALLOWED_LAYOUT_DIRECTIONS = {"column", "row"}
ALLOWED_LAYOUT_KINDS = {"grid"}
ALLOWED_TEXT_STYLES = {"title", "subtitle", "body", "meta"}
ALLOWED_ALIGNMENTS = {"left", "center", "right"}
ALLOWED_VERTICAL_ALIGNMENTS = {"top", "center", "bottom"}
ALLOWED_DB_VIEW_SCHEMA_KEYS = {
    "view_kind",
    "source_resource_ids",
    "select_sql_template",
    "columns",
    "cleanup_policy",
    "schema_version",
}
ALLOWED_DB_VIEW_KINDS = {"sql_view"}
ALLOWED_DB_VIEW_CLEANUP_POLICIES = {"drop_view", "keep"}
ALLOWED_DB_VIEW_COLUMN_KEYS = {"name", "label", "type", "nullable"}
ALLOWED_DB_VIEW_COLUMN_TYPES = {"text", "int", "number", "bool", "json"}


def _validate_managed_identifier(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not MANAGED_VIEW_ID_RE.match(normalized):
        raise ValueError(f"{field_name} 必须是以小写字母开头、只包含字母数字下划线的标识符")
    return normalized


def _normalize_mapping(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")
    return dict(raw)


def _normalize_storage_mode(raw: Any) -> str:
    storage_mode = str(raw or "managed_dataset").strip().lower()
    if storage_mode not in ALLOWED_DATA_STORAGE_MODES:
        raise ValueError("storage_mode 只支持 managed_dataset/custom_table")
    return storage_mode


def _normalize_cleanup_policy(raw: Any, *, storage_mode: str) -> str:
    default = "delete_rows" if storage_mode == "managed_dataset" else "drop_table"
    cleanup_policy = str(raw or default).strip().lower()
    if cleanup_policy not in ALLOWED_DATA_CLEANUP_POLICIES:
        raise ValueError("cleanup_policy 只支持 delete_rows/drop_table/keep")
    return cleanup_policy


def normalize_data_resource(resource_id: str, resource: Any) -> dict[str, Any]:
    if not isinstance(resource, dict):
        raise ValueError("数据资源 schema 必须是对象")

    unknown_keys = sorted(set(resource) - ALLOWED_DATA_RESOURCE_KEYS)
    if unknown_keys:
        raise ValueError(f"数据资源声明包含不支持的字段: {', '.join(unknown_keys)}")

    normalized_resource_id = _validate_managed_identifier(resource_id, field_name="resource_id")
    storage_mode = _normalize_storage_mode(resource.get("storage_mode"))
    record_key_field = _validate_managed_identifier(
        str(resource.get("record_key_field") or "id"),
        field_name="record_key_field",
    )
    return {
        "resource_id": normalized_resource_id,
        "storage_mode": storage_mode,
        "record_key_field": record_key_field,
        "schema": _normalize_mapping(resource.get("schema"), field_name="schema"),
        "indexes": _normalize_mapping(resource.get("indexes"), field_name="indexes"),
        "cleanup_policy": _normalize_cleanup_policy(
            resource.get("cleanup_policy"),
            storage_mode=storage_mode,
        ),
    }


def _normalize_binding(raw: Any, *, field_name: str) -> str:
    binding = str(raw or "").strip()
    if not binding:
        raise ValueError(f"{field_name} 不能为空")
    return binding


def _normalize_alignment(raw: Any, *, field_name: str) -> str:
    alignment = str(raw or "").strip().lower()
    if alignment not in ALLOWED_ALIGNMENTS:
        raise ValueError(f"{field_name} 不受支持: {alignment}")
    return alignment


def _normalize_vertical_alignment(raw: Any, *, field_name: str) -> str:
    alignment = str(raw or "").strip().lower()
    if alignment not in ALLOWED_VERTICAL_ALIGNMENTS:
        raise ValueError(f"{field_name} 不受支持: {alignment}")
    return alignment


def _normalize_non_negative_int(raw: Any, *, field_name: str) -> int:
    value = int(raw)
    if value < 0:
        raise ValueError(f"{field_name} 必须 >= 0")
    return value


def _normalize_page_scroll(raw: Any, *, field_name: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_PAGE_SCROLL_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    vertical = str(raw.get("vertical") or "auto").strip().lower()
    if vertical not in ALLOWED_PAGE_SCROLL_VERTICAL_VALUES:
        raise ValueError(f"{field_name}.vertical 不受支持: {vertical}")
    return {"vertical": vertical}


def _normalize_string_list(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是字符串数组")
    return [_validate_managed_identifier(str(item), field_name=field_name) for item in raw]


def _normalize_action_params(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    normalized: dict[str, Any] = {}
    for key, value in raw.items():
        param_name = str(key or "").strip()
        if not param_name:
            raise ValueError(f"{field_name} 中的参数名不能为空")

        if isinstance(value, dict):
            unknown_keys = sorted(set(value) - ALLOWED_ACTION_PARAM_SPEC_KEYS)
            if unknown_keys:
                raise ValueError(
                    f"{field_name}.{param_name} 包含不支持的字段: {', '.join(unknown_keys)}"
                )

            has_binding = value.get("binding") is not None
            has_value = "value" in value
            if has_binding == has_value:
                raise ValueError(f"{field_name}.{param_name} 必须且只能提供 binding 或 value")
            if has_binding:
                normalized[param_name] = {
                    "binding": _normalize_binding(
                        value.get("binding"),
                        field_name=f"{field_name}.{param_name}.binding",
                    )
                }
                continue
            normalized[param_name] = {"value": value.get("value")}
            continue

        normalized[param_name] = {"value": value}

    return normalized


def _normalize_button_action(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_BUTTON_ACTION_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    action_type = str(raw.get("type") or "").strip()
    if action_type not in {"reload", "open_page", "page_action", "ui_action"}:
        raise ValueError(f"{field_name}.type 只支持 reload / open_page / page_action / ui_action")

    action: dict[str, Any] = {"type": action_type}
    if action_type == "open_page":
        action["page_id"] = _validate_managed_identifier(
            str(raw.get("page_id") or ""),
            field_name=f"{field_name}.page_id",
        )
        params = _normalize_action_params(raw.get("params"), field_name=f"{field_name}.params")
        if params:
            action["params"] = params
    elif action_type in {"page_action", "ui_action"}:
        action["name"] = _validate_managed_identifier(
            str(raw.get("name") or ""),
            field_name=f"{field_name}.name",
        )
        params = _normalize_action_params(raw.get("params"), field_name=f"{field_name}.params")
        if params:
            action["params"] = params
        if raw.get("page_id") is not None:
            raise ValueError(f"{field_name}.type={action_type} 时不能再传 page_id")
    elif any(raw.get(key) is not None for key in ("page_id", "name", "params")):
        raise ValueError(f"{field_name}.type=reload 时不能再传 page_id/name/params")

    return action


def _normalize_row_action(raw: Any, *, field_name: str) -> dict[str, Any]:
    action = _normalize_button_action(raw, field_name=field_name)
    if action.get("type") != "open_page":
        raise ValueError(f"{field_name}.type 只支持 open_page")
    return action


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

    column_type = str(raw.get("type") or "text").strip().lower()
    if column_type not in ALLOWED_TABLE_COLUMN_TYPES:
        raise ValueError(f"不支持的数据表列类型: {column_type}")

    column: dict[str, Any] = {
        "key": key,
        "label": label,
        "type": column_type,
    }
    for key_name in ("visible", "required", "readonly", "sortable", "searchable", "stretch"):
        if raw.get(key_name) is not None:
            column[key_name] = bool(raw.get(key_name))
    if raw.get("default") is not None:
        column["default"] = raw.get("default")
    if raw.get("width") is not None:
        width = int(raw.get("width"))
        if width < 1:
            raise ValueError("column.width 必须 >= 1")
        column["width"] = width
    if raw.get("align") is not None:
        align = str(raw.get("align") or "").strip().lower()
        if align not in ALLOWED_ALIGNMENTS:
            raise ValueError(f"column.align 不受支持: {align}")
        column["align"] = align
    if column_type == "select":
        options = raw.get("options")
        if not isinstance(options, list) or not options:
            raise ValueError("select 列必须提供非空 options 数组")
        column["options"] = [str(option) for option in options]
    elif raw.get("options") is not None:
        raise ValueError("只有 select 列允许配置 options")

    return column


def _normalize_sort_spec(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")
    unknown_keys = sorted(set(raw) - ALLOWED_SORT_SPEC_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
    field = _validate_managed_identifier(str(raw.get("field") or ""), field_name=f"{field_name}.field")
    direction = str(raw.get("direction") or "asc").strip().lower()
    if direction not in {"asc", "desc"}:
        raise ValueError(f"{field_name}.direction 只支持 asc/desc")
    return {"field": field, "direction": direction}


def _normalize_features(raw: Any, *, field_name: str) -> dict[str, Any]:
    features = raw or {}
    if not isinstance(features, dict):
        raise ValueError(f"{field_name} 必须是对象")
    unknown_keys = sorted(set(features) - ALLOWED_FEATURES_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    search = features.get("search") or {}
    if not isinstance(search, dict):
        raise ValueError(f"{field_name}.search 必须是对象")
    unknown_keys = sorted(set(search) - ALLOWED_SEARCH_FEATURE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name}.search 包含不支持的字段: {', '.join(unknown_keys)}")

    sort = features.get("sort") or {}
    if not isinstance(sort, dict):
        raise ValueError(f"{field_name}.sort 必须是对象")
    unknown_keys = sorted(set(sort) - ALLOWED_SORT_FEATURE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name}.sort 包含不支持的字段: {', '.join(unknown_keys)}")

    pagination = features.get("pagination") or {}
    if not isinstance(pagination, dict):
        raise ValueError(f"{field_name}.pagination 必须是对象")
    unknown_keys = sorted(set(pagination) - ALLOWED_PAGINATION_FEATURE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name}.pagination 包含不支持的字段: {', '.join(unknown_keys)}")

    default_sort = sort.get("default") or []
    if not isinstance(default_sort, list):
        raise ValueError(f"{field_name}.sort.default 必须是数组")
    page_size_options = pagination.get("page_size_options") or [10, 20, 50, 100]
    if not isinstance(page_size_options, list) or not page_size_options:
        raise ValueError(f"{field_name}.pagination.page_size_options 必须是非空数组")

    return {
        "search": {
            "enabled": bool(search.get("enabled", True)),
            "placeholder": str(search.get("placeholder") or "搜索…").strip() or "搜索…",
        },
        "sort": {
            "enabled": bool(sort.get("enabled", True)),
            "default": [
                _normalize_sort_spec(item, field_name=f"{field_name}.sort.default[{index}]")
                for index, item in enumerate(default_sort)
            ],
        },
        "pagination": {
            "enabled": bool(pagination.get("enabled", True)),
            "page_size": max(1, int(pagination.get("page_size", 20))),
            "page_size_options": [max(1, int(option)) for option in page_size_options],
        },
    }


def _normalize_table_data_source(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")
    unknown_keys = sorted(set(raw) - ALLOWED_DATA_SOURCE_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    source_type = str(raw.get("type") or "").strip().lower()
    if source_type not in ALLOWED_INLINE_DATA_SOURCE_TYPES:
        raise ValueError(f"{field_name}.type 只支持 binding/rows/query_handler/managed_resource")

    normalized: dict[str, Any] = {"type": source_type}
    if source_type == "query_handler":
        normalized["handler"] = _validate_managed_identifier(
            str(raw.get("handler") or ""),
            field_name=f"{field_name}.handler",
        )
    elif source_type == "managed_resource":
        normalized["resource_id"] = _validate_managed_identifier(
            str(raw.get("resource_id") or ""),
            field_name=f"{field_name}.resource_id",
        )
    elif source_type == "binding":
        normalized["binding"] = _normalize_binding(raw.get("binding"), field_name=f"{field_name}.binding")
    elif source_type == "rows":
        rows = raw.get("rows")
        if not isinstance(rows, list):
            raise ValueError(f"{field_name}.rows 必须是数组")
        normalized["rows"] = [dict(item) for item in rows if isinstance(item, dict)]
    return normalized


def _normalize_crud_form_columns(raw: Any, *, field_name: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是数组")
    return [
        _validate_managed_identifier(str(item), field_name=f"{field_name}[{index}]")
        for index, item in enumerate(raw)
    ]


def _normalize_table_crud_toolbar(raw: Any, *, field_name: str) -> dict[str, bool]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")
    unknown_keys = sorted(set(raw) - ALLOWED_TABLE_CRUD_TOOLBAR_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
    return {
        key: bool(raw.get(key))
        for key in ("create", "update", "delete")
        if key in raw
    }


def _normalize_table_crud(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_TABLE_CRUD_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    mode = str(raw.get("mode") or "handlers").strip().lower()
    if mode != "handlers":
        raise ValueError(f"{field_name}.mode 目前只支持 handlers")
    render = str(raw.get("render") or "toolbar").strip().lower()
    if render not in ALLOWED_TABLE_CRUD_RENDER_MODES:
        raise ValueError(f"{field_name}.render 不受支持: {render}")

    form = raw.get("form") or {}
    if not isinstance(form, dict):
        raise ValueError(f"{field_name}.form 必须是对象")
    unknown_form_keys = sorted(set(form) - ALLOWED_TABLE_CRUD_FORM_KEYS)
    if unknown_form_keys:
        raise ValueError(f"{field_name}.form 包含不支持的字段: {', '.join(unknown_form_keys)}")

    normalized = {
        "mode": mode,
        "render": render,
        "toolbar": _normalize_table_crud_toolbar(
            raw.get("toolbar"),
            field_name=f"{field_name}.toolbar",
        ),
        "primary_key": _validate_managed_identifier(
            str(raw.get("primary_key") or ""),
            field_name=f"{field_name}.primary_key",
        ),
        "form": {
            "create_columns": _normalize_crud_form_columns(
                form.get("create_columns"),
                field_name=f"{field_name}.form.create_columns",
            ),
            "update_columns": _normalize_crud_form_columns(
                form.get("update_columns"),
                field_name=f"{field_name}.form.update_columns",
            ),
        },
    }
    for handler_key in ("create_handler", "update_handler", "delete_handler"):
        if raw.get(handler_key) is not None:
            normalized[handler_key] = _validate_managed_identifier(
                str(raw.get(handler_key) or ""),
                field_name=f"{field_name}.{handler_key}",
            )
    return normalized


def _normalize_db_view_column(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")
    unknown_keys = sorted(set(raw) - ALLOWED_DB_VIEW_COLUMN_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
    name = _validate_managed_identifier(str(raw.get("name") or ""), field_name=f"{field_name}.name")
    column_type = str(raw.get("type") or "text").strip().lower()
    if column_type not in ALLOWED_DB_VIEW_COLUMN_TYPES:
        raise ValueError(f"{field_name}.type 不受支持: {column_type}")
    column = {
        "name": name,
        "type": column_type,
        "nullable": bool(raw.get("nullable", True)),
    }
    return column


def normalize_db_view_schema(view_id: str, schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError("数据库视图 schema 必须是对象")

    unknown_keys = sorted(set(schema) - ALLOWED_DB_VIEW_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"数据库视图 schema 包含不支持的字段: {', '.join(unknown_keys)}")

    managed_view_id = _validate_managed_identifier(view_id, field_name="view_id")
    view_kind = str(schema.get("view_kind") or "sql_view").strip().lower()
    if view_kind not in ALLOWED_DB_VIEW_KINDS:
        raise ValueError("view_kind 只支持 sql_view")
    source_resource_ids = _normalize_string_list(
        schema.get("source_resource_ids"),
        field_name="source_resource_ids",
    )
    if not source_resource_ids:
        raise ValueError("source_resource_ids 不能为空")
    select_sql_template = str(schema.get("select_sql_template") or "").strip()
    if not select_sql_template:
        raise ValueError("select_sql_template 不能为空")
    columns = schema.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("columns 必须是非空数组")
    cleanup_policy = str(schema.get("cleanup_policy") or "drop_view").strip().lower()
    if cleanup_policy not in ALLOWED_DB_VIEW_CLEANUP_POLICIES:
        raise ValueError("cleanup_policy 只支持 drop_view/keep")
    schema_version = int(schema.get("schema_version") or 1)
    if schema_version < 1:
        raise ValueError("schema_version 必须 >= 1")
    return {
        "view_id": managed_view_id,
        "view_kind": view_kind,
        "source_resource_ids": source_resource_ids,
        "select_sql_template": select_sql_template,
        "columns": [
            _normalize_db_view_column(item, field_name=f"columns[{index}]")
            for index, item in enumerate(columns)
        ],
        "cleanup_policy": cleanup_policy,
        "schema_version": schema_version,
    }


def _normalize_inline_table_schema(raw: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_INLINE_TABLE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")

    columns = raw.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError(f"{field_name}.columns 必须是非空数组")

    table_id_raw = str(raw.get("table_id") or "inline_table").strip() or "inline_table"
    data_source_raw = raw.get("data_source")
    if data_source_raw is None:
        raise ValueError(f"{field_name} 必须提供 data_source")

    normalized: dict[str, Any] = {
        "type": "DataTable",
        "table_id": _validate_managed_identifier(table_id_raw, field_name=f"{field_name}.table_id"),
        "columns": [
            _normalize_table_column({"key": str(column), "label": str(column)})
            if isinstance(column, str)
            else _normalize_table_column(column)
            for column in columns
        ],
        "features": _normalize_features(raw.get("features"), field_name=f"{field_name}.features"),
        "data_source": _normalize_table_data_source(
            data_source_raw,
            field_name=f"{field_name}.data_source",
        ),
    }
    if raw.get("title") is not None:
        normalized["title"] = str(raw.get("title") or "").strip()
    if raw.get("empty_text") is not None:
        normalized["empty_text"] = str(raw.get("empty_text") or "").strip()
    if raw.get("row_action") is not None:
        normalized["row_action"] = _normalize_row_action(
            raw.get("row_action"),
            field_name=f"{field_name}.row_action",
        )
    if raw.get("crud") is not None:
        normalized["crud"] = _normalize_table_crud(
            raw.get("crud"),
            field_name=f"{field_name}.crud",
        )
    return normalized


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


def _normalize_page_children(raw: Any, *, field_name: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} 必须是数组")
    return [_normalize_page_component(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(raw)]


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

    if component_type == "Card":
        unknown_keys = sorted(set(raw) - ALLOWED_CARD_SCHEMA_KEYS)
        if unknown_keys:
            raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
        card: dict[str, Any] = {
            "type": "Card",
            "children": _normalize_page_children(raw.get("children"), field_name=f"{field_name}.children"),
        }
        if raw.get("title") is not None:
            card["title"] = str(raw.get("title") or "").strip()
        if raw.get("title_align") is not None:
            card["title_align"] = _normalize_alignment(
                raw.get("title_align"),
                field_name=f"{field_name}.title_align",
            )
        if raw.get("content_align") is not None:
            card["content_align"] = _normalize_alignment(
                raw.get("content_align"),
                field_name=f"{field_name}.content_align",
            )
        if raw.get("content_vertical_align") is not None:
            card["content_vertical_align"] = _normalize_vertical_alignment(
                raw.get("content_vertical_align"),
                field_name=f"{field_name}.content_vertical_align",
            )
        if raw.get("min_height") is not None:
            card["min_height"] = _normalize_non_negative_int(
                raw.get("min_height"),
                field_name=f"{field_name}.min_height",
            )
        if raw.get("padding") is not None:
            card["padding"] = _normalize_non_negative_int(
                raw.get("padding"),
                field_name=f"{field_name}.padding",
            )
        layout = _normalize_layout(raw.get("layout"), field_name=f"{field_name}.layout")
        if layout:
            card["layout"] = layout
        return card

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
        icon = str(raw.get("icon") or "").strip()
        aria_label = str(raw.get("aria_label") or "").strip()
        if not label and not icon:
            raise ValueError(f"{field_name} 必须提供 label 或 icon")
        if icon and not label and not aria_label:
            raise ValueError(f"{field_name}.aria_label 在纯图标按钮中不能为空")
        item = {
            "type": "Button",
            "action": _normalize_button_action(raw.get("action"), field_name=f"{field_name}.action"),
        }
        if label:
            item["label"] = label
        if icon:
            item["icon"] = icon
        if aria_label:
            item["aria_label"] = aria_label
        if raw.get("size") is not None:
            size = str(raw.get("size") or "").strip().lower()
            if size not in ALLOWED_BUTTON_SIZES:
                raise ValueError(f"{field_name}.size 不受支持: {size}")
            item["size"] = size
        if raw.get("variant") is not None:
            variant = str(raw.get("variant") or "").strip().lower()
            if variant not in ALLOWED_BUTTON_VARIANTS:
                raise ValueError(f"{field_name}.variant 不受支持: {variant}")
            item["variant"] = variant
        return item

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
    scroll = _normalize_page_scroll(schema.get("scroll"), field_name="scroll")
    if scroll:
        normalized["scroll"] = scroll
    return normalized


__all__ = ["normalize_data_resource", "normalize_db_view_schema", "normalize_page_schema"]
