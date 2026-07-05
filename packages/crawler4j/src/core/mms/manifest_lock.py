"""Manifest lock verification for installable core-native-v2 modules."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.mms.models import ModuleInstallError, ModuleManifest

CORE_NATIVE_V2_RUNTIME_API = "core-native-v2"
MANIFEST_LOCK_KEYS = frozenset({"schema_version", "runtime_api", "module", "version", "declarations"})
IGNORED_MODULE_DIRS = frozenset(
    {
        ".git",
        ".idea",
        ".venv",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
    }
)


def _is_ignored_module_path(relative: Path, ignored_dirs: frozenset[str] = IGNORED_MODULE_DIRS) -> bool:
    return any(part in ignored_dirs or part.endswith(".egg-info") for part in relative.parts)


def _ensure_safe_module_tree(module_root: Path) -> None:
    root = module_root.resolve()
    for path in module_root.rglob("*"):
        relative = path.relative_to(module_root)
        relative_posix = relative.as_posix()
        if _is_ignored_module_path(relative):
            continue
        if path.is_symlink():
            raise ModuleInstallError(f"模块文件不能是符号链接: {relative_posix}")
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ModuleInstallError(f"模块文件路径越界: {relative_posix}") from exc


def verify_manifest_lock(module_root: Path, manifest: ModuleManifest) -> None:
    if str(manifest.runtime_api or "").strip() != CORE_NATIVE_V2_RUNTIME_API:
        return

    lock_path = module_root / ".crawler4j" / "manifest.lock.json"
    if not lock_path.exists():
        raise ModuleInstallError("缺少 manifest lock: .crawler4j/manifest.lock.json")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModuleInstallError(f"manifest lock 不是合法 JSON: {exc}") from exc
    if not isinstance(lock, dict):
        raise ModuleInstallError("manifest lock 顶层必须是 JSON 对象")

    if set(lock) - MANIFEST_LOCK_KEYS:
        raise ModuleInstallError("manifest lock 包含已废弃字段，请重新生成")
    if lock.get("schema_version") != 1:
        raise ModuleInstallError("manifest lock schema_version 不匹配")
    if lock.get("runtime_api") != CORE_NATIVE_V2_RUNTIME_API:
        raise ModuleInstallError("manifest lock runtime_api 不匹配")
    if str(lock.get("module") or "").strip() != manifest.name:
        raise ModuleInstallError("manifest lock module 不匹配")
    if str(lock.get("version") or "").strip() != str(manifest.version or "").strip():
        raise ModuleInstallError("manifest lock version 不匹配")

    declarations = lock.get("declarations")
    if not isinstance(declarations, list) or not any(
        isinstance(item, dict) and item.get("kind") == "workflow" for item in declarations
    ):
        raise ModuleInstallError("manifest lock 缺少 @workflow 声明")
    _ensure_safe_module_tree(module_root)
