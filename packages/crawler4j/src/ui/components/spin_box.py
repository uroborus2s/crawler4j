from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSpinBox, QStyle, QStyleOptionSpinBox


def _draw_chevron(painter: QPainter, rect: QRect, *, direction: str, color: str = "#e5e7eb") -> None:
    if rect.isNull():
        return

    half_width = max(2.8, min(rect.width(), rect.height()) * 0.16)
    half_height = max(2.0, min(rect.width(), rect.height()) * 0.12)
    center_x = rect.center().x()
    center_y = rect.center().y()

    if direction == "up":
        points = (
            QPointF(center_x - half_width, center_y + half_height),
            QPointF(center_x, center_y - half_height),
            QPointF(center_x + half_width, center_y + half_height),
        )
    else:
        points = (
            QPointF(center_x - half_width, center_y - half_height),
            QPointF(center_x, center_y + half_height),
            QPointF(center_x + half_width, center_y - half_height),
        )

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(points[0], points[1])
    painter.drawLine(points[1], points[2])
    painter.restore()


class StyledSpinBox(QSpinBox):
    """统一风格的数字输入框。
    
    特性:
    1. 统一的深色背景和边框样式。
    2. 自定义上下箭头按钮，集成在输入框内部右侧。
    3. 支持鼠标悬停和聚焦状态样式。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()

    def _setup_style(self):
        """应用统一的 CSS 样式。"""
        self.setStyleSheet("""
            QSpinBox {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 20px;
                min-width: 80px;
            }
            QSpinBox:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: rgba(99, 102, 241, 0.5);
            }
            QSpinBox:focus {
                border-color: #6366f1;
                background: rgba(50, 50, 60, 1);
            }
            
            /* 上下按钮区域 */
            QSpinBox::up-button, QSpinBox::down-button {
                width: 24px;
                background: rgba(255, 255, 255, 0.05);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            QSpinBox::up-button {
                border-top-right-radius: 4px;
                margin-bottom: 0px;
                subcontrol-origin: border;
                subcontrol-position: top right;
            }
            QSpinBox::down-button {
                border-bottom-right-radius: 4px;
                margin-top: 0px;
                subcontrol-origin: border;
                subcontrol-position: bottom right;
            }
            
            /* 箭头图标 */
            QSpinBox::up-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
                background: transparent;
            }
            QSpinBox::down-arrow {
                image: none;
                border: none;
                width: 0px;
                height: 0px;
                background: transparent;
            }
        """)

    def paintEvent(self, event):
        super().paintEvent(event)

        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        up_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxUp,
            self,
        )
        down_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxDown,
            self,
        )

        painter = QPainter(self)
        _draw_chevron(painter, up_rect.adjusted(0, 1, 0, 0), direction="up")
        _draw_chevron(painter, down_rect.adjusted(0, 0, 0, -1), direction="down")
