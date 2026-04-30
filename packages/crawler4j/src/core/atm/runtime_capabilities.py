"""ATM 运行时工具注入实现。

将 Core 能力以统一工具形式注入 TaskContext，供 model 脚本通过 SDK 访问。
"""

from __future__ import annotations

import re
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
from crawler4j_contracts.database import DatabaseClient
from crawler4j_contracts.hosted_ui import (
    normalize_page_schema as sdk_normalize_page_schema,
)
from src.core.mms.data_contract import load_sql_file, validate_resource_sql
from src.core.persistence import get_module_data_store
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
RUNTIME_SURFACE_HOSTED_UI_ACTION = "hosted_ui_action"
RUNTIME_SURFACE_ENV_CANDIDATES = "env_candidates"
RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES = "env_cleanup_candidates"

_RUNTIME_SURFACE_TOOL_NAMES: dict[str, frozenset[str] | None] = {
    RUNTIME_SURFACE_FULL: None,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE: frozenset(
        {
            "ui.declare_page",
        }
    ),
    RUNTIME_SURFACE_HOSTED_UI_READONLY: frozenset(
        {
            "ui.get_page",
        }
    ),
    RUNTIME_SURFACE_HOSTED_UI_ACTION: frozenset(
        {
            "ui.get_page",
        }
    ),
    RUNTIME_SURFACE_ENV_CANDIDATES: frozenset(),
    RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES: frozenset(),
}
DECLARE_UI_SIDE_EFFECT_DB_TOOLS: set[str] = set()


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


