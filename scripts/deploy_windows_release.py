#!/usr/bin/env python3
"""Build and upload Windows Velopack release artifacts."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from scripts import package_windows_release
from scripts.release_upload import ensure_trailing_slash, resolve_platform_upload_target


UPLOAD_TARGET_ENV = "CRAWLER4J_UPDATE_UPLOAD_TARGET"
UPLOAD_PLATFORM_DIR = "win"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Velopack artifacts and upload them to the Windows release directory."
    )
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing PyInstaller onedir output.")
    parser.add_argument(
        "--env-file",
        type=Path,
        help=(
            "Load release environment variables from a dotenv file "
            f"(default: {package_windows_release.DEFAULT_ENV_FILE} if present)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=package_windows_release.DEFAULT_UPDATES_DIR,
        help=f"Directory for Velopack output artifacts (default: {package_windows_release.DEFAULT_UPDATES_DIR}).",
    )
    parser.add_argument("--pack-id", help="Override Velopack pack id.")
    parser.add_argument("--channel", help="Override Velopack channel.")
    parser.add_argument("--runtime", help="Override Velopack runtime RID.")
    parser.add_argument("--main-exe", help="Override the packaged entry executable name.")
    parser.add_argument(
        "--upload-target",
        help=f"Rsync/scp-style target base directory, or set via {UPLOAD_TARGET_ENV}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rsync plan without uploading files.",
    )
    return parser.parse_args(argv)


def resolve_upload_target(args: argparse.Namespace, env: dict[str, str] | None = None) -> str:
    env_map = package_windows_release.resolve_runtime_env(env, env_file=args.env_file)
    base_target = (args.upload_target or env_map.get(UPLOAD_TARGET_ENV, "")).strip()
    if not base_target:
        raise ValueError(f"缺少上传目标目录，请传 --upload-target 或设置 {UPLOAD_TARGET_ENV}。")
    return resolve_platform_upload_target(base_target, UPLOAD_PLATFORM_DIR)


def build_rsync_command(source_dir: Path, upload_target: str, *, dry_run: bool) -> list[str]:
    command = ["rsync", "-av"]
    if dry_run:
        command.append("--dry-run")
    command.extend([ensure_trailing_slash(str(source_dir.resolve())), ensure_trailing_slash(upload_target)])
    return command


def upload_release_artifacts(source_dir: Path, upload_target: str, *, dry_run: bool) -> None:
    command = build_rsync_command(source_dir, upload_target, dry_run=dry_run)
    subprocess.run(command, cwd=package_windows_release.WORKSPACE_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    upload_target = resolve_upload_target(args)

    artifacts = package_windows_release.build_release_artifacts(args)
    upload_release_artifacts(artifacts.output_dir, upload_target, dry_run=args.dry_run)

    action = "planned" if args.dry_run else "uploaded"
    print(f"[upload] {action} {artifacts.output_dir} -> {ensure_trailing_slash(upload_target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
