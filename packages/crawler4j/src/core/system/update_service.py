"""Application update service.

The desktop host now delegates macOS packaged-app updates to Sparkle while
keeping a small cross-platform wrapper for UI code and preference syncing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.system.sparkle import SparkleAvailability, SparkleError, SparkleUpdater, sparkle_availability


class UpdateChannel(str, Enum):
    """Update channel placeholder for future non-Sparkle backends."""

    STABLE = "stable"
    BETA = "beta"
    NIGHTLY = "nightly"


@dataclass(slots=True)
class UpdateInfo:
    """Reserved update payload for non-Sparkle backends."""

    version: str
    channel: UpdateChannel
    release_notes: str
    download_url: str
    file_size: int
    sha256: str
    is_critical: bool = False


class UpdateService(QObject):
    """Thin UI-facing facade for desktop self-update integrations."""

    availability_changed = pyqtSignal(bool, str)
    update_check_failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._channel = UpdateChannel.STABLE
        self._desired_auto_check = True
        self._availability = sparkle_availability()
        self._sparkle: SparkleUpdater | None = None
        self._started = False

    @property
    def channel(self) -> UpdateChannel:
        return self._channel

    @channel.setter
    def channel(self, value: UpdateChannel) -> None:
        self._channel = value

    @property
    def availability(self) -> SparkleAvailability:
        return self._availability

    @property
    def is_supported(self) -> bool:
        return self._availability.supported

    @property
    def availability_reason(self) -> str:
        return self._availability.reason

    def configure(self, *, auto_check: bool) -> None:
        """Persist the desired auto-check preference and push it if active."""
        self._desired_auto_check = bool(auto_check)
        if self._sparkle is not None:
            self._sparkle.set_automatically_checks_for_updates(self._desired_auto_check)

    def startup(self) -> bool:
        """Initialize the Sparkle bridge when the packaged macOS app starts."""
        if self._started:
            return self.is_supported

        self._started = True
        self._availability = sparkle_availability()
        if not self._availability.supported:
            self.availability_changed.emit(False, self._availability.reason)
            return False

        try:
            self._sparkle = SparkleUpdater()
            self._sparkle.set_automatically_checks_for_updates(self._desired_auto_check)
        except SparkleError as exc:
            self._availability = SparkleAvailability(False, str(exc))
            self.availability_changed.emit(False, self._availability.reason)
            return False

        self.availability_changed.emit(True, "")
        return True

    def check_for_updates(self) -> bool:
        """Open Sparkle's standard update UI when available."""
        if not self.startup() or self._sparkle is None:
            self.update_check_failed.emit(self.availability_reason)
            return False

        if not self._sparkle.can_check_for_updates():
            self.update_check_failed.emit("当前更新器不可用，请稍后重试。")
            return False

        try:
            self._sparkle.check_for_updates()
        except SparkleError as exc:
            self.update_check_failed.emit(str(exc))
            return False
        return True


_update_service: Optional[UpdateService] = None


def get_update_service() -> UpdateService:
    """Return the process-wide update service instance."""
    global _update_service
    if _update_service is None:
        _update_service = UpdateService()
    return _update_service
