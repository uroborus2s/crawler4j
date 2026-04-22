"""ATM 运行时工具注入实现。

将 Core 能力以统一工具形式注入 TaskContext，供 model 脚本通过 SDK 访问。
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Any, Callable

from crawler4j_sdk.hosted_ui import (
    normalize_page_schema as sdk_normalize_page_schema,
    normalize_table_schema as sdk_normalize_table_schema,
)
from crawler4j_contracts.context import (
    BBox,
    ClickCaptchaDebugInfo,
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
    ImageInput,
    SliderCaptchaDebugInfo,
    SliderCaptchaMatchResult,
    ToolSpec,
    ToolsCapability,
)
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.persistence import get_kv_store, get_module_data_store
from src.core.rem.ip_pool import IPEntry, get_ip_pool_manager
from src.core.rem.manager import (
    RESOURCE_POOL_METADATA_NAMESPACE,
    build_resource_pool_card,
    build_resource_pool_metadata_key,
    get_environment_manager,
)
from src.utils.paths import get_resource_path


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append(dict(item))

    return normalized


MANAGED_VIEW_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
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
HOSTED_PAGE_ENTRY_RE = re.compile(r"^core:(page|data_table):([a-z][a-z0-9_]*)$")
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


@lru_cache(maxsize=1)
def _resolve_captcha_resource_root() -> Path | None:
    bundled_root = Path(get_resource_path("resources"))
    if bundled_root.is_dir():
        return bundled_root

    try:
        dist = distribution("sinanz")
    except PackageNotFoundError:
        return None

    for entry in dist.files or []:
        parts = Path(str(entry)).parts
        if "resources" not in parts:
            continue
        resource_index = parts.index("resources")
        candidate = Path(dist.locate_file(Path(*parts[: resource_index + 1]))).resolve()
        if candidate.is_dir():
            return candidate

    return None


@lru_cache(maxsize=1)
def _resolve_captcha_models_root() -> Path | None:
    resource_root = _resolve_captcha_resource_root()
    if resource_root is None:
        return None

    models_root = resource_root / "models"
    if models_root.is_dir():
        return models_root
    return resource_root


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


def _normalize_table_schema(view_id: str, schema: dict[str, Any]) -> dict[str, Any]:
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


def _normalize_binding(raw: Any, *, field_name: str) -> str:
    if raw is None:
        return ""
    binding = str(raw).strip()
    if not binding:
        raise ValueError(f"{field_name} 不能为空字符串")
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
    if raw.get("direction") is not None:
        direction = str(raw.get("direction") or "").strip().lower()
        if direction not in ALLOWED_LAYOUT_DIRECTIONS:
            raise ValueError(f"{field_name}.direction 只支持 column 或 row")
        layout["direction"] = direction
    if raw.get("kind") is not None:
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in ALLOWED_LAYOUT_KINDS:
            raise ValueError(f"{field_name}.kind 只支持 grid")
        layout["kind"] = kind
    if raw.get("columns") is not None:
        columns = int(raw.get("columns"))
        if columns <= 0:
            raise ValueError(f"{field_name}.columns 必须大于 0")
        layout["columns"] = columns
    if raw.get("gap") is not None:
        gap = int(raw.get("gap"))
        if gap < 0:
            raise ValueError(f"{field_name}.gap 不能小于 0")
        layout["gap"] = gap

    return layout


def _normalize_hosted_entry(raw: Any, *, field_name: str) -> str:
    entry = str(raw or "").strip()
    if not HOSTED_PAGE_ENTRY_RE.match(entry):
        raise ValueError(f"{field_name} 只支持 `core:page:<id>` 或 `core:data_table:<id>`")
    return entry


def _normalize_button_action(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Button.action 必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_BUTTON_ACTION_KEYS)
    if unknown_keys:
        raise ValueError(f"Button.action 包含不支持的字段: {', '.join(unknown_keys)}")

    action_type = str(raw.get("type") or "").strip()
    if action_type not in {"reload", "open_page"}:
        raise ValueError("Button.action.type 只支持 reload 或 open_page")

    if action_type == "reload":
        return {"type": "reload"}

    if raw.get("entry") is not None:
        return {
            "type": "open_page",
            "entry": _normalize_hosted_entry(raw.get("entry"), field_name="Button.action.entry"),
        }
    if raw.get("page_id") is not None:
        return {
            "type": "open_page",
            "entry": f"core:page:{_validate_managed_identifier(str(raw.get('page_id')), field_name='Button.action.page_id')}",
        }
    if raw.get("view_id") is not None:
        return {
            "type": "open_page",
            "entry": f"core:data_table:{_validate_managed_identifier(str(raw.get('view_id')), field_name='Button.action.view_id')}",
        }
    raise ValueError("open_page 动作必须提供 entry、page_id 或 view_id")


def _normalize_inline_table_schema(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("DataTable 组件必须是对象")

    unknown_keys = sorted(set(raw) - ALLOWED_INLINE_TABLE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"DataTable 组件包含不支持的字段: {', '.join(unknown_keys)}")

    columns = raw.get("columns", [])
    if not isinstance(columns, list):
        raise ValueError("DataTable.columns 必须是数组")

    schema: dict[str, Any] = {
        "type": "DataTable",
        "title": str(raw.get("title") or "").strip(),
        "columns": [_normalize_table_column(column) for column in columns],
        "empty_text": str(raw.get("empty_text") or "暂无数据").strip() or "暂无数据",
    }
    if raw.get("binding") is not None:
        schema["binding"] = _normalize_binding(raw.get("binding"), field_name="DataTable.binding")
    if raw.get("rows") is not None:
        schema["rows"] = _normalize_records(raw.get("rows"))
    return schema


def _normalize_page_children(raw: Any, *, field_name: str) -> list[dict[str, Any]]:
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
        return {
            "type": "Section",
            "title": str(raw.get("title") or "").strip(),
            "variant": str(raw.get("variant") or "group").strip() or "group",
            "layout": _normalize_layout(raw.get("layout"), field_name=f"{field_name}.layout"),
            "children": _normalize_page_children(raw.get("children", []), field_name=f"{field_name}.children"),
        }

    if component_type == "Text":
        unknown_keys = sorted(set(raw) - ALLOWED_TEXT_SCHEMA_KEYS)
        if unknown_keys:
            raise ValueError(f"{field_name} 包含不支持的字段: {', '.join(unknown_keys)}")
        style = str(raw.get("style") or "body").strip().lower() or "body"
        if style not in ALLOWED_TEXT_STYLES:
            raise ValueError(f"{field_name}.style 不受支持: {style}")
        component: dict[str, Any] = {
            "type": "Text",
            "style": style,
        }
        if raw.get("text") is not None:
            component["text"] = str(raw.get("text") or "")
        if raw.get("binding") is not None:
            component["binding"] = _normalize_binding(raw.get("binding"), field_name=f"{field_name}.binding")
        return component

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
            "action": _normalize_button_action(raw.get("action")),
        }

    if component_type == "DataTable":
        return _normalize_inline_table_schema(raw)

    raise ValueError(f"{field_name}.type 不受支持: {component_type or '<empty>'}")


def _normalize_page_schema(page_id: str, schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError("页面 schema 必须是对象")

    unknown_keys = sorted(set(schema) - ALLOWED_PAGE_SCHEMA_KEYS)
    if unknown_keys:
        raise ValueError(f"页面 schema 包含不支持的字段: {', '.join(unknown_keys)}")

    component_type = str(schema.get("type") or "").strip()
    if component_type != "Page":
        raise ValueError("页面 schema 顶层必须是 type=Page")

    normalized: dict[str, Any] = {
        "type": "Page",
        "title": str(schema.get("title") or page_id).strip() or page_id,
        "layout": _normalize_layout(schema.get("layout"), field_name="Page.layout"),
        "children": _normalize_page_children(schema.get("children", []), field_name="Page.children"),
    }

    if schema.get("load_handler") is not None:
        normalized["load_handler"] = _validate_managed_identifier(
            str(schema.get("load_handler")),
            field_name="load_handler",
        )

    return normalized


class CoreDatabaseTools:
    """Core 侧基础数据工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._data_store = get_module_data_store()
        self._kv = get_kv_store()

    def _lock_key(self, scope: str, key: str) -> str:
        return f"module:{self._module_name}:lock:{scope}:{key}"

    def list_records(self, dataset: str) -> list[dict[str, Any]]:
        return self._data_store.read_dataset(self._module_name, dataset)

    def replace_records(self, dataset: str, records: list[dict[str, Any]]) -> bool:
        return self._data_store.write_dataset(self._module_name, dataset, _normalize_records(records))

    def append_event(
        self,
        dataset: str,
        event_type: str,
        *,
        entity_key: str | None = None,
        run_id: str | None = None,
        previous_status: str | None = None,
        next_status: str | None = None,
        result: str | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
        created_at: int | None = None,
    ) -> bool:
        self._data_store.append_audit_event(
            self._module_name,
            dataset,
            {
                "entity_key": entity_key,
                "event_type": event_type,
                "run_id": run_id,
                "previous_status": previous_status,
                "next_status": next_status,
                "result": result,
                "reason": reason,
                "payload": dict(payload or {}),
                "created_at": created_at,
            },
        )
        return True

    def query_events(
        self,
        dataset: str,
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
        return self._data_store.query_audit_events(
            self._module_name,
            dataset,
            entity_key=entity_key,
            event_type=event_type,
            run_id=run_id,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
            offset=offset,
            order=order,
        )

    def acquire_lock(
        self,
        scope: str,
        key: str,
        *,
        ttl: int,
        owner: dict[str, Any] | None = None,
    ) -> bool:
        lock_key = self._lock_key(scope, key)
        if self._kv.exists(lock_key):
            return False
        payload = {
            "module": self._module_name,
            "scope": scope,
            "key": key,
            "owner": owner or {},
            "claimed_at": int(time.time()),
        }
        return self._kv.set(lock_key, payload, ttl=ttl)

    def release_lock(self, scope: str, key: str) -> bool:
        return self._kv.delete(self._lock_key(scope, key))

    def is_locked(self, scope: str, key: str) -> bool:
        return self._kv.exists(self._lock_key(scope, key))

    def get_state(self, key: str) -> Any:
        return self._kv.get(key)

    def set_state(self, key: str, value: Any, ttl: int | None = None) -> bool:
        return self._kv.set(key, value, ttl=ttl)

    def exists_state(self, key: str) -> bool:
        return self._kv.exists(key)


class CoreIPPoolTools:
    """Core 侧 IP 池工具实现。"""

    def _iter_candidate_entries(self, pool_id: str | None) -> list[IPEntry]:
        manager = get_ip_pool_manager()
        pools = []
        if pool_id:
            pool = manager.get_pool(pool_id)
            if pool:
                pools.append(pool)
        else:
            pools = manager.list_pools()

        entries: list[IPEntry] = []
        for pool in pools:
            entries.extend(pool.entries)
        return entries

    def pick_proxy(self, criteria: dict[str, Any] | None = None) -> dict[str, Any] | None:
        criteria = criteria or {}
        pool_id = str(criteria.get("pool_id", "")).strip() or None
        protocol = str(criteria.get("protocol", "")).strip().lower() or None
        min_safety_score = int(criteria.get("min_safety_score", 0))

        max_bound_count_raw = criteria.get("max_bound_count")
        max_bound_count = None
        if max_bound_count_raw is not None:
            try:
                max_bound_count = int(max_bound_count_raw)
            except (TypeError, ValueError):
                max_bound_count = None

        candidates = []
        for entry in self._iter_candidate_entries(pool_id):
            if entry.is_expired():
                continue
            if protocol and entry.protocol.lower() != protocol:
                continue
            if entry.safety_score < min_safety_score:
                continue
            if max_bound_count is not None and entry.bound_count > max_bound_count:
                continue
            candidates.append(entry)

        if not candidates:
            return None

        selected = sorted(candidates, key=lambda e: (e.bound_count, -e.safety_score, e.created_at))[0]
        auth = ""
        if selected.username and selected.password:
            auth = f"{selected.username}:{selected.password}@"
        proxy_url = f"{selected.protocol}://{auth}{selected.address}:{selected.port}"

        return {
            "id": selected.id,
            "pool_id": selected.pool_id,
            "protocol": selected.protocol,
            "type": selected.protocol,
            "host": selected.address,
            "port": selected.port,
            "username": selected.username or "",
            "password": selected.password or "",
            "proxy_url": proxy_url,
            "safety_score": selected.safety_score,
            "bound_count": selected.bound_count,
        }


class CoreEnvTools:
    """Core 侧环境操作工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name

    def _publish_resource_pool_updated(self, *, env_id: int, pool_name: str) -> None:
        get_event_bus().publish(
            Event(
                type=EventType.ENV_RESOURCE_POOL_UPDATED,
                data={
                    "env_id": int(env_id),
                    "module_name": self._module_name,
                    "pool_name": str(pool_name or "").strip(),
                },
                module_name=self._module_name,
            )
        )

    async def set_proxy(
        self,
        env_id: int,
        *,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
    ) -> bool:
        manager = get_environment_manager()
        return await manager.update_env(
            env_id,
            proxy_value=proxy_value or None,
            proxy_pool_id=proxy_pool_id or None,
        )

    async def bind_resource_pool(
        self,
        env_id: int,
        *,
        pool_name: str,
        eligible: bool = True,
        reason: str = "",
        exclusive: bool = True,
    ) -> bool:
        manager = get_environment_manager()
        metadata_key = build_resource_pool_metadata_key(self._module_name, pool_name)
        card = build_resource_pool_card(
            self._module_name,
            pool_name,
            eligible=eligible,
            reason=reason,
            exclusive=exclusive,
        )
        ok = await manager.set_metadata(
            int(env_id),
            RESOURCE_POOL_METADATA_NAMESPACE,
            metadata_key,
            card,
            value_type="json",
        )
        if ok:
            self._publish_resource_pool_updated(env_id=int(env_id), pool_name=pool_name)
        return ok

    async def mark_resource_pool_eligible(
        self,
        env_id: int,
        *,
        pool_name: str,
        reason: str = "",
    ) -> bool:
        manager = get_environment_manager()
        metadata_key = build_resource_pool_metadata_key(self._module_name, pool_name)
        current = await manager.get_metadata(int(env_id), RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
        exclusive = bool(current.get("exclusive", True)) if isinstance(current, dict) else True
        card = build_resource_pool_card(
            self._module_name,
            pool_name,
            eligible=True,
            reason=reason,
            exclusive=exclusive,
        )
        ok = await manager.set_metadata(
            int(env_id),
            RESOURCE_POOL_METADATA_NAMESPACE,
            metadata_key,
            card,
            value_type="json",
        )
        if ok:
            self._publish_resource_pool_updated(env_id=int(env_id), pool_name=pool_name)
        return ok

    async def mark_resource_pool_ineligible(
        self,
        env_id: int,
        *,
        pool_name: str,
        reason: str,
    ) -> bool:
        manager = get_environment_manager()
        metadata_key = build_resource_pool_metadata_key(self._module_name, pool_name)
        current = await manager.get_metadata(int(env_id), RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
        exclusive = bool(current.get("exclusive", True)) if isinstance(current, dict) else True
        card = build_resource_pool_card(
            self._module_name,
            pool_name,
            eligible=False,
            reason=reason,
            exclusive=exclusive,
        )
        ok = await manager.set_metadata(
            int(env_id),
            RESOURCE_POOL_METADATA_NAMESPACE,
            metadata_key,
            card,
            value_type="json",
        )
        if ok:
            self._publish_resource_pool_updated(env_id=int(env_id), pool_name=pool_name)
        return ok

    async def remove_resource_pool(
        self,
        env_id: int,
        *,
        pool_name: str,
    ) -> bool:
        manager = get_environment_manager()
        metadata_key = build_resource_pool_metadata_key(self._module_name, pool_name)
        await manager.delete_metadata(int(env_id), RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
        self._publish_resource_pool_updated(env_id=int(env_id), pool_name=pool_name)
        return True

    async def replace_resource_pool_snapshot(
        self,
        *,
        pool_name: str,
        entries: list[dict[str, Any]],
    ) -> bool:
        manager = get_environment_manager()
        metadata_key = build_resource_pool_metadata_key(self._module_name, pool_name)
        desired_env_ids: set[int] = set()

        for entry in entries:
            env_id = int(entry["env_id"])
            desired_env_ids.add(env_id)
            card = build_resource_pool_card(
                self._module_name,
                pool_name,
                eligible=bool(entry.get("eligible", True)),
                reason=str(entry.get("reason", "")),
                exclusive=bool(entry.get("exclusive", True)),
            )
            await manager.set_metadata(
                env_id,
                RESOURCE_POOL_METADATA_NAMESPACE,
                metadata_key,
                card,
                value_type="json",
            )

        for env in await manager.list_envs():
            if int(env.id) in desired_env_ids:
                continue
            current = await manager.get_metadata(int(env.id), RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
            if current is not None:
                await manager.delete_metadata(int(env.id), RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
                self._publish_resource_pool_updated(env_id=int(env.id), pool_name=pool_name)
        for env_id in desired_env_ids:
            self._publish_resource_pool_updated(env_id=env_id, pool_name=pool_name)
        return True


class CoreUITools:
    """Core 侧 UI 声明工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._data_store = get_module_data_store()

    def declare_page(self, page_id: str, schema: dict[str, Any]) -> bool:
        managed_page_id = _validate_managed_identifier(page_id, field_name="page_id")
        meta = sdk_normalize_page_schema(managed_page_id, dict(schema or {}))
        return self._data_store.write_page_schema(self._module_name, managed_page_id, meta)

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._data_store.read_page_schema(self._module_name, page_id)

    def declare_data_table(self, view_id: str, schema: dict[str, Any]) -> bool:
        managed_view_id = _validate_managed_identifier(view_id, field_name="view_id")
        meta = sdk_normalize_table_schema(managed_view_id, dict(schema or {}))
        return self._data_store.write_data_table_schema(self._module_name, managed_view_id, meta)

    def get_data_table(self, view_id: str) -> dict[str, Any]:
        return self._data_store.read_data_table_schema(self._module_name, view_id)


def _solve_slider_with_sinanz(
    *,
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    puzzle_piece_start_bbox: BBox | None = None,
    device: str = "auto",
    return_debug: bool = False,
) -> SliderCaptchaMatchResult:
    from sinanz import CaptchaSolver

    result = CaptchaSolver(
        device=device,
        asset_root=_resolve_captcha_models_root(),
    ).sn_match_slider(
        background_image,
        puzzle_piece_image,
        puzzle_piece_start_bbox=puzzle_piece_start_bbox,
        return_debug=return_debug,
    )

    debug = None
    if return_debug and result.debug is not None:
        debug = SliderCaptchaDebugInfo(notes=list(result.debug.notes))

    return SliderCaptchaMatchResult(
        target_center=tuple(result.target_center),
        target_bbox=tuple(result.target_bbox),
        puzzle_piece_offset=tuple(result.puzzle_piece_offset) if result.puzzle_piece_offset is not None else None,
        debug=debug,
    )


def _solve_click_with_sinanz(
    *,
    query_icons_image: ImageInput,
    background_image: ImageInput,
    device: str = "auto",
    return_debug: bool = False,
) -> ClickCaptchaMatchResult:
    from sinanz_group1_service import solve_click_targets

    result = solve_click_targets(
        query_icons_image=query_icons_image,
        background_image=background_image,
        device=device,
        asset_root=_resolve_captcha_resource_root(),
        return_debug=return_debug,
    )

    debug = None
    if return_debug and result.debug is not None:
        debug = ClickCaptchaDebugInfo(notes=list(result.debug.notes))

    ordered_targets = [
        ClickCaptchaOrderedTarget(
            query_order=int(item.query_order),
            center=tuple(item.center),
            class_id=int(item.class_id),
            class_name=str(item.class_name),
            score=float(item.score),
        )
        for item in result.ordered_targets
    ]

    return ClickCaptchaMatchResult(
        ordered_target_centers=[tuple(point) for point in result.ordered_target_centers],
        ordered_targets=ordered_targets,
        missing_query_orders=[int(order) for order in result.missing_query_orders],
        ambiguous_query_orders=[int(order) for order in result.ambiguous_query_orders],
        debug=debug,
    )


class CoreCaptchaTools:
    """Core 侧验证码工具实现。"""

    def match_slider(
        self,
        background_image: ImageInput,
        puzzle_piece_image: ImageInput,
        *,
        puzzle_piece_start_bbox: BBox | None = None,
        device: str = "auto",
        return_debug: bool = False,
    ) -> SliderCaptchaMatchResult:
        return _solve_slider_with_sinanz(
            background_image=background_image,
            puzzle_piece_image=puzzle_piece_image,
            puzzle_piece_start_bbox=puzzle_piece_start_bbox,
            device=device,
            return_debug=return_debug,
        )

    def match_click_targets(
        self,
        query_icons_image: ImageInput,
        background_image: ImageInput,
        *,
        device: str = "auto",
        return_debug: bool = False,
    ) -> ClickCaptchaMatchResult:
        return _solve_click_with_sinanz(
            query_icons_image=query_icons_image,
            background_image=background_image,
            device=device,
            return_debug=return_debug,
        )


@dataclass(frozen=True)
class _ToolBinding:
    spec: ToolSpec
    handler: Callable[..., Any]


class CoreToolsCapabilityImpl(ToolsCapability):
    """Core 侧统一工具注册表。"""

    def __init__(self, module_name: str):
        self._bindings: dict[str, _ToolBinding] = {}

        db_tools = CoreDatabaseTools(module_name)
        ip_pool_tools = CoreIPPoolTools()
        env_tools = CoreEnvTools(module_name)
        ui_tools = CoreUITools(module_name)
        captcha_tools = CoreCaptchaTools()

        self._register("db.list_records", "读取模块数据集", db_tools.list_records)
        self._register("db.replace_records", "全量覆盖模块数据集", db_tools.replace_records)
        self._register("db.append_event", "追加模块审计事件", db_tools.append_event)
        self._register("db.query_events", "查询模块审计事件", db_tools.query_events)
        self._register("db.acquire_lock", "获取模块幂等锁", db_tools.acquire_lock)
        self._register("db.release_lock", "释放模块幂等锁", db_tools.release_lock)
        self._register("db.is_locked", "查询模块锁状态", db_tools.is_locked)
        self._register("db.get_state", "读取轻量运行状态", db_tools.get_state)
        self._register("db.set_state", "写入轻量运行状态", db_tools.set_state)
        self._register("db.exists_state", "检查状态键是否存在", db_tools.exists_state)

        self._register("ip_pool.pick_proxy", "按条件挑选可用代理", ip_pool_tools.pick_proxy)
        self._register("env.set_proxy", "为当前环境设置代理", env_tools.set_proxy, is_async=True)
        self._register("env.bind_resource_pool", "登记环境资源池资格", env_tools.bind_resource_pool, is_async=True)
        self._register(
            "env.mark_resource_pool_eligible",
            "标记环境资源池可接单",
            env_tools.mark_resource_pool_eligible,
            is_async=True,
        )
        self._register(
            "env.mark_resource_pool_ineligible",
            "标记环境资源池不可接单",
            env_tools.mark_resource_pool_ineligible,
            is_async=True,
        )
        self._register("env.remove_resource_pool", "移除环境资源池资格", env_tools.remove_resource_pool, is_async=True)
        self._register(
            "env.replace_resource_pool_snapshot",
            "重建环境资源池资格快照",
            env_tools.replace_resource_pool_snapshot,
            is_async=True,
        )

        self._register("ui.declare_page", "声明宿主页 schema", ui_tools.declare_page)
        self._register("ui.get_page", "读取宿主页 schema", ui_tools.get_page)
        self._register("ui.declare_data_table", "声明数据表视图元数据", ui_tools.declare_data_table)
        self._register("ui.get_data_table", "读取数据表视图元数据", ui_tools.get_data_table)

        self._register("captcha.match_slider", "识别滑块验证码缺口位置", captcha_tools.match_slider)
        self._register("captcha.match_click_targets", "识别点选验证码目标位置", captcha_tools.match_click_targets)

    def _register(self, name: str, description: str, handler: Callable[..., Any], *, is_async: bool = False) -> None:
        self._bindings[name] = _ToolBinding(
            spec=ToolSpec(name=name, description=description, is_async=is_async),
            handler=handler,
        )

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._bindings

    def list_tools(self) -> list[ToolSpec]:
        return [binding.spec for binding in sorted(self._bindings.values(), key=lambda item: item.spec.name)]

    def call(self, tool_name: str, /, **kwargs: Any) -> Any:
        binding = self._bindings.get(tool_name)
        if binding is None:
            raise KeyError(f"Unknown core tool: {tool_name}")
        return binding.handler(**kwargs)


@dataclass
class RuntimeCapabilities:
    tools: ToolsCapability


def build_runtime_capabilities(task_name: str) -> RuntimeCapabilities:
    module_name = (task_name or "").split(".")[0] or "default"
    return RuntimeCapabilities(tools=CoreToolsCapabilityImpl(module_name))
