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


def _build_widget(qtbot, monkeypatch):
    import src.core.atm.ui.task_list_widget as task_list_widget

    monkeypatch.setattr(
        task_list_widget.QTimer,
        "singleShot",
        staticmethod(lambda *_args, **_kwargs: None),
    )
    widget = task_list_widget.TaskListWidget()
    qtbot.addWidget(widget)
    return task_list_widget, widget


def test_task_list_widget_declares_wide_actions_column(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    first_column = widget.TABLE_SCHEMA["columns"][0]
    name_column = next(column for column in widget.TABLE_SCHEMA["columns"] if column["key"] == "name")
    actions_column = next(column for column in widget.TABLE_SCHEMA["columns"] if column["key"] == "actions")

    assert first_column["key"] == "__index__"
    assert first_column["label"] == "序号"
    assert first_column["sortable"] is False
    assert name_column["width"] == 240
    assert name_column.get("stretch", False) is False
    assert actions_column["stretch"] is True
    assert task_list_widget.TaskListWidget.TABLE_SCHEMA["features"]["pagination"]["enabled"] is True
    assert task_list_widget.TaskListWidget.TABLE_SCHEMA["features"]["loading"] == {
        "inline": False,
        "disable_interaction": False,
    }


def test_task_list_widget_uses_dialog_only_for_run_progress_not_inline_table_bar(qtbot, monkeypatch):
    _task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    widget.table.set_loading(True)

    assert widget.table.loading_bar.isHidden() is True
    assert widget.table.table.isEnabled() is True


def test_task_list_widget_renders_manual_batch_run_once_button(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    job = Job(
        id="job-manual",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    widget._display_items = [
        task_list_widget.JobDisplayItem(
            raw=job,
            display_status_text="已暂停",
            display_status_color="#9ca3af",
        )
    ]

    widget._refresh_table()
    row = widget.table.displayed_rows()[0]
    button_texts = [action["label"] for action in row["actions"]]

    assert row["trigger"] == "手动执行一次"
    assert "▶ 执行一次" in button_texts
    assert "▶ 启动" not in button_texts


def test_task_list_widget_stop_run_once_uses_confirm_dialog(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)
    created_tasks = []
    prompts: list[tuple[str, str, str, bool]] = []

    def _fake_confirm(parent, title, message, *, confirm_text="确定", danger=False):
        assert parent is widget
        assert title == "中止任务"
        assert "manual-create" in message
        prompts.append((title, message, confirm_text, danger))
        return True

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(task_list_widget.ConfirmDialog, "confirm", _fake_confirm)
    monkeypatch.setattr(task_list_widget.asyncio, "create_task", _fake_create_task)

    job = Job(
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
    widget._jobs = [job]
    widget._display_items = [
        task_list_widget.JobDisplayItem(
            raw=job,
            display_status_text="执行中",
            display_status_color="#facc15",
            active_task_count=1,
            run_once_phase="running",
        )
    ]

    widget._stop_run_once("job-create")

    assert prompts == [("中止任务", "要中止“manual-create”这次手动执行吗？环境会统一关闭并回收。", "中止", True)]
    assert "job-create" in widget._run_once_stopping_job_ids
    assert created_tasks


def test_task_list_widget_renders_manual_batch_busy_button(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    job = Job(
        id="job-manual-busy",
        name="manual-batch-busy",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    widget._display_items = [
        task_list_widget.JobDisplayItem(
            raw=job,
            display_status_text="执行中",
            display_status_color=task_list_widget.TaskListWidget.STATUS_COLORS[JobState.ACTIVE],
            active_task_count=1,
            run_once_phase="running",
        )
    ]

    widget._refresh_table()
    row = widget.table.displayed_rows()[0]
    stop_action = next(action for action in row["actions"] if action["id"] == "stop_run_once")

    assert row["status"]["text"] == "执行中"
    assert stop_action["label"] == "⏹ 中止"
    assert stop_action["enabled"] is True


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
                "error": "等待环境候选超时: bound_account_ready (30s)",
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
    row = widget.table.displayed_rows()[0]
    stop_action = next(action for action in row["actions"] if action["id"] == "stop_run_once")

    assert row["status"]["text"] == "环境启动中"
    assert stop_action["label"] == "⏹ 中止"
    assert stop_action["enabled"] is True


def test_task_list_widget_renders_manual_batch_stopping_button(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    job = Job(
        id="job-manual-stopping",
        name="manual-batch-stopping",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    widget._display_items = [
        task_list_widget.JobDisplayItem(
            raw=job,
            display_status_text="中止中",
            display_status_color="#f97316",
            active_task_count=1,
            run_once_phase="stopping",
        )
    ]

    widget._refresh_table()
    row = widget.table.displayed_rows()[0]
    stop_action = next(action for action in row["actions"] if action["id"] == "stop_run_once")

    assert row["status"]["text"] == "中止中"
    assert stop_action["label"] == "⏹ 中止中"
    assert stop_action["enabled"] is False


def test_task_list_widget_refreshes_on_task_started_event():
    import src.core.atm.ui.task_list_widget as task_list_widget

    assert task_list_widget.EventType.TASK_STARTED in task_list_widget.TaskListWidget.REFRESH_EVENTS


def test_task_list_widget_run_once_locks_row_immediately(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    created_tasks = []
    published = []

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(task_list_widget.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(
        task_list_widget,
        "get_event_bus",
        lambda: SimpleNamespace(publish=published.append),
    )

    job = Job(
        id="job-manual",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
    )
    widget._jobs = [job]
    widget._display_items = [
        task_list_widget.JobDisplayItem(
            raw=job,
            display_status_text="已暂停",
            display_status_color="#9ca3af",
        )
    ]
    widget._refresh_table()

    widget._run_job_once("job-manual")
    row = widget.table.displayed_rows()[0]

    assert "job-manual" in widget._pending_run_once_job_ids
    assert "job-manual" in widget._run_once_requesting_job_ids
    assert created_tasks
    assert published
    assert published[0].type == task_list_widget.EventType.TASK_PROGRESS
    assert published[0].data["phase"] == "requesting"
    assert published[0].data["job_id"] == "job-manual"
    assert row["actions"][0]["label"] == "⏹ 中止"


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
    assert widget.table.displayed_rows()[0]["status"]["text"] == "环境启动中"

    widget._run_once_requesting_job_ids.clear()
    widget._load_seq = 2
    await widget._load_data_async(2)

    assert job.id not in widget._pending_run_once_job_ids
    assert widget.table.displayed_rows()[0]["status"]["text"] == "已暂停"


@pytest.mark.asyncio
async def test_task_list_widget_run_once_failure_uses_async_warning_dialog(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    warning_async = AsyncMock(return_value=0)
    warning_sync = MagicMock(side_effect=AssertionError("sync warning dialog should not be used"))
    service = SimpleNamespace(run_job_once=AsyncMock(return_value=False))

    monkeypatch.setattr(task_list_widget, "get_task_service", lambda: service)
    monkeypatch.setattr(task_list_widget.MessageDialog, "warning_async", warning_async)
    monkeypatch.setattr(task_list_widget.MessageDialog, "warning", warning_sync)

    widget.load_data = MagicMock()
    widget._refresh_table = MagicMock()
    widget._jobs = [
        Job(
            id="job-manual",
            name="manual-batch",
            type=JobType.BATCH,
            state=JobState.PAUSED,
            trigger=TriggerConfig(type=TriggerType.MANUAL),
        )
    ]
    widget._pending_run_once_job_ids.add("job-manual")
    widget._run_once_requesting_job_ids.add("job-manual")

    await widget._async_op("job-manual", "run_once")

    service.run_job_once.assert_awaited_once_with("job-manual")
    warning_async.assert_awaited_once_with(widget, "操作失败", "执行失败，请确认当前没有未结束的批次任务且运行模板可用。")
    warning_sync.assert_not_called()
    widget.load_data.assert_called_once_with()
    assert "job-manual" not in widget._pending_run_once_job_ids
    assert "job-manual" not in widget._run_once_requesting_job_ids


@pytest.mark.asyncio
async def test_task_list_widget_stop_run_once_failure_uses_async_warning_dialog(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    warning_async = AsyncMock(return_value=0)
    warning_sync = MagicMock(side_effect=AssertionError("sync warning dialog should not be used"))
    service = SimpleNamespace(stop_run_once=AsyncMock(return_value=False))

    monkeypatch.setattr(task_list_widget, "get_task_service", lambda: service)
    monkeypatch.setattr(task_list_widget.MessageDialog, "warning_async", warning_async)
    monkeypatch.setattr(task_list_widget.MessageDialog, "warning", warning_sync)

    widget.load_data = MagicMock()
    widget._refresh_table = MagicMock()
    widget._run_once_stopping_job_ids.add("job-manual")

    await widget._async_stop_run_once("job-manual")

    service.stop_run_once.assert_awaited_once_with("job-manual")
    warning_async.assert_awaited_once_with(widget, "中止失败", "当前没有可中止的批次任务，或任务已经结束。")
    warning_sync.assert_not_called()
    widget.load_data.assert_called_once_with()
    assert "job-manual" not in widget._run_once_stopping_job_ids


def test_task_list_widget_row_click_opens_detail_dialog(qtbot, monkeypatch):
    import src.core.atm.ui.task_detail_dialog as detail_dialog_module

    _task_list_widget, widget = _build_widget(qtbot, monkeypatch)
    opened_job_ids: list[str] = []
    selected_job_ids: list[str] = []

    class _FakeDialog:
        def __init__(self, job_id, parent=None):
            assert parent is widget
            opened_job_ids.append(job_id)

        def exec(self):
            return 0

    monkeypatch.setattr(detail_dialog_module, "JobDetailDialog", _FakeDialog)
    widget.task_selected.connect(selected_job_ids.append)

    widget._on_table_row_clicked({"job_id": "job-42"})

    assert selected_job_ids == ["job-42"]
    assert opened_job_ids == ["job-42"]


def test_task_list_widget_numbers_rows_across_pages(qtbot, monkeypatch):
    _task_list_widget, widget = _build_widget(qtbot, monkeypatch)
    widget._table_rows = [
        {
            "job_id": f"job-{index}",
            "name": f"job-{index}",
            "type": "批次任务",
            "runtime": {"text": "demo"},
            "concurrency": {"text": "1", "sort_value": 1},
            "trigger": "手动执行一次",
            "status": {"text": "已暂停", "tone": "neutral"},
            "actions": [],
        }
        for index in range(1, 5)
    ]

    widget.table.set_query({"search_text": "", "sort": [], "page": 2, "page_size": 2})
    widget.table.request_refresh()

    rows = widget.table.displayed_rows()

    assert [row["__index__"]["text"] for row in rows] == ["3", "4"]
