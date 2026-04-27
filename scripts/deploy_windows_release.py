#!/usr/bin/env python3
"""Build and upload Windows Velopack release artifacts."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from scripts import package_windows_release
from scripts.release_upload import ensure_trailing_slash, resolve_platform_upload_target, split_remote_target


UPLOAD_TARGET_ENV = "CRAWLER4J_UPDATE_UPLOAD_TARGET"
UPLOAD_PLATFORM_DIR = "win"
SFTP_BIN = "sftp"


class SFTPTarget(NamedTuple):
    host: str
    remote_dir: str


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
        help=f"SFTP host:path-style target base directory, or set via {UPLOAD_TARGET_ENV}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the upload plan without uploading files.",
    )
    return parser.parse_args(argv)


def resolve_upload_target(args: argparse.Namespace, env: dict[str, str] | None = None) -> str:
    env_map = package_windows_release.resolve_runtime_env(env, env_file=args.env_file)
    base_target = (args.upload_target or env_map.get(UPLOAD_TARGET_ENV, "")).strip()
    if not base_target:
        raise ValueError(f"缺少上传目标目录，请传 --upload-target 或设置 {UPLOAD_TARGET_ENV}。")
    return resolve_platform_upload_target(base_target, UPLOAD_PLATFORM_DIR)


def parse_sftp_target(upload_target: str) -> SFTPTarget:
    remote = split_remote_target(upload_target)
    if remote is None:
        raise ValueError(f"Windows 自动上传要求远端 SFTP 目标，当前值无法解析为 host:path：{upload_target}")
    host, remote_dir = remote
    return SFTPTarget(host=host, remote_dir=ensure_trailing_slash(remote_dir).rstrip("/"))


def build_sftp_command(target: SFTPTarget, batch_file: Path) -> list[str]:
    return [SFTP_BIN, "-b", str(batch_file.resolve()), target.host]


def build_sftp_batch_commands(source_dir: Path, remote_dir: str) -> list[str]:
    commands = [f"-mkdir {directory}" for directory in _build_remote_directory_chain(remote_dir)]
    commands.append(f"cd {_format_sftp_token(remote_dir)}")
    for item in sorted(source_dir.iterdir(), key=lambda path: path.name):
        local_path = _format_sftp_token(str(item.resolve()))
        remote_name = _format_sftp_token(item.name)
        if item.is_dir():
            commands.append(f"put -R {local_path} {remote_name}")
        else:
            commands.append(f"put {local_path} {remote_name}")
    return commands


def _build_remote_directory_chain(remote_dir: str) -> list[str]:
    path = PurePosixPath(remote_dir)
    chain: list[str] = []
    current = PurePosixPath("/") if path.is_absolute() else PurePosixPath()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current = current / part if current.parts else PurePosixPath(part)
        chain.append(current.as_posix())
    return chain


def _format_sftp_token(value: str) -> str:
    escaped = value.replace('"', r"\"")
    if any(char.isspace() for char in value):
        return f'"{escaped}"'
    return escaped


def upload_release_artifacts(source_dir: Path, upload_target: str, *, dry_run: bool) -> None:
    remote = split_remote_target(upload_target)
    if remote is None:
        _copy_release_artifacts_locally(source_dir, Path(upload_target), dry_run=dry_run)
        return
    _upload_release_artifacts_via_sftp(source_dir, parse_sftp_target(upload_target), dry_run=dry_run)


def _upload_release_artifacts_via_sftp(source_dir: Path, target: SFTPTarget, *, dry_run: bool) -> None:
    commands = build_sftp_batch_commands(source_dir, target.remote_dir)
    if dry_run:
        for command in commands:
            print(f"[sftp] {command}")
        return
    with tempfile.TemporaryDirectory(prefix="crawler4j-sftp-") as temp_dir:
        batch_file = Path(temp_dir) / "upload.batch"
        batch_file.write_text("\n".join(commands) + "\n", encoding="utf-8")
        subprocess.run(build_sftp_command(target, batch_file), cwd=package_windows_release.WORKSPACE_ROOT, check=True)


def _copy_release_artifacts_locally(source_dir: Path, upload_target: Path, *, dry_run: bool) -> None:
    target_dir = upload_target.expanduser().resolve()
    if dry_run:
        print(f"[copy] {source_dir.resolve()} -> {target_dir}")
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_dir.iterdir(), key=lambda path: path.name):
        destination = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


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
