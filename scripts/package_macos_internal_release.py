#!/usr/bin/env python3
"""Create an internal macOS DMG release with Sparkle metadata."""

import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from scripts import package_desktop_app


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
PACKAGE_PYPROJECT = APP_ROOT / "pyproject.toml"
DEFAULT_UPDATES_DIR = APP_ROOT / "dist" / "updates" / "macos"
DEFAULT_SPARKLE_ROOT = APP_ROOT / "vendor" / "macos" / "sparkle"
DEFAULT_ENV_FILE = WORKSPACE_ROOT / ".env"

SPARKLE_ROOT_ENV = "CRAWLER4J_SPARKLE_ROOT"
SPARKLE_FEED_URL_ENV = "CRAWLER4J_SPARKLE_FEED_URL"
SPARKLE_PUBLIC_KEY_ENV = "CRAWLER4J_SPARKLE_PUBLIC_ED_KEY"
SPARKLE_APPCAST_TOOL_ENV = "CRAWLER4J_SPARKLE_GENERATE_APPCAST_PATH"
SPARKLE_PRIVATE_KEY_ENV = "CRAWLER4J_SPARKLE_PRIVATE_ED_KEY"
SPARKLE_PRIVATE_KEY_FILE_ENV = "CRAWLER4J_SPARKLE_PRIVATE_ED_KEY_FILE"
SPARKLE_KEYCHAIN_ACCOUNT_ENV = "CRAWLER4J_SPARKLE_KEYCHAIN_ACCOUNT"
DEFAULT_SPARKLE_KEYCHAIN_ACCOUNT = "ed25519"

SPARKLE_FRAMEWORK_NAME = "Sparkle.framework"
SPARKLE_FEED_URL_KEY = "SUFeedURL"
SPARKLE_PUBLIC_KEY_KEY = "SUPublicEDKey"
SPARKLE_ENABLE_AUTOMATIC_CHECKS_KEY = "SUEnableAutomaticChecks"
SPARKLE_ENABLE_CODE_SIGNING_VALIDATION_KEY = "SUEnableCodeSigningValidation"
SPARKLE_PACKAGE_SIGNING_CERTIFICATE_KEY = "SUPackageSigningCertificate"

DMG_WINDOW_BOUNDS = (120, 120, 960, 620)
DMG_ICON_SIZE = 160
DMG_TEXT_SIZE = 16
DMG_APP_POSITION = (220, 250)
DMG_APPLICATIONS_POSITION = (560, 250)


@dataclass(slots=True)
class SparkleReleaseConfig:
    """Build-time Sparkle configuration."""

    sparkle_root: Path
    feed_url: str
    public_key: str
    keychain_account: str = DEFAULT_SPARKLE_KEYCHAIN_ACCOUNT
    private_key_file: Path | None = None
    private_key: str | None = field(default=None, repr=False)
    auto_check: bool = True
    generate_appcast_tool: Path | None = None

    @property
    def framework_path(self) -> Path:
        return self.sparkle_root / SPARKLE_FRAMEWORK_NAME


@dataclass(slots=True)
class SparkleReleaseArtifacts:
    """Artifacts produced by the internal Sparkle release packaging flow."""

    version: str
    app_bundle: Path
    output_dir: Path
    dmg_path: Path
    appcast_generated: bool


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an internal macOS Sparkle DMG release.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse the existing packaged .app.")
    parser.add_argument("--skip-appcast", action="store_true", help="Skip running Sparkle generate_appcast.")
    parser.add_argument(
        "--env-file",
        type=Path,
        help=f"Load release environment variables from a dotenv file (default: {DEFAULT_ENV_FILE} if present).",
    )
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


def load_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number} 缺少 '='。")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"{path}:{line_number} 缺少环境变量名。")
        if value and value[0] in {'"', "'"}:
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise ValueError(f"{path}:{line_number} 引号未闭合。")
            value = value[1:-1]
        values[key] = value
    return values


