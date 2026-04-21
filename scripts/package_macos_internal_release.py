#!/usr/bin/env python3
"""Create an internal macOS DMG release with Sparkle metadata."""

import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scripts import package_desktop_app


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
PACKAGE_PYPROJECT = APP_ROOT / "pyproject.toml"
DEFAULT_UPDATES_DIR = APP_ROOT / "dist" / "updates" / "macos"
DEFAULT_SPARKLE_ROOT = APP_ROOT / "vendor" / "macos" / "sparkle"

SPARKLE_ROOT_ENV = "CRAWLER4J_SPARKLE_ROOT"
SPARKLE_FEED_URL_ENV = "CRAWLER4J_SPARKLE_FEED_URL"
SPARKLE_PUBLIC_KEY_ENV = "CRAWLER4J_SPARKLE_PUBLIC_ED_KEY"
SPARKLE_APPCAST_TOOL_ENV = "CRAWLER4J_SPARKLE_GENERATE_APPCAST_PATH"

SPARKLE_FRAMEWORK_NAME = "Sparkle.framework"
SPARKLE_FEED_URL_KEY = "SUFeedURL"
SPARKLE_PUBLIC_KEY_KEY = "SUPublicEDKey"
SPARKLE_ENABLE_AUTOMATIC_CHECKS_KEY = "SUEnableAutomaticChecks"


@dataclass(slots=True)
class SparkleReleaseConfig:
    """Build-time Sparkle configuration."""

    sparkle_root: Path
    feed_url: str
    public_key: str
    auto_check: bool = True
    generate_appcast_tool: Path | None = None

    @property
    def framework_path(self) -> Path:
        return self.sparkle_root / SPARKLE_FRAMEWORK_NAME


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an internal macOS Sparkle DMG release.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing packaged .app.")
    parser.add_argument("--skip-appcast", action="store_true", help="Skip running Sparkle generate_appcast.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_UPDATES_DIR,
        help=f"Directory for DMG/appcast outputs (default: {DEFAULT_UPDATES_DIR}).",
    )
    parser.add_argument(
        "--volume-name",
        default=package_desktop_app.APP_NAME,
        help="Mounted DMG volume name.",
    )
    return parser.parse_args(argv)


def load_project_version() -> str:
    import tomllib

    with PACKAGE_PYPROJECT.open("rb") as f:
        pyproject = tomllib.load(f)
    return str(pyproject["project"]["version"])


def resolve_sparkle_root(env: dict[str, str] | None = None) -> Path:
    env_map = env or os.environ
    override = str(env_map.get(SPARKLE_ROOT_ENV, "")).strip()
    root = Path(override).expanduser() if override else DEFAULT_SPARKLE_ROOT
    root = root.resolve()
    if not root.exists():
        raise ValueError(
            f"未找到 Sparkle 分发目录: {root}。请设置 {SPARKLE_ROOT_ENV} 或把 Sparkle 解压到 {DEFAULT_SPARKLE_ROOT}"
        )
    return root


def resolve_generate_appcast_tool(sparkle_root: Path, env: dict[str, str] | None = None) -> Path | None:
    env_map = env or os.environ
    override = str(env_map.get(SPARKLE_APPCAST_TOOL_ENV, "")).strip()
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.exists() else None

    candidate = sparkle_root / "bin" / "generate_appcast"
    return candidate if candidate.exists() else None


def load_sparkle_release_config(env: dict[str, str] | None = None) -> SparkleReleaseConfig:
    env_map = env or os.environ
    sparkle_root = resolve_sparkle_root(env_map)
    feed_url = str(env_map.get(SPARKLE_FEED_URL_ENV, "")).strip()
    public_key = str(env_map.get(SPARKLE_PUBLIC_KEY_ENV, "")).strip()
    if not feed_url:
        raise ValueError(f"缺少 {SPARKLE_FEED_URL_ENV}。")
    if not public_key:
        raise ValueError(f"缺少 {SPARKLE_PUBLIC_KEY_ENV}。")

    config = SparkleReleaseConfig(
        sparkle_root=sparkle_root,
        feed_url=feed_url,
        public_key=public_key,
        auto_check=True,
        generate_appcast_tool=resolve_generate_appcast_tool(sparkle_root, env_map),
    )
    if not config.framework_path.exists():
        raise ValueError(f"未找到 Sparkle.framework: {config.framework_path}")
    return config


