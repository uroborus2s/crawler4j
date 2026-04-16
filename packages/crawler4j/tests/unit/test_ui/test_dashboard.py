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
