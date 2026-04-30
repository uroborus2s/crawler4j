"""Core-owned runtime descriptor discovery for core-native-v2 modules."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from crawler4j_contracts import (
    CRAWLER4J_META_ATTR,
    Crawler4jMeta,
    TaskContext,
    TaskResult,
)
from crawler4j_contracts.hosted_ui import normalize_page_schema

from src.core.mms.models import ModuleManifest
from src.core.mms.module_loader import load_root_module_from_path

V2_RUNTIME_API = "core-native-v2"
V2_SCAN_DIRECTORIES = ("interfaces", "objects", "workflows", "tasks", "data", "pages")


@dataclass(frozen=True)
class PageRuntimeSpec:
    id: str
    label: str = ""
    icon: str = "📋"
    menu: bool = False
    order: int = 0
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PageRuntimeEntry:
    spec: PageRuntimeSpec
    module_name: str
    target: Callable[..., Any] | None = None
    handlers: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def get_handler(self, handler_name: str) -> Callable[..., Any] | None:
        return self.handlers.get(handler_name)


@dataclass(frozen=True)
class V2RuntimeEntry:
    meta: Crawler4jMeta
    target: Any
    module_name: str
    attr_name: str
    owner: str


@dataclass(frozen=True)
class ModuleRuntimeDescriptorV2:
    interfaces: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    components: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    workflows: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    page_actions: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    pages: dict[str, PageRuntimeEntry] = field(default_factory=dict)
    data_tables: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    data_queries: dict[str, V2RuntimeEntry] = field(default_factory=dict)
    implementations: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _iter_python_modules(package_dir: Path, directory_name: str) -> list[tuple[str, str]]:
    if not package_dir.exists():
        return []
    modules: list[tuple[str, str]] = []
    for path in sorted(package_dir.rglob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        relative = path.relative_to(package_dir)
        if any(part.startswith("_") for part in relative.parts[:-1]):
            continue
        module_name = ".".join(relative.with_suffix("").parts)
        owner = f"{directory_name}/{relative.as_posix()}"
        modules.append((module_name, owner))
    return modules


def _import_v2_submodule(module_name: str, directory_name: str, item_name: str, owner: str) -> Any:
    import_target = f"{module_name}.{directory_name}.{item_name}"
    try:
        return importlib.import_module(import_target)
    except Exception as exc:  # pragma: no cover - exercised by caller tests
        raise RuntimeError(f"{owner} 无法导入: {exc.__class__.__name__}: {exc}") from exc


def _iter_decorated_entries(module: Any, owner: str) -> list[V2RuntimeEntry]:
    entries: list[V2RuntimeEntry] = []
    for attr_name in sorted(dir(module)):
        if attr_name.startswith("_"):
            continue
        target = getattr(module, attr_name)
        if getattr(target, "__module__", module.__name__) != module.__name__:
            continue
        meta = getattr(target, CRAWLER4J_META_ATTR, None)
        if not isinstance(meta, Crawler4jMeta):
            continue
        entries.append(
            V2RuntimeEntry(
                meta=meta,
                target=target,
                module_name=module.__name__,
                attr_name=attr_name,
                owner=owner,
            )
        )
    return entries


def _add_v2_entry(bucket: dict[str, V2RuntimeEntry], entry: V2RuntimeEntry, *, label: str) -> None:
    previous = bucket.get(entry.meta.name)
    if previous is not None:
        raise RuntimeError(f"{label} 名称重复: {entry.meta.name} ({previous.owner}、{entry.owner})")
    bucket[entry.meta.name] = entry


def _collect_v2_entries(module_name: str, package_root: Path) -> list[V2RuntimeEntry]:
    entries: list[V2RuntimeEntry] = []
    for directory_name in V2_SCAN_DIRECTORIES:
        directory = package_root / directory_name
        for item_name, owner in _iter_python_modules(directory, directory_name):
            module = _import_v2_submodule(module_name, directory_name, item_name, owner)
            entries.extend(_iter_decorated_entries(module, owner))
    return entries


def _build_v2_descriptor(entries: list[V2RuntimeEntry]) -> ModuleRuntimeDescriptorV2:
    interfaces: dict[str, V2RuntimeEntry] = {}
    components: dict[str, V2RuntimeEntry] = {}
    workflows: dict[str, V2RuntimeEntry] = {}
    page_actions: dict[str, V2RuntimeEntry] = {}
    pages: dict[str, PageRuntimeEntry] = {}
    data_tables: dict[str, V2RuntimeEntry] = {}
    data_queries: dict[str, V2RuntimeEntry] = {}
    page_owners: dict[str, str] = {}

    for entry in entries:
        kind = entry.meta.kind
        if kind == "interface":
            _add_v2_entry(interfaces, entry, label="interface")
        elif kind == "component":
            _add_v2_entry(components, entry, label="component")
        elif kind == "workflow":
            _add_v2_entry(workflows, entry, label="workflow")
        elif kind == "page":
            previous_owner = page_owners.get(entry.meta.name)
            if previous_owner and previous_owner != entry.owner:
                raise RuntimeError(f"宿主页 {entry.meta.name} 重复定义: {previous_owner}、{entry.owner}")
            page_owners[entry.meta.name] = entry.owner
            pages[entry.meta.name] = _page_entry_from_v2_entry(entry)
        elif kind == "page_action":
            _add_v2_entry(page_actions, entry, label="page_action")
        elif kind == "data_table":
            _add_v2_entry(data_tables, entry, label="data_table")
        elif kind == "data_query":
            _add_v2_entry(data_queries, entry, label="data_query")
        else:  # pragma: no cover
            raise RuntimeError(f"{entry.owner} 包含不支持的装饰器类型: {kind}")

    descriptor = ModuleRuntimeDescriptorV2(
        interfaces=interfaces,
        components=components,
        workflows=workflows,
        page_actions=page_actions,
        pages=pages,
        data_tables=data_tables,
        data_queries=data_queries,
        implementations=_build_implementations(interfaces, components),
    )
    _validate_v2_inject_targets(descriptor)
    _validate_v2_dependency_graph(descriptor)
    return descriptor


def _build_implementations(
    interfaces: dict[str, V2RuntimeEntry],
    components: dict[str, V2RuntimeEntry],
) -> dict[str, tuple[str, ...]]:
    implementations: dict[str, list[str]] = {}
    for component_name, entry in components.items():
        interface_name = entry.meta.implements
        if not interface_name:
            raise RuntimeError(f"{entry.owner} 的 component {component_name} 缺少 implements")
        if interface_name not in interfaces:
            raise RuntimeError(f"{entry.owner} 的 component {component_name} implements 目标不存在: {interface_name}")
        implementations.setdefault(interface_name, []).append(component_name)
    return {name: tuple(sorted(items)) for name, items in sorted(implementations.items())}


def _validate_v2_inject_targets(descriptor: ModuleRuntimeDescriptorV2) -> None:
    for entry in [*descriptor.components.values(), *descriptor.workflows.values()]:
        for inject in entry.meta.inject:
            if inject.type == "interface" and inject.target not in descriptor.interfaces:
                raise RuntimeError(f"注入目标不存在: {entry.meta.kind} {entry.meta.name} -> interface {inject.target}")
            if inject.type == "object" and inject.target not in descriptor.components:
                raise RuntimeError(f"注入目标不存在: {entry.meta.kind} {entry.meta.name} -> object {inject.target}")


def _component_dependencies(component_name: str, descriptor: ModuleRuntimeDescriptorV2) -> tuple[str, ...]:
    entry = descriptor.components[component_name]
    dependencies: set[str] = set()
    for inject in entry.meta.inject:
        if inject.type == "object":
            dependencies.add(inject.target)
        elif inject.type == "interface":
            dependencies.update(descriptor.implementations.get(inject.target, ()))
    return tuple(sorted(dependencies))


def _validate_v2_dependency_graph(descriptor: ModuleRuntimeDescriptorV2) -> None:
    states: dict[str, str] = {}
    path: list[str] = []

    def visit(component_name: str) -> None:
        state = states.get(component_name)
        if state == "done":
            return
        if state == "visiting":
            start = path.index(component_name)
            raise RuntimeError("循环依赖: " + " -> ".join([*path[start:], component_name]))
        states[component_name] = "visiting"
        path.append(component_name)
        for dependency in _component_dependencies(component_name, descriptor):
            visit(dependency)
        path.pop()
        states[component_name] = "done"

    for component_name in sorted(descriptor.components):
        visit(component_name)


def _page_handlers(module: Any) -> dict[str, Callable[..., Any]]:
    handlers: dict[str, Callable[..., Any]] = {}
    for attr_name in dir(module):
        if attr_name.startswith("_"):
            continue
        candidate = getattr(module, attr_name)
        if not callable(candidate):
            continue
        handlers[attr_name] = candidate
    return handlers


def _page_entry_from_v2_entry(entry: V2RuntimeEntry) -> PageRuntimeEntry:
    page_id = str(entry.meta.name or "").strip()
    raw_schema = dict(entry.meta.page_schema or {})
    load_handler = str(raw_schema.get("load_handler") or "").strip()
    if load_handler and load_handler != entry.attr_name:
        raise RuntimeError(f"{entry.owner} 的 @page load_handler 必须与装饰函数一致: {entry.attr_name}")
    raw_schema["load_handler"] = entry.attr_name
    normalized_schema = normalize_page_schema(page_id, raw_schema)
    module = inspect.getmodule(entry.target)
    handlers = _page_handlers(module) if module is not None else {}
    return PageRuntimeEntry(
        spec=PageRuntimeSpec(
            id=page_id,
            label=str(entry.meta.label or page_id).strip() or page_id,
            icon=str(entry.meta.icon or "📋").strip() or "📋",
            menu=bool(entry.meta.menu),
            order=int(entry.meta.order or 0),
            schema=normalized_schema,
        ),
        module_name=entry.module_name,
        target=entry.target if callable(entry.target) else None,
        handlers=handlers,
    )


def normalize_result_payload(result: object, context: TaskContext) -> TaskResult:
    if isinstance(result, TaskResult):
        return result
    if result is None:
        return TaskResult.ok(data=dict(context.state))
    if isinstance(result, dict):
        return TaskResult.ok(data=result)
    return TaskResult.ok(data={"value": result})


async def invoke_runtime_callable(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def load_runtime_descriptor_v2(
    module_name: str,
    package_root: Path,
    manifest: ModuleManifest,
    *,
    force_reload: bool = False,
) -> ModuleRuntimeDescriptorV2:
    runtime_api = str(manifest.runtime_api or "").strip()
    if runtime_api != V2_RUNTIME_API:
        raise RuntimeError(f"module.yaml.runtime_api 必须是 {V2_RUNTIME_API}: {runtime_api}")

    load_root_module_from_path(module_name, package_root, force_reload=force_reload)
    return _build_v2_descriptor(_collect_v2_entries(module_name, package_root))
