"""通用表格组件。

提供统一的深色透明样式（Glassmorphism），并修复原生 QTableWidget 的视觉问题。
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractButton, QTableWidget


class SkyTableWidget(QTableWidget):
    """自定义样式表格。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._set_sky_style()
        
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
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(True)
        self.verticalHeader().setDefaultSectionSize(60)  # 增加行高以容纳操作按钮
        
        # 设置左上角按钮文字 "序号"
        btn = self.findChild(QAbstractButton)
        if btn:
            btn.setText("序号")
            btn.setStyleSheet("""
                QAbstractButton {
                    background-color: rgba(45, 45, 55, 0.95);
                    color: rgba(255, 255, 255, 0.8);
                    border: none;
                    border-right: 1px solid rgba(255, 255, 255, 0.05);
                    border-bottom: 2px solid rgba(99, 102, 241, 0.3);
                    font-weight: bold;
                }
            """)

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
            
            /* 关键点：修复纵向表头（序号列）的白色背景问题 */
            QHeaderView::section:vertical {
                background-color: rgba(50, 50, 60, 0.9);
                color: rgba(255, 255, 255, 0.5);
                border-right: 2px solid rgba(99, 102, 241, 0.2);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
                text-align: center;
                padding-left: 10px;
                padding-right: 10px;
            }
            
            QTableCornerButton::section {
                background-color: rgba(45, 45, 55, 0.95);
                border: none;
            }
            
            /* 滚动条美化 */
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
