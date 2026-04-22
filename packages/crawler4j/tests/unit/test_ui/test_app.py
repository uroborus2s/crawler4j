from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


def test_main_dispatches_embedded_debug_worker_before_starting_gui(monkeypatch):
    from src.ui import app
    from src.core.debug import worker_entry

    observed: dict[str, list[str]] = {}

    def fake_worker_main() -> None:
        observed["argv"] = list(app.sys.argv)
        raise SystemExit(7)

    def fail_qapplication(*args, **kwargs):
        raise AssertionError("GUI should not start for embedded debug worker")

    monkeypatch.setattr(app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(worker_entry, "main", fake_worker_main)
    monkeypatch.setattr(app, "QApplication", fail_qapplication)

    exit_code = app.main(["Crawler4j", "--crawler4j-debug-worker", "/tmp/session.json"])

    assert exit_code == 7
    assert observed["argv"] == ["Crawler4j", "/tmp/session.json"]


def test_main_dispatches_embedded_debugpy_adapter_before_starting_gui(monkeypatch):
    from src.ui import app

    observed: dict[str, list[str]] = {}

    def fake_run_module(module_name: str, run_name: str):
        observed["module_name"] = module_name
        observed["run_name"] = run_name
        observed["argv"] = list(app.sys.argv)
        raise SystemExit(9)

    def fail_qapplication(*args, **kwargs):
        raise AssertionError("GUI should not start for embedded debugpy adapter")

    monkeypatch.setattr(app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app.runpy, "run_module", fake_run_module)
    monkeypatch.setattr(app, "QApplication", fail_qapplication)

    exit_code = app.main(
        [
            "Crawler4j",
            "--crawler4j-debugpy-adapter",
            "/tmp/debugpy/adapter",
            "--for-server",
            "32123",
        ]
    )

    assert exit_code == 9
    assert observed["module_name"] == "debugpy.adapter"
    assert observed["run_name"] == "__main__"
    assert observed["argv"] == ["Crawler4j", "--for-server", "32123"]


def test_main_bootstraps_host_updater_before_starting_gui(monkeypatch):
    from src.ui import app

    observed: list[str] = []

    def fake_bootstrap() -> None:
        observed.append("bootstrap")

    def fake_init_database() -> None:
        observed.append("init_database")

    class StopAfterBootstrap(RuntimeError):
        pass

    def fake_get_preferences_service():
        observed.append("get_preferences_service")
        raise StopAfterBootstrap

    monkeypatch.setattr(app, "bootstrap_host_updater", fake_bootstrap)
    monkeypatch.setattr(app, "init_database", fake_init_database)
    monkeypatch.setattr(app, "get_preferences_service", fake_get_preferences_service)

    with pytest.raises(StopAfterBootstrap):
        app.main(["Crawler4j"])

    assert observed == ["bootstrap", "init_database", "get_preferences_service"]


def test_main_disables_quit_on_last_window_closed_before_async_startup(monkeypatch):
    from src.ui import app

    observed: list[tuple[str, object]] = []

    class DummyIcon:
        def isNull(self) -> bool:
            return True

    class DummyApplication:
        def __init__(self, argv):
            observed.append(("argv", list(argv)))

        def setApplicationName(self, name: str) -> None:
            observed.append(("name", name))

        def setWindowIcon(self, icon) -> None:
            observed.append(("icon", icon))

        def setQuitOnLastWindowClosed(self, enabled: bool) -> None:
            observed.append(("quit", enabled))

    class DummyLoop:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def run_until_complete(self, awaitable) -> None:
            observed.append(("run_until_complete", True))
            awaitable.close()

    monkeypatch.setattr(app, "bootstrap_host_updater", lambda: None)
    monkeypatch.setattr(app, "init_database", lambda: None)
    monkeypatch.setattr(app, "get_preferences_service", lambda: object())
    monkeypatch.setattr(app, "get_app_data_dir", lambda: Path("/tmp/crawler4j-tests"))
    monkeypatch.setattr(app, "install_logging_preferences_sync", lambda prefs, *, log_dir: None)
    monkeypatch.setattr(app, "install_update_preferences_sync", lambda prefs: None)
    monkeypatch.setattr(app, "QApplication", DummyApplication)
    monkeypatch.setattr(app, "load_app_icon", lambda: DummyIcon())
    monkeypatch.setattr(app, "install_qasync_timer_compat", lambda qasync_module: True)
    monkeypatch.setattr(app.asyncio, "set_event_loop", lambda loop: observed.append(("set_event_loop", loop)))
    monkeypatch.setitem(sys.modules, "qasync", SimpleNamespace(QEventLoop=lambda qt_app: DummyLoop()))

    exit_code = app.main(["Crawler4j"])

    assert exit_code == 0
    quit_index = observed.index(("quit", False))
    run_index = observed.index(("run_until_complete", True))
    assert quit_index < run_index


@pytest.mark.asyncio
async def test_run_application_restores_quit_on_last_window_closed_after_window_show(monkeypatch):
    from src.ui import app

    observed: list[tuple[str, object]] = []

    class FakeSignal:
        def __init__(self) -> None:
            self._callbacks: list[object] = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self) -> None:
            for callback in list(self._callbacks):
                callback()

    class FakeApplication:
        def __init__(self) -> None:
            self.aboutToQuit = FakeSignal()

        def setQuitOnLastWindowClosed(self, enabled: bool) -> None:
            observed.append(("quit", enabled))
            if enabled:
                self.aboutToQuit.emit()

    class FakePrefs:
        def get(self, key, default=None):
            return False

    class FakeEnvironmentManager:
        async def startup(self) -> None:
            observed.append(("env_manager", "startup"))

    class FakeTaskService:
        async def start(self) -> None:
            observed.append(("task_service", "start"))

        async def stop(self) -> None:
            observed.append(("task_service", "stop"))

    class FakeDebugService:
        async def shutdown(self) -> None:
            observed.append(("debug_service", "shutdown"))

    class FakeUpdateService:
        def startup(self) -> None:
            observed.append(("update_service", "startup"))

    class FakeWindow:
        def show(self) -> None:
            observed.append(("window", "show"))

        def showMinimized(self) -> None:
            observed.append(("window", "show_minimized"))

    async def fake_force_shutdown() -> None:
        observed.append(("playwright", "force_shutdown"))

    monkeypatch.setattr("src.core.rem.manager.get_environment_manager", lambda: FakeEnvironmentManager())
    monkeypatch.setattr("src.core.atm.service.get_task_service", lambda: FakeTaskService())
    monkeypatch.setattr("src.core.system.update_service.get_update_service", lambda: FakeUpdateService())
    monkeypatch.setattr("src.core.debug.service.get_debug_service", lambda: FakeDebugService())
    monkeypatch.setattr("src.core.rem.handle.PlaywrightManager.force_shutdown", fake_force_shutdown)
    monkeypatch.setattr(app, "Shell", FakeWindow)

    await app._run_application(FakeApplication(), FakePrefs())

    show_index = observed.index(("window", "show"))
    quit_restore_index = observed.index(("quit", True))
    assert show_index < quit_restore_index
    assert ("task_service", "stop") in observed
    assert ("debug_service", "shutdown") in observed
    assert ("playwright", "force_shutdown") in observed
