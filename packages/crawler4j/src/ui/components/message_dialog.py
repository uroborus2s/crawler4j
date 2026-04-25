"""Shared dark message dialog."""

from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MessageKind = Literal["info", "warning", "error"]


class MessageDialog(QDialog):
    """Public message dialog with a dark custom title bar."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        details: str = "",
        kind: MessageKind = "info",
        primary_text: str = "OK",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.title = str(title or "")
        self.message = str(message or "")
        self.details = str(details or "")
        self.kind: MessageKind = kind if kind in {"info", "warning", "error"} else "info"

        self.setModal(True)
        self.setMinimumWidth(520)
        self.setWindowTitle(self.title)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui(primary_text)

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #0b1220;
                border: 1px solid #243044;
                border-radius: 14px;
            }
            QWidget#messageTitleBar {
                background-color: #0f172a;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom: 1px solid #1f2a3d;
            }
            QLabel {
                background: transparent;
            }
            QLabel#messageTitle {
                color: #e5e7eb;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#messageCloseButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                border-radius: 12px;
                min-width: 24px;
                min-height: 24px;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#messageCloseButton:hover {
                background-color: rgba(148, 163, 184, 0.16);
                color: #f8fafc;
            }
            QLabel#messageIcon {
                min-width: 64px;
                min-height: 64px;
                border-radius: 32px;
                background-color: #e2e8f0;
                color: #475569;
                font-size: 38px;
                font-weight: 800;
            }
            QLabel#messageText {
                color: #e5e7eb;
                font-size: 17px;
                font-weight: 700;
                line-height: 1.35;
            }
            QPlainTextEdit#messageDetails {
                background-color: #020617;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #2563eb;
                font-size: 12px;
            }
            QPushButton {
                min-width: 110px;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton#messageDetailsButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                color: #e2e8f0;
            }
            QPushButton#messageDetailsButton:hover {
                background-color: #273449;
            }
            QPushButton#messagePrimaryButton {
                background-color: #2563eb;
                border: 1px solid #60a5fa;
                color: #f8fafc;
            }
            QPushButton#messagePrimaryButton:hover {
                background-color: #1d4ed8;
            }
        """

    def _setup_ui(self, primary_text: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("messageTitleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 10, 12, 10)
        title_layout.setSpacing(8)

        title_label = QLabel(self.title)
        title_label.setObjectName("messageTitle")
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        close_button = QPushButton("x")
        close_button.setObjectName("messageCloseButton")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.reject)
        title_layout.addWidget(close_button)
        root.addWidget(title_bar)

        body = QVBoxLayout()
        body.setContentsMargins(28, 26, 28, 24)
        body.setSpacing(18)
        root.addLayout(body)

        content = QHBoxLayout()
        content.setSpacing(24)
        icon = QLabel(self._icon_text())
        icon.setObjectName("messageIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        message_label = QLabel(self.message)
        message_label.setObjectName("messageText")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(message_label, stretch=1)
        body.addLayout(content)

        self.details_edit = QPlainTextEdit()
        self.details_edit.setObjectName("messageDetails")
        self.details_edit.setPlainText(self.details)
        self.details_edit.setReadOnly(True)
        self.details_edit.setMinimumHeight(140)
        self.details_edit.setVisible(False)
        body.addWidget(self.details_edit)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        if self.details:
            details_button = QPushButton("Show Details...")
            details_button.setObjectName("messageDetailsButton")
            details_button.clicked.connect(self._toggle_details)
            buttons.addWidget(details_button)
            self.details_button = details_button
        buttons.addStretch()

        primary_button = QPushButton(primary_text)
        primary_button.setObjectName("messagePrimaryButton")
        primary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        primary_button.clicked.connect(self.accept)
        buttons.addWidget(primary_button)
        body.addLayout(buttons)

    def _icon_text(self) -> str:
        if self.kind == "error":
            return "x"
        return "!" if self.kind == "warning" else "i"

    def _toggle_details(self) -> None:
        visible = not self.details_edit.isVisible()
        self.details_edit.setVisible(visible)
        if hasattr(self, "details_button"):
            self.details_button.setText("Hide Details" if visible else "Show Details...")
        self.adjustSize()

    @classmethod
    def information(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="info", parent=parent).exec()

    @classmethod
    def warning(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="warning", parent=parent).exec()

    @classmethod
    def error(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="error", parent=parent).exec()
