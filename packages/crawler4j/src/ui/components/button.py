from __future__ import annotations

from typing import Literal

from PyQt6.QtWidgets import QPushButton

ButtonVariant = Literal["primary", "secondary"]


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
        },
        "secondary": {
            "background": "rgba(255, 255, 255, 0.1)",
            "hover": "rgba(255, 255, 255, 0.2)",
            "border": "1px solid rgba(255, 255, 255, 0.2)",
            "weight": "500",
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
                color: white;
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