def resolve_runtime_env(env: dict[str, str] | None = None, *, env_file: Path | None = None) -> dict[str, str]:
    env_map: dict[str, str] = {}
    dotenv_path = env_file.expanduser().resolve() if env_file else DEFAULT_ENV_FILE
    if env_file is not None:
        if not dotenv_path.exists():
            raise FileNotFoundError(f"未找到 dotenv 文件: {dotenv_path}")
        env_map.update(load_dotenv_file(dotenv_path))
    elif dotenv_path.exists():
        env_map.update(load_dotenv_file(dotenv_path))
    env_map.update(os.environ)
    if env:
        env_map.update(env)
    return env_map


def resolve_sparkle_root(env: dict[str, str] | None = None, *, env_file: Path | None = None) -> Path:
    env_map = resolve_runtime_env(env, env_file=env_file)
    override = str(env_map.get(SPARKLE_ROOT_ENV, "")).strip()
    root = Path(override).expanduser() if override else DEFAULT_SPARKLE_ROOT
    root = root.resolve()
    if not root.exists():
        raise ValueError(
            f"未找到 Sparkle 分发目录: {root}。请设置 {SPARKLE_ROOT_ENV} 或把 Sparkle 解压到 {DEFAULT_SPARKLE_ROOT}"
        )
    return root


def resolve_generate_appcast_tool(
    sparkle_root: Path, env: dict[str, str] | None = None, *, env_file: Path | None = None
) -> Path | None:
    env_map = resolve_runtime_env(env, env_file=env_file)
    override = str(env_map.get(SPARKLE_APPCAST_TOOL_ENV, "")).strip()
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.exists() else None

    candidate = sparkle_root / "bin" / "generate_appcast"
    return candidate if candidate.exists() else None


