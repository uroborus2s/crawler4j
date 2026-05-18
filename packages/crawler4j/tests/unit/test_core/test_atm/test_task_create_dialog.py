from PyQt6.QtWidgets import QPushButton

from src.core.atm.models import Job, TriggerConfig, TriggerType
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.ui.components.button import StyledButton


def _make_run_profile() -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=45,
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
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


def test_task_create_dialog_keeps_inline_config_button_wide_enough(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)
    dialog._inline_run_profile = _make_run_profile()
    dialog._update_inline_preview()

    expected_min_width = max(
        220,
        dialog.inline_config_btn.fontMetrics().horizontalAdvance("重新编辑运行模板") + 48,
    )

    assert dialog.inline_config_btn.text() == "重新编辑运行模板"
    assert dialog.inline_config_btn.minimumWidth() >= expected_min_width
    assert dialog.inline_config_btn.minimumHeight() == 40


def test_task_create_dialog_uses_taller_primary_and_secondary_actions(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)

    buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}

    assert isinstance(dialog.inline_config_btn, StyledButton)
    assert isinstance(dialog.cancel_btn, StyledButton)
    assert isinstance(dialog.create_btn, StyledButton)
    assert buttons["配置运行模板"].minimumHeight() == 40
    assert buttons["取消"].minimumHeight() == 40
    assert buttons["创建"].minimumHeight() == 40
    assert buttons["取消"].minimumWidth() == 92
    assert buttons["创建"].minimumWidth() == 92


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


def test_task_create_dialog_preview_shows_candidates_for_select_mode(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                candidates="bound_account_ready",
                wait_timeout=45,
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
        ),
    )

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)
    dialog._inline_run_profile = run_profile
    dialog._update_inline_preview()

    assert "候选函数: bound_account_ready" in dialog.inline_preview.text()
    assert "选择器" not in dialog.inline_preview.text()


def test_task_create_dialog_preview_keeps_spacing_above_inline_button(qtbot):
    from src.core.atm.ui.task_create_dialog import TaskCreateDialog

    dialog = TaskCreateDialog()
    qtbot.addWidget(dialog)
    dialog._inline_run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                candidates="reuse_bound_account_env",
                wait_timeout=45,
            ),
        ),
        execution=ExecutionContext(
            module="ctrip_crawler",
            workflow="auto_strip_login_workflow",
        ),
    )
    dialog._update_inline_preview()
    dialog.show()
    qtbot.waitExposed(dialog)

    preview_bottom = dialog.inline_preview.geometry().bottom()
    button_top = dialog.inline_config_btn.geometry().top()

    assert button_top - preview_bottom >= 6
