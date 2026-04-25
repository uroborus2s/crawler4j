import inspect
import json
from unittest.mock import AsyncMock
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QScrollArea

from src.core.atm.models import Job
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.core.debug.models import DebugSession, DebugSessionRequest, DebugSessionState
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource


def _make_job() -> Job:
    return Job(
        id="job-1",
        name="Demo Job",
        run_profile=_make_run_profile(),
        params={"city": "Shanghai"},
    )


def _make_run_profile() -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=90,
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.EPHEMERAL,
                    params={"region": "cn"},
                ),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            hooks_module="demo_module.hooks",
            params={"lang": "zh-CN"},
            timeout=180,
        ),
    )


def _make_module(tmp_path: Path) -> ModuleInfo:
    module_dir = tmp_path / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module", display_name="Demo Module"),
        source=ModuleSource.DEV_LINK,
        path=module_dir,
    )


def _make_session(tmp_path: Path, *, logs: list[str], state: DebugSessionState = DebugSessionState.RUNNING) -> DebugSession:
    return DebugSession(
        id="session-logs",
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=5678,
        state=state,
        logs=logs,
    )


def test_job_debug_dialog_builds_request_from_form(qtbot, tmp_path):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)

    page.attach_port_spin.setValue(6789)
    page.timeout_spin.setValue(240)
    page.wait_for_attach_checkbox.setChecked(False)
    page.stop_on_entry_checkbox.setChecked(True)
    page.keep_environment_checkbox.setChecked(True)
    page.params_editor.setPlainText(json.dumps({"lang": "en", "city": "Paris"}, ensure_ascii=False))

    request = page.build_request()

    assert isinstance(request, DebugSessionRequest)
    assert request.job_id == "job-1"
    assert request.attach_port == 6789
    assert request.timeout == 240
    assert request.wait_for_attach is False
    assert request.stop_on_entry is True
    assert request.keep_environment is True
    assert request.params == {"lang": "en", "city": "Paris"}


def test_job_debug_dialog_copies_attach_address(qtbot, tmp_path):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)

    session = DebugSession(
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=5678,
        state=DebugSessionState.WAITING_FOR_ATTACH,
    )
    page._apply_session(session)
    page.copy_attach_address()

    assert QApplication.clipboard().text() == "127.0.0.1:5678"


def test_job_debug_dialog_generate_vscode_config_uses_active_session_attach_target(
    qtbot,
    tmp_path,
    monkeypatch,
):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)
    page.attach_port_spin.setValue(5678)

    session = DebugSession(
        id="session-1",
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=5679,
        state=DebugSessionState.WAITING_FOR_ATTACH,
    )
    page._current_session_id = session.id
    page._apply_session(session)

    captured: dict[str, object] = {}

    def fake_ensure(source_path, *, host, port, configuration_name="Attach to Crawler4j"):
        captured["source_path"] = source_path
        captured["host"] = host
        captured["port"] = port
        captured["configuration_name"] = configuration_name
        return Path(source_path) / ".vscode" / "launch.json"

    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.ensure_vscode_attach_config", fake_ensure)
    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.MessageDialog.information", lambda *args: None)
    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.MessageDialog.warning", lambda *args: None)

    page.generate_vscode_config()

    assert captured["source_path"] == page._module.path
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 5679


def test_job_debug_dialog_generate_vscode_config_ignores_final_session_attach_target(
    qtbot,
    tmp_path,
    monkeypatch,
):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)
    page.attach_port_spin.setValue(5680)

    session = DebugSession(
        id="session-2",
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=5679,
        state=DebugSessionState.FAILED,
    )
    page._current_session_id = session.id
    page._apply_session(session)

    captured: dict[str, object] = {}

    def fake_ensure(source_path, *, host, port, configuration_name="Attach to Crawler4j"):
        captured["source_path"] = source_path
        captured["host"] = host
        captured["port"] = port
        captured["configuration_name"] = configuration_name
        return Path(source_path) / ".vscode" / "launch.json"

    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.ensure_vscode_attach_config", fake_ensure)
    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.MessageDialog.information", lambda *args: None)
    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.MessageDialog.warning", lambda *args: None)

    page.generate_vscode_config()

    assert captured["source_path"] == page._module.path
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 5680


