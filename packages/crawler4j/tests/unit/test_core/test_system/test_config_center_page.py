from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from src.ui.components.button import StyledButton
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
    assert "about" not in page._domain_buttons
    assert "update" not in page._domain_buttons
    assert "browser.virtualbrowser.port" in page._field_widgets
    assert "atm.env_action_timeout_seconds" in page._field_widgets
    assert "system.autostart" not in page._field_widgets
    assert "system.minimize_on_start" not in page._field_widgets
    assert isinstance(page._field_widgets["network.proxy_mode"], StyledComboBox)
    assert isinstance(page._field_widgets["browser.virtualbrowser.path"], StyledLineEdit)
    assert isinstance(page._field_widgets["atm.env_action_timeout_seconds"], StyledSpinBox)
    assert isinstance(page.reset_domain_btn, StyledButton)
    assert page.objectName() == "configCenterPage"
    assert page.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert "#configDomainPage" in page.styleSheet()
    assert not page.findChildren(QWidget, "sharedCard")

    system_page = page._domain_pages["system"]
    assert system_page.objectName() == "configDomainScroll"
    assert system_page.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert system_page.viewport().objectName() == "configDomainViewport"
    assert system_page.viewport().testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert system_page.widget().objectName() == "configDomainPage"
    assert system_page.widget().testAttribute(Qt.WidgetAttribute.WA_StyledBackground)
    assert system_page.widget().findChild(QWidget, "configSectionBody") is not None


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
