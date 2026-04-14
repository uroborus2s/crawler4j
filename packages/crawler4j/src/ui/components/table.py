"""通用表格组件。

提供统一的深色透明样式（Glassmorphism），并修复原生 QTableWidget 的视觉问题。
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QTableWidget


class SkyTableWidget(QTableWidget):
    """自定义样式表格。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_sky_style()
        self._init_corner_label()
        
    def _set_sky_style(self):
        """应用通用的深色透明样式。"""
        # 基本设置
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        
        # 表头设置
        h_header = self.horizontalHeader()
        if h_header is not None:
            # 禁用自动拉伸最后一列，允许所有列可调整宽度
            h_header.setStretchLastSection(True)
            
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(True)
            v_header.setDefaultSectionSize(60)
        
        # 核心样式表
        self.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.85);
                alternate-background-color: rgba(40, 40, 50, 0.4);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                gridline-color: rgba(255, 255, 255, 0.05);
                selection-background-color: rgba(99, 102, 241, 0.3);
                selection-color: #ffffff;
                outline: none;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            }
            QHeaderView {
                background-color: transparent; 
                background: transparent;
                border: none;
            }
            QHeaderView::section {
                background-color: rgba(45, 45, 55, 0.95);
                color: rgba(255, 255, 255, 0.8);
                padding: 8px 12px;
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: 2px solid rgba(99, 102, 241, 0.3);
                font-weight: bold;
            }
            QHeaderView::section:vertical {
                background-color: rgba(50, 50, 60, 0.9);
                color: rgba(255, 255, 255, 0.5);
                border-right: 2px solid rgba(99, 102, 241, 0.2);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                text-align: center;
            }
            /* 左上角按钮样式 - 即使被 Label 覆盖，保留底色作为保险 */
            QTableCornerButton::section {
                background-color: rgba(45, 45, 55, 0.95);
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: 2px solid rgba(99, 102, 241, 0.3);
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(30, 30, 40, 0.5);
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.1);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def _init_corner_label(self):
        """初始化左上角序号标签。"""
        self._corner_label = QLabel("序号", self)
        self._corner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 穿透鼠标事件，保留点击全选功能
        self._corner_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._corner_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: rgba(255, 255, 255, 0.8);
                font-weight: bold;
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: 2px solid rgba(99, 102, 241, 0.3);
            }
        """)
        # 初始定位
        self._update_corner_geometry()

    def resizeEvent(self, event):
        """处理大小调整。"""
        super().resizeEvent(event)
        self._update_corner_geometry()

    def updateGeometries(self):
        """处理几何变动（如表头大小改变）。"""
        super().updateGeometries()
        self._update_corner_geometry()

    def _update_corner_geometry(self):
        """更新角落标签位置和显隐。"""
        if not hasattr(self, '_corner_label'):
            return
            
        h_header = self.horizontalHeader()
        v_header = self.verticalHeader()
        
        if h_header is not None and v_header is not None and v_header.isVisible():
            v_width = v_header.width()
            h_height = h_header.height()
            self._corner_label.setGeometry(0, 0, v_width, h_height)
            self._corner_label.show()
            self._corner_label.raise_()
        else:
            self._corner_label.hide()

