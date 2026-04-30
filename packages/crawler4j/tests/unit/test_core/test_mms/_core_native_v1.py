from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

from src.core.mms.models import (
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    UIPageInfo,
)
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import get_module_service


def make_page_info(page_id: str, *, label: str | None = None, icon: str = "📄") -> UIPageInfo:
    return UIPageInfo(
        id=page_id,
        label=label or page_id.replace("_", " ").title(),
        icon=icon,
    )


def make_manifest(
    module_name: str,
    *,
    workflows: tuple[str, ...] = ("main_workflow",),  # noqa: ARG001
    default_workflow: str | None = None,  # noqa: ARG001
    pages: list[UIPageInfo] | None = None,  # noqa: ARG001
    display_name: str | None = None,
    description: str = "",
) -> ModuleManifest:
    return ModuleManifest(
        name=module_name,
        runtime_api="core-native-v2",
        display_name=display_name or module_name.replace("_", " ").title(),
        description=description,
    )


def write_module_tree(base_dir: Path, module_name: str, *, files: dict[str, str]) -> Path:
    module_dir = base_dir / module_name
    for package_dir in (
        module_dir,
        module_dir / "interfaces",
        module_dir / "objects",
        module_dir / "tasks",
        module_dir / "workflows",
        module_dir / "data",
        module_dir / "pages",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        init_file = package_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    for relative_path, content in files.items():
        file_path = module_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = dedent(content).strip() + "\n"
        file_path.write_text(rendered, encoding="utf-8")
    return module_dir


def register_module(
    module_name: str,
    module_dir: Path,
    *,
    manifest: ModuleManifest | None = None,
    source: ModuleSource = ModuleSource.DEV_LINK,
) -> tuple[object, object, ModuleInfo]:
    module_info = ModuleInfo(
        name=module_name,
        manifest=manifest or make_manifest(module_name),
        path=module_dir,
        source=source,
    )
    service = get_module_service()
    service._descriptor_cache_v2.pop(module_name, None)
    original_registry = service.registry
    service.registry = SimpleNamespace(
        get_module=lambda name: module_info
        if name in {module_name, module_name.split(".")[0]}
        else None
    )
    return service, original_registry, module_info


def restore_module(service: object, original_registry: object, module_name: str) -> None:
    service._descriptor_cache_v2.pop(module_name, None)
    service.registry = original_registry
    purge_module_namespace(module_name)
