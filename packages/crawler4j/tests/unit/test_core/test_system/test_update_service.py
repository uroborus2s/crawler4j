from __future__ import annotations

from src.core.system.sparkle import SparkleAvailability
from src.core.system.update_service import UpdateService
from src.core.system.preferences_service import PreferenceKey, PreferencesService
from src.ui.app import install_update_preferences_sync


def test_update_service_stays_unsupported_when_sparkle_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "src.core.system.update_service.sparkle_availability",
        lambda: SparkleAvailability(False, "Sparkle unavailable in tests"),
    )

    service = UpdateService()

    assert service.startup() is False
    assert service.is_supported is False
    assert service.availability_reason == "Sparkle unavailable in tests"


def test_update_service_configures_and_triggers_sparkle_backend(monkeypatch):
    observed: dict[str, object] = {}

    class FakeSparkleUpdater:
        def set_automatically_checks_for_updates(self, enabled: bool) -> None:
            observed["auto_check"] = enabled

        def can_check_for_updates(self) -> bool:
            return True

        def check_for_updates(self) -> None:
            observed["checked"] = True

    monkeypatch.setattr(
        "src.core.system.update_service.sparkle_availability",
        lambda: SparkleAvailability(True, ""),
    )
    monkeypatch.setattr("src.core.system.update_service.SparkleUpdater", FakeSparkleUpdater)

    service = UpdateService()
    service.configure(auto_check=False)

    assert service.startup() is True
    assert service.is_supported is True
    assert observed["auto_check"] is False
    assert service.check_for_updates() is True
    assert observed["checked"] is True


def test_install_update_preferences_sync_hot_updates_service(monkeypatch):
    observed: list[bool] = []

    class DummyUpdateService:
        def configure(self, *, auto_check: bool) -> None:
            observed.append(auto_check)

    prefs = PreferencesService()
    prefs.set(PreferenceKey.AUTO_UPDATE, False)

    monkeypatch.setattr(
        "src.core.system.update_service.get_update_service",
        lambda: DummyUpdateService(),
    )

    install_update_preferences_sync(prefs)
    prefs.set(PreferenceKey.AUTO_UPDATE, True)

    assert observed == [False, True]
