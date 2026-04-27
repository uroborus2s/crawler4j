from __future__ import annotations

from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit


_UI_FONT_STACK = '"PingFang SC", "Microsoft YaHei", "Segoe UI", "Helvetica Neue"'
_MONO_FONT_STACK = '"SF Mono", "Menlo", "Consolas", "Monaco", monospace'


def _build_text_edit_stylesheet(
    selector: str,
    *,
    background: str,
    hover_background: str,
    focus_background: str,
    font_family: str,
    font_size: int,
    border_radius: int,
    padding: str,
) -> str:
    return f"""
        {selector} {{
            background: {background};
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: {border_radius}px;
            padding: {padding};
            font-size: {font_size}px;
            font-family: {font_family};
        }}
        {selector}:hover {{
            background: {hover_background};
            border-color: rgba(99, 102, 241, 0.5);
        }}
        {selector}:focus {{
            border-color: #6366f1;
            background: {focus_background};
        }}
        {selector}:disabled {{
            background: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.05);
        }}
        {selector}[readOnly="true"] {{
            background: rgba(18, 18, 28, 0.92);
            color: rgba(255, 255, 255, 0.78);
        }}
    """


class StyledTextEdit(QTextEdit):
    """统一风格的多行文本编辑器。"""

    def __init__(
        self,
        parent=None,
        *,
        monospace: bool = False,
        background: str = "rgba(20, 20, 30, 0.9)",
        hover_background: str = "rgba(26, 26, 38, 0.96)",
        focus_background: str = "rgba(24, 24, 36, 0.98)",
        font_size: int = 13,
        border_radius: int = 6,
        padding: str = "8px 10px",
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            _build_text_edit_stylesheet(
                "QTextEdit",
                background=background,
                hover_background=hover_background,
                focus_background=focus_background,
                font_family=_MONO_FONT_STACK if monospace else _UI_FONT_STACK,
                font_size=font_size,
                border_radius=border_radius,
                padding=padding,
            )
        )


class StyledPlainTextEdit(QPlainTextEdit):
    """统一风格的纯文本编辑器。"""

    def __init__(
        self,
        parent=None,
        *,
        monospace: bool = False,
        background: str = "rgba(20, 20, 30, 0.9)",
        hover_background: str = "rgba(26, 26, 38, 0.96)",
        focus_background: str = "rgba(24, 24, 36, 0.98)",
        font_size: int = 13,
        border_radius: int = 6,
        padding: str = "8px 10px",
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            _build_text_edit_stylesheet(
                "QPlainTextEdit",
                background=background,
                hover_background=hover_background,
                focus_background=focus_background,
                font_family=_MONO_FONT_STACK if monospace else _UI_FONT_STACK,
                font_size=font_size,
                border_radius=border_radius,
                padding=padding,
            )
        )
