"""Dashboard 仪表盘页面。

显示系统运行状态概览：
    - 任务统计
    - 环境状态
    - 模块概览
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.atm import TaskStatus, get_task_service
from src.core.mms import ModuleStatus, get_module_registry
from src.core.rem import EnvStatus


class StatCard(QFrame):
    """统计卡片组件。"""
    
    def __init__(
        self,
        title: str,
        value: str = "0",
        subtitle: str = "",
        color: str = "#6366f1",
        parent=None,
    ):
        super().__init__(parent)
        self._setup_ui(title, value, subtitle, color)
    
    def _setup_ui(self, title: str, value: str, subtitle: str, color: str):
        self.setStyleSheet("""
            StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(99, 102, 241, 0.2),
                    stop:1 rgba(99, 102, 241, 0.05));
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        self.setMinimumHeight(120)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题
        title_label = QLabel(title)
        title_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 13px;")
        layout.addWidget(title_label)
        
        # 数值
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold;")
        layout.addWidget(self.value_label)
        
        # 副标题
        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None
        
        layout.addStretch()
    
    def set_value(self, value: str):
        self.value_label.setText(value)
    
    def set_subtitle(self, text: str):
        if self.subtitle_label:
            self.subtitle_label.setText(text)


class DashboardPage(QWidget):
    """仪表盘页面。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._setup_timer()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("📊 仪表盘")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # 统计卡片网格
        cards_grid = QGridLayout()
        cards_grid.setSpacing(16)
        
        # 任务统计
        self.running_card = StatCard("运行中任务", "0", "正在执行", "#facc15")
        cards_grid.addWidget(self.running_card, 0, 0)
        
        self.completed_card = StatCard("已完成任务", "0", "今日完成", "#4ade80")
        cards_grid.addWidget(self.completed_card, 0, 1)
        
        self.failed_card = StatCard("失败任务", "0", "需要关注", "#f87171")
        cards_grid.addWidget(self.failed_card, 0, 2)
        
        # 环境统计
        self.env_ready_card = StatCard("就绪环境", "0", "可用实例", "#60a5fa")
        cards_grid.addWidget(self.env_ready_card, 1, 0)
        
        self.env_busy_card = StatCard("忙碌环境", "0", "正在使用", "#a78bfa")
        cards_grid.addWidget(self.env_busy_card, 1, 1)
        
        # 模块统计
        self.modules_card = StatCard("已加载模块", "0", "已启用", "#34d399")
        cards_grid.addWidget(self.modules_card, 1, 2)
        
        layout.addLayout(cards_grid)
        
        # 快速操作区
        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """)
        actions_layout = QVBoxLayout(actions_frame)
        actions_layout.setContentsMargins(20, 20, 20, 20)
        
        actions_title = QLabel("⚡ 快速操作")
        actions_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        actions_layout.addWidget(actions_title)
        
        actions_btns = QHBoxLayout()
        actions_btns.setSpacing(12)
        
        btn_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """
        
        refresh_modules_btn = QPushButton("🔄 刷新模块")
        refresh_modules_btn.setStyleSheet(btn_style)
        refresh_modules_btn.clicked.connect(self._refresh_modules)
        actions_btns.addWidget(refresh_modules_btn)
        
        view_logs_btn = QPushButton("📋 查看日志")
        view_logs_btn.setStyleSheet(btn_style)
        actions_btns.addWidget(view_logs_btn)
        
        actions_btns.addStretch()
        actions_layout.addLayout(actions_btns)
        
        layout.addWidget(actions_frame)
        
        layout.addStretch()
    
    def _setup_timer(self):
        """设置自动刷新定时器。"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_data)
        self._timer.start(5000)  # 每 5 秒刷新
    
    def load_data(self):
        """加载统计数据。"""
        self._load_task_stats()
        self._load_env_stats()
        self._load_module_stats()
    
    def _load_task_stats(self):
        """加载任务统计。"""
        try:
            service = get_task_service()
            tasks = service.list_recent(100)
            
            running = sum(1 for t in tasks if t.status == TaskStatus.RUNNING)
            completed = sum(1 for t in tasks if t.status == TaskStatus.SUCCEEDED)
            failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
            
            self.running_card.set_value(str(running))
            self.completed_card.set_value(str(completed))
            self.failed_card.set_value(str(failed))
        except Exception:
            pass
    
    def _load_env_stats(self):
        """加载环境统计。"""
        try:
            from src.core.rem.manager import get_environment_manager
            manager = get_environment_manager()
            # 同步访问内存中的环境列表
            envs = list(manager.pool._environments.values())
            
            ready = sum(1 for e in envs if e.status == EnvStatus.READY)
            busy = sum(1 for e in envs if e.status == EnvStatus.BUSY)
            
            self.env_ready_card.set_value(str(ready))
            self.env_busy_card.set_value(str(busy))
        except Exception:
            pass
    
    def _load_module_stats(self):
        """加载模块统计。"""
        try:
            registry = get_module_registry()
            modules = registry.list_modules()
            
            total = len(modules)
            enabled = sum(1 for m in modules if m.status == ModuleStatus.ENABLED)
            
            self.modules_card.set_value(str(total))
            self.modules_card.set_subtitle(f"{enabled} 已启用")
        except Exception:
            pass
    
    def _refresh_modules(self):
        """刷新模块。"""
        try:
            registry = get_module_registry()
            registry.refresh()
            self._load_module_stats()
        except Exception:
            pass