def load_sparkle_release_config(
    env: dict[str, str] | None = None, *, env_file: Path | None = None
) -> SparkleReleaseConfig:
    env_map = resolve_runtime_env(env, env_file=env_file)
    sparkle_root = resolve_sparkle_root(env_map, env_file=env_file)
    feed_url = str(env_map.get(SPARKLE_FEED_URL_ENV, "")).strip()
    public_key = str(env_map.get(SPARKLE_PUBLIC_KEY_ENV, "")).strip()
    keychain_account = str(env_map.get(SPARKLE_KEYCHAIN_ACCOUNT_ENV, DEFAULT_SPARKLE_KEYCHAIN_ACCOUNT)).strip()
    private_key = str(env_map.get(SPARKLE_PRIVATE_KEY_ENV, "")).strip() or None
    private_key_file_value = str(env_map.get(SPARKLE_PRIVATE_KEY_FILE_ENV, "")).strip()
    private_key_file = Path(private_key_file_value).expanduser().resolve() if private_key_file_value else None
    if not feed_url:
        raise ValueError(f"缺少 {SPARKLE_FEED_URL_ENV}。")
    if not public_key:
        raise ValueError(f"缺少 {SPARKLE_PUBLIC_KEY_ENV}。")
    private_key_sources = [private_key is not None, private_key_file is not None]
    if sum(private_key_sources) > 1:
        raise ValueError(
            f"{SPARKLE_PRIVATE_KEY_ENV} 与 {SPARKLE_PRIVATE_KEY_FILE_ENV} 只能设置一种私钥来源。"
        )
    if private_key_file is not None and not private_key_file.exists():
        raise ValueError(f"未找到私钥文件: {private_key_file}")

    config = SparkleReleaseConfig(
        sparkle_root=sparkle_root,
        feed_url=feed_url,
        public_key=public_key,
        keychain_account=keychain_account or DEFAULT_SPARKLE_KEYCHAIN_ACCOUNT,
        private_key_file=private_key_file,
        private_key=private_key,
        auto_check=True,
        generate_appcast_tool=resolve_generate_appcast_tool(sparkle_root, env_map, env_file=env_file),
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
    data[SPARKLE_ENABLE_CODE_SIGNING_VALIDATION_KEY] = False
    data[SPARKLE_PACKAGE_SIGNING_CERTIFICATE_KEY] = ""

    with plist_path.open("wb") as f:
        plistlib.dump(data, f)

    return plist_path


def codesign_bundle_command(app_bundle: Path) -> list[str]:
    return [
        "codesign",
        "--force",
        "--sign",
        "-",
        "--deep",
        "--timestamp=none",
        str(app_bundle),
    ]


def ad_hoc_sign_bundle(app_bundle: Path) -> None:
    subprocess.run(codesign_bundle_command(app_bundle), cwd=WORKSPACE_ROOT, check=True)


def dmg_name(version: str) -> str:
    return f"{package_desktop_app.APP_NAME}-{version}.dmg"


def writable_dmg_name(version: str) -> str:
    return f"{package_desktop_app.APP_NAME}-{version}-staging.dmg"


def hybrid_dmg_name(version: str) -> str:
    return f"{package_desktop_app.APP_NAME}-{version}-hybrid.dmg"


def parse_hdiutil_attach_plist(output: bytes) -> tuple[str, Path]:
    data = plistlib.loads(output)
    entities = data.get("system-entities", [])
    for entity in entities:
        mount_point = entity.get("mount-point")
        if mount_point:
            return str(entity.get("dev-entry", "")), Path(str(mount_point))
    raise ValueError("无法从 hdiutil attach 输出中解析挂载点。")


def dmg_finder_applescript(volume_name: str, app_name: str) -> str:
    escaped_volume_name = volume_name.replace("\\", "\\\\").replace('"', '\\"')
    escaped_app_name = app_name.replace("\\", "\\\\").replace('"', '\\"')
    left, top, right, bottom = DMG_WINDOW_BOUNDS
    app_x, app_y = DMG_APP_POSITION
    applications_x, applications_y = DMG_APPLICATIONS_POSITION

    return textwrap.dedent(
        f"""
        tell application "Finder"
            tell disk "{escaped_volume_name}"
                open
                delay 1
                set current view of container window to icon view
                set toolbar visible of container window to false
                set statusbar visible of container window to false
                set the bounds of container window to {{{left}, {top}, {right}, {bottom}}}
                set theViewOptions to the icon view options of container window
                set arrangement of theViewOptions to not arranged
                set icon size of theViewOptions to {DMG_ICON_SIZE}
                set text size of theViewOptions to {DMG_TEXT_SIZE}
                set position of item "{escaped_app_name}" of container window to {{{app_x}, {app_y}}}
                set position of item "Applications" of container window to {{{applications_x}, {applications_y}}}
                update without registering applications
                delay 2
                close
                open
                delay 1
            end tell
        end tell
        """
    ).strip()


def apply_dmg_finder_layout(mounted_volume: Path, *, app_name: str) -> None:
    script = dmg_finder_applescript(mounted_volume.name, app_name)
    try:
        subprocess.run(["osascript", "-e", script], cwd=WORKSPACE_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("DMG Finder 布局设置失败，请在已登录 Finder 图形会话的 macOS 上执行。") from exc


def create_dmg(app_bundle: Path, output_dir: Path, *, version: str, volume_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    dmg_path = output_dir / dmg_name(version)

    with tempfile.TemporaryDirectory(prefix="crawler4j-dmg-") as tmpdir:
        staging_root = Path(tmpdir) / volume_name
        staging_dmg_path = Path(tmpdir) / writable_dmg_name(version)
        hybrid_source_dir = Path(tmpdir) / f"{package_desktop_app.APP_NAME}-{version}-hybrid-source"
        hybrid_dmg_path = Path(tmpdir) / hybrid_dmg_name(version)
        staging_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app_bundle, staging_root / app_bundle.name, symlinks=True)
        (staging_root / "Applications").symlink_to("/Applications")

        create_command = [
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
            "UDRW",
            str(staging_dmg_path),
        ]
        subprocess.run(create_command, cwd=WORKSPACE_ROOT, check=True)

        mount_point: Path | None = None
        try:
            attach_result = subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    "-readwrite",
                    "-noverify",
                    "-noautoopen",
                    "-plist",
                    str(staging_dmg_path),
                ],
                cwd=WORKSPACE_ROOT,
                check=True,
                capture_output=True,
            )
            _device, mount_point = parse_hdiutil_attach_plist(attach_result.stdout)
            apply_dmg_finder_layout(mount_point, app_name=app_bundle.name)
            shutil.copytree(mount_point, hybrid_source_dir, symlinks=True)
        finally:
            if mount_point is not None:
                subprocess.run(["hdiutil", "detach", str(mount_point)], cwd=WORKSPACE_ROOT, check=True)

        makehybrid_command = [
            "hdiutil",
            "makehybrid",
            "-hfs",
            "-default-volume-name",
            volume_name,
            "-hfs-volume-name",
            volume_name,
            "-hfs-openfolder",
            str(hybrid_source_dir),
            "-ov",
            "-o",
            str(hybrid_dmg_path),
            str(hybrid_source_dir),
        ]
        subprocess.run(makehybrid_command, cwd=WORKSPACE_ROOT, check=True)

        convert_command = [
            "hdiutil",
            "convert",
            str(hybrid_dmg_path),
            "-ov",
            "-format",
            "UDZO",
            "-o",
            str(dmg_path),
        ]
        subprocess.run(convert_command, cwd=WORKSPACE_ROOT, check=True)

    return dmg_path


