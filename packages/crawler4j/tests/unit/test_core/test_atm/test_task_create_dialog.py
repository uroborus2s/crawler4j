from src.core.atm.models import Job, TriggerConfig, TriggerType
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    MatchConfig,
    ResourceConfig,
    RunProfile,
)


def _make_run_profile() -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                selector=MatchConfig(wait_timeout=45),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            hooks_module="demo_module.hooks",
        ),
    )


def test_task_create_dialog_returns_inline_run_profile_data(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("batch-demo")
    dialog.trigger_combo.setCurrentIndex(dialog.trigger_combo.findData(TriggerType.CRON.value))
    dialog.cron_edit.setText("0 * * * *")
    dialog._inline_run_profile = _make_run_profile()
    dialog._update_inline_preview()

    data = dialog.get_job_data()

    assert data["run_profile"]["execution"]["module"] == "demo_module"
    assert data["job_type"] == "batch"
    assert data["trigger_config"] == {"type": TriggerType.CRON.value, "cron_expr": "0 * * * *"}


def test_task_create_dialog_initializes_inline_job_mode(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    run_profile = _make_run_profile()
    job = Job(
        id="job-inline",
        name="inline-job",
        run_profile=run_profile,
        trigger=TriggerConfig(type=TriggerType.CRON, cron_expr="0 * * * *"),
    )

    dialog = TaskCreateDialog(job=job)
    qtbot.addWidget(dialog)

    assert "virtualbrowser" in dialog.inline_preview.text()
    data = dialog.get_job_data()
    assert data["run_profile"]["execution"]["workflow"] == "repair"
    assert data["trigger_config"]["type"] == TriggerType.CRON.value


def test_task_create_dialog_supports_manual_batch_trigger(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)
    dialog.name_edit.setText("batch-manual")
    dialog._inline_run_profile = _make_run_profile()
    dialog._update_inline_preview()

    data = dialog.get_job_data()

    assert data["job_type"] == "batch"
    assert data["trigger_config"] == {"type": TriggerType.MANUAL.value}
    assert dialog.trigger_combo.currentData() == TriggerType.MANUAL.value


def test_task_create_dialog_initializes_manual_batch_job_mode(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    run_profile = _make_run_profile()
    job = Job(
        id="job-manual",
        name="manual-job",
        run_profile=run_profile,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    dialog = TaskCreateDialog(job=job)
    qtbot.addWidget(dialog)

    assert dialog.type_combo.currentData() == "batch"
    assert dialog.trigger_combo.currentData() == TriggerType.MANUAL.value
    assert dialog.trigger_combo.currentText() == "执行一次"
    assert dialog.trigger_stack.currentIndex() == 0
