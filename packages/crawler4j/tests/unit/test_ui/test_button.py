from PyQt6.QtGui import QFontInfo

from src.ui.components.button import StyledButton


def test_styled_button_primary_uses_explicit_font_stack_and_size(qtbot):
    button = StyledButton("创建", variant="primary", min_height=48, min_width=92)
    qtbot.addWidget(button)
    button.show()

    font_info = QFontInfo(button.font())

    assert button.minimumHeight() == 48
    assert button.minimumWidth() == 92
    assert "font-family" in button.styleSheet()
    assert "padding: 0px 16px;" in button.styleSheet()
    assert font_info.family() in {".AppleSystemUIFont", "PingFang SC", "Microsoft YaHei UI", "Segoe UI", "Helvetica Neue"}


def test_styled_button_secondary_uses_secondary_palette(qtbot):
    button = StyledButton("取消", variant="secondary", min_height=48, min_width=92, horizontal_padding=20)
    qtbot.addWidget(button)

    assert "rgba(255, 255, 255, 0.1)" in button.styleSheet()
    assert "font-weight: 500;" in button.styleSheet()
    assert "padding: 0px 20px;" in button.styleSheet()


def test_styled_button_success_uses_module_dialog_action_palette(qtbot):
    button = StyledButton("开始检查", variant="success", min_height=48, min_width=120)
    qtbot.addWidget(button)

    assert "background: #10d982;" in button.styleSheet()
    assert "color: #04130c;" in button.styleSheet()
    assert "font-weight: 700;" in button.styleSheet()
