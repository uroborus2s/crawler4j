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
from crawler4j_contracts.hosted_ui import (
    normalize_page_schema as sdk_normalize_page_schema,
)
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.mms.data_contract import load_sql_file, validate_resource_sql
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
        raise ValueError("resource records must be a list of objects")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"resource records[{index}] must be an object")
        normalized.append(dict(item))

    return normalized


MANAGED_VIEW_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
RUNTIME_SURFACE_FULL = "full"
RUNTIME_SURFACE_HOSTED_UI_DECLARE = "hosted_ui_declare"
RUNTIME_SURFACE_HOSTED_UI_READONLY = "hosted_ui_readonly"

_RUNTIME_SURFACE_TOOL_NAMES: dict[str, frozenset[str] | None] = {
    RUNTIME_SURFACE_FULL: None,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE: frozenset(
        {
            "ui.declare_page",
        }
    ),
    RUNTIME_SURFACE_HOSTED_UI_READONLY: frozenset(
        {
            "db.get_record",
            "db.list_records",
            "db.query_events",
            "db.run_query",
            "db.query_view",
            "ui.get_page",
        }
    ),
}
DECLARE_UI_SIDE_EFFECT_DB_TOOLS = {
    "db.replace_records",
    "db.append_event",
    "db.set_state",
    "db.acquire_lock",
    "db.release_lock",
}


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


def _raise_declare_ui_side_effect_error(tool_name: str) -> None:
    raise RuntimeError(f"declare_ui 不允许调用 {tool_name}；UI 声明必须保持无副作用")


def _resolve_runtime_surface_tools(surface: str) -> frozenset[str] | None:
    if surface not in _RUNTIME_SURFACE_TOOL_NAMES:
        raise ValueError(f"Unknown runtime capability surface: {surface}")
    return _RUNTIME_SURFACE_TOOL_NAMES[surface]


class HostedUIDeclarationBuffer:
    """声明期的 hosted UI staging buffer。"""

    def __init__(self):
        self.page_schemas: dict[str, dict[str, Any]] = {}
        self._collecting = True

    @property
    def is_collecting(self) -> bool:
        return self._collecting

    def stage_page(self, page_id: str, schema: dict[str, Any]) -> None:
        self.page_schemas[page_id] = dict(schema)

    def seal(self) -> None:
        self._collecting = False


