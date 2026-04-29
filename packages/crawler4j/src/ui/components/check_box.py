from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QCheckBox


class StyledCheckBox(QCheckBox):
    """统一风格的复选框组件。"""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._setup_style()

    def _setup_style(self) -> None:
        self.setStyleSheet(
            """
            QCheckBox {
                color: rgba(255, 255, 255, 0.82);
                background: transparent;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.18);
                background: rgba(255, 255, 255, 0.06);
            }
            QCheckBox::indicator:hover {
                border-color: rgba(99, 102, 241, 0.7);
                background: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background: rgba(99, 102, 241, 0.95);
                border-color: rgba(99, 102, 241, 0.95);
            }
            QCheckBox:disabled {
                color: rgba(255, 255, 255, 0.34);
            }
            QCheckBox::indicator:disabled {
                background: rgba(255, 255, 255, 0.04);
                border-color: rgba(255, 255, 255, 0.08);
            }
            """
        )


class ToggleSwitch(QCheckBox):
    """统一公共库里的滑动开关组件。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")
        self.setFixedSize(54, 30)

    def sizeHint(self) -> QSize:
        return QSize(54, 30)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        knob_diameter = rect.height() - 6.0
        knob_y = rect.top() + (rect.height() - knob_diameter) / 2
        knob_x = rect.right() - knob_diameter - 3.0 if self.isChecked() else rect.left() + 3.0

        if self.isEnabled():
            track_color = QColor("#6366f1") if self.isChecked() else QColor(60, 60, 72)
            border_color = QColor("#6366f1") if self.isChecked() else QColor(255, 255, 255, 36)
            knob_color = QColor(255, 255, 255)
        else:
            track_color = QColor(255, 255, 255, 18)
            border_color = QColor(255, 255, 255, 24)
            knob_color = QColor(255, 255, 255, 120)

        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        knob_rect = QRectF(knob_x, knob_y, knob_diameter, knob_diameter)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob_rect)
