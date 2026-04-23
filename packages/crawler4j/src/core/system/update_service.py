"""Application update service.

The desktop host now delegates macOS packaged-app updates to Sparkle and
Windows installed-app updates to Velopack while keeping a small UI-facing
wrapper for preference syncing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import sys
from typing import Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.system.sparkle import SparkleError, SparkleUpdater, sparkle_availability
from src.core.system.velopack import VelopackError, VelopackUpdater, bootstrap_velopack, velopack_availability


_windows_bootstrap_error: str | None = None


class UpdateChannel(str, Enum):
    """Update channel placeholder for future non-Sparkle backends."""

    STABLE = "stable"
    BETA = "beta"
    NIGHTLY = "nightly"


@dataclass(slots=True)
class UpdateAvailability:
    """User-facing updater availability state."""

    supported: bool
    reason: str = ""
    backend: str = ""


def bootstrap_update_runtime() -> None:
    """Run any packaged-app updater bootstrap that must happen before GUI init."""
    global _windows_bootstrap_error

    if not sys.platform.startswith("win"):
        return

    try:
        bootstrap_velopack()
        _windows_bootstrap_error = None
    except VelopackError as exc:
        _windows_bootstrap_error = str(exc)
    except Exception as exc:  # pragma: no cover - defensive fallback
        _windows_bootstrap_error = f"Velopack 启动失败：{exc}"


def _sparkle_update_result(updater: SparkleUpdater) -> tuple[bool, str]:
    updater.check_for_updates()
    return True, "已打开 Sparkle 更新检查。"


def resolve_update_backend() -> tuple[str, UpdateAvailability, Callable[[], object] | None]:
    """Resolve the platform-specific updater backend."""
    if sys.platform == "darwin":
        availability = sparkle_availability()
        return (
            "Sparkle",
            UpdateAvailability(availability.supported, availability.reason, "Sparkle"),
            SparkleUpdater if availability.supported else None,
        )

    if sys.platform.startswith("win"):
        if _windows_bootstrap_error:
            availability = UpdateAvailability(False, _windows_bootstrap_error, "Velopack")
        else:
            velopack_state = velopack_availability()
            availability = UpdateAvailability(velopack_state.supported, velopack_state.reason, "Velopack")
        return ("Velopack", availability, VelopackUpdater if availability.supported else None)

    return ("None", UpdateAvailability(False, "当前平台暂不支持宿主自更新。"), None)


class UpdateService(QObject):
    """Thin UI-facing facade for desktop self-update integrations."""

    availability_changed = pyqtSignal(bool, str)
    update_check_failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._channel = UpdateChannel.STABLE
        self._desired_auto_check = True
        _backend_name, self._availability, _factory = resolve_update_backend()
        self._backend_name = _backend_name
        self._backend: object | None = None
        self._factory: Callable[[], object] | None = _factory
        self._started = False
        self._last_action_message = ""

    @property
    def channel(self) -> UpdateChannel:
        return self._channel

    @channel.setter
    def channel(self, value: UpdateChannel) -> None:
        self._channel = value

    @property
    def availability(self) -> UpdateAvailability:
        return self._availability

    @property
    def is_supported(self) -> bool:
        return self._availability.supported

    @property
    def availability_reason(self) -> str:
        return self._availability.reason

    @property
    def last_action_message(self) -> str:
        return self._last_action_message

    def configure(self, *, auto_check: bool) -> None:
        """Persist the desired auto-check preference and push it if active."""
        self._desired_auto_check = bool(auto_check)
        if self._backend is not None:
            self._backend.set_automatically_checks_for_updates(self._desired_auto_check)

    def startup(self) -> bool:
        """Initialize the platform-specific updater bridge when the app starts."""
        if self._started:
            return self.is_supported

        self._started = True
        self._backend_name, self._availability, self._factory = resolve_update_backend()
        if not self._availability.supported or self._factory is None:
            self.availability_changed.emit(False, self._availability.reason)
            return False

        try:
            self._backend = self._factory()
            self._backend.set_automatically_checks_for_updates(self._desired_auto_check)
        except (SparkleError, VelopackError) as exc:
            self._availability = UpdateAvailability(False, str(exc), self._backend_name)
            self.availability_changed.emit(False, self._availability.reason)
            return False

        self.availability_changed.emit(True, "")
        return True

    def check_for_updates(self) -> bool:
        """Trigger the platform-specific update flow when available."""
        self._last_action_message = ""
        if not self.startup() or self._backend is None:
            self._last_action_message = self.availability_reason
            self.update_check_failed.emit(self._last_action_message)
            return False

        if not self._backend.can_check_for_updates():
            self._last_action_message = "当前更新器不可用，请稍后重试。"
            self.update_check_failed.emit(self._last_action_message)
            return False

        try:
            started, message = self._check_backend_for_updates()
        except (SparkleError, VelopackError) as exc:
            self._last_action_message = str(exc)
            self.update_check_failed.emit(self._last_action_message)
            return False
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._last_action_message = str(exc)
            self.update_check_failed.emit(self._last_action_message)
            return False

        self._last_action_message = message
        if not started:
            return False
        return True

    def _check_backend_for_updates(self) -> tuple[bool, str]:
        if isinstance(self._backend, SparkleUpdater):
            return _sparkle_update_result(self._backend)

        result = self._backend.check_for_updates()
        if isinstance(result, tuple) and len(result) == 2:
            started, message = result
            return bool(started), str(message)
        if isinstance(result, bool):
            return bool(result), ""
        return bool(result), ""


_update_service: Optional[UpdateService] = None


def get_update_service() -> UpdateService:
    """Return the process-wide update service instance."""
    global _update_service
    if _update_service is None:
        _update_service = UpdateService()
    return _update_service
