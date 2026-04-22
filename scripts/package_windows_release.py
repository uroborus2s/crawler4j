#!/usr/bin/env python3
"""Create a Windows Velopack release from the packaged onedir app."""

import argparse
import importlib.metadata
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
import subprocess

from scripts import package_desktop_app
from scripts import release_packaging_helpers


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
WINDOWS_PACKAGE_ICON = APP_ROOT / "src" / "ui" / "assets" / "app_icon.ico"
DEFAULT_ENV_FILE = release_packaging_helpers.DEFAULT_ENV_FILE
DEFAULT_UPDATES_DIR = APP_ROOT / "dist" / "updates" / "windows"
UPDATE_CONFIG_FILENAME = "crawler4j.update.json"

VELOPACK_FEED_URL_ENV = "CRAWLER4J_VELOPACK_FEED_URL"
VELOPACK_PACK_ID_ENV = "CRAWLER4J_VELOPACK_PACK_ID"
VELOPACK_CHANNEL_ENV = "CRAWLER4J_VELOPACK_CHANNEL"
VELOPACK_RUNTIME_ENV = "CRAWLER4J_VELOPACK_RUNTIME"
VPK_BIN_ENV = "CRAWLER4J_VPK_BIN"
VPK_USE_DNX_ENV = "CRAWLER4J_VPK_USE_DNX"

DEFAULT_PACK_ID = "io.github.uroborus2s.crawler4j"
DEFAULT_CHANNEL = "win"
DEFAULT_RUNTIME = "win-x64"
DEFAULT_VPK_BIN = "vpk"
BATCH_SCRIPT_SUFFIXES = {".bat", ".cmd"}


@dataclass(slots=True)
class WindowsReleaseConfig:
    feed_url: str
    pack_id: str
    channel: str
    runtime: str
    main_exe: str = f"{package_desktop_app.APP_NAME}.exe"
    vpk_bin: str = DEFAULT_VPK_BIN
    use_dnx: bool = False


@dataclass(slots=True)
class WindowsReleaseArtifacts:
    version: str
    bundle_dir: Path
    output_dir: Path
    update_config_path: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Windows Velopack release from the packaged onedir app.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing PyInstaller onedir output.")
    parser.add_argument(
        "--env-file",
        type=Path,
        help=f"Load release environment variables from a dotenv file (default: {DEFAULT_ENV_FILE} if present).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_UPDATES_DIR,
        help=f"Directory for Velopack output artifacts (default: {DEFAULT_UPDATES_DIR}).",
    )
    parser.add_argument("--pack-id", help="Override Velopack pack id.")
    parser.add_argument("--channel", help="Override Velopack channel.")
    parser.add_argument("--runtime", help="Override Velopack runtime RID.")
    parser.add_argument("--main-exe", help="Override the packaged entry executable name.")
    return parser.parse_args(argv)


def resolve_runtime_env(env: dict[str, str] | None = None, *, env_file: Path | None = None) -> dict[str, str]:
    return release_packaging_helpers.resolve_runtime_env(
        env,
        env_file=env_file,
        default_env_file=DEFAULT_ENV_FILE,
    )


def load_windows_release_config(
    env: dict[str, str] | None = None,
    *,
    env_file: Path | None = None,
    pack_id: str | None = None,
    channel: str | None = None,
    runtime: str | None = None,
    main_exe: str | None = None,
) -> WindowsReleaseConfig:
    env_map = resolve_runtime_env(env, env_file=env_file)
    feed_url = str(env_map.get(VELOPACK_FEED_URL_ENV, "")).strip()
    if not feed_url:
        raise ValueError(f"缺少 {VELOPACK_FEED_URL_ENV}。")

    return WindowsReleaseConfig(
        feed_url=feed_url,
        pack_id=(pack_id or str(env_map.get(VELOPACK_PACK_ID_ENV, "")).strip() or DEFAULT_PACK_ID),
        channel=(channel or str(env_map.get(VELOPACK_CHANNEL_ENV, "")).strip() or DEFAULT_CHANNEL),
        runtime=(runtime or str(env_map.get(VELOPACK_RUNTIME_ENV, "")).strip() or DEFAULT_RUNTIME),
        main_exe=(main_exe or f"{package_desktop_app.APP_NAME}.exe"),
        vpk_bin=str(env_map.get(VPK_BIN_ENV, DEFAULT_VPK_BIN)).strip() or DEFAULT_VPK_BIN,
        use_dnx=str(env_map.get(VPK_USE_DNX_ENV, "")).strip().lower() in {"1", "true", "yes", "on"},
    )


def windows_bundle_dir() -> Path:
    return package_desktop_app.dist_dir("win32") / package_desktop_app.APP_NAME


