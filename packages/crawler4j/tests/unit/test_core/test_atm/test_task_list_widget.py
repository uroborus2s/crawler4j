from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.atm.models import Job, JobState, JobType, Task, TaskStatus, TriggerConfig, TriggerType
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)


def test_task_list_widget_uses_wider_actions_column(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    assert widget.table.table.columnWidth(6) == 240


def test_task_list_widget_renders_manual_batch_run_once_button(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    job = Job(
        id="job-manual",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    item = task_list_widget.JobDisplayItem(
        raw=job,
        display_status_text="已暂停",
        display_status_color="#9ca3af",
    )

    table = widget.table.table
    table.setRowCount(1)
    widget._render_row(0, item, table)

    assert table.item(0, 4).text() == "手动执行一次"

    action_widget = table.cellWidget(0, 6)
    button_texts = [button.text() for button in action_widget.findChildren(task_list_widget.QPushButton)]

    assert "▶ 执行一次" in button_texts
    assert "▶ 启动" not in button_texts


def test_task_list_widget_can_destroy_run_once_env_only_for_create_mode(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    create_job = Job(
        id="job-create",
        name="manual-create",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.CREATE,
                    creation=CreationConfig(params={"groups": ["default"]}),
                )
            ),
            execution=ExecutionContext(module="demo_module"),
        ),
    )
    select_job = Job(
        id="job-select",
        name="manual-select",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    selector_name="pick_ready",
                )
            ),
            execution=ExecutionContext(module="demo_module"),
        ),
    )

    assert widget._can_destroy_run_once_env(create_job) is True
    assert widget._can_destroy_run_once_env(select_job) is False


def test_task_list_widget_renders_manual_batch_busy_button(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    job = Job(
        id="job-manual-busy",
        name="manual-batch-busy",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    item = task_list_widget.JobDisplayItem(
        raw=job,
        display_status_text="执行中",
        display_status_color=task_list_widget.TaskListWidget.STATUS_COLORS[JobState.ACTIVE],
        active_task_count=1,
        run_once_phase="running",
    )

    table = widget.table.table
    table.setRowCount(1)
    widget._render_row(0, item, table)

    assert table.item(0, 5).text() == "执行中"

    action_widget = table.cellWidget(0, 6)
    buttons = action_widget.findChildren(task_list_widget.QPushButton)
    run_button = next(button for button in buttons if button.text() == "⏹ 中止")

    assert run_button.isEnabled() is True


def test_task_list_widget_refreshes_on_task_failed_event(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

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
    monkeypatch.setattr(task_list_widget, "get_event_bus", lambda: event_bus)
    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()

    event_bus.publish(
        task_list_widget.Event(
            type=task_list_widget.EventType.TASK_FAILED,
            data={
                "job_id": "job-timeout",
                "task_id": "task-timeout",
                "error": "等待环境池工位超时: bound_account_ready (30s)",
            },
            task_run_id="task-timeout",
        )
    )

    widget.load_data.assert_called_once_with()


@pytest.mark.asyncio
async def test_task_list_widget_marks_pending_manual_batch_as_starting(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    job = Job(
        id="job-manual-starting",
        name="manual-batch-starting",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    service = SimpleNamespace(
        list_jobs=AsyncMock(return_value=[job]),
        count_active_tasks=AsyncMock(return_value=1),
        list_tasks=AsyncMock(
            return_value=[Task(id="task-pending", job_id=job.id, status=TaskStatus.PENDING)]
        ),
    )
    monkeypatch.setattr(task_list_widget, "get_task_service", lambda: service)

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    widget._load_seq = 1
    await widget._load_data_async(1)

    assert widget.table.table.item(0, 5).text() == "环境启动中"
    action_widget = widget.table.table.cellWidget(0, 6)
    buttons = action_widget.findChildren(task_list_widget.QPushButton)
    run_button = next(button for button in buttons if button.text() == "⏹ 中止")
    assert run_button.isEnabled() is True
    assert widget.startup_hint.isHidden() is False
    assert "manual-batch-starting" in widget.startup_hint_label.text()


def test_task_list_widget_renders_manual_batch_stopping_button(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    job = Job(
        id="job-manual-stopping",
        name="manual-batch-stopping",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    item = task_list_widget.JobDisplayItem(
        raw=job,
        display_status_text="中止中",
        display_status_color="#f97316",
        active_task_count=1,
        run_once_phase="stopping",
    )

    table = widget.table.table
    table.setRowCount(1)
    widget._render_row(0, item, table)

    assert table.item(0, 5).text() == "中止中"
    action_widget = table.cellWidget(0, 6)
    buttons = action_widget.findChildren(task_list_widget.QPushButton)
    stop_button = next(button for button in buttons if button.text() == "⏹ 中止中")
    assert stop_button.isEnabled() is False


def test_task_list_widget_run_once_locks_row_immediately(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    created_tasks = []

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(task_list_widget.asyncio, "create_task", _fake_create_task)

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)

    widget._run_job_once("job-manual")

    assert "job-manual" in widget._pending_run_once_job_ids
    assert "job-manual" in widget._run_once_requesting_job_ids
    assert created_tasks
    assert widget.startup_hint.isHidden() is False


@pytest.mark.asyncio
async def test_task_list_widget_clears_run_once_lock_after_active_tasks_clear(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )

    job = Job(
        id="job-manual",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    service = SimpleNamespace(
        list_jobs=AsyncMock(return_value=[job]),
        count_active_tasks=AsyncMock(side_effect=[0, 0]),
        list_tasks=AsyncMock(side_effect=[[], []]),
    )
    monkeypatch.setattr(task_list_widget, "get_task_service", lambda: service)

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)
    widget._pending_run_once_job_ids.add(job.id)
    widget._run_once_requesting_job_ids.add(job.id)

    widget._load_seq = 1
    await widget._load_data_async(1)
    assert job.id in widget._pending_run_once_job_ids
    assert widget.table.table.item(0, 5).text() == "环境启动中"
    assert widget.startup_hint.isHidden() is False

    widget._run_once_requesting_job_ids.clear()
    widget._load_seq = 2
    await widget._load_data_async(2)

    assert job.id not in widget._pending_run_once_job_ids
    assert widget.table.table.item(0, 5).text() == "已暂停"
    assert widget.startup_hint.isHidden() is True
