#!/usr/bin/env python3
"""Build and upload internal macOS Sparkle release artifacts."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from scripts import package_macos_internal_release


UPLOAD_TARGET_ENV = "CRAWLER4J_UPDATE_UPLOAD_TARGET"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DMG/appcast and upload them to a server directory.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing packaged .app.")
    parser.add_argument("--skip-appcast", action="store_true", help="Skip running Sparkle generate_appcast.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_macos_internal_release.DEFAULT_UPDATES_DIR,
        help=f"Directory for DMG/appcast outputs (default: {package_macos_internal_release.DEFAULT_UPDATES_DIR}).",
    )
    parser.add_argument(
        "--volume-name",
        default=package_macos_internal_release.package_desktop_app.APP_NAME,
        help="Mounted DMG volume name.",
    )
    parser.add_argument(
        "--upload-target",
        help=f"Rsync/scp-style target directory, or set via {UPLOAD_TARGET_ENV}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rsync plan without uploading files.",
    )
    return parser.parse_args(argv)


def resolve_upload_target(args: argparse.Namespace, env: dict[str, str] | None = None) -> str:
    env_map = env or os.environ
    target = (args.upload_target or env_map.get(UPLOAD_TARGET_ENV, "")).strip()
    if not target:
        raise ValueError(f"缺少上传目标目录，请传 --upload-target 或设置 {UPLOAD_TARGET_ENV}。")
    return target


def ensure_trailing_slash(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"


def build_rsync_command(source_dir: Path, upload_target: str, *, dry_run: bool) -> list[str]:
    command = ["rsync", "-av"]
    if dry_run:
        command.append("--dry-run")
    command.extend([ensure_trailing_slash(str(source_dir.resolve())), ensure_trailing_slash(upload_target)])
    return command


def upload_release_artifacts(source_dir: Path, upload_target: str, *, dry_run: bool) -> None:
    command = build_rsync_command(source_dir, upload_target, dry_run=dry_run)
    subprocess.run(command, cwd=package_macos_internal_release.WORKSPACE_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    upload_target = resolve_upload_target(args)

    artifacts = package_macos_internal_release.build_release_artifacts(args)
    upload_release_artifacts(artifacts.output_dir, upload_target, dry_run=args.dry_run)

    action = "planned" if args.dry_run else "uploaded"
    print(f"[upload] {action} {artifacts.output_dir} -> {ensure_trailing_slash(upload_target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
