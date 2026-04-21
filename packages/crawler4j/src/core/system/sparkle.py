"""macOS Sparkle updater integration.

This module keeps Sparkle-specific Objective-C bridging isolated behind a small
Python API so the rest of the app can treat updates as a normal service.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SPARKLE_FRAMEWORK_ENV = "CRAWLER4J_SPARKLE_FRAMEWORK_PATH"
SPARKLE_FEED_URL_KEY = "SUFeedURL"
SPARKLE_PUBLIC_KEY_KEY = "SUPublicEDKey"


class SparkleError(RuntimeError):
    """Raised when Sparkle cannot be initialized or used."""


@dataclass(slots=True)
class SparkleAvailability:
    """User-facing Sparkle availability state."""

    supported: bool
    reason: str = ""


def sparkle_availability() -> SparkleAvailability:
    """Return whether the current process can use Sparkle."""
    if sys.platform != "darwin":
        return SparkleAvailability(False, "Sparkle 仅支持 macOS 打包版。")
    if not getattr(sys, "frozen", False):
        return SparkleAvailability(False, "当前是源码开发模式，Sparkle 仅在打包后的 .app 中启用。")

    framework_path = resolve_sparkle_framework_path()
    if framework_path is None:
        return SparkleAvailability(False, "当前 app 未嵌入 Sparkle.framework。")

    metadata = read_main_bundle_sparkle_metadata()
    if not metadata.get(SPARKLE_FEED_URL_KEY):
        return SparkleAvailability(False, "当前 app 缺少 Sparkle feed 地址（SUFeedURL）。")
    if not metadata.get(SPARKLE_PUBLIC_KEY_KEY):
        return SparkleAvailability(False, "当前 app 缺少 Sparkle 公钥（SUPublicEDKey）。")

    return SparkleAvailability(True, "")


def resolve_sparkle_framework_path() -> Path | None:
    """Locate the Sparkle framework expected by the packaged app."""
    override = str(os.environ.get(SPARKLE_FRAMEWORK_ENV, "")).strip()
    if override:
        candidate = Path(override).expanduser().resolve()
        return candidate if candidate.exists() else None

    if not getattr(sys, "frozen", False):
        return None

    executable = Path(sys.executable).resolve()
    contents_dir = executable.parent.parent
    framework_path = contents_dir / "Frameworks" / "Sparkle.framework"
    return framework_path if framework_path.exists() else None


def read_main_bundle_sparkle_metadata() -> dict[str, str]:
    """Read Sparkle keys from the main bundle plist when available."""
    if sys.platform != "darwin":
        return {}

    try:
        from Foundation import NSBundle
    except ImportError:
        return {}

    info = NSBundle.mainBundle().infoDictionary() or {}
    result: dict[str, str] = {}
    for key in (SPARKLE_FEED_URL_KEY, SPARKLE_PUBLIC_KEY_KEY):
        value = info.get(key)
        if value is not None:
            result[key] = str(value)
    return result


class SparkleUpdater:
    """Thin wrapper around Sparkle's standard updater controller."""

    def __init__(self):
        self._framework_path = resolve_sparkle_framework_path()
        if self._framework_path is None:
            raise SparkleError("Sparkle.framework 未找到。")

        metadata = read_main_bundle_sparkle_metadata()
        if not metadata.get(SPARKLE_FEED_URL_KEY):
            raise SparkleError("当前 app 缺少 Sparkle feed 地址（SUFeedURL）。")
        if not metadata.get(SPARKLE_PUBLIC_KEY_KEY):
            raise SparkleError("当前 app 缺少 Sparkle 公钥（SUPublicEDKey）。")

        self._bundle = self._load_bundle(self._framework_path)
        self._controller = self._create_controller()
        self._updater = self._controller.updater()

    @staticmethod
    def _load_bundle(framework_path: Path) -> Any:
        try:
            import objc
            from Foundation import NSBundle
        except ImportError as exc:
            raise SparkleError("缺少 PyObjC 依赖，无法加载 Sparkle.framework。") from exc

        bundle = NSBundle.bundleWithPath_(str(framework_path))
        if bundle is None:
            raise SparkleError(f"无法打开 Sparkle.framework: {framework_path}")
        if not bundle.load():
            raise SparkleError(f"无法加载 Sparkle.framework: {framework_path}")

        try:
            objc.lookUpClass("SPUStandardUpdaterController")
        except Exception as exc:  # pragma: no cover - depends on real framework loading
            raise SparkleError("Sparkle.framework 已加载，但缺少 SPUStandardUpdaterController。") from exc

        return bundle

    @staticmethod
    def _create_controller() -> Any:
        import objc

        controller_cls = objc.lookUpClass("SPUStandardUpdaterController")
        controller = controller_cls.alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
            True,
            None,
            None,
        )
        if controller is None:
            raise SparkleError("创建 Sparkle updater controller 失败。")
        return controller

    def can_check_for_updates(self) -> bool:
        """Return whether Sparkle currently allows a user-triggered check."""
        return bool(self._updater.canCheckForUpdates())

    def set_automatically_checks_for_updates(self, enabled: bool) -> None:
        """Mirror the app's persisted update preference into Sparkle."""
        if bool(self._updater.automaticallyChecksForUpdates()) == bool(enabled):
            return
        self._updater.setAutomaticallyChecksForUpdates_(bool(enabled))

    def check_for_updates(self) -> None:
        """Trigger Sparkle's standard update UI."""
        if hasattr(self._updater, "checkForUpdates_"):
            self._updater.checkForUpdates_(None)
            return
        if hasattr(self._updater, "checkForUpdates"):
            self._updater.checkForUpdates()
            return
        raise SparkleError("当前 Sparkle 运行时不支持手动检查更新。")
