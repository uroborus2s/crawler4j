import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QScrollArea

from src.core.atm.models import Job
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    ExecutionContext,
    MatchConfig,
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
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                selector=MatchConfig(wait_timeout=90),
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
