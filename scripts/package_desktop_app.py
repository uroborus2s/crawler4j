#!/usr/bin/env python3
"""Build the desktop app with fixed PyInstaller output directories."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
SPEC_PATH = APP_ROOT / "crawler4j.spec"
DESKTOP_DIST_ROOT = APP_ROOT / "dist" / "desktop"
PYINSTALLER_BUILD_ROOT = APP_ROOT / "build" / "pyinstaller"


def platform_slug(platform: str | None = None) -> str:
    value = platform or sys.platform
    if value == "darwin":
        return "macos"
    if value.startswith("win"):
        return "windows"
    if value.startswith("linux"):
        return "linux"
    return value.replace("/", "-").replace("\\", "-").lower()


def dist_dir(platform: str | None = None) -> Path:
    return DESKTOP_DIST_ROOT / platform_slug(platform)


def build_dir(platform: str | None = None) -> Path:
    return PYINSTALLER_BUILD_ROOT / platform_slug(platform)


def clean_output_dirs(platform: str | None = None) -> tuple[Path, Path]:
    target_dist_dir = dist_dir(platform)
    target_build_dir = build_dir(platform)
    shutil.rmtree(target_dist_dir, ignore_errors=True)
    shutil.rmtree(target_build_dir, ignore_errors=True)
    target_dist_dir.mkdir(parents=True, exist_ok=True)
    target_build_dir.mkdir(parents=True, exist_ok=True)
    return target_dist_dir, target_build_dir


def build_command(platform: str | None = None) -> list[str]:
    target_dist_dir = dist_dir(platform)
    target_build_dir = build_dir(platform)
    return [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(target_dist_dir),
        "--workpath",
        str(target_build_dir),
        str(SPEC_PATH),
    ]


def main() -> int:
    slug = platform_slug()
    target_dist_dir, target_build_dir = clean_output_dirs(slug)
    command = build_command(slug)

    print(f"[desktop-package] platform={slug}")
    print(f"[dist]  {target_dist_dir}")
    print(f"[build] {target_build_dir}")
    print(f"[cmd]   {' '.join(command)}")

    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)
    print(f"[done] desktop package available under {target_dist_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
