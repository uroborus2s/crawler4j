from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class SegmentedOptionControl(QWidget):
    """轻量分段按钮选择器。"""

    def __init__(self, options: list[tuple[str, object]], on_change=None, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._on_change = on_change
        self._current_value = self._options[0][1] if self._options else None
        self._buttons: dict[object, QPushButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        total = len(self._options)
        for index, (text, value) in enumerate(self._options):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            radius_left = "6px" if index == 0 else "0"
            radius_right = "6px" if index == total - 1 else "0"
            border_left = "1px" if index == 0 else "0"
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.05);
                    color: rgba(255, 255, 255, 0.88);
                    border-top: 1px solid rgba(255, 255, 255, 0.1);
                    border-right: 1px solid rgba(255, 255, 255, 0.1);
                    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    border-left: {border_left} solid rgba(255, 255, 255, 0.1);
                    border-top-left-radius: {radius_left};
                    border-bottom-left-radius: {radius_left};
                    border-top-right-radius: {radius_right};
                    border-bottom-right-radius: {radius_right};
                    min-height: 32px;
                    padding: 0 18px;
                }}
                QPushButton:checked {{
                    background: #6366f1;
                    border-color: #6366f1;
                    color: white;
                    font-weight: bold;
                }}
                QPushButton:disabled {{
                    color: rgba(255, 255, 255, 0.35);
                }}
                """
            )
            button.clicked.connect(
                lambda checked, current=value: self.set_current_data(current, emit_change=True)
            )
            self._buttons[value] = button
            layout.addWidget(button)

        layout.addStretch()
        if self._options:
            self.set_current_data(self._options[0][1], emit_change=False)

    def currentData(self):
        return self._current_value

    def set_current_data(self, value, emit_change: bool = False) -> None:
        if value not in self._buttons:
            return
        self._current_value = value
        for option_value, button in self._buttons.items():
            button.setChecked(option_value == value)
        if emit_change and callable(self._on_change):
            self._on_change()

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 - Qt API
        super().setEnabled(enabled)
        for button in self._buttons.values():
            button.setEnabled(enabled)
