from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionComboBox,
    QStyleOptionViewItem,
)


def _draw_chevron(painter: QPainter, rect: QRect, *, direction: str, color: str = "#e5e7eb") -> None:
    if rect.isNull():
        return

    half_width = max(3.5, min(rect.width(), rect.height()) * 0.16)
    half_height = max(2.5, min(rect.width(), rect.height()) * 0.12)
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
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(points[0], points[1])
    painter.drawLine(points[1], points[2])
    painter.restore()


class DropdownDelegate(QStyledItemDelegate):
    """自定义下拉框代理，用于绘制选中状态的对勾。"""
    
    def __init__(self, target_combo, parent=None):
        super().__init__(parent)
        self.target_combo = target_combo
        
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)
        
        # 检查是否是当前选中的项
        if index.row() == self.target_combo.currentIndex():
            self._draw_checkmark(item_option=option, painter=painter)
            
    def _draw_checkmark(self, item_option: QStyleOptionViewItem, painter: QPainter):
        """绘制白色对勾。"""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 强制使用白色，确保在深色背景下可见
        painter.setPen(QColor("white"))
        
        rect = item_option.rect
        # 在左侧 padding (24px) 的中间绘制
        # 假设图标宽度 12px，左偏 6px
        
        size = 10
        x = rect.left() + 8
        y = rect.top() + (rect.height() - size) // 2
        
        # 绘制对勾
        #      P3
        #     /
        #   P2
        #  /
        # P1
        
        p1 = (x, y + size * 0.5)
        p2 = (x + size * 0.4, y + size * 0.9)
        p3 = (x + size, y + size * 0.2)
        
        painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))
        painter.drawLine(int(p2[0]), int(p2[1]), int(p3[0]), int(p3[1]))
        
        painter.restore()


class StyledComboBox(QComboBox):
    """统一风格的下拉框组件。
    
    特性:
    1. 强制使用 QListView 视图，解决 MacOS 下无法自定义样式的问题。
    2. 统一的 CSS 样式，增加行间距和点击区域。
    3. 支持自定义最小高度。
    """

    def __init__(self, parent=None, min_height: int = 32):
        super().__init__(parent)
        self._min_height = min_height
        self._setup_view()
        self._setup_style()

    def _setup_view(self):
        """配置视图以支持 CSS 样式。"""
        view = QListView()
        view.setItemDelegate(DropdownDelegate(target_combo=self, parent=view))
        self.setView(view)

    def _setup_style(self):
        """应用统一的 CSS 样式。"""
        self.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 0px 10px;
                min-height: {self._min_height}px;
                min-width: 120px;
            }}
            QComboBox:hover {{
                border-color: rgba(99, 102, 241, 0.5);
                background: rgba(255, 255, 255, 0.15);
            }}
            QComboBox:focus {{
                border-color: #6366f1;
                background: rgba(50, 50, 60, 1);
            }}
            
            /* 下拉列表视图 */
            QComboBox QAbstractItemView {{
                background-color: #2d2d38;
                border: 2px solid 2d2d38;
                border-radius: 4px;
                outline: none;
                selection-background-color: transparent; /* 取消默认选中背景，使用 item 样式控制 */
            }}
            
            /* 下拉列表项 */
            QComboBox QAbstractItemView::item {{
                color: white;
                min-height: 32px; /* 增加行间距 */
                padding: 2px 24px;
                border-radius: 4px;
            }}
            
            /* 悬停状态 */
            QComboBox QAbstractItemView::item:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            
            /* 选中状态 */
            QComboBox QAbstractItemView::item:selected {{
                background-color: #6366f1;
                color: white;
                font-weight: bold;
            }}
            
            /* 下拉箭头 */
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left-width: 0px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
                width: 0px;
                height: 0px;
                background: transparent;
            }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)

        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )

        painter = QPainter(self)
        _draw_chevron(painter, arrow_rect.adjusted(0, 0, -2, 0), direction="down")
