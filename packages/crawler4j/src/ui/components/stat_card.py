from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from src.ui.theme.styles import StyleSheets

CardDeltaDirection = Literal["up", "down", "neutral"]


class StatCard(QFrame):
    """统一的统计卡片组件，支持标题、数值、副标题和变化值。"""

    _DELTA_STYLES: dict[str, tuple[str, str, str]] = {
        "up": ("#4ade80", "↑", "rgba(74, 222, 128, 0.14)"),
        "down": ("#f87171", "↓", "rgba(248, 113, 113, 0.14)"),
        "neutral": ("rgba(255, 255, 255, 0.72)", "•", "rgba(255, 255, 255, 0.08)"),
    }

    def __init__(
        self,
        title: str,
        value: str = "0",
        *,
        subtitle: str = "",
        accent_color: str = "#6366f1",
        delta_text: str = "",
        delta_direction: CardDeltaDirection = "neutral",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self._setup_ui(title, value)
        self.set_subtitle(subtitle)
        self.set_delta(delta_text, direction=delta_direction)

    def _setup_ui(self, title: str, value: str) -> None:
        self.setStyleSheet(StyleSheets.stat_card(accent_color=self._accent_color))
        self.setMinimumHeight(96)
        self.setMaximumHeight(108)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("statCardTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statCardValue")
        layout.addWidget(self.value_label)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("statCardSubtitle")
        self.subtitle_label.setHidden(True)
        footer.addWidget(self.subtitle_label)

        footer.addStretch()

        self.delta_label = QLabel()
        self.delta_label.setObjectName("statCardDelta")
        self.delta_label.setHidden(True)
        footer.addWidget(self.delta_label)

        layout.addLayout(footer)
        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_subtitle(self, text: str) -> None:
        normalized = str(text or "").strip()
        self.subtitle_label.setText(normalized)
        self.subtitle_label.setHidden(not normalized)

    def set_delta(self, text: str, *, direction: CardDeltaDirection = "neutral") -> None:
        normalized_text = str(text or "").strip()
        if not normalized_text:
            self.delta_label.clear()
            self.delta_label.setHidden(True)
            return

        normalized_direction = direction if direction in self._DELTA_STYLES else "neutral"
        color, prefix, background = self._DELTA_STYLES[normalized_direction]
        self.delta_label.setText(f"{prefix} {normalized_text}")
        self.delta_label.setStyleSheet(
            f"""
            color: {color};
            background: {background};
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
            """
        )
        self.delta_label.setHidden(False)
