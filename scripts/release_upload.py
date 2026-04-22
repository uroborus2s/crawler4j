"""Shared helpers for release artifact uploads."""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath


WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def resolve_platform_upload_target(base_target: str, platform_dir: str) -> str:
    target = base_target.strip()
    if not target:
        raise ValueError("上传目标不能为空。")
    subdir = platform_dir.strip("/\\")
    if not subdir:
        return target

    if _looks_like_windows_path(target):
        return _append_windows_path(target, subdir)

    remote = _split_rsync_remote_target(target)
    if remote is not None:
        host, path = remote
        return f"{host}:{_append_posix_path(path, subdir)}"

    return _append_local_path(target, subdir)


def _looks_like_windows_path(target: str) -> bool:
    return target.startswith("\\\\") or bool(WINDOWS_DRIVE_RE.match(target))


def _append_windows_path(target: str, subdir: str) -> str:
    path = PureWindowsPath(target)
    if path.name.lower() == subdir.lower():
        return str(path)
    return str(path / subdir)


def _split_rsync_remote_target(target: str) -> tuple[str, str] | None:
    if target.startswith("rsync://") or WINDOWS_DRIVE_RE.match(target):
        return None
    if ":" not in target:
        return None
    host, path = target.split(":", 1)
    if not host:
        return None
    return host, path or "/"


def _append_posix_path(path: str, subdir: str) -> str:
    normalized = path.rstrip("/")
    if normalized == subdir or normalized.endswith(f"/{subdir}"):
        return normalized
    if not normalized:
        return f"/{subdir}"
    if normalized == "/":
        return f"/{subdir}"
    return f"{normalized}/{subdir}"


def _append_local_path(target: str, subdir: str) -> str:
    path = Path(target)
    if path.name == subdir:
        return str(path)
    return str(path / subdir)
