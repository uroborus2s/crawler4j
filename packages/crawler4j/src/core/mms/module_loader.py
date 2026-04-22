"""Shared helpers for loading module packages from disk."""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType


def purge_module_namespace(module_name: str) -> None:
    prefix = f"{module_name}."
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(prefix):
            sys.modules.pop(loaded_name, None)


def purge_module_bytecode_cache(package_root: Path) -> None:
    for cache_dir in package_root.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)


def load_root_module_from_path(
    module_name: str,
    module_path: Path,
    *,
    force_reload: bool = False,
) -> ModuleType:
    package_root = Path(module_path).resolve()
    package_init = package_root / "__init__.py"
    if not package_init.exists():
        raise FileNotFoundError(package_root)

    existing = sys.modules.get(module_name)
    existing_file = getattr(existing, "__file__", "") if existing else ""
    same_origin = bool(existing_file) and Path(existing_file).resolve() == package_init

    if force_reload or (existing and not same_origin):
        purge_module_namespace(module_name)
        purge_module_bytecode_cache(package_root)
    elif same_origin:
        return existing

    importlib.invalidate_caches()
    spec = importlib.util.spec_from_file_location(
        module_name,
        package_init,
        submodule_search_locations=[str(package_root)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从 `{package_root}` 构建模块加载规格")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
