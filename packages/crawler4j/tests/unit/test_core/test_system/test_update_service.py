from __future__ import annotations

from src.core.system.config_center import get_config_center
from src.core.system.update_service import UpdateAvailability, UpdateService
from src.ui.app import install_update_config_sync


def test_update_service_stays_unsupported_when_no_backend_is_available(monkeypatch):
    monkeypatch.setattr(
        "src.core.system.update_service.resolve_update_backend",
        lambda: ("None", UpdateAvailability(False, "No updater in tests"), None),
    )

    service = UpdateService()

    assert service.startup() is False
    assert service.is_supported is False
    assert service.availability_reason == "No updater in tests"


def test_update_service_configures_and_triggers_backend(monkeypatch):
    observed: dict[str, object] = {}

    class FakeBackend:
        def set_automatically_checks_for_updates(self, enabled: bool) -> None:
            observed["auto_check"] = enabled

        def can_check_for_updates(self) -> bool:
            return True

        def check_for_updates(self):
            observed["checked"] = True
            return True, "started"

    monkeypatch.setattr(
        "src.core.system.update_service.resolve_update_backend",
        lambda: ("Velopack", UpdateAvailability(True, "", "Velopack"), FakeBackend),
    )

    service = UpdateService()
    service.configure(auto_check=False)

    assert service.startup() is True
    assert service.is_supported is True
    assert observed["auto_check"] is False
    assert service.check_for_updates() is True
    assert observed["checked"] is True
    assert service.last_action_message == "started"


def test_update_service_surfaces_no_update_message(monkeypatch):
    class FakeBackend:
        def set_automatically_checks_for_updates(self, enabled: bool) -> None:
            return None

        def can_check_for_updates(self) -> bool:
            return True

        def check_for_updates(self):
            return False, "当前已是最新版本。"

    monkeypatch.setattr(
        "src.core.system.update_service.resolve_update_backend",
        lambda: ("Velopack", UpdateAvailability(True, "", "Velopack"), FakeBackend),
    )

    service = UpdateService()

    assert service.check_for_updates() is False
    assert service.last_action_message == "当前已是最新版本。"


def test_install_update_config_sync_hot_updates_service(monkeypatch, tmp_path):
    observed: list[bool] = []

    class DummyUpdateService:
        def configure(self, *, auto_check: bool) -> None:
            observed.append(auto_check)

    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()

    config = get_config_center()
    config.set("system.auto_update", False)

    monkeypatch.setattr(
        "src.core.system.update_service.get_update_service",
        lambda: DummyUpdateService(),
    )

    install_update_config_sync(config)
    config.set("system.auto_update", True)

    assert observed == [False, True]
