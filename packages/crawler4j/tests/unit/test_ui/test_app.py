from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import QEvent


def test_importing_app_keeps_debug_launcher_and_shell_lazy():
    sys.modules.pop("src.ui.app", None)
    sys.modules.pop("src.core.debug.launcher", None)
    sys.modules.pop("src.ui.shell", None)

    module = importlib.import_module("src.ui.app")

    assert module.__name__ == "src.ui.app"
    assert "src.core.debug.launcher" not in sys.modules
    assert "src.ui.shell" not in sys.modules


def test_main_dispatches_host_http_runtime_check_before_starting_host(monkeypatch):
    from src.ui import app

    observed: list[list[str]] = []

    def fake_run_http_runtime_check(argv: list[str]) -> int:
        observed.append(list(argv))
        return 0

    def fail_host_startup() -> None:
        raise AssertionError("host startup should not run for the HTTP runtime check")

    monkeypatch.setattr(app, "_run_host_http_runtime_check_if_requested", fake_run_http_runtime_check)
    monkeypatch.setattr(app, "bootstrap_host_updater", fail_host_startup)

    exit_code = app.main(["Crawler4j", "--crawler4j-verify-http-runtime"])

    assert exit_code == 0
    assert observed == [["Crawler4j", "--crawler4j-verify-http-runtime"]]


def test_main_dispatches_embedded_debug_worker_before_starting_gui(monkeypatch):
    from src.ui import app

    observed: dict[str, object] = {}

    def fake_extract_worker_args(argv: list[str]) -> list[str]:
        observed["extract_argv"] = list(argv)
        return ["/tmp/session.json"]

    def fake_run_worker(worker_args: list[str], *, executable: str) -> int:
        observed["worker_args"] = list(worker_args)
        observed["executable"] = executable
        return 7

    def fail_qapplication(*args, **kwargs):
        raise AssertionError("GUI should not start for embedded debug worker")

    monkeypatch.setattr(app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app, "_extract_embedded_debug_worker_args", fake_extract_worker_args)
    monkeypatch.setattr(app, "_run_embedded_debug_worker", fake_run_worker)
    monkeypatch.setattr(app, "QApplication", fail_qapplication)

    exit_code = app.main(["Crawler4j", "--crawler4j-debug-worker", "/tmp/session.json"])

    assert exit_code == 7
    assert observed["extract_argv"] == ["Crawler4j", "--crawler4j-debug-worker", "/tmp/session.json"]
    assert observed["worker_args"] == ["/tmp/session.json"]
    assert observed["executable"] == "Crawler4j"


def test_main_dispatches_embedded_debugpy_adapter_before_starting_gui(monkeypatch):
    from src.ui import app

    observed: dict[str, object] = {}

    def fake_extract_adapter_args(argv: list[str]) -> list[str]:
        observed["extract_argv"] = list(argv)
        return ["--for-server", "32123"]

    def fake_run_adapter(adapter_args: list[str], *, executable: str) -> int:
        observed["adapter_args"] = list(adapter_args)
        observed["executable"] = executable
        return 9

    def fail_qapplication(*args, **kwargs):
        raise AssertionError("GUI should not start for embedded debugpy adapter")

    monkeypatch.setattr(app.sys, "frozen", True, raising=False)
    monkeypatch.setattr(app, "_extract_embedded_debugpy_adapter_args", fake_extract_adapter_args)
    monkeypatch.setattr(app, "_run_embedded_debugpy_adapter", fake_run_adapter)
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
    assert observed["extract_argv"] == [
        "Crawler4j",
        "--crawler4j-debugpy-adapter",
        "/tmp/debugpy/adapter",
        "--for-server",
        "32123",
    ]
    assert observed["adapter_args"] == ["--for-server", "32123"]
    assert observed["executable"] == "Crawler4j"


def test_main_bootstraps_host_updater_before_starting_gui(monkeypatch):
    from src.ui import app

    observed: list[str] = []

    def fake_bootstrap() -> None:
        observed.append("bootstrap")

    def fake_init_database() -> None:
        observed.append("init_database")

    class StopAfterBootstrap(RuntimeError):
        pass

    def fake_get_config_center():
        observed.append("get_config_center")
        raise StopAfterBootstrap

    monkeypatch.setattr(app, "bootstrap_host_updater", fake_bootstrap)
    monkeypatch.setattr(app, "init_database", fake_init_database)
    monkeypatch.setattr(app, "get_config_center", fake_get_config_center)

    with pytest.raises(StopAfterBootstrap):
        app.main(["Crawler4j"])

    assert observed == ["bootstrap", "init_database", "get_config_center"]


