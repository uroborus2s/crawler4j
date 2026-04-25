from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QPlainTextEdit, QWidget

from src.ui.components.message_dialog import MessageDialog


def test_message_dialog_uses_public_dark_frameless_shell(qtbot):
    dialog = MessageDialog(
        "代理测试成功",
        "出口 IP: 1.2.3.4\nHTTP 状态: 200",
        details="stage: probe",
        kind="info",
    )
    qtbot.addWidget(dialog)

    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.findChild(QWidget, "messageTitleBar") is not None
    assert dialog.findChild(QLabel, "messageTitle").text() == "代理测试成功"
    assert dialog.findChild(QLabel, "messageText").text().startswith("出口 IP")
    assert dialog.findChild(QPlainTextEdit, "messageDetails").toPlainText() == "stage: probe"
    assert dialog.findChild(QPushButton, "messagePrimaryButton").text() == "OK"

    stylesheet = dialog.styleSheet()
    assert "QWidget#messageTitleBar" in stylesheet
    assert "background-color: #0f172a;" in stylesheet
    assert "QPlainTextEdit#messageDetails" in stylesheet
