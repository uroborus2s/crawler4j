from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from src.ui.theme.styles import StyleSheets

CardVariant = Literal["plain", "group", "card"]


class Card(QFrame):
    """Shared card surface for dashboard widgets and hosted UI containers."""

    def __init__(
        self,
        *,
        title: str = "",
        variant: CardVariant = "card",
        gap: int = 10,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._variant = variant if variant in {"plain", "group", "card"} else "card"
        self.setStyleSheet(StyleSheets.card(variant=self._variant))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(18, 16, 18, 16)
        self.content_layout.setSpacing(max(0, gap))

        self.title_label: QLabel | None = None
        normalized_title = str(title or "").strip()
        if normalized_title:
            self.title_label = QLabel(normalized_title)
            self.title_label.setObjectName("cardTitle")
            self.content_layout.addWidget(self.title_label)