def windows_update_config_path(bundle_dir: Path) -> Path:
    return bundle_dir / UPDATE_CONFIG_FILENAME


def write_windows_update_config(bundle_dir: Path, config: WindowsReleaseConfig) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    config_path = windows_update_config_path(bundle_dir)
    config_path.write_text(
        json.dumps(
            {
                "feed_url": config.feed_url,
                "pack_id": config.pack_id,
                "channel": config.channel,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return config_path


def resolve_velopack_version() -> str | None:
    try:
        return importlib.metadata.version("velopack")
    except importlib.metadata.PackageNotFoundError:
        return None


def normalize_dnx_package_version(version: str) -> str:
    normalized = version.strip()
    if "+" in normalized:
        normalized = normalized.split("+", 1)[0]
    if ".dev" in normalized:
        normalized = normalized.split(".dev", 1)[0]
    return normalized


def _resolve_process_prefix(command: str, *extra_args: str) -> list[str]:
    resolved = shutil.which(command) or command
    if Path(resolved).suffix.lower() in BATCH_SCRIPT_SUFFIXES:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/c", resolved, *extra_args]
    return [resolved, *extra_args]


def _resolve_vpk_prefix(config: WindowsReleaseConfig, *, velopack_version: str | None = None) -> list[str]:
    if not config.use_dnx:
        return _resolve_process_prefix(config.vpk_bin)
    if not velopack_version:
        raise ValueError("使用 dnx 调用 vpk 时必须能解析当前 velopack Python 包版本。")
    dnx_version = normalize_dnx_package_version(velopack_version)
    if dnx_version != velopack_version:
        print(
            "[vpk]    normalized Python velopack version "
            f"{velopack_version} -> {dnx_version} for dnx/NuGet compatibility"
        )
    return _resolve_process_prefix("dnx", "vpk", "--version", dnx_version)


def build_vpk_pack_command(
    bundle_dir: Path,
    output_dir: Path,
    *,
    version: str,
    config: WindowsReleaseConfig,
    velopack_version: str | None = None,
) -> list[str]:
    return [
        *_resolve_vpk_prefix(config, velopack_version=velopack_version),
        "pack",
        "--packId",
        config.pack_id,
        "--packVersion",
        version,
        "--packDir",
        str(bundle_dir),
        "--outputDir",
        str(output_dir),
        "--channel",
        config.channel,
        "--runtime",
        config.runtime,
        "--mainExe",
        config.main_exe,
        "--packTitle",
        package_desktop_app.APP_NAME,
        "--icon",
        str(WINDOWS_PACKAGE_ICON.resolve()),
    ]


def _build_base_bundle() -> Path:
    slug = "win32"
    target_dist_dir, target_build_dir = package_desktop_app.clean_output_dirs(slug)
    command = package_desktop_app.build_command(slug)

    print("[desktop-package] platform=windows")
    print(f"[dist]  {target_dist_dir}")
    print(f"[build] {target_build_dir}")
    print(f"[cmd]   {' '.join(command)}")

    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)
    bundle_dir = windows_bundle_dir()
    if not bundle_dir.exists():
        raise FileNotFoundError(f"未找到 PyInstaller onedir 宿主目录: {bundle_dir}")
    return bundle_dir


def build_release_artifacts(args: argparse.Namespace, env: dict[str, str] | None = None) -> WindowsReleaseArtifacts:
    version = release_packaging_helpers.load_project_version()
    config = load_windows_release_config(
        env,
        env_file=args.env_file,
        pack_id=args.pack_id,
        channel=args.channel,
        runtime=args.runtime,
        main_exe=args.main_exe,
    )

    bundle_dir = windows_bundle_dir() if args.skip_build else _build_base_bundle()
    if not bundle_dir.exists():
        raise FileNotFoundError(f"未找到 Windows 宿主目录: {bundle_dir}")

    output_dir = release_packaging_helpers.reset_output_dir(args.output_dir)

    update_config_path = write_windows_update_config(bundle_dir, config)
    velopack_version = resolve_velopack_version() if config.use_dnx else None
    vpk_command = build_vpk_pack_command(
        bundle_dir,
        output_dir,
        version=version,
        config=config,
        velopack_version=velopack_version,
    )
    print(f"[config] {update_config_path}")
    print(f"[vpk]    {' '.join(vpk_command)}")
    subprocess.run(vpk_command, cwd=WORKSPACE_ROOT, check=True)

    return WindowsReleaseArtifacts(
        version=version,
        bundle_dir=bundle_dir,
        output_dir=output_dir,
        update_config_path=update_config_path,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = build_release_artifacts(args)
    print(f"[done] Windows Velopack artifacts are under {artifacts.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
