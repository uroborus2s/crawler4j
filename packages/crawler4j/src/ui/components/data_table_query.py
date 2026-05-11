"""Query helpers for SkyDataTable providers."""

from __future__ import annotations

from typing import Any


def normalize_cell_value(value: Any, *, column_type: str) -> dict[str, Any]:
    if column_type == "actions":
        actions = value if isinstance(value, list) else []
        return {"text": "", "sort_value": "", "search_text": "", "tooltip": "", "tone": "", "actions": actions}

    if isinstance(value, dict):
        raw_text = value.get("text", value.get("value"))
        text = _stringify(raw_text, column_type=column_type)
        return {
            "text": text,
            "sort_value": value.get("sort_value", _default_sort_value(raw_text, column_type=column_type)),
            "search_text": str(value.get("search_text", text)),
            "tooltip": str(value.get("tooltip") or ""),
            "tone": str(value.get("tone") or ""),
        }

    text = _stringify(value, column_type=column_type)
    return {
        "text": text,
        "sort_value": _default_sort_value(value, column_type=column_type),
        "search_text": text,
        "tooltip": "",
        "tone": "",
    }


def resolve_local_data_table_result(
    rows: list[dict[str, Any]],
    *,
    columns: list[dict[str, Any]],
    query: dict[str, Any],
) -> dict[str, Any]:
    column_map = {str(column.get("key")): column for column in columns if isinstance(column, dict)}
    searchable_columns = [
        column for column in columns
        if isinstance(column, dict) and column.get("type") != "actions" and column.get("searchable") is True
    ]
    filtered = [dict(row) for row in rows if isinstance(row, dict)]

    search_text = str(query.get("search_text") or "").strip().lower()
    if search_text:
        filtered = [
            row
            for row in filtered
            if any(
                search_text in normalize_cell_value(row.get(str(column["key"])), column_type=str(column.get("type") or "text"))["search_text"].lower()
                for column in searchable_columns
            )
        ]

    sort_specs = query.get("sort")
    if isinstance(sort_specs, list):
        for sort_spec in reversed(sort_specs):
            if not isinstance(sort_spec, dict):
                continue
            field = str(sort_spec.get("field") or "").strip()
            direction = str(sort_spec.get("direction") or "asc").strip().lower()
            column = column_map.get(field)
            if not field or column is None or column.get("type") == "actions" or column.get("sortable") is not True:
                continue
            reverse = direction == "desc"
            filtered.sort(
                key=lambda row, key=field, column_type=str(column.get("type") or "text"): _safe_sort_key(
                    normalize_cell_value(row.get(key), column_type=column_type)["sort_value"]
                ),
                reverse=reverse,
            )

    total = len(filtered)
    page_size = max(1, int(query.get("page_size", 20)))
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(max(1, int(query.get("page", 1))), total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    paged_rows = filtered[start:end]
    return {
        "rows": paged_rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": list(sort_specs or []),
    }


def attach_display_index(
    result: dict[str, Any],
    *,
    key: str = "__index__",
) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    rows = result.get("rows")
    if not isinstance(rows, list):
        return dict(result)

    page = max(1, int(result.get("page", 1)))
    page_size = max(1, int(result.get("page_size", len(rows) or 1)))
    base_index = (page - 1) * page_size
    numbered_rows: list[dict[str, Any]] = []
    for offset, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        numbered_row = dict(row)
        numbered_row[key] = {
            "text": str(base_index + offset),
            "sort_value": base_index + offset,
        }
        numbered_rows.append(numbered_row)

    normalized = dict(result)
    normalized["rows"] = numbered_rows
    return normalized


def _safe_sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, str):
        return (0, value.lower())
    return (0, value)


def _default_sort_value(value: Any, *, column_type: str) -> Any:
    if column_type in {"int", "number"}:
        if value in (None, ""):
            return 0
        try:
            return float(value)
        except (TypeError, ValueError):
            return _stringify(value, column_type=column_type).lower()
    if column_type == "bool":
        return bool(value)
    return _stringify(value, column_type=column_type).lower()


def _stringify(value: Any, *, column_type: str) -> str:
    if column_type == "bool":
        return "是" if bool(value) else "否"
    if value is None:
        return ""
    return str(value)
