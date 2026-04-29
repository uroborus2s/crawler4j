from PyQt6.QtWidgets import QWidget

from src.core.foundation.event_bus import Event, EventType


def test_task_progress_presenter_shows_starting_task_and_closes_on_started(qtbot):
    import src.core.atm.ui.task_progress_presenter as presenter_module

    parent = QWidget()
    qtbot.addWidget(parent)

    presenter = presenter_module.TaskProgressPresenter(parent, subscribe=False)

    presenter._on_task_progress(
        Event(
            type=EventType.TASK_PROGRESS,
            task_run_id="task-1",
            data={
                "phase": "environment_starting",
                "task_id": "task-1",
                "job_id": "job-1",
                "job_name": "携程数据采集",
            },
        )
    )

    assert presenter._progress_dialog is not None
    assert presenter._progress_dialog.windowTitle() == "任务进度"
    assert "携程数据采集" in presenter._progress_dialog.message_label.text()
    assert "环境启动中" in presenter._progress_dialog.message_label.text()

    presenter._on_task_started(
        Event(
            type=EventType.TASK_STARTED,
            task_run_id="task-1",
            data={
                "task_id": "task-1",
                "job_id": "job-1",
            },
        )
    )

    assert presenter._progress_dialog is None


def test_task_progress_presenter_tracks_import_queue_until_drained(qtbot):
    from src.core.atm.ui.task_progress_presenter import TaskProgressPresenter

    parent = QWidget()
    qtbot.addWidget(parent)

    presenter = TaskProgressPresenter(parent, subscribe=False)

    presenter._on_task_progress(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "phase": "queued",
                "job_id": "job-import",
                "job_name": "携程数据采集",
                "queued_count": 2,
            },
        )
    )

    assert presenter._progress_dialog is not None
    assert "携程数据采集" in presenter._progress_dialog.message_label.text()
    assert "2 个环境排队等待并发窗口" in presenter._progress_dialog.message_label.text()

    presenter._on_task_progress(
        Event(
            type=EventType.TASK_PROGRESS,
            data={
                "phase": "queued",
                "job_id": "job-import",
                "job_name": "携程数据采集",
                "queued_count": 0,
            },
        )
    )

    assert presenter._progress_dialog is None
