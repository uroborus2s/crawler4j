from src.ui.components.check_box import StyledCheckBox, ToggleSwitch


def test_styled_check_box_uses_shared_indicator_palette(qtbot):
    checkbox = StyledCheckBox("自动更新")
    qtbot.addWidget(checkbox)

    assert "QCheckBox::indicator" in checkbox.styleSheet()
    assert "rgba(99, 102, 241, 0.95)" in checkbox.styleSheet()


def test_toggle_switch_keeps_shared_dimensions(qtbot):
    toggle = ToggleSwitch()
    qtbot.addWidget(toggle)

    assert toggle.width() == 54
    assert toggle.height() == 30