def app_bundle_path() -> Path:
    return package_desktop_app.dist_dir("darwin") / package_desktop_app.MACOS_APP_NAME


def info_plist_path(app_bundle: Path) -> Path:
    return app_bundle / "Contents" / "Info.plist"


def build_base_app_bundle() -> Path:
    slug = "darwin"
    target_dist_dir, target_build_dir = package_desktop_app.clean_output_dirs(slug)
    command = package_desktop_app.build_command(slug)

    print("[desktop-package] platform=macos")
    print(f"[dist]  {target_dist_dir}")
    print(f"[build] {target_build_dir}")
    print(f"[cmd]   {' '.join(command)}")
    subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)
    removed = package_desktop_app.prune_macos_collect_dir(slug)
    if removed is not None:
        print(f"[prune] removed non-distribution collect dir {removed}")
    bundle = app_bundle_path()
    if not bundle.exists():
        raise FileNotFoundError(f"未找到打包后的 app bundle: {bundle}")
    return bundle


def copy_sparkle_framework(app_bundle: Path, framework_source: Path) -> Path:
    frameworks_dir = app_bundle / "Contents" / "Frameworks"
    frameworks_dir.mkdir(parents=True, exist_ok=True)
    target = frameworks_dir / SPARKLE_FRAMEWORK_NAME
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(framework_source, target, symlinks=True)
    return target


def update_bundle_plist(app_bundle: Path, *, version: str, config: SparkleReleaseConfig) -> Path:
    plist_path = info_plist_path(app_bundle)
    with plist_path.open("rb") as f:
        data = plistlib.load(f)

    data["CFBundleVersion"] = version
    data["CFBundleShortVersionString"] = version
    data[SPARKLE_FEED_URL_KEY] = config.feed_url
    data[SPARKLE_PUBLIC_KEY_KEY] = config.public_key
    data[SPARKLE_ENABLE_AUTOMATIC_CHECKS_KEY] = bool(config.auto_check)

    with plist_path.open("wb") as f:
        plistlib.dump(data, f)

    return plist_path


def dmg_name(version: str) -> str:
    return f"{package_desktop_app.APP_NAME}-{version}.dmg"


def create_dmg(app_bundle: Path, output_dir: Path, *, version: str, volume_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    dmg_path = output_dir / dmg_name(version)

    with tempfile.TemporaryDirectory(prefix="crawler4j-dmg-") as tmpdir:
        staging_root = Path(tmpdir) / volume_name
        staging_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app_bundle, staging_root / app_bundle.name, symlinks=True)
        (staging_root / "Applications").symlink_to("/Applications")

        command = [
            "hdiutil",
            "create",
            "-ov",
            "-volname",
            volume_name,
            "-srcfolder",
            str(staging_root),
            "-fs",
            "HFS+",
            "-format",
            "UDZO",
            str(dmg_path),
        ]
        subprocess.run(command, cwd=WORKSPACE_ROOT, check=True)

    return dmg_path


def generate_appcast_command(tool_path: Path, updates_dir: Path) -> list[str]:
    return [str(tool_path), str(updates_dir)]


def run_generate_appcast(tool_path: Path, updates_dir: Path) -> None:
    subprocess.run(generate_appcast_command(tool_path, updates_dir), cwd=WORKSPACE_ROOT, check=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_sparkle_release_config()
    version = load_project_version()

    if args.skip_build:
        bundle = app_bundle_path()
        if not bundle.exists():
            raise FileNotFoundError(f"未找到现有 app bundle: {bundle}")
    else:
        bundle = build_base_app_bundle()

    copied_framework = copy_sparkle_framework(bundle, config.framework_path)
    update_bundle_plist(bundle, version=version, config=config)

    print(f"[sparkle] framework copied to {copied_framework}")
    print(f"[sparkle] feed={config.feed_url}")

    dmg_path = create_dmg(bundle, args.output_dir, version=version, volume_name=args.volume_name)
    print(f"[dmg] {dmg_path}")

    if not args.skip_appcast:
        if config.generate_appcast_tool is None:
            raise FileNotFoundError(
                f"未找到 generate_appcast，请设置 {SPARKLE_APPCAST_TOOL_ENV} 或提供 Sparkle bin/ 目录。"
            )
        run_generate_appcast(config.generate_appcast_tool, args.output_dir)
        print(f"[appcast] generated under {args.output_dir}")

    print(f"[done] internal macOS Sparkle release artifacts are under {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
