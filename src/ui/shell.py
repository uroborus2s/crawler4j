"""UI Shell - 全局布局容器。

提供：
    - 顶栏 (标题 + 状态)
    - 侧边栏 (导航)
    - 内容区 (动态加载 Core 子系统 UI)
    - 状态栏
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QFrame):
    """侧边栏导航。"""
    
    nav_changed = pyqtSignal(str)  # 导航变更信号
    
    NAV_ITEMS = [
        ("dashboard", "📊 仪表盘"),
        ("tasks", "📋 任务监控"),
        ("environments", "🖥️ 环境管理"),
        ("modules", "📦 模块管理"),
        ("strategy", "⚙️ 策略配置"),
        ("settings", "🔧 系统设置"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFixedWidth(200)
        self.setStyleSheet("""
            Sidebar {
                background-color: rgba(30, 30, 40, 0.9);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Logo
        logo = QLabel("🕷️ Crawler4j")
        logo.setStyleSheet("""
            padding: 20px;
            font-size: 18px;
            font-weight: bold;
            color: white;
        """)
        layout.addWidget(logo)
        
        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 12px 20px;
                color: rgba(255, 255, 255, 0.7);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:selected {
                background: rgba(99, 102, 241, 0.3);
                color: white;
            }
        """)
        
        for nav_id, label in self.NAV_ITEMS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, nav_id)
            self.nav_list.addItem(item)
        
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)
        
        layout.addWidget(self.nav_list)
        layout.addStretch()
    
    def _on_nav_changed(self, current, previous):
        if current:
            nav_id = current.data(Qt.ItemDataRole.UserRole)
            self.nav_changed.emit(nav_id)


class Shell(QMainWindow):
    """UI Shell - 全局布局容器。"""
    
    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_ui()
        self._register_pages()
    
    def _setup_window(self):
        self.setWindowTitle("Crawler4j")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f14;
            }
        """)
    
    def _setup_ui(self):
        # 中央容器
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 侧边栏
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        layout.addWidget(self.sidebar)
        
        # 内容区
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #1a1a24;
            }
        """)
        layout.addWidget(self.content_stack)
    
    def _register_pages(self):
        """注册 Core 子系统页面。"""
        self._pages = {}
        
        # 仪表盘 (占位)
        self._add_page("dashboard", self._create_placeholder("仪表盘"))
        
        # 任务监控 - ATM UI
        from src.core.atm.ui import TaskListWidget
        self._add_page("tasks", TaskListWidget())
        
        # 环境管理 - REM UI
        from src.core.rem.ui import EnvListWidget
        self._add_page("environments", EnvListWidget())
        
        # 模块管理 - MMS UI
        from src.core.mms.ui import ModuleListWidget
        self._add_page("modules", ModuleListWidget())
        
        # 策略配置 - TSM UI
        from src.core.tsm.ui import StrategyEditorPage
        self._add_page("strategy", StrategyEditorPage())
        
        # 系统设置 - Settings UI
        from src.core.settings.ui import SettingsPage
        self._add_page("settings", SettingsPage())
    
    def _add_page(self, page_id: str, widget: QWidget):
        self._pages[page_id] = widget
        self.content_stack.addWidget(widget)
    
    def _create_placeholder(self, title: str) -> QWidget:
        """创建占位页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 24px; color: white;")
        layout.addWidget(label)
        return page
    
    def _on_nav_changed(self, nav_id: str):
        """导航变更处理。"""
        if nav_id in self._pages:
            widget = self._pages[nav_id]
            self.content_stack.setCurrentWidget(widget)
            
            # 如果页面有 load_data 方法，调用它
            if hasattr(widget, "load_data"):
                widget.load_data()
