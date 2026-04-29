from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.ui.theme.styles import StyleSheets

CardVariant = Literal["plain", "group", "card"]
CardHorizontalAlign = Literal["left", "center", "right"]
CardVerticalAlign = Literal["top", "center", "bottom"]
CardPadding = int | tuple[int, int, int, int]


class Card(QFrame):
    """Shared card surface for dashboard widgets and hosted UI containers."""

    def __init__(
        self,
        *,
        title: str = "",
        variant: CardVariant = "card",
        gap: int = 10,
        title_align: CardHorizontalAlign = "left",
        content_align: CardHorizontalAlign = "left",
        content_vertical_align: CardVerticalAlign = "top",
        min_height: int | None = None,
        padding: CardPadding = (18, 16, 18, 16),
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._variant = variant if variant in {"plain", "group", "card"} else "card"
        self.title_align = title_align if title_align in {"left", "center", "right"} else "left"
        self.content_align = content_align if content_align in {"left", "center", "right"} else "left"
        self.content_vertical_align = (
            content_vertical_align if content_vertical_align in {"top", "center", "bottom"} else "top"
        )
        self.padding = self._normalize_padding(padding)
        self.setObjectName("sharedCard")
        self.setStyleSheet(StyleSheets.card(variant=self._variant))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        if min_height is not None:
            self.setMinimumHeight(max(0, int(min_height)))

        self.frame_layout = QVBoxLayout(self)
        self.frame_layout.setContentsMargins(*self.padding)
        self.frame_layout.setSpacing(max(0, gap))

        self.title_label: QLabel | None = None
        normalized_title = str(title or "").strip()
        if normalized_title:
            self.title_label = QLabel(normalized_title)
            self.title_label.setObjectName("cardTitle")
            self.title_label.setAlignment(self._qt_horizontal_alignment(self.title_align))
            self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.frame_layout.addWidget(self.title_label)

        if self.content_vertical_align in {"center", "bottom"}:
            self.frame_layout.addStretch()

        self.content_container = QWidget()
        self.content_row_layout = QHBoxLayout(self.content_container)
        self.content_row_layout.setContentsMargins(0, 0, 0, 0)
        self.content_row_layout.setSpacing(0)

        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(max(0, gap))

        if self.content_align in {"center", "right"}:
            self.content_row_layout.addStretch()
        self.content_row_layout.addWidget(self.content_widget)
        if self.content_align in {"left", "center"}:
            self.content_row_layout.addStretch()

        self.frame_layout.addWidget(self.content_container)
        if self.content_vertical_align in {"top", "center"}:
            self.frame_layout.addStretch()

    @staticmethod
    def _normalize_padding(padding: CardPadding) -> tuple[int, int, int, int]:
        if isinstance(padding, int):
            normalized = max(0, padding)
            return (normalized, normalized, normalized, normalized)
        if isinstance(padding, tuple) and len(padding) == 4:
            return tuple(max(0, int(value)) for value in padding)
        return (18, 16, 18, 16)

    @staticmethod
    def _qt_horizontal_alignment(alignment: CardHorizontalAlign) -> Qt.AlignmentFlag:
        if alignment == "center":
            return Qt.AlignmentFlag.AlignHCenter
        if alignment == "right":
            return Qt.AlignmentFlag.AlignRight
        return Qt.AlignmentFlag.AlignLeft