def _get_ip_pool_manager():
    from src.core.rem.ip_pool import get_ip_pool_manager

    return get_ip_pool_manager()


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

    def __init__(self, module_name: str, *, enabled: bool = True, read_only: bool = False):
        self._module_name = module_name
        self._data_store = get_module_data_store()
        self._enabled = enabled
        self._read_only = read_only

    @staticmethod
    def _normalize_resource_name(resource: str | None) -> str:
        name = str(resource or "").strip()
        if not name:
            raise ValueError("必须提供 resource")
        return name

    def _ensure_enabled(self) -> None:
        if not self._enabled:
            raise RuntimeError("ctx.db is not available in this runtime context")

    def _manifest_data(self) -> dict[str, Any]:
        from src.core.mms.registry import get_module_registry

        module = get_module_registry().get_module(self._module_name)
        manifest = getattr(module, "manifest", None) if module is not None else None
        data = getattr(manifest, "data", None)
        return data if isinstance(data, dict) else {"resources": [], "views": [], "queries": [], "seeds": []}

    def _manifest_resource(self, resource_id: str) -> dict[str, Any] | None:
        for resource in self._manifest_data().get("resources", []):
            if isinstance(resource, dict) and resource.get("resource_id") == resource_id:
                return resource
        return None

    def _joins_for_resource(self, resource_id: str) -> list[dict[str, Any]]:
        resource = self._manifest_resource(resource_id)
        joins = resource.get("joins", []) if isinstance(resource, dict) else []
        return [dict(item) for item in joins if isinstance(item, dict)]

    @staticmethod
    def _columns_from_resource(resource: dict[str, Any]) -> list[dict[str, Any]]:
        schema = resource.get("schema") if isinstance(resource.get("schema"), dict) else {}
        raw_columns = schema.get("columns", []) if isinstance(schema, dict) else []
        columns: list[dict[str, Any]] = []
        for raw in raw_columns if isinstance(raw_columns, list) else []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("key") or "").strip()
            if not name:
                continue
            columns.append(
                {
                    "name": name,
                    "type": str(raw.get("type") or "text").strip().lower(),
                    "nullable": bool(raw.get("nullable")) if "nullable" in raw else not bool(raw.get("required")),
                }
            )
        return columns

    def describe_source(self, source: str) -> dict[str, Any]:
        self._ensure_enabled()
        source_id = _validate_managed_identifier(str(source or "").strip(), field_name="source")
        resources = {item["resource_id"]: item for item in self._data_store.list_data_resources(self._module_name)}
        resource = resources.get(source_id)
        if resource is not None:
            source_kind = "relation" if resource["storage_mode"] == "custom_table" else "snapshot"
            columns = self._columns_from_resource(resource)
            if not columns:
                raise ValueError(f"数据源缺少 schema.columns，不能进入 ctx.db 查询面: {source_id}")
            if source_kind == "snapshot":
                column_names = {column["name"] for column in columns}
                for system_column, column_type in (
                    ("run_status", "text"),
                    ("record_status", "text"),
                    ("created_at", "int"),
                    ("updated_at", "int"),
                ):
                    if system_column not in column_names:
                        columns.append({"name": system_column, "type": column_type, "nullable": True})
            return {
                "source": source_id,
                "source_kind": source_kind,
                "storage_mode": resource["storage_mode"],
                "record_key_field": resource.get("record_key_field") or "id",
                "columns": columns,
                "joins": self._joins_for_resource(source_id) if source_kind == "relation" else [],
            }

        views = {item["view_id"]: item for item in self._data_store.list_db_views(self._module_name)}
        view = views.get(source_id)
        if view is not None:
            return {
                "source": source_id,
                "source_kind": "read_model",
                "columns": [dict(column) for column in view["columns"]],
                "joins": [],
            }
        raise ValueError(f"未注册的数据源: {source_id}")

    def execute_plan(self, plan: dict[str, Any]) -> Any:
        self._ensure_enabled()
        if not isinstance(plan, dict):
            raise ValueError("query plan must be an object")
        kind = str(plan.get("kind") or "select").strip()
        if kind == "named_query":
            return self._run_named_query(str(plan.get("query_id") or ""), params=dict(plan.get("params") or {}))
        if kind == "append_audit_event":
            if self._read_only:
                raise RuntimeError("ctx.db 当前运行面不允许写入")
            return self._append_audit_event(
                dataset=str(plan.get("dataset") or ""),
                event=dict(plan.get("event") or {}),
            )
        if kind == "query_audit_events":
            return self._query_audit_events(
                dataset=str(plan.get("dataset") or ""),
                entity_key=plan.get("entity_key"),
                event_type=plan.get("event_type"),
                run_id=plan.get("run_id"),
                start_at=plan.get("start_at"),
                end_at=plan.get("end_at"),
                limit=plan.get("limit", 100),
                offset=plan.get("offset", 0),
                order=str(plan.get("order") or "desc"),
            )
        if kind == "replace_records":
            if self._read_only:
                raise RuntimeError("ctx.db 当前运行面不允许写入")
            return self._replace_resource_records(
                resource=str(plan.get("resource") or ""),
                records=_normalize_records(plan.get("records")),
            )
        if kind != "select":
            raise ValueError(f"unsupported query plan kind: {kind}")
        return self._data_store.execute_query_plan(
            self._module_name,
            plan,
            describe_source=self.describe_source,
        )

    def _normalize_audit_dataset_name(self, dataset: str | None) -> str:
        return _validate_managed_identifier(str(dataset or "").strip(), field_name="dataset")

    def _replace_resource_records(
        self,
        *,
        resource: str,
        records: list[dict[str, Any]],
    ) -> bool:
        resource_name = self._normalize_resource_name(resource)
        return self._data_store.replace_resource_records(self._module_name, resource_name, _normalize_records(records))

    def _append_audit_event(self, *, dataset: str, event: dict[str, Any]) -> str:
        dataset_name = self._normalize_audit_dataset_name(dataset)
        return self._data_store.append_audit_event(self._module_name, dataset_name, event)

    def _query_audit_events(
        self,
        *,
        dataset: str,
        entity_key: Any = None,
        event_type: Any = None,
        run_id: Any = None,
        start_at: Any = None,
        end_at: Any = None,
        limit: Any = 100,
        offset: Any = 0,
        order: str = "desc",
    ) -> list[dict[str, Any]]:
        dataset_name = self._normalize_audit_dataset_name(dataset)
        return self._data_store.query_audit_events(
            self._module_name,
            dataset_name,
            entity_key=None if entity_key is None else str(entity_key),
            event_type=None if event_type is None else str(event_type),
            run_id=None if run_id is None else str(run_id),
            start_at=None if start_at is None else int(start_at),
            end_at=None if end_at is None else int(end_at),
            limit=int(limit),
            offset=int(offset),
            order=order,
        )

    def _run_named_query(self, query_id: str, *, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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

        sql = str(query_spec.get("sql") or "").strip()
        if not sql:
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


class CoreIPPoolTools:
    """Core 侧 IP 池工具实现。"""

    def _iter_candidate_entries(self, pool_id: str | None) -> list[Any]:
        manager = _get_ip_pool_manager()
        pools = []
        if pool_id:
            pool = manager.get_pool(pool_id)
            if pool:
                pools.append(pool)
        else:
            pools = manager.list_pools()

        entries: list[Any] = []
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
        from src.core.rem.manager import get_environment_manager

        manager = get_environment_manager()
        return await manager.update_env(
            env_id,
            proxy_value=proxy_value or None,
            proxy_pool_id=proxy_pool_id or None,
        )


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

        ip_pool_tools = CoreIPPoolTools()
        env_tools = CoreEnvTools()
        ui_tools = CoreUITools(
            module_name,
            declaration_buffer=ui_declaration_buffer,
            declared_page_schemas=declared_page_schemas,
            allow_persisted_pages=allow_persisted_pages,
        )
        captcha_tools = CoreCaptchaTools()

        self._register("ip_pool.pick_proxy", "按条件挑选可用代理", ip_pool_tools.pick_proxy)
        self._register("env.set_proxy", "为当前环境设置代理", env_tools.set_proxy, is_async=True)

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
    db: DatabaseClient


def build_runtime_capabilities(
    task_name: str,
    *,
    ui_declaration_buffer: HostedUIDeclarationBuffer | None = None,
    surface: str = RUNTIME_SURFACE_FULL,
    declared_page_schemas: dict[str, dict[str, Any]] | None = None,
) -> RuntimeCapabilities:
    module_name = (task_name or "").split(".")[0] or "default"
    db_enabled = surface != RUNTIME_SURFACE_HOSTED_UI_DECLARE
    db_read_only = surface in {
        RUNTIME_SURFACE_HOSTED_UI_READONLY,
        RUNTIME_SURFACE_ENV_CANDIDATES,
        RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    }
    return RuntimeCapabilities(
        tools=CoreToolsCapabilityImpl(
            module_name,
            ui_declaration_buffer=ui_declaration_buffer,
            allowed_tool_names=_resolve_runtime_surface_tools(surface),
            declared_page_schemas=declared_page_schemas,
            allow_persisted_pages=surface == RUNTIME_SURFACE_FULL,
        ),
        db=DatabaseClient(CoreDatabaseTools(module_name, enabled=db_enabled, read_only=db_read_only)),
    )
