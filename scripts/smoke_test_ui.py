"""Headless UI smoke test for workspace development."""

from __future__ import annotations

import asyncio
import faulthandler
import os
import sys
from pathlib import Path
from types import SimpleNamespace


faulthandler.enable()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
sys.path.insert(0, str(APP_ROOT))


async def _check_shell_structure(qt_app) -> None:
    import src.core.atm.ui.task_list_widget as task_list_widget_module
    from src.ui.shell import Shell

    original_task_list_load = task_list_widget_module.TaskListWidget.load_data

    print("Instantiating Shell...")
    try:
        task_list_widget_module.TaskListWidget.load_data = lambda self: None
        shell = Shell()
        try:
            qt_app.processEvents()
            await asyncio.sleep(0)
            assert shell.windowTitle() == "蛛行演略 · crawler4j"
            assert shell.sidebar.nav_list.count() == 6
            assert shell.content_stack.count() == 7
            print("Shell structure verified.")
        finally:
            shell.close()
            shell.deleteLater()
            qt_app.processEvents()
            await asyncio.sleep(0)
    finally:
        task_list_widget_module.TaskListWidget.load_data = original_task_list_load


async def _check_dashboard_refresh() -> None:
    import src.core.rem.manager as rem_manager
    import src.ui.dashboard as dashboard_module

    original_setup_timer = dashboard_module.DashboardPage._setup_timer
    original_get_module_registry = dashboard_module.get_module_registry
    original_get_task_service = dashboard_module.get_task_service
    original_get_environment_manager = rem_manager.get_environment_manager

    try:
        dashboard_module.DashboardPage._setup_timer = lambda self: None
        dashboard_module.get_module_registry = lambda: SimpleNamespace(
            list_modules=lambda: [
                SimpleNamespace(status=dashboard_module.ModuleStatus.ENABLED),
                SimpleNamespace(status=dashboard_module.ModuleStatus.DISABLED),
            ]
        )
        rem_manager.get_environment_manager = lambda: SimpleNamespace(
            pool=SimpleNamespace(
                _environments={
                    "ready": SimpleNamespace(status=dashboard_module.EnvStatus.READY),
                    "busy": SimpleNamespace(status=dashboard_module.EnvStatus.BUSY),
                }
            )
        )
        
        async def fake_list_jobs():
            return [
                SimpleNamespace(state=dashboard_module.JobState.ACTIVE),
                SimpleNamespace(state=dashboard_module.JobState.COMPLETED),
                SimpleNamespace(state=dashboard_module.JobState.ERROR),
            ]

        dashboard_module.get_task_service = lambda: SimpleNamespace(
            list_jobs=fake_list_jobs
        )

        page = dashboard_module.DashboardPage()
        try:
            page.load_data()
            task = page._load_task
            if task is None:
                raise RuntimeError("Dashboard refresh task was not created")

            await task
            await asyncio.sleep(0)

            assert page.running_card.value_label.text() == "1"
            assert page.completed_card.value_label.text() == "1"
            assert page.failed_card.value_label.text() == "1"
            assert page.env_ready_card.value_label.text() == "1"
            assert page.env_busy_card.value_label.text() == "1"
            assert page.modules_card.value_label.text() == "2"
            assert page._load_task is None
            print("Dashboard async refresh verified.")
        finally:
            page.close()
            page.deleteLater()
    finally:
        dashboard_module.DashboardPage._setup_timer = original_setup_timer
        dashboard_module.get_module_registry = original_get_module_registry
        dashboard_module.get_task_service = original_get_task_service
        rem_manager.get_environment_manager = original_get_environment_manager


async def _run_smoke_checks(qt_app) -> None:
    await _check_shell_structure(qt_app)
    print("Loading DashboardPage data...")
    await _check_dashboard_refresh()


def test_ui_instantiation() -> int:
    print("Initializing QApplication...")
    try:
        from PyQt6.QtWidgets import QApplication

        qt_app = QApplication.instance() or QApplication(sys.argv)
    except Exception as exc:
        print(f"FAILED to init QApplication: {exc}")
        return 1

    try:
        import qasync
    except Exception as exc:
        print(f"FAILED to import qasync: {exc}")
        return 1

    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    try:
        with loop:
            loop.run_until_complete(_run_smoke_checks(qt_app))
    except Exception as exc:
        print(f"FAILED to run UI smoke checks: {exc}")
        import traceback

        traceback.print_exc()
        return 1

    qt_app.quit()
    print("Smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(test_ui_instantiation())
