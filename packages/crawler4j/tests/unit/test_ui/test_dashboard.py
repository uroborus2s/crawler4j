import asyncio
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QSizePolicy

from src.ui.components.button import StyledButton
from src.ui.components.stat_card import StatCard


def test_dashboard_compresses_summary_area_for_log_console(qtbot, monkeypatch):
    import src.ui.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module.DashboardPage, "_setup_timer", lambda self: None)

    page = dashboard_module.DashboardPage()
    page.resize(1600, 900)
    page._apply_card_layout()
    qtbot.addWidget(page)

    layout = page.layout()
    margins = layout.contentsMargins()

    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (20, 20, 20, 20)
    assert layout.spacing() == 16
    assert isinstance(page.running_card, StatCard)
    assert page.cards_grid.itemAtPosition(0, 0).widget() is page.running_card
    assert page.cards_grid.itemAtPosition(0, 5).widget() is page.modules_card
    assert page.cards_grid.itemAtPosition(1, 0) is None
    assert page.running_card.minimumHeight() == 76
    assert page.running_card.maximumHeight() == 84
    assert page.log_console.minimumHeight() == 520
    assert page.log_console.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding


def test_dashboard_keeps_single_row_summary_on_narrow_width(qtbot, monkeypatch):
    import src.ui.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module.DashboardPage, "_setup_timer", lambda self: None)

    page = dashboard_module.DashboardPage()
    page.resize(900, 700)
    page._apply_card_layout()
    qtbot.addWidget(page)

    assert page.cards_grid.itemAtPosition(0, 0).widget() is page.running_card
    assert page.cards_grid.itemAtPosition(0, 2).widget() is page.failed_card
    assert page.cards_grid.itemAtPosition(0, 3).widget() is page.env_ready_card
    assert page.cards_grid.itemAtPosition(0, 5).widget() is page.modules_card
    assert page.cards_grid.itemAtPosition(1, 0) is None


def test_dashboard_uses_public_refresh_button(qtbot, monkeypatch):
    import src.ui.dashboard as dashboard_module

    monkeypatch.setattr(dashboard_module.DashboardPage, "_setup_timer", lambda self: None)

    page = dashboard_module.DashboardPage()
    qtbot.addWidget(page)

    assert isinstance(page.refresh_btn, StyledButton)


@pytest.mark.asyncio
async def test_dashboard_load_data_ignores_stale_results_from_cancelled_refresh(qtbot, monkeypatch):
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
            try:
                await first_call_gate.wait()
            except asyncio.CancelledError:
                pass
            return [
                SimpleNamespace(state=dashboard_module.JobState.COMPLETED),
                SimpleNamespace(state=dashboard_module.JobState.COMPLETED),
            ]
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

    first_call_gate.set()

    await second_task
    await first_task
    await asyncio.sleep(0)

    assert call_count == 2
    assert page._load_task is None
    assert page.running_card.value_label.text() == "1"
    assert page.completed_card.value_label.text() == "0"
    assert page.failed_card.value_label.text() == "1"
    assert page.env_ready_card.value_label.text() == "1"
    assert page.env_busy_card.value_label.text() == "1"
    assert page.modules_card.value_label.text() == "2"
