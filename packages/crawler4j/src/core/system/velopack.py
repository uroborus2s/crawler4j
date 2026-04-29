"""Windows Velopack updater integration."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


UPDATE_CONFIG_FILENAME = "crawler4j.update.json"
UPDATE_CONFIG_PATH_ENV = "CRAWLER4J_VELOPACK_CONFIG_PATH"
VELOPACK_FEED_URL_ENV = "CRAWLER4J_VELOPACK_FEED_URL"
VELOPACK_PACK_ID_ENV = "CRAWLER4J_VELOPACK_PACK_ID"
VELOPACK_CHANNEL_ENV = "CRAWLER4J_VELOPACK_CHANNEL"

DEFAULT_CHANNEL = "win"


class VelopackError(RuntimeError):
    """Raised when Velopack cannot be initialized or used."""


@dataclass(slots=True)
class VelopackAvailability:
    """User-facing Velopack availability state."""

    supported: bool
    reason: str = ""


@dataclass(slots=True)
class VelopackUpdateConfig:
    """Bundled Windows update metadata."""

    feed_url: str
    pack_id: str = ""
    channel: str = DEFAULT_CHANNEL


def _load_velopack_module() -> Any:
    try:
        import velopack
    except ImportError as exc:
        raise VelopackError("缺少 velopack 运行时依赖。") from exc
    return velopack


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def has_velopack_release_layout(bundle_dir: Path | None = None) -> bool:
    """Detect the minimal Windows layout Velopack needs to self-update."""
    root = bundle_dir or resolve_velopack_bundle_dir()
    if root is None:
        return False

    installed_layout = _path_exists(root / "sq.version") and _path_exists(root.parent / "Update.exe")
    portable_layout = _path_exists(root / "Update.exe") and _path_exists(root / "current" / "sq.version")
    return installed_layout or portable_layout


def resolve_velopack_bundle_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def resolve_velopack_update_config_path() -> Path | None:
    override = str(os.environ.get(UPDATE_CONFIG_PATH_ENV, "")).strip()
    if override:
        return Path(override).expanduser().resolve()

    bundle_dir = resolve_velopack_bundle_dir()
    if bundle_dir is None:
        return None
    return bundle_dir / UPDATE_CONFIG_FILENAME


def load_velopack_update_config() -> VelopackUpdateConfig:
    env_feed_url = str(os.environ.get(VELOPACK_FEED_URL_ENV, "")).strip()
    env_pack_id = str(os.environ.get(VELOPACK_PACK_ID_ENV, "")).strip()
    env_channel = str(os.environ.get(VELOPACK_CHANNEL_ENV, DEFAULT_CHANNEL)).strip() or DEFAULT_CHANNEL

    if env_feed_url:
        return VelopackUpdateConfig(
            feed_url=env_feed_url,
            pack_id=env_pack_id,
            channel=env_channel,
        )

    config_path = resolve_velopack_update_config_path()
    if config_path is None or not config_path.exists():
        raise VelopackError("当前 Windows 包缺少 Velopack 更新配置。")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    feed_url = str(payload.get("feed_url", "")).strip()
    pack_id = str(payload.get("pack_id", "")).strip()
    channel = str(payload.get("channel", DEFAULT_CHANNEL)).strip() or DEFAULT_CHANNEL
    if not feed_url:
        raise VelopackError("当前 Windows 包缺少 Velopack feed 地址。")
    return VelopackUpdateConfig(feed_url=feed_url, pack_id=pack_id, channel=channel)


def bootstrap_velopack() -> None:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return

    velopack = _load_velopack_module()
    app_factory = getattr(velopack, "App", None)
    if app_factory is None:
        raise VelopackError("当前 velopack 运行时缺少 App 入口。")

    app_factory().run()


def velopack_availability() -> VelopackAvailability:
    if sys.platform != "win32":
        return VelopackAvailability(False, "Velopack 仅支持 Windows 打包版。")
    if not getattr(sys, "frozen", False):
        return VelopackAvailability(False, "当前是源码开发模式，Velopack 仅在打包后的 Windows 客户端中启用。")
    if not has_velopack_release_layout():
        return VelopackAvailability(False, "当前 Windows 包不是 Velopack 正式发布产物，不能执行宿主自更新。")

    try:
        config = load_velopack_update_config()
        manager = _load_velopack_module().UpdateManager(config.feed_url)
    except VelopackError as exc:
        return VelopackAvailability(False, str(exc))
    except Exception as exc:
        return VelopackAvailability(False, f"Velopack 初始化失败：{exc}")

    del manager

    return VelopackAvailability(True, "")


class VelopackUpdater:
    """Thin wrapper around the Velopack Python runtime."""

    def __init__(self):
        self._config = load_velopack_update_config()
        if not has_velopack_release_layout():
            raise VelopackError("当前 Windows 包不是 Velopack 正式发布产物，不能执行宿主自更新。")
        self._manager = _load_velopack_module().UpdateManager(self._config.feed_url)
        self._auto_check = True

    def can_check_for_updates(self) -> bool:
        return True

    def set_automatically_checks_for_updates(self, enabled: bool) -> None:
        self._auto_check = bool(enabled)

    def check_for_updates(self) -> tuple[bool, str]:
        update_info = self._manager.check_for_updates()
        if not update_info:
            return False, "当前已是最新版本。"

        self._manager.download_updates(update_info)
        self._manager.apply_updates_and_restart(update_info)
        return True, "已下载更新，应用将退出并重启。"