class CoreDatabaseTools:
    """Core 侧基础数据工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._data_store = get_module_data_store()
        self._kv = get_kv_store()

    def _lock_key(self, scope: str, key: str) -> str:
        return f"module:{self._module_name}:lock:{scope}:{key}"

    @staticmethod
    def _normalize_resource_name(resource: str | None) -> str:
        name = str(resource or "").strip()
        if not name:
            raise ValueError("必须提供 resource")
        return name

    def list_records(
        self,
        *,
        resource: str,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        resource_name = self._normalize_resource_name(resource)
        return self._data_store.list_records(
            self._module_name,
            resource_name,
            filters=dict(filters or {}),
            sort=list(sort or []),
            limit=limit,
            offset=offset,
        )

    def get_record(self, key: Any, *, resource: str) -> dict[str, Any] | None:
        resource_name = self._normalize_resource_name(resource)
        return self._data_store.get_record(self._module_name, resource_name, key)

    def replace_records(
        self,
        *,
        resource: str,
        records: list[dict[str, Any]],
    ) -> bool:
        resource_name = self._normalize_resource_name(resource)
        return self._data_store.replace_resource_records(self._module_name, resource_name, _normalize_records(records))

    def run_query(self, query_id: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        from src.core.mms.registry import get_module_registry

        normalized_query_id = _validate_managed_identifier(str(query_id or "").strip(), field_name="query_id")
        module = get_module_registry().get_module(self._module_name)
        if module is None or module.path is None:
            raise RuntimeError(f"未找到模块数据契约: {self._module_name}")

        query_spec = next(
            (item for item in module.manifest.data["queries"] if item["query_id"] == normalized_query_id),
            None,
        )
        if query_spec is None:
            raise ValueError(f"未注册的 query_id: {normalized_query_id}")

        sql = load_sql_file(module.path, query_spec["sql_file"], expected_prefix="data/sql/queries/")
        validate_resource_sql(
            sql,
            source_resource_ids=query_spec["source_resource_ids"],
            owner_label=f"data.queries[{normalized_query_id}]",
        )
        normalized_params = dict(params or {})
        declared_params = {item["name"]: item for item in query_spec["params"]}
        missing = sorted(
            name
            for name, spec in declared_params.items()
            if spec["required"] and name not in normalized_params
        )
        if missing:
            raise ValueError(f"query 参数缺失: {', '.join(missing)}")
        extra = sorted(set(normalized_params) - set(declared_params))
        if extra:
            raise ValueError(f"query 参数未注册: {', '.join(extra)}")
        return self._data_store.run_registered_query(
            self._module_name,
            source_resource_ids=query_spec["source_resource_ids"],
            sql_template=sql,
            columns=query_spec["columns"],
            params=normalized_params,
        )

    def query_view(
        self,
        view_id: str,
        *,
        filters: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        query_db_view = getattr(self._data_store, "query_db_view", None)
        if not callable(query_db_view):
            raise RuntimeError("当前宿主不支持 db.query_view")
        return query_db_view(
            self._module_name,
            view_id,
            filters=dict(filters or {}),
            sort=[dict(item) for item in (sort or []) if isinstance(item, dict)],
            limit=limit,
            offset=offset,
        )

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

    def __init__(
        self,
        module_name: str,
        *,
        declaration_buffer: HostedUIDeclarationBuffer | None = None,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
        allow_persisted_pages: bool = True,
    ):
        self._module_name = module_name
        self._allow_persisted_pages = allow_persisted_pages
        self._data_store = get_module_data_store() if allow_persisted_pages else None
        self._declaration_buffer = declaration_buffer
        self._declared_page_schemas = (
            {
                str(page_id): dict(schema)
                for page_id, schema in dict(declared_page_schemas or {}).items()
                if isinstance(schema, dict)
            }
            if declared_page_schemas is not None
            else None
        )

    def declare_page(self, page_id: str, schema: dict[str, Any]) -> bool:
        managed_page_id = _validate_managed_identifier(page_id, field_name="page_id")
        meta = sdk_normalize_page_schema(managed_page_id, dict(schema or {}))
        if self._declaration_buffer and self._declaration_buffer.is_collecting:
            self._declaration_buffer.stage_page(managed_page_id, meta)
            return True
        if not self._allow_persisted_pages or self._data_store is None:
            raise RuntimeError("hosted UI declare surface 必须使用声明缓冲区，不能持久化页面 schema")
        return self._data_store.write_page_schema(self._module_name, managed_page_id, meta)

    def get_page(self, page_id: str) -> dict[str, Any]:
        if self._declared_page_schemas is not None:
            return dict(self._declared_page_schemas.get(str(page_id or "").strip(), {}))
        if not self._allow_persisted_pages or self._data_store is None:
            raise RuntimeError("hosted UI readonly surface 必须使用本轮声明的页面 schema")
        return self._data_store.read_page_schema(self._module_name, page_id)


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

    def __init__(
        self,
        module_name: str,
        *,
        ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
        allowed_tool_names: frozenset[str] | None = None,
        declared_page_schemas: dict[str, dict[str, Any]] | None = None,
        allow_persisted_pages: bool = True,
    ):
        self._bindings: dict[str, _ToolBinding] = {}
        self._allowed_tool_names = allowed_tool_names
        self._ui_declaration_buffer = ui_declaration_buffer

        db_tools = CoreDatabaseTools(module_name)
        ip_pool_tools = CoreIPPoolTools()
        env_tools = CoreEnvTools(module_name)
        ui_tools = CoreUITools(
            module_name,
            declaration_buffer=ui_declaration_buffer,
            declared_page_schemas=declared_page_schemas,
            allow_persisted_pages=allow_persisted_pages,
        )
        captcha_tools = CoreCaptchaTools()

        self._register("db.list_records", "读取模块资源记录", db_tools.list_records)
        self._register("db.get_record", "按主键读取单条模块记录", db_tools.get_record)
        self._register("db.replace_records", "全量覆盖模块资源记录", db_tools.replace_records)
        self._register("db.run_query", "执行已注册命名 SQL 查询", db_tools.run_query)
        self._register("db.query_view", "查询数据库统计视图", db_tools.query_view)
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

        self._register("captcha.match_slider", "识别滑块验证码缺口位置", captcha_tools.match_slider)
        self._register("captcha.match_click_targets", "识别点选验证码目标位置", captcha_tools.match_click_targets)

    def _register(self, name: str, description: str, handler: Callable[..., Any], *, is_async: bool = False) -> None:
        if self._allowed_tool_names is not None and name not in self._allowed_tool_names:
            return
        self._bindings[name] = _ToolBinding(
            spec=ToolSpec(name=name, description=description, is_async=is_async),
            handler=handler,
        )

    def _blocks_side_effect_tool(self, tool_name: str) -> bool:
        return bool(
            self._ui_declaration_buffer
            and self._ui_declaration_buffer.is_collecting
            and tool_name in DECLARE_UI_SIDE_EFFECT_DB_TOOLS
        )

    def has_tool(self, tool_name: str) -> bool:
        if self._blocks_side_effect_tool(tool_name):
            return False
        return tool_name in self._bindings

    def list_tools(self) -> list[ToolSpec]:
        return [
            binding.spec
            for binding in sorted(self._bindings.values(), key=lambda item: item.spec.name)
            if not self._blocks_side_effect_tool(binding.spec.name)
        ]

    def call(self, tool_name: str, /, **kwargs: Any) -> Any:
        if self._blocks_side_effect_tool(tool_name):
            _raise_declare_ui_side_effect_error(tool_name)
        binding = self._bindings.get(tool_name)
        if binding is None:
            raise KeyError(f"Unknown core tool: {tool_name}")
        return binding.handler(**kwargs)


@dataclass
class RuntimeCapabilities:
    tools: ToolsCapability


def build_runtime_capabilities(
    task_name: str,
    *,
    ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
    surface: str = RUNTIME_SURFACE_FULL,
    declared_page_schemas: dict[str, dict[str, Any]] | None = None,
) -> RuntimeCapabilities:
    module_name = (task_name or "").split(".")[0] or "default"
    return RuntimeCapabilities(
        tools=CoreToolsCapabilityImpl(
            module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            allowed_tool_names=_resolve_runtime_surface_tools(surface),
            declared_page_schemas=declared_page_schemas,
            allow_persisted_pages=surface == RUNTIME_SURFACE_FULL,
        )
    )
