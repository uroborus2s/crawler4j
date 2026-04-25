"""Shared dark message dialog."""

from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.button import StyledButton
from src.ui.components.dialog_async import open_dialog_async

MessageKind = Literal["info", "warning", "error"]


class MessageDialog(QDialog):
    """Public dark message dialog aligned with the app dialog surface."""

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
        self.setMinimumWidth(580)
        self.setWindowTitle(self.title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui(primary_text)

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                background: transparent;
            }
            QWidget#messagePanel {
                background-color: #1e1e28;
            }
            QLabel#messageEyebrow {
                color: rgba(255, 255, 255, 0.68);
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 0px;
            }
            QLabel#messageText {
                color: #f7f7fb;
                font-size: 16px;
                font-weight: 700;
                line-height: 1.45;
            }
            QPlainTextEdit#messageDetails {
                background-color: rgba(255, 255, 255, 0.07);
                color: rgba(255, 255, 255, 0.76);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 10px;
                selection-background-color: rgba(99, 102, 241, 0.55);
                font-size: 12px;
            }
        """

    def _setup_ui(self, primary_text: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 34, 40, 34)
        root.setSpacing(18)

        panel = QWidget()
        panel.setObjectName("messagePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(16)
        root.addWidget(panel)

        eyebrow = QLabel(self._eyebrow_text())
        eyebrow.setObjectName("messageEyebrow")
        eyebrow.setStyleSheet(f"color: {self._eyebrow_color()};")
        panel_layout.addWidget(eyebrow)

        message_label = QLabel(self.message)
        message_label.setObjectName("messageText")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        panel_layout.addWidget(message_label)

        self.details_edit = QPlainTextEdit()
        self.details_edit.setObjectName("messageDetails")
        self.details_edit.setPlainText(self.details)
        self.details_edit.setReadOnly(True)
        self.details_edit.setMinimumHeight(150)
        self.details_edit.setVisible(False)
        panel_layout.addWidget(self.details_edit)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 10, 0, 0)
        buttons.setSpacing(12)
        if self.details:
            details_button = StyledButton(
                "Show Details...",
                variant="secondary",
                min_height=40,
                min_width=132,
                horizontal_padding=18,
            )
            details_button.setObjectName("messageDetailsButton")
            details_button.clicked.connect(self._toggle_details)
            buttons.addWidget(details_button)
            self.details_button = details_button
        buttons.addStretch()

        primary_button = StyledButton(
            primary_text,
            variant="success",
            min_height=40,
            min_width=112,
            horizontal_padding=22,
        )
        primary_button.setObjectName("messagePrimaryButton")
        primary_button.setCursor(Qt.CursorShape.PointingHandCursor)
        primary_button.clicked.connect(self.accept)
        buttons.addWidget(primary_button)
        panel_layout.addLayout(buttons)

    def _eyebrow_text(self) -> str:
        if self.kind == "error":
            return "错误"
        return "警告" if self.kind == "warning" else "信息"

    def _eyebrow_color(self) -> str:
        if self.kind == "error":
            return "#fb7185"
        return "#fbbf24" if self.kind == "warning" else "rgba(255, 255, 255, 0.68)"

    def _toggle_details(self) -> None:
        visible = not self.details_edit.isVisible()
        self.details_edit.setVisible(visible)
        if hasattr(self, "details_button"):
            self.details_button.setText("Hide Details" if visible else "Show Details...")
        self.adjustSize()

    @classmethod
    async def show_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
        kind: MessageKind = "info",
    ) -> int:
        dialog = cls(title, message, details=details, kind=kind, parent=parent)
        return await open_dialog_async(dialog)

    @classmethod
    def information(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="info", parent=parent).exec()

    @classmethod
    async def information_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> int:
        return await cls.show_async(parent, title, message, details=details, kind="info")

    @classmethod
    def warning(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="warning", parent=parent).exec()

    @classmethod
    async def warning_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> int:
        return await cls.show_async(parent, title, message, details=details, kind="warning")

    @classmethod
    def error(cls, parent: QWidget | None, title: str, message: str, *, details: str = "") -> int:
        return cls(title, message, details=details, kind="error", parent=parent).exec()

    @classmethod
    async def error_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        details: str = "",
    ) -> int:
        return await cls.show_async(parent, title, message, details=details, kind="error")
