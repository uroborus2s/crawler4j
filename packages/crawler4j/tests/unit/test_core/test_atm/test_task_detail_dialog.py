from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from crawler4j_contracts import EnvAction, TaskSignal

from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)


def _build_job() -> Job:
    return Job(id="job-1", name="Demo Job")


def _build_waiting_task() -> Task:
    return Task(
        id="task-1",
        job_id="job-1",
        status=TaskStatus.WAITING_CONFIRMATION,
        message="等待人工确认",
        signal=TaskSignal.wait_for_confirmation(
            message="等待人工确认",
            env_action=EnvAction.KEEP_ALIVE,
            payload={
                "confirmation": {
                    "title": "账号复核",
                    "description": "请确认该账号是否允许继续执行。",
                    "fields": [
                        {"label": "账号", "value": "demo-account"},
                        {"label": "风险等级", "value": "high"},
                    ],
                    "confirm_text": "确认放行",
                    "reject_text": "确认拦截",
                }
            },
        ).to_dict(),
    )


def test_task_confirmation_dialog_renders_structured_payload(qtbot):
    from src.core.atm.ui.task_confirmation_dialog import TaskConfirmationDialog

    dialog = TaskConfirmationDialog(_build_waiting_task())
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "账号复核"
    assert dialog.title_label.text() == "账号复核"
    assert "请确认该账号是否允许继续执行" in dialog.description_label.text()
    assert dialog.details_table.rowCount() == 2
    assert dialog.details_table.item(0, 0).text() == "账号"
    assert dialog.details_table.item(0, 1).text() == "demo-account"
    assert dialog.confirm_btn.text() == "确认放行"
    assert dialog.reject_btn.text() == "确认拦截"


@pytest.mark.asyncio
async def test_job_detail_dialog_presents_waiting_confirmation_task(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    service = SimpleNamespace(
        get_job=AsyncMock(return_value=_build_job()),
        list_tasks=AsyncMock(return_value=[_build_waiting_task()]),
    )
    shown_task_ids: list[str] = []

    monkeypatch.setattr(dialog_module, "get_task_service", lambda: service)
    monkeypatch.setattr(
        dialog_module.asyncio,
        "create_task",
        lambda coro: (coro.close(), SimpleNamespace())[1],
    )
    monkeypatch.setattr(
        dialog_module.JobDetailDialog,
        "_present_confirmation_task",
        lambda self, task: shown_task_ids.append(task.id),
    )

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)

    await dialog._load_data_async()

    assert shown_task_ids == ["task-1"]


@pytest.mark.asyncio
async def test_job_detail_dialog_confirms_waiting_task_after_dialog_accept(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    task = _build_waiting_task()
    service = SimpleNamespace(
        get_job=AsyncMock(return_value=_build_job()),
        list_tasks=AsyncMock(return_value=[task]),
        confirm_task_success=AsyncMock(return_value=True),
        confirm_task_failure=AsyncMock(return_value=True),
    )

    class _FakeDialog:
        def __init__(self, task_obj, parent=None):
            self.task = task_obj
            self.parent = parent

        def exec(self):
            return dialog_module.QDialog.DialogCode.Accepted

        @property
        def confirmed(self) -> bool:
            return True

        def get_message(self) -> str:
            return "人工确认通过"

    monkeypatch.setattr(dialog_module, "get_task_service", lambda: service)
    monkeypatch.setattr(dialog_module.JobDetailDialog, "_load_data", lambda self: None)
    monkeypatch.setattr(dialog_module, "TaskConfirmationDialog", _FakeDialog)

    scheduled = []

    def _capture_create_task(coro):
        scheduled.append(coro)
        return SimpleNamespace()

    monkeypatch.setattr(dialog_module.asyncio, "create_task", _capture_create_task)

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)

    dialog._present_confirmation_task(task)

    assert scheduled
    await scheduled.pop(0)
    service.confirm_task_success.assert_awaited_once_with(task.id, "人工确认通过")


@pytest.mark.asyncio
async def test_job_detail_dialog_shows_resource_pool_binding(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    job = Job(
        id="job-1",
        name="Demo Job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    resource_pool="bound_account_ready",
                    wait_timeout=60,
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
    )
    service = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        list_tasks=AsyncMock(return_value=[]),
    )

    monkeypatch.setattr(dialog_module, "get_task_service", lambda: service)
    monkeypatch.setattr(
        dialog_module.asyncio,
        "create_task",
        lambda coro: (coro.close(), SimpleNamespace())[1],
    )

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)

    await dialog._load_data_async()

    assert "资源池: bound_account_ready" in dialog.config_text.toPlainText()
    assert "选择器: -" in dialog.config_text.toPlainText()


@pytest.mark.asyncio
async def test_job_detail_dialog_shows_timeout_reason_instead_of_waiting_message(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    timed_out_task = Task(
        id="task-timeout",
        job_id="job-1",
        status=TaskStatus.FAILED,
        message="",
        error="等待环境池工位超时: bound_account_ready (30s)",
    )
    service = SimpleNamespace(
        get_job=AsyncMock(return_value=_build_job()),
        list_tasks=AsyncMock(return_value=[timed_out_task]),
    )

    monkeypatch.setattr(dialog_module, "get_task_service", lambda: service)
    monkeypatch.setattr(
        dialog_module.asyncio,
        "create_task",
        lambda coro: (coro.close(), SimpleNamespace())[1],
    )

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)

    await dialog._load_data_async()

    assert dialog.task_table.displayed_rows()[0]["result"] == "等待环境池工位超时: bound_account_ready (30s)"


def test_job_detail_dialog_refreshes_on_task_failed_event(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    class _FakeEventBus:
        def __init__(self):
            self._handlers = {}

        def subscribe(self, event_type, handler):
            self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe(self, event_type, handler):
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        def publish(self, event):
            for handler in list(self._handlers.get(event.type, [])):
                handler(event)

    event_bus = _FakeEventBus()
    monkeypatch.setattr(dialog_module, "get_event_bus", lambda: event_bus)
    monkeypatch.setattr(
        dialog_module.asyncio,
        "create_task",
        lambda coro: (coro.close(), SimpleNamespace())[1],
    )

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)
    dialog._load_data = MagicMock()

    event_bus.publish(
        dialog_module.Event(
            type=dialog_module.EventType.TASK_FAILED,
            data={
                "job_id": "job-1",
                "task_id": "task-timeout",
                "error": "等待环境池工位超时: bound_account_ready (30s)",
            },
            task_run_id="task-timeout",
        )
    )

    dialog._load_data.assert_called_once_with()
