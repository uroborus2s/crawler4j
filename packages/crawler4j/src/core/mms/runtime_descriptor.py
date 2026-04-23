"""Core-owned runtime descriptor discovery for core-native-v1 modules."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from pkgutil import iter_modules
from typing import Any, Callable

from crawler4j_contracts import EnvSelectorSpec, PageSpec, TaskResult, TaskSpec, TaskContext, WorkflowSpec
from crawler4j_contracts.hosted_ui import normalize_page_schema

from src.core.mms.models import ModuleManifest
from src.core.mms.module_loader import load_root_module_from_path

HOOK_NAMES = (
    "prepare_env",
    "init_env",
    "before_run",
    "on_success",
    "on_failure",
    "on_timeout",
    "on_cleanup",
)


@dataclass(frozen=True)
class TaskRuntimeEntry:
    spec: TaskSpec
    execute: Callable[..., Any]


@dataclass(frozen=True)
class WorkflowRuntimeEntry:
    spec: WorkflowSpec
    run: Callable[..., Any]


@dataclass(frozen=True)
class EnvSelectorRuntimeEntry:
    spec: EnvSelectorSpec
    select: Callable[..., Any]


@dataclass(frozen=True)
class PageRuntimeEntry:
    spec: PageSpec
    module_name: str
    handlers: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def get_handler(self, handler_name: str) -> Callable[..., Any] | None:
        return self.handlers.get(handler_name)


@dataclass(frozen=True)
class ModuleRuntimeDescriptor:
    tasks: dict[str, TaskRuntimeEntry] = field(default_factory=dict)
    workflows: dict[str, WorkflowRuntimeEntry] = field(default_factory=dict)
    hooks: dict[str, Callable[..., Any]] = field(default_factory=dict)
    env_selectors: dict[str, EnvSelectorRuntimeEntry] = field(default_factory=dict)
    pages: dict[str, PageRuntimeEntry] = field(default_factory=dict)
    default_workflow: str = ""


def _iter_module_files(package_dir: Path) -> list[str]:
    if not package_dir.exists():
        return []
    return sorted(
        module_info.name
        for module_info in iter_modules([str(package_dir)])
        if not module_info.name.startswith("_")
    )


def _iter_page_modules(package_dir: Path) -> list[tuple[str, str]]:
    if not package_dir.exists():
        return []
    page_modules: list[tuple[str, str]] = []
    for path in sorted(package_dir.rglob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        relative = path.relative_to(package_dir)
        if any(part.startswith("_") for part in relative.parts[:-1]):
            continue
        module_name = ".".join(relative.with_suffix("").parts)
        owner = f"pages/{relative.as_posix()}"
        page_modules.append((module_name, owner))
    return page_modules


def _import_submodule(module_name: str, subpackage: str, item_name: str) -> Any:
    import_target = f"{module_name}.{subpackage}.{item_name}"
    try:
        return importlib.import_module(import_target)
    except Exception as exc:  # pragma: no cover - exercised by caller tests
        raise RuntimeError(
            f"{subpackage}/{item_name}.py 无法导入: {exc.__class__.__name__}: {exc}"
        ) from exc


def _require_callable(module: Any, export_name: str, *, owner: str) -> Callable[..., Any]:
    candidate = getattr(module, export_name, None)
    if candidate is None or not callable(candidate):
        raise RuntimeError(f"{owner} 缺少可调用导出: {export_name}")
    return candidate


def _require_spec(module: Any, export_name: str, spec_type: type[Any], *, owner: str) -> Any:
    spec = getattr(module, export_name, None)
    if not isinstance(spec, spec_type):
        raise RuntimeError(f"{owner} 缺少 {export_name}，或类型不是 {spec_type.__name__}")
    return spec


def _discover_tasks(module_name: str, package_root: Path) -> dict[str, TaskRuntimeEntry]:
    tasks: dict[str, TaskRuntimeEntry] = {}
    for item_name in _iter_module_files(package_root / "tasks"):
        module = _import_submodule(module_name, "tasks", item_name)
        owner = f"tasks/{item_name}.py"
        spec = _require_spec(module, "TASK", TaskSpec, owner=owner)
        execute = _require_callable(module, "execute", owner=owner)
        if not str(spec.name or "").strip():
            raise RuntimeError(f"{owner} 的 TASK.name 不能为空")
        tasks[spec.name] = TaskRuntimeEntry(spec=spec, execute=execute)
    return tasks


def _discover_workflows(module_name: str, package_root: Path) -> dict[str, WorkflowRuntimeEntry]:
    workflows: dict[str, WorkflowRuntimeEntry] = {}
    for item_name in _iter_module_files(package_root / "workflows"):
        module = _import_submodule(module_name, "workflows", item_name)
        owner = f"workflows/{item_name}.py"
        spec = _require_spec(module, "WORKFLOW", WorkflowSpec, owner=owner)
        run = _require_callable(module, "run", owner=owner)
        if not str(spec.name or "").strip():
            raise RuntimeError(f"{owner} 的 WORKFLOW.name 不能为空")
        workflows[spec.name] = WorkflowRuntimeEntry(spec=spec, run=run)
    return workflows


def _discover_hooks(module_name: str, package_root: Path) -> dict[str, Callable[..., Any]]:
    hooks: dict[str, Callable[..., Any]] = {}
    for hook_name in _iter_module_files(package_root / "hooks"):
        module = _import_submodule(module_name, "hooks", hook_name)
        owner = f"hooks/{hook_name}.py"
        handle = _require_callable(module, "handle", owner=owner)
        hooks[hook_name] = handle
    return hooks


def _discover_env_selectors(module_name: str, package_root: Path) -> dict[str, EnvSelectorRuntimeEntry]:
    selectors: dict[str, EnvSelectorRuntimeEntry] = {}
    for item_name in _iter_module_files(package_root / "env_selectors"):
        module = _import_submodule(module_name, "env_selectors", item_name)
        owner = f"env_selectors/{item_name}.py"
        spec = _require_spec(module, "SELECTOR", EnvSelectorSpec, owner=owner)
        select = _require_callable(module, "select", owner=owner)
        if not str(spec.name or "").strip():
            raise RuntimeError(f"{owner} 的 SELECTOR.name 不能为空")
        selectors[spec.name] = EnvSelectorRuntimeEntry(spec=spec, select=select)
    return selectors


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


def _discover_pages(module_name: str, package_root: Path) -> dict[str, PageRuntimeEntry]:
    pages: dict[str, PageRuntimeEntry] = {}
    page_owners: dict[str, str] = {}
    for item_name, owner in _iter_page_modules(package_root / "pages"):
        module = _import_submodule(module_name, "pages", item_name)
        spec = _require_spec(module, "PAGE", PageSpec, owner=owner)
        page_id = str(spec.id or "").strip()
        if not page_id:
            raise RuntimeError(f"{owner} 的 PAGE.id 不能为空")
        previous_owner = page_owners.get(page_id)
        if previous_owner and previous_owner != owner:
            raise RuntimeError(f"宿主页 {page_id} 重复定义: {previous_owner}、{owner}")
        normalized_schema = normalize_page_schema(page_id, dict(spec.schema or {}))
        normalized_spec = PageSpec(
            id=page_id,
            label=str(spec.label or "").strip() or page_id,
            icon=str(spec.icon or "📋").strip() or "📋",
            schema=normalized_schema,
        )
        page_owners[page_id] = owner
        pages[page_id] = PageRuntimeEntry(
            spec=normalized_spec,
            module_name=module.__name__,
            handlers=_page_handlers(module),
        )
    return pages


def resolve_default_workflow(manifest: ModuleManifest, workflows: dict[str, WorkflowRuntimeEntry]) -> str:
    default_workflow = str(manifest.default_workflow or "").strip()
    if default_workflow:
        return default_workflow
    if manifest.workflows:
        first_declared = str(manifest.workflows[0].name or "").strip()
        if first_declared:
            return first_declared
    if workflows:
        return next(iter(workflows))
    return ""


def normalize_result_payload(result: object, context: TaskContext) -> TaskResult:
    if isinstance(result, TaskResult):
        return result
    if result is None:
        return TaskResult.ok(data=dict(context.state))
    if isinstance(result, dict):
        return TaskResult.ok(data=result)
    return TaskResult.ok(data={"value": result})


async def invoke_runtime_callable(func: Callable[..., Any], *args: Any) -> Any:
    result = func(*args)
    if inspect.isawaitable(result):
        return await result
    return result


def load_runtime_descriptor(
    module_name: str,
    package_root: Path,
    manifest: ModuleManifest,
    *,
    force_reload: bool = False,
) -> ModuleRuntimeDescriptor:
    load_root_module_from_path(module_name, package_root, force_reload=force_reload)

    tasks = _discover_tasks(module_name, package_root)
    workflows = _discover_workflows(module_name, package_root)
    hooks = _discover_hooks(module_name, package_root)
    env_selectors = _discover_env_selectors(module_name, package_root)
    pages = _discover_pages(module_name, package_root)

    return ModuleRuntimeDescriptor(
        tasks=tasks,
        workflows=workflows,
        hooks=hooks,
        env_selectors=env_selectors,
        pages=pages,
        default_workflow=resolve_default_workflow(manifest, workflows),
    )