def test_job_debug_dialog_uses_dark_theme_controls(qtbot, tmp_path):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog
    from src.ui.components.spin_box import StyledSpinBox

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)

    assert isinstance(page.attach_port_spin, StyledSpinBox)
    assert isinstance(page.timeout_spin, StyledSpinBox)
    assert isinstance(page.scroll_area, QScrollArea)
    assert page.scroll_area.widgetResizable() is True
    assert "#1a1b26" in page.styleSheet()
    assert "QCheckBox::indicator" in page.styleSheet()
    assert page.close_btn.text() == "关闭"
    screen = page.screen() or QApplication.primaryScreen()
    if screen is not None:
        assert page.maximumHeight() <= screen.availableGeometry().height()


def test_job_debug_dialog_run_async_skips_when_no_event_loop(qtbot, tmp_path, monkeypatch):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)

    async def sample():
        return None

    coro = sample()
    monkeypatch.setattr(
        "src.core.atm.ui.task_debug_dialog.asyncio.get_running_loop",
        lambda: (_ for _ in ()).throw(RuntimeError()),
    )

    page._run_async(coro)

    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED


def test_job_debug_dialog_restart_uses_current_form_values(qtbot, tmp_path, monkeypatch):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    old_session = DebugSession(
        id="session-old",
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=5678,
        stop_on_entry=False,
        state=DebugSessionState.STOPPED,
    )
    new_session = DebugSession(
        id="session-new",
        job_id="job-1",
        job_name="Demo Job",
        module_name="demo_module",
        source_path=str(tmp_path / "demo_module"),
        workflow="repair",
        attach_host="127.0.0.1",
        attach_port=6789,
        stop_on_entry=True,
        state=DebugSessionState.CREATED,
    )

    debug_service = SimpleNamespace(
        stop_session=AsyncMock(return_value=True),
        restart_session=AsyncMock(),
        create_session=AsyncMock(return_value=new_session),
        start_session=AsyncMock(return_value=new_session),
    )

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=debug_service,
    )
    qtbot.addWidget(page)
    page._current_session_id = old_session.id
    page._apply_session(old_session)
    page.attach_port_spin.setValue(6789)
    page.stop_on_entry_checkbox.setChecked(True)
    monkeypatch.setattr(page, "_refresh", AsyncMock())
    monkeypatch.setattr("src.core.atm.ui.task_debug_dialog.MessageDialog.warning", lambda *args: None)

    import asyncio

    asyncio.run(page._restart_debug())

    debug_service.stop_session.assert_awaited_once_with(old_session.id)
    debug_service.restart_session.assert_not_called()
    debug_service.create_session.assert_awaited_once()
    request = debug_service.create_session.await_args.args[0]
    assert isinstance(request, DebugSessionRequest)
    assert request.attach_port == 6789
    assert request.stop_on_entry is True
    debug_service.start_session.assert_awaited_once_with(new_session.id)
    assert page._current_session_id == new_session.id


def test_job_debug_dialog_preserves_logs_scroll_position_when_content_is_unchanged(qtbot, tmp_path):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)
    page.resize(960, 640)
    page.logs_view.setFixedHeight(120)
    page.show()

    session = _make_session(tmp_path, logs=[f"log line {i}" for i in range(80)])
    page._apply_session(session)
    QApplication.processEvents()

    scrollbar = page.logs_view.verticalScrollBar()
    assert scrollbar.maximum() > 0

    target_value = scrollbar.maximum() // 2
    scrollbar.setValue(target_value)
    QApplication.processEvents()

    page._apply_session(session)
    QApplication.processEvents()

    assert page.logs_view.verticalScrollBar().value() == target_value


def test_job_debug_dialog_auto_scrolls_logs_when_user_is_following_latest_output(qtbot, tmp_path):
    from src.core.atm.ui.task_debug_dialog import JobDebugDialog

    page = JobDebugDialog(
        _make_job(),
        _make_run_profile(),
        _make_module(tmp_path),
        debug_service=SimpleNamespace(),
    )
    qtbot.addWidget(page)
    page.resize(960, 640)
    page.logs_view.setFixedHeight(120)
    page.show()

    page._apply_session(_make_session(tmp_path, logs=[f"log line {i}" for i in range(80)]))
    QApplication.processEvents()

    scrollbar = page.logs_view.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    QApplication.processEvents()

    page._apply_session(_make_session(tmp_path, logs=[f"log line {i}" for i in range(100)]))
    QApplication.processEvents()

    new_scrollbar = page.logs_view.verticalScrollBar()
    assert new_scrollbar.value() == new_scrollbar.maximum()
