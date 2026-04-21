from __future__ import annotations

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
