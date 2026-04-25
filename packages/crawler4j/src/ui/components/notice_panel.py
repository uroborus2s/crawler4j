"""Shared inline notice panel."""

from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

NoticeKind = Literal["info", "success", "warning", "error"]


class NoticePanel(QWidget):
    """Compact dark notice panel for forms and dialogs."""

    _COLORS = {
        "info": ("rgba(99, 102, 241, 0.14)", "#c7d2fe"),
        "success": ("rgba(34, 197, 94, 0.14)", "#86efac"),
        "warning": ("rgba(245, 158, 11, 0.14)", "#fcd34d"),
        "error": ("rgba(248, 113, 113, 0.14)", "#fca5a5"),
    }

    def __init__(
        self,
        text: str = "",
        *,
        kind: NoticeKind = "info",
        parent=None,
        margins: tuple[int, int, int, int] = (12, 10, 12, 10),
    ) -> None:
        super().__init__(parent)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(0)
        layout.addWidget(self.label)
        self.set_kind(kind)

    def set_kind(self, kind: NoticeKind) -> None:
        background, foreground = self._COLORS.get(kind, self._COLORS["info"])
        self.setStyleSheet(
            f"background: {background}; border: none; border-radius: 8px;"
        )
        self.label.setStyleSheet(
            f"color: {foreground}; background: transparent; border: none; padding: 0;"
        )

    def set_text(self, text: str) -> None:
        self.label.setText(text)