def test_main_disables_quit_on_last_window_closed_before_async_startup(monkeypatch):
    from src.ui import app

    observed: list[tuple[str, object]] = []

    class DummyIcon:
        def isNull(self) -> bool:
            return True

    class DummyApplication:
        def __init__(self, argv):
            observed.append(("argv", list(argv)))
            self.lastWindowClosed = SimpleNamespace(connect=lambda callback: observed.append(("lastWindowClosed.connect", callback)))
            self.aboutToQuit = SimpleNamespace(connect=lambda callback: observed.append(("aboutToQuit.connect", callback)))

        def setApplicationName(self, name: str) -> None:
            observed.append(("name", name))

        def setWindowIcon(self, icon) -> None:
            observed.append(("icon", icon))

        def setQuitOnLastWindowClosed(self, enabled: bool) -> None:
            observed.append(("quit", enabled))

        def installEventFilter(self, event_filter) -> None:
            observed.append(("installEventFilter", event_filter))

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
    monkeypatch.setattr(app, "get_config_center", lambda: object())
    monkeypatch.setattr(app, "get_app_data_dir", lambda: Path("/tmp/crawler4j-tests"))
    monkeypatch.setattr(app, "install_logging_config_sync", lambda config, *, log_dir: None)
    monkeypatch.setattr(app, "install_update_config_sync", lambda config: None)
    monkeypatch.setattr(app, "QApplication", DummyApplication)
    monkeypatch.setattr(app, "load_app_icon", lambda: DummyIcon())
    monkeypatch.setattr(app, "install_qasync_timer_compat", lambda qasync_module: True)
    monkeypatch.setattr(app, "_load_qasync_module", lambda: SimpleNamespace(QEventLoop=lambda qt_app: DummyLoop()))
    monkeypatch.setattr(app.asyncio, "set_event_loop", lambda loop: observed.append(("set_event_loop", loop)))

    exit_code = app.main(["Crawler4j"])

    assert exit_code == 0
    quit_index = observed.index(("quit", False))
    run_index = observed.index(("run_until_complete", True))
    assert quit_index < run_index
    assert ("quit", True) not in observed
    assert any(item[0] == "installEventFilter" for item in observed)


@pytest.mark.asyncio
async def test_run_application_shuts_down_after_last_window_closed(monkeypatch):
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
            self.lastWindowClosed = FakeSignal()
            self.aboutToQuit = FakeSignal()
            self._event_filters: list[object] = []

        def installEventFilter(self, event_filter) -> None:
            self._event_filters.append(event_filter)

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

    async def fake_sleep(delay: float) -> None:
        observed.append(("sleep", delay))
        fake_app.lastWindowClosed.emit()

    monkeypatch.setattr("src.core.rem.manager.get_environment_manager", lambda: FakeEnvironmentManager())
    monkeypatch.setattr("src.core.atm.service.get_task_service", lambda: FakeTaskService())
    monkeypatch.setattr("src.core.system.update_service.get_update_service", lambda: FakeUpdateService())
    monkeypatch.setattr("src.core.debug.service.get_debug_service", lambda: FakeDebugService())
    monkeypatch.setattr("src.core.rem.handle.PlaywrightManager.force_shutdown", fake_force_shutdown)
    monkeypatch.setattr(app, "_load_shell_class", lambda: FakeWindow)
    monkeypatch.setattr(app.asyncio, "sleep", fake_sleep)

    fake_app = FakeApplication()

    await app._run_application(fake_app)

    show_index = observed.index(("window", "show"))
    sleep_index = observed.index(("sleep", 0))
    update_index = observed.index(("update_service", "startup"))
    assert show_index < sleep_index < update_index
    assert ("task_service", "stop") in observed
    assert ("debug_service", "shutdown") in observed
    assert ("playwright", "force_shutdown") in observed

@pytest.mark.asyncio
async def test_run_application_defers_quit_event_until_shutdown_finishes(monkeypatch):
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
            self.lastWindowClosed = FakeSignal()
            self.aboutToQuit = FakeSignal()
            self._event_filters: list[object] = []

        def installEventFilter(self, event_filter) -> None:
            self._event_filters.append(event_filter)

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

    async def fake_sleep(delay: float) -> None:
        observed.append(("sleep", delay))
        quit_event = QEvent(QEvent.Type.Quit)
        handled = fake_app._event_filters[0].eventFilter(fake_app, quit_event)
        observed.append(("quit_event_handled", handled))

    monkeypatch.setattr("src.core.rem.manager.get_environment_manager", lambda: FakeEnvironmentManager())
    monkeypatch.setattr("src.core.atm.service.get_task_service", lambda: FakeTaskService())
    monkeypatch.setattr("src.core.system.update_service.get_update_service", lambda: FakeUpdateService())
    monkeypatch.setattr("src.core.debug.service.get_debug_service", lambda: FakeDebugService())
    monkeypatch.setattr("src.core.rem.handle.PlaywrightManager.force_shutdown", fake_force_shutdown)
    monkeypatch.setattr(app, "_load_shell_class", lambda: FakeWindow)
    monkeypatch.setattr(app.asyncio, "sleep", fake_sleep)

    fake_app = FakeApplication()

    await app._run_application(fake_app)

    assert ("quit_event_handled", True) in observed
    assert ("task_service", "stop") in observed
    assert ("debug_service", "shutdown") in observed
    assert ("playwright", "force_shutdown") in observed
