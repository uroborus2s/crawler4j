from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QPlainTextEdit, QWidget

from src.ui.components.message_dialog import MessageDialog


def test_message_dialog_uses_module_install_dark_native_shell(qtbot):
    dialog = MessageDialog(
        "代理测试成功",
        "出口 IP: 1.2.3.4\nHTTP 状态: 200",
        details="stage: probe",
        kind="info",
    )
    qtbot.addWidget(dialog)

    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.windowFlags() & Qt.WindowType.WindowCloseButtonHint
    assert dialog.windowTitle() == "代理测试成功"
    assert dialog.findChild(QWidget, "messagePanel") is not None
    assert dialog.findChild(QLabel, "messageEyebrow").text() == "信息"
    assert dialog.findChild(QLabel, "messageText").text().startswith("出口 IP")
    assert dialog.findChild(QPlainTextEdit, "messageDetails").toPlainText() == "stage: probe"
    assert dialog.findChild(QPushButton, "messagePrimaryButton").text() == "OK"

    stylesheet = dialog.styleSheet()
    assert "background-color: #1e1e28;" in stylesheet
    assert "QWidget#messagePanel" in stylesheet
    assert "QPlainTextEdit#messageDetails" in stylesheet

    primary_style = dialog.findChild(QPushButton, "messagePrimaryButton").styleSheet()
    assert "background: #10d982;" in primary_style
