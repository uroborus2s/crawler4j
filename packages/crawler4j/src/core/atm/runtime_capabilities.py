"""ATM 运行时工具注入实现。

将 Core 能力以统一工具形式注入 TaskContext，供 model 脚本通过 SDK 访问。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
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
from src.core.persistence import get_kv_store
from src.core.rem.ip_pool import IPEntry, get_ip_pool_manager
from src.core.rem.manager import get_environment_manager


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append(dict(item))

    return normalized


class CoreDatabaseTools:
    """Core 侧基础数据工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._kv = get_kv_store()

    def _dataset_key(self, dataset: str) -> str:
        return f"module:{self._module_name}:dataset:{dataset}"

    def _lock_key(self, scope: str, key: str) -> str:
        return f"module:{self._module_name}:lock:{scope}:{key}"

    def list_records(self, dataset: str) -> list[dict[str, Any]]:
        raw = self._kv.get(self._dataset_key(dataset)) or []
        return _normalize_records(raw)

    def replace_records(self, dataset: str, records: list[dict[str, Any]]) -> bool:
        return self._kv.set(self._dataset_key(dataset), _normalize_records(records))

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


class CoreUITools:
    """Core 侧 UI 声明工具实现。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._kv = get_kv_store()

    def _meta_key(self, view_id: str) -> str:
        return f"module:{self._module_name}:ui:data_table:{view_id}"

    def _dataset_key(self, dataset: str) -> str:
        return f"module:{self._module_name}:dataset:{dataset}"

    def declare_data_table(self, view_id: str, schema: dict[str, Any]) -> bool:
        meta = dict(schema or {})
        meta.setdefault("title", view_id)
        meta.setdefault("dataset", view_id)
        meta.setdefault("primary_key", "id")
        meta.setdefault("columns", [])

        dataset = str(meta.get("dataset") or view_id)
        if self._kv.get(self._dataset_key(dataset)) is None:
            self._kv.set(self._dataset_key(dataset), [])

        return self._kv.set(self._meta_key(view_id), meta)

    def get_data_table(self, view_id: str) -> dict[str, Any]:
        return self._kv.get(self._meta_key(view_id)) or {}


def _solve_slider_with_sinanz(
    *,
    background_image: ImageInput,
    puzzle_piece_image: ImageInput,
    puzzle_piece_start_bbox: BBox | None = None,
    device: str = "auto",
    return_debug: bool = False,
) -> SliderCaptchaMatchResult:
    from sinanz import sn_match_slider

    result = sn_match_slider(
        background_image,
        puzzle_piece_image,
        puzzle_piece_start_bbox=puzzle_piece_start_bbox,
        device=device,
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
        asset_root=None,
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
        env_tools = CoreEnvTools()
        ui_tools = CoreUITools(module_name)
        captcha_tools = CoreCaptchaTools()

        self._register("db.list_records", "读取模块数据集", db_tools.list_records)
        self._register("db.replace_records", "全量覆盖模块数据集", db_tools.replace_records)
        self._register("db.acquire_lock", "获取模块幂等锁", db_tools.acquire_lock)
        self._register("db.release_lock", "释放模块幂等锁", db_tools.release_lock)
        self._register("db.is_locked", "查询模块锁状态", db_tools.is_locked)
        self._register("db.get_state", "读取轻量运行状态", db_tools.get_state)
        self._register("db.set_state", "写入轻量运行状态", db_tools.set_state)
        self._register("db.exists_state", "检查状态键是否存在", db_tools.exists_state)

        self._register("ip_pool.pick_proxy", "按条件挑选可用代理", ip_pool_tools.pick_proxy)
        self._register("env.set_proxy", "为当前环境设置代理", env_tools.set_proxy, is_async=True)

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
