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


def test_task_list_widget_can_destroy_run_once_env_only_for_create_mode(qtbot, monkeypatch):
    _task_list_widget, widget = _build_widget(qtbot, monkeypatch)

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


def test_task_list_widget_stop_run_once_uses_public_choice_dialog(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)
    created_tasks = []
    selected_choices: list[tuple[str, list[str]]] = []

    def _fake_choose(parent, title, message, *, choices, detail="", cancel_text="取消"):
        assert parent is widget
        assert title == "中止任务"
        assert "manual-create" in message
        selected_choices.append((detail, [choice.id for choice in choices]))
        return "destroy"

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(task_list_widget.ChoiceDialog, "choose", _fake_choose)
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

    assert selected_choices == [
        ("保留环境会关闭环境但不删除；删除环境会删除本次创建的环境。", ["recycle", "destroy"])
    ]
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
    row = widget.table.displayed_rows()[0]
    stop_action = next(action for action in row["actions"] if action["id"] == "stop_run_once")

    assert row["status"]["text"] == "环境启动中"
    assert stop_action["label"] == "⏹ 中止"
    assert stop_action["enabled"] is True
    assert widget.startup_hint.isHidden() is False
    assert "manual-batch-starting" in widget.startup_hint_label.text()


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


def test_task_list_widget_run_once_locks_row_immediately(qtbot, monkeypatch):
    task_list_widget, widget = _build_widget(qtbot, monkeypatch)

    created_tasks = []

    def _fake_create_task(coro):
        created_tasks.append(coro)
        coro.close()
        return MagicMock()

    monkeypatch.setattr(task_list_widget.asyncio, "create_task", _fake_create_task)

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
    assert widget.startup_hint.isHidden() is False
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
    assert widget.startup_hint.isHidden() is False

    widget._run_once_requesting_job_ids.clear()
    widget._load_seq = 2
    await widget._load_data_async(2)

    assert job.id not in widget._pending_run_once_job_ids
    assert widget.table.displayed_rows()[0]["status"]["text"] == "已暂停"
    assert widget.startup_hint.isHidden() is True


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
