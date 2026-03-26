"""环境管理页面（Tab 容器）。

设计参考: docs/03-solution/reference-design/module-01-runtime-environment.md §5.5

将环境列表和 IP 池管理整合为 Tab 页面：
    - EnvManagerPage: 环境管理主页面（Tab 容器）
"""

from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from src.core.rem.ui.env_list_widget import EnvListWidget
from src.core.rem.ui.ip_pool_tab import IPPoolTab


class EnvManagerPage(QWidget):
    """环境管理页面。
    
    包含两个 Tab：
        - 环境列表
        - IP 池管理
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建 Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1a1a24;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #252530;
                color: rgba(255, 255, 255, 0.7);
                padding: 10px 24px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:hover {
                background-color: #2a2a38;
                color: white;
            }
            QTabBar::tab:selected {
                background-color: #1a1a24;
                color: white;
                border-bottom: 2px solid #89b4fa;
            }
        """)
        
        # 环境列表 Tab
        self.env_list = EnvListWidget()
        self.tabs.addTab(self.env_list, "🖥️ 环境列表")
        
        # IP 池管理 Tab
        self.ip_pool = IPPoolTab()
        self.tabs.addTab(self.ip_pool, "🌐 IP 池管理")
        
        layout.addWidget(self.tabs)
    
    def load_data(self) -> None:
        """加载数据（被 Shell 调用）。"""
        # 加载当前 Tab 的数据
        current = self.tabs.currentWidget()
        if hasattr(current, "load_data"):
            current.load_data()