def generate_appcast_command(
    tool_path: Path, updates_dir: Path, *, config: SparkleReleaseConfig | None = None
) -> list[str]:
    command = [str(tool_path)]
    if config is not None:
        if config.private_key is not None:
            command.extend(["--ed-key-file", "-"])
        elif config.private_key_file is not None:
            command.extend(["--ed-key-file", str(config.private_key_file)])
        elif config.keychain_account:
            command.extend(["--account", config.keychain_account])
    command.append(str(updates_dir))
    return command


def run_generate_appcast(tool_path: Path, updates_dir: Path, *, config: SparkleReleaseConfig) -> None:
    subprocess.run(
        generate_appcast_command(tool_path, updates_dir, config=config),
        cwd=WORKSPACE_ROOT,
        check=True,
        input=config.private_key.encode("utf-8") if config.private_key is not None else None,
    )


def build_release_artifacts(args: argparse.Namespace, env: dict[str, str] | None = None) -> SparkleReleaseArtifacts:
    """Build Sparkle-enabled DMG/appcast artifacts for internal macOS releases."""
    config = load_sparkle_release_config(env, env_file=args.env_file)
    version = load_project_version()

    if args.skip_build:
        bundle = app_bundle_path()
        if not bundle.exists():
            raise FileNotFoundError(f"未找到现有 app bundle: {bundle}")
    else:
        bundle = build_base_app_bundle()

    copied_framework = copy_sparkle_framework(bundle, config.framework_path)
    update_bundle_plist(bundle, version=version, config=config)
    ad_hoc_sign_bundle(bundle)

    print(f"[sparkle] framework copied to {copied_framework}")
    print(f"[sparkle] feed={config.feed_url}")
    print(f"[codesign] ad-hoc re-signed {bundle}")

    dmg_path = create_dmg(bundle, args.output_dir, version=version, volume_name=args.volume_name)
    print(f"[dmg] {dmg_path}")

    appcast_generated = False
    if not args.skip_appcast:
        if config.generate_appcast_tool is None:
            raise FileNotFoundError(
                f"未找到 generate_appcast，请设置 {SPARKLE_APPCAST_TOOL_ENV} 或提供 Sparkle bin/ 目录。"
            )
        run_generate_appcast(config.generate_appcast_tool, args.output_dir, config=config)
        print(f"[appcast] generated under {args.output_dir}")
        appcast_generated = True

    print(f"[done] internal macOS Sparkle release artifacts are under {args.output_dir}")
    return SparkleReleaseArtifacts(
        version=version,
        app_bundle=bundle,
        output_dir=args.output_dir,
        dmg_path=dmg_path,
        appcast_generated=appcast_generated,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    build_release_artifacts(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
