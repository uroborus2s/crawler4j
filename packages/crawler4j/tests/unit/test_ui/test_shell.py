from types import SimpleNamespace


def test_shell_defaults_to_1420px_startup_width(qtbot, monkeypatch):
    import src.ui.shell as shell_module

    monkeypatch.setattr(shell_module.Shell, "_setup_ui", lambda self: None)
    monkeypatch.setattr(shell_module.Shell, "_register_pages", lambda self: None)
    monkeypatch.setattr(shell_module.Shell, "_subscribe_events", lambda self: None)

    fake_geometry = SimpleNamespace(width=lambda: 1600, height=lambda: 1000)
    fake_screen = SimpleNamespace(availableGeometry=lambda: fake_geometry)
    monkeypatch.setattr(shell_module.QApplication, "primaryScreen", lambda: fake_screen)

    window = shell_module.Shell()
    qtbot.addWidget(window)

    assert window.minimumWidth() == 1200
    assert window.width() == 1420
    assert window.height() == 800


def test_sidebar_includes_help_entry():
    from src.ui.shell import Sidebar

    assert ("help", "📘 使用文档") in Sidebar.NAV_ITEMS
