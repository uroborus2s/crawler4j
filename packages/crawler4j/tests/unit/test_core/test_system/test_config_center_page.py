from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from src.ui.components.button import StyledButton
from src.ui.components.check_box import ToggleSwitch
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.spin_box import StyledSpinBox


def test_config_center_page_renders_registered_config_items(qtbot, tmp_path: Path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        from src.core.system.ui.config_center_page import ConfigCenterPage

        page = ConfigCenterPage()
        qtbot.addWidget(page)

    assert "system" in page._domain_buttons
    assert "atm" in page._domain_buttons
    assert "browser.virtualbrowser.port" in page._field_widgets
    assert "atm.cleanup_hook_timeout_seconds" in page._field_widgets
    assert "system.autostart" not in page._field_widgets
    assert "system.minimize_on_start" not in page._field_widgets
    assert isinstance(page._field_widgets["system.auto_update"], ToggleSwitch)
    assert page._field_widgets["system.auto_update"].width() == 54
    assert page._field_widgets["system.auto_update"].minimumWidth() == 54
    assert isinstance(page._field_widgets["network.proxy_mode"], StyledComboBox)
    assert isinstance(page._field_widgets["browser.virtualbrowser.path"], StyledLineEdit)
    assert isinstance(page._field_widgets["atm.cleanup_hook_timeout_seconds"], StyledSpinBox)
    assert isinstance(page.reset_domain_btn, StyledButton)


def test_config_center_page_saves_changes_through_config_center(qtbot, tmp_path: Path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        from src.core.system.config_center import get_config_center
        from src.core.system.ui.config_center_page import ConfigCenterPage

        page = ConfigCenterPage()
        qtbot.addWidget(page)
        config = get_config_center()

        port_spin = page._field_widgets["browser.virtualbrowser.port"]
        port_spin.setValue(9101)

        assert config.get("browser.virtualbrowser.port") == 9101
