from PyQt6.QtWidgets import QSpinBox


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
                image: url(src/ui/assets/arrow_up.svg);
                width: 10px;
                height: 10px;
            }
            QSpinBox::down-arrow {
                image: url(src/ui/assets/arrow_down.svg);
                width: 10px;
                height: 10px;
            }
        """)
