from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.atm.models import Job, JobState, JobType, TriggerConfig, TriggerType


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
    )

    table = widget.table.table
    table.setRowCount(1)
    widget._render_row(0, item, table)

    assert table.item(0, 5).text() == "执行中"

    action_widget = table.cellWidget(0, 6)
    buttons = action_widget.findChildren(task_list_widget.QPushButton)
    run_button = next(button for button in buttons if button.text() == "⏳ 执行中")

    assert run_button.isEnabled() is False


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
    )
    monkeypatch.setattr(task_list_widget, "get_task_service", lambda: service)

    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)
    widget._pending_run_once_job_ids.add(job.id)
    widget._run_once_requesting_job_ids.add(job.id)

    widget._load_seq = 1
    await widget._load_data_async(1)
    assert job.id in widget._pending_run_once_job_ids
    assert widget.table.table.item(0, 5).text() == "执行中"

    widget._run_once_requesting_job_ids.clear()
    widget._load_seq = 2
    await widget._load_data_async(2)

    assert job.id not in widget._pending_run_once_job_ids
    assert widget.table.table.item(0, 5).text() == "已暂停"
