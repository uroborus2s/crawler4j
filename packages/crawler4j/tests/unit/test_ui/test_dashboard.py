import asyncio
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QSizePolicy


def test_dashboard_compresses_summary_area_for_log_console(qtbot, monkeypatch):
    import src.ui.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module.DashboardPage, "_setup_timer", lambda self: None)

    page = dashboard_module.DashboardPage()
    qtbot.addWidget(page)

    layout = page.layout()
    margins = layout.contentsMargins()

    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (20, 20, 20, 20)
    assert layout.spacing() == 16
    assert page.running_card.minimumHeight() == 96
    assert page.running_card.maximumHeight() == 108
    assert page.log_console.minimumHeight() == 320
    assert page.log_console.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding


@pytest.mark.asyncio
async def test_dashboard_load_data_cancels_previous_pending_refresh(qtbot, monkeypatch):
    import src.ui.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module.DashboardPage, "_setup_timer", lambda self: None)
    monkeypatch.setattr(
        dashboard_module,
        "get_module_registry",
        lambda: SimpleNamespace(
            list_modules=lambda: [
                SimpleNamespace(status=dashboard_module.ModuleStatus.ENABLED),
                SimpleNamespace(status=dashboard_module.ModuleStatus.DISABLED),
            ]
        ),
    )
    monkeypatch.setattr(
        "src.core.rem.manager.get_environment_manager",
        lambda: SimpleNamespace(
            pool=SimpleNamespace(
                _environments={
                    "ready": SimpleNamespace(status=dashboard_module.EnvStatus.READY),
                    "busy": SimpleNamespace(status=dashboard_module.EnvStatus.BUSY),
                }
            )
        ),
    )

    first_call_gate = asyncio.Event()
    call_count = 0

    async def fake_list_jobs():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await first_call_gate.wait()
        return [
            SimpleNamespace(state=dashboard_module.JobState.ACTIVE),
            SimpleNamespace(state=dashboard_module.JobState.ERROR),
        ]

    monkeypatch.setattr(
        dashboard_module,
        "get_task_service",
        lambda: SimpleNamespace(list_jobs=fake_list_jobs),
    )

    page = dashboard_module.DashboardPage()
    qtbot.addWidget(page)

    page.load_data()
    await asyncio.sleep(0)
    first_task = page._load_task
    assert first_task is not None
    assert first_task.done() is False

    page.load_data()
    await asyncio.sleep(0)
    second_task = page._load_task
    assert second_task is not None
    assert second_task is not first_task

    with pytest.raises(asyncio.CancelledError):
        await first_task

    await second_task
    await asyncio.sleep(0)

    assert call_count == 2
    assert page._load_task is None
    assert page.running_card.value_label.text() == "1"
    assert page.failed_card.value_label.text() == "1"
    assert page.env_ready_card.value_label.text() == "1"
    assert page.env_busy_card.value_label.text() == "1"
    assert page.modules_card.value_label.text() == "2"
