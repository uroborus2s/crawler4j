from __future__ import annotations

from types import SimpleNamespace

from src.core.system.preferences_service import PREFERENCE_DEFAULTS, PreferenceKey
from src.ui.components.button import StyledButton
from src.ui.components.check_box import StyledCheckBox
from src.ui.components.line_edit import StyledLineEdit


class _MissingPreferences:
    def __init__(self):
        self.preference_changed = SimpleNamespace(connect=lambda _handler: None)

    def get(self, key, default=None):
        if key == PreferenceKey.VIRTUALBROWSER_PORT:
            return default
        if isinstance(key, PreferenceKey):
            return PREFERENCE_DEFAULTS.get(key, default)
        return default


def test_settings_page_uses_virtualbrowser_default_port_when_preference_is_missing(
    qtbot,
    monkeypatch,
):
    import src.core.system.ui.settings_page as settings_page_module

    monkeypatch.setattr(
        settings_page_module,
        "get_preferences_service",
        lambda: _MissingPreferences(),
    )

    page = settings_page_module.SettingsPage()
    qtbot.addWidget(page)

    assert PREFERENCE_DEFAULTS[PreferenceKey.VIRTUALBROWSER_PORT] == 9002
    assert page.virt_port_spin.value() == 9002


def test_settings_page_uses_public_form_controls(qtbot, monkeypatch):
    import src.core.system.ui.settings_page as settings_page_module

    monkeypatch.setattr(
        settings_page_module,
        "get_preferences_service",
        lambda: _MissingPreferences(),
    )

    page = settings_page_module.SettingsPage()
    qtbot.addWidget(page)

    assert isinstance(page.reset_btn, StyledButton)
    assert isinstance(page.autostart_check, StyledCheckBox)
    assert isinstance(page.minimize_check, StyledCheckBox)
    assert isinstance(page.auto_update_check, StyledCheckBox)
    assert isinstance(page.http_proxy_edit, StyledLineEdit)
    assert isinstance(page.bit_path_edit, StyledLineEdit)
    assert isinstance(page.virt_apikey_edit, StyledLineEdit)
    assert isinstance(page.virt_path_edit, StyledLineEdit)
