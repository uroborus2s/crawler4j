"""Manifest lock verification for installable core-native-v2 modules."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.core.mms.models import ModuleInstallError, ModuleManifest

CORE_NATIVE_V2_RUNTIME_API = "core-native-v2"


def _iter_manifest_lock_files(module_root: Path) -> list[Path]:
    ignored_dirs = {
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
    ignored_files = {".DS_Store", ".crawler4j/manifest.lock.json"}
    root = module_root.resolve()
    files: list[Path] = []
    for path in module_root.rglob("*"):
        relative = path.relative_to(module_root)
        relative_posix = relative.as_posix()
        if any(part in ignored_dirs or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_symlink():
            raise ModuleInstallError(f"模块文件不能是符号链接: {relative_posix}")
        if path.is_dir():
            continue
        if path.name in ignored_files or relative_posix in ignored_files:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise ModuleInstallError(f"模块文件路径越界: {relative_posix}") from exc
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(module_root).as_posix())


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_lock_entries(module_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(module_root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _hash_file(path),
        }
        for path in _iter_manifest_lock_files(module_root)
    ]


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

    actual_files = lock.get("files")
    if not isinstance(actual_files, list):
        raise ModuleInstallError("manifest lock 缺少 files 完整性列表")
    expected_files = _file_lock_entries(module_root)
    try:
        normalized_actual = sorted(
            (
                {
                    "path": str(item.get("path") or ""),
                    "size": int(item.get("size")),
                    "sha256": str(item.get("sha256") or ""),
                }
                for item in actual_files
                if isinstance(item, dict)
            ),
            key=lambda item: item["path"],
        )
    except (TypeError, ValueError) as exc:
        raise ModuleInstallError("manifest lock files 完整性列表格式无效") from exc
    if normalized_actual != expected_files:
        raise ModuleInstallError("manifest lock 已过期或文件完整性校验失败")
