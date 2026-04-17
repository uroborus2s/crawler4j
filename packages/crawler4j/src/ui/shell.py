"""UI Shell - 全局布局容器。

提供：
    - 顶栏 (标题 + 状态指示)
    - 侧边栏 (导航)
    - 内容区 (动态加载 Core 子系统 UI)
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
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

from src.core.atm import TaskStatus, get_task_service


class StatusIndicator(QFrame):
    """顶栏状态指示器。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_timer()
    
    def _setup_ui(self):
        self.setFixedHeight(48)
        self.setStyleSheet("""
            StatusIndicator {
                background: rgba(30, 30, 40, 0.95);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        
        # 标题
        title = QLabel("🕷️ 蛛行演略 · crawler4j")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 状态指示
        self.running_label = QLabel("⏳ 0 运行中")
        self.running_label.setStyleSheet("color: #facc15; font-size: 13px; padding: 0 12px;")
        layout.addWidget(self.running_label)
        
        self.env_label = QLabel("🖥️ 0 环境")
        self.env_label.setStyleSheet("color: #4ade80; font-size: 13px; padding: 0 12px;")
        layout.addWidget(self.env_label)
        
        self.module_label = QLabel("📦 0 模块")
        self.module_label.setStyleSheet("color: #60a5fa; font-size: 13px; padding: 0 12px;")
        layout.addWidget(self.module_label)
        
        # 版本号显示
        from src.core.system.version_service import get_current_version
        self.version_label = QLabel(f"v{get_current_version()}")
        self.version_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.6);
            font-size: 12px;
            padding: 0 12px;
        """)
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.setToolTip("点击查看版本信息")
        self.version_label.mousePressEvent = self._on_version_clicked
        layout.addWidget(self.version_label)
    
    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(3000)  # 每 3 秒刷新
    
    def _refresh_status(self):
        try:
            # 任务统计
            service = get_task_service()
            tasks = service.list_recent(50)
            running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
            self.running_label.setText(f"⏳ {running} 运行中")
            
            # 模块统计
            from src.core.mms import get_module_registry
            registry = get_module_registry()
            modules = registry.list_modules()
            self.module_label.setText(f"📦 {len(modules)} 模块")
        except Exception:
            pass
    
    def _on_version_clicked(self, ev):
        """版本号点击事件。"""
        from src.core.system.ui import AboutDialog
        dialog = AboutDialog(self.window())
        dialog.exec()


class Sidebar(QFrame):
    """侧边栏导航。
    
    仅包含 Core 系统功能的固定导航项。
    模块配置入口在"模块管理"页面的模块详情中。
    """
    
    nav_changed = pyqtSignal(str)
    
    # Core 系统导航项
    NAV_ITEMS = [
        ("dashboard", "📊 仪表盘"),
        ("tasks", "📋 任务监控"),
        ("environments", "🖥️ 环境管理"),
        ("modules", "📦 模块管理"),
        ("help", "📘 使用文档"),
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
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(0)
        
        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 14px 20px;
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
        self._subscribe_events()
    
    def _subscribe_events(self):
        """订阅全局事件。"""
        from src.core.foundation.event_bus import EventType, get_event_bus
        
        bus = get_event_bus()
        bus.subscribe(EventType.ENV_OPERATION_FAILED, self._on_env_operation_failed)
    
    def _on_env_operation_failed(self, event):
        """处理环境操作失败事件。"""
        from src.ui.components.toast import Toast
        
        message = event.data.get("message", "操作失败")
        env_name = event.data.get("env_name", "")
        
        if env_name:
            display_msg = f"[{env_name}] {message}"
        else:
            display_msg = message
        
        Toast.error(self, display_msg)

    
    def _setup_window(self):
        self.setWindowTitle("蛛行演略 · crawler4j")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f0f14;
            }
        """)

        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            default_width = min(available.width(), 1420)
            default_height = min(available.height(), self.minimumHeight())
            self.resize(default_width, default_height)
    
    def _setup_ui(self):
        # 中央容器
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 顶栏状态
        self.status_bar = StatusIndicator()
        main_layout.addWidget(self.status_bar)
        
        # 主内容区
        content_area = QWidget()
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 侧边栏
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        content_layout.addWidget(self.sidebar)
        
        # 内容栈
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #1a1a24;
            }
        """)
        content_layout.addWidget(self.content_stack)
        
        main_layout.addWidget(content_area)
    
    def _register_pages(self):
        """注册 Core 子系统页面。"""
        self._pages = {}
        
        # 仪表盘 - Dashboard
        from src.ui.dashboard import DashboardPage
        self._add_page("dashboard", DashboardPage())
        
        # 任务监控 - ATM UI
        from src.core.atm.ui import TaskListWidget
        self._add_page("tasks", TaskListWidget())
        
        # 环境管理 - REM UI (包含环境列表和 IP 池 Tab)
        from src.core.rem.ui import EnvManagerPage
        self._add_page("environments", EnvManagerPage())
        
        # 模块管理 - MMS UI
        from src.core.mms.ui import ModuleListWidget
        from src.core.mms.ui.module_detail_page import ModuleDetailPage
        
        modules_page = ModuleListWidget()
        self._add_page("modules", modules_page)
        
        # 模块详情页
        self.module_detail_page = ModuleDetailPage()
        self._add_page("module_detail", self.module_detail_page)
        
        # 连接信号: 列表页 → 详情页
        modules_page.open_detail.connect(self._open_module_detail)
        self.module_detail_page.back_requested.connect(self._back_to_modules)
        
        # 系统设置 - System UI
        from src.core.system.ui import HelpPage
        from src.core.system.ui import SettingsPage
        self._add_page("help", HelpPage())
        self._add_page("settings", SettingsPage())
    
    def _add_page(self, page_id: str, widget: QWidget):
        self._pages[page_id] = widget
        self.content_stack.addWidget(widget)
    
    def _on_nav_changed(self, nav_id: str):
        """导航变更处理。"""
        if nav_id in self._pages:
            widget = self._pages[nav_id]
            self.content_stack.setCurrentWidget(widget)
            
            # 如果页面有 load_data 方法，调用它
            if hasattr(widget, "load_data"):
                widget.load_data()
    
    def _open_module_detail(self, module):
        """打开模块详情页。"""
        self.module_detail_page.set_module(module)
        self.content_stack.setCurrentWidget(self.module_detail_page)
    
    def _back_to_modules(self):
        """返回模块列表页。"""
        if "modules" in self._pages:
            self.content_stack.setCurrentWidget(self._pages["modules"])
