from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton

from src.core.system.preferences_service import PREFERENCE_DEFAULTS, PreferenceKey
from src.ui.components.button import StyledButton


class _DummyPreferences:
    def __init__(self):
        self.preference_changed = SimpleNamespace(connect=lambda _handler: None)

    def get(self, _key, default=None):
        if isinstance(_key, PreferenceKey):
            return PREFERENCE_DEFAULTS.get(_key, default)
        return default


def test_settings_about_page_embeds_full_about_content_without_details_button(qtbot, monkeypatch):
    import src.core.system.ui.about_dialog as about_dialog_module
    import src.core.system.ui.settings_page as settings_page_module

    monkeypatch.setattr(settings_page_module, "get_preferences_service", lambda: _DummyPreferences())
    monkeypatch.setattr(
        about_dialog_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash=None)),
    )
    monkeypatch.setattr(
        about_dialog_module,
        "get_update_service",
        lambda: SimpleNamespace(check_for_updates=lambda: True, availability_reason=""),
    )
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_dialog_module, "load_app_icon_pixmap", lambda _size: pixmap)

    page = settings_page_module.SettingsPage()
    qtbot.addWidget(page)
    page.show()
    page.nav_list.setCurrentRow(3)

    about_page = page._pages["about"]
    label_texts = {label.text() for label in about_page.findChildren(QLabel)}
    button_texts = {button.text() for button in about_page.findChildren(QPushButton)}

    assert "蛛行演略 · crawler4j" in label_texts
    assert "v0.2.0" in label_texts
    assert "Development Build" in label_texts
    assert "关于" not in label_texts
    assert any(about_dialog_module.DOCS_URL in text for text in label_texts)
    assert "🔍 检查更新" in button_texts
    assert "📋 完整信息" not in button_texts
    assert isinstance(about_page.findChild(StyledButton), StyledButton)
    assert page.reset_btn.isHidden()


def test_about_dialog_still_provides_full_content(qtbot, monkeypatch):
    import src.core.system.ui.about_dialog as about_dialog_module

    monkeypatch.setattr(
        about_dialog_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash=None)),
    )
    monkeypatch.setattr(
        about_dialog_module,
        "get_update_service",
        lambda: SimpleNamespace(check_for_updates=lambda: True, availability_reason=""),
    )
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_dialog_module, "load_app_icon_pixmap", lambda _size: pixmap)

    dialog = about_dialog_module.AboutDialog()
    qtbot.addWidget(dialog)

    label_texts = {label.text() for label in dialog.findChildren(QLabel)}
    button_texts = {button.text() for button in dialog.findChildren(QPushButton)}

    assert dialog.windowTitle() == "关于 蛛行演略"
    assert "蛛行演略 · crawler4j" in label_texts
    assert any(about_dialog_module.DOCS_URL in text for text in label_texts)
    assert "🔍 检查更新" in button_texts
    assert isinstance(dialog.findChild(StyledButton), StyledButton)
