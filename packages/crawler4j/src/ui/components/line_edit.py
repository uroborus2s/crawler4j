from PyQt6.QtWidgets import QLineEdit


class StyledLineEdit(QLineEdit):
    """统一风格的单行文本输入框。
    
    特性:
    1. 统一的深色背景和边框样式。
    2. 支持鼠标悬停和聚焦状态样式。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()

    def _setup_style(self):
        """应用统一的 CSS 样式。"""
        self.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 20px;
                min-width: 200px;
            }
            QLineEdit:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: rgba(99, 102, 241, 0.5);
            }
            QLineEdit:focus {
                border-color: #6366f1;
                background: rgba(50, 50, 60, 1);
            }
            QLineEdit:disabled {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.3);
                border-color: rgba(255, 255, 255, 0.05);
            }
        """)
