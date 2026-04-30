"""Safe ZIP validation and extraction helpers for module packages."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

from src.core.mms.models import ModuleInstallError

MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


def _validate_zip_member(info: zipfile.ZipInfo, *, seen: set[str]) -> str:
    name = info.filename
    if not name or name.startswith("__MACOSX/"):
        return ""
    if "\\" in name:
        raise ModuleInstallError(f"ZIP 包含非法反斜杠路径: {name}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ModuleInstallError(f"ZIP 包含非法路径: {name}")
    normalized = pure.as_posix()
    if normalized in seen:
        raise ModuleInstallError(f"ZIP 包含重复路径: {normalized}")
    seen.add(normalized)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise ModuleInstallError(f"ZIP 包含不允许的符号链接: {normalized}")
    return normalized


def safe_extract_zip(zf: zipfile.ZipFile, target_dir: Path) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ModuleInstallError(f"ZIP 条目过多: {len(infos)} > {MAX_ZIP_ENTRIES}")

    seen: set[str] = set()
    total_size = 0
    root = target_dir.resolve()
    for info in infos:
        normalized = _validate_zip_member(info, seen=seen)
        if not normalized:
            continue
        total_size += int(info.file_size)
        if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ModuleInstallError("ZIP 解压后体积超过限制")
        destination = (root / normalized).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise ModuleInstallError(f"ZIP 解压路径越界: {normalized}") from exc
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)
