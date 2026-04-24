from __future__ import annotations

from types import SimpleNamespace

from src.core.system.preferences_service import PREFERENCE_DEFAULTS, PreferenceKey


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
