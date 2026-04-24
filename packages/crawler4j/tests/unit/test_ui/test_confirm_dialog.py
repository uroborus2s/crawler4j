from PyQt6.QtWidgets import QLabel, QPushButton

from src.ui.components.confirm_dialog import ConfirmDialog


def test_confirm_dialog_applies_dark_danger_theme(qtbot):
    dialog = ConfirmDialog(
        "确认删除",
        "确定要删除示例记录吗？此操作不可恢复。",
        confirm_text="删除",
        cancel_text="取消",
        danger=True,
    )
    qtbot.addWidget(dialog)

    title_label = dialog.findChild(QLabel, "confirmTitle")
    message_label = dialog.findChild(QLabel, "confirmMessage")
    cancel_button = dialog.findChild(QPushButton, "confirmCancel")
    confirm_button = dialog.findChild(QPushButton, "confirmDanger")

    assert title_label is not None
    assert message_label is not None
    assert cancel_button is not None
    assert confirm_button is not None

    stylesheet = dialog.styleSheet()
    assert "QDialog {" in stylesheet
    assert "background-color: #1e1e2e;" in stylesheet
    assert "QLabel#confirmTitle" in stylesheet
    assert "color: #f5e0dc;" in stylesheet
    assert "QLabel#confirmMessage" in stylesheet
    assert "color: #bac2de;" in stylesheet
    assert "QPushButton#confirmCancel" in stylesheet
    assert "QPushButton#confirmDanger" in stylesheet
    assert "#f38ba8" in stylesheet
