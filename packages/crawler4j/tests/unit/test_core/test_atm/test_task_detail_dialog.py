from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.ui.components.button import StyledButton
from src.ui.components.text_edit import StyledTextEdit


def _build_job() -> Job:
    return Job(id="job-1", name="Demo Job")


def test_job_detail_dialog_uses_public_detail_controls(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    monkeypatch.setattr(dialog_module.JobDetailDialog, "_load_data", lambda self: None)

    dialog = dialog_module.JobDetailDialog("job-1")
    qtbot.addWidget(dialog)

    assert isinstance(dialog.debug_btn, StyledButton)
    assert isinstance(dialog.config_text, StyledTextEdit)


@pytest.mark.asyncio
async def test_job_detail_dialog_shows_candidate_binding(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    job = Job(
        id="job-1",
        name="Demo Job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    candidates="bound_account_ready",
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

    assert "候选函数: bound_account_ready" in dialog.config_text.toPlainText()
    assert "选择器" not in dialog.config_text.toPlainText()


@pytest.mark.asyncio
async def test_job_detail_dialog_shows_fixed_env_binding(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    job = Job(
        id="job-1",
        name="Demo Job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    env_id=21,
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

    assert "指定环境: 21" in dialog.config_text.toPlainText()
    assert "候选函数" not in dialog.config_text.toPlainText()


@pytest.mark.asyncio
async def test_job_detail_dialog_shows_timeout_reason_instead_of_waiting_message(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as dialog_module

    timed_out_task = Task(
        id="task-timeout",
        job_id="job-1",
        status=TaskStatus.FAILED,
        message="",
        error="等待环境候选超时: bound_account_ready (30s)",
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

    assert dialog.task_table.displayed_rows()[0]["result"] == "等待环境候选超时: bound_account_ready (30s)"


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
                "error": "等待环境候选超时: bound_account_ready (30s)",
            },
            task_run_id="task-timeout",
        )
    )

    dialog._load_data.assert_called_once_with()
