from __future__ import annotations

from typing import Literal, cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton

ButtonVariant = Literal["primary", "secondary", "success", "warning", "danger"]


class StyledButton(QPushButton):
    """统一风格的按钮组件。

    目标：
    1. 收口页面内散落的 QPushButton 局部样式。
    2. 为中文按钮文本提供明确的字体栈，而不是依赖泛型 `Sans Serif`。
    3. 使用固定高度 + 仅横向 padding，避免每个页面重复用垂直 padding 参与文字排版。
    """

    _FONT_STACK = '"PingFang SC", "Microsoft YaHei", "Segoe UI", "Helvetica Neue"'

    _VARIANT_STYLES: dict[str, dict[str, str]] = {
        "primary": {
            "background": "rgba(99, 102, 241, 0.9)",
            "hover": "rgba(99, 102, 241, 1)",
            "border": "none",
            "weight": "600",
            "color": "white",
        },
        "secondary": {
            "background": "rgba(255, 255, 255, 0.1)",
            "hover": "rgba(255, 255, 255, 0.2)",
            "border": "1px solid rgba(255, 255, 255, 0.2)",
            "weight": "500",
            "color": "white",
        },
        "success": {
            "background": "#10d982",
            "hover": "#0fca79",
            "border": "none",
            "weight": "700",
            "color": "#04130c",
        },
        "warning": {
            "background": "#f59e0b",
            "hover": "#d97706",
            "border": "none",
            "weight": "700",
            "color": "#111827",
        },
        "danger": {
            "background": "rgba(248, 113, 113, 0.92)",
            "hover": "rgba(248, 113, 113, 1)",
            "border": "none",
            "weight": "700",
            "color": "#19070a",
        },
    }

    def __init__(
        self,
        text: str = "",
        *,
        variant: ButtonVariant = "primary",
        min_height: int = 40,
        min_width: int | None = None,
        horizontal_padding: int = 16,
        border_radius: int = 6,
        parent=None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = variant
        self._horizontal_padding = horizontal_padding
        self._border_radius = border_radius
        self._apply_style()
        self.setMinimumHeight(min_height)
        if min_width is not None:
            self.setMinimumWidth(min_width)

    def _apply_style(self) -> None:
        palette = self._VARIANT_STYLES[self._variant]
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {palette["background"]};
                color: {palette["color"]};
                border: {palette["border"]};
                border-radius: {self._border_radius}px;
                padding: 0px {self._horizontal_padding}px;
                text-align: center;
                font-size: 13px;
                font-weight: {palette["weight"]};
                font-family: {self._FONT_STACK};
            }}
            QPushButton:hover {{
                background: {palette["hover"]};
            }}
            QPushButton:disabled {{
                color: rgba(255, 255, 255, 0.35);
                border: 1px solid rgba(255, 255, 255, 0.1);
                background: rgba(255, 255, 255, 0.05);
            }}
            """
        )


def normalize_button_variant(
    variant: str | None,
    *,
    default: ButtonVariant = "secondary",
) -> ButtonVariant:
    """Normalize schema/user supplied button variants to supported shared variants."""

    value = str(variant or default).strip().lower()
    if value == "ghost":
        value = "secondary"
    if value not in StyledButton._VARIANT_STYLES:
        return default
    return cast(ButtonVariant, value)


def create_action_button(
    text: str,
    *,
    variant: str | None = "secondary",
    min_height: int = 34,
    min_width: int | None = None,
    horizontal_padding: int = 10,
    border_radius: int = 4,
    parent=None,
) -> StyledButton:
    """Create a compact action button with the shared StyledButton palette."""

    button = StyledButton(
        text,
        variant=normalize_button_variant(variant),
        min_height=min_height,
        min_width=min_width,
        horizontal_padding=horizontal_padding,
        border_radius=border_radius,
        parent=parent,
    )
    # Table cell widgets clip children that grow beyond their content rect. A
    # fixed compact height keeps Chinese text and emoji labels stable.
    button.setFixedHeight(max(0, int(min_height)))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
