from src.core.atm.models import Job, JobState, JobType, TriggerConfig, TriggerType


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
