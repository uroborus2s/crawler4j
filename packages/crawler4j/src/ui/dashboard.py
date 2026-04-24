"""Dashboard 仪表盘页面。

显示系统运行状态概览：
    - 任务统计
    - 环境状态
    - 模块概览
"""

import asyncio

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.atm import JobState, get_task_service
from src.core.mms import ModuleStatus, get_module_registry
from src.core.rem import EnvStatus
from src.ui.components.log_console import LogConsoleWidget
from src.ui.components.stat_card import StatCard


class DashboardPage(QWidget):
    """仪表盘页面。"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._load_seq = 0
        self._load_task: asyncio.Task[None] | None = None
        self._setup_ui()
        self._setup_timer()
        self.destroyed.connect(lambda *_args: self._cancel_pending_load())
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题栏
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("📊 仪表盘")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # 统计卡片网格
        self.cards_grid = QGridLayout()
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setHorizontalSpacing(12)
        self.cards_grid.setVerticalSpacing(8)
        
        # 任务 (Job) 统计
        self.running_card = StatCard("活跃作业", "0", subtitle="正在运行", accent_color="#facc15", compact=True)
        
        self.completed_card = StatCard("已完成作业", "0", subtitle="Batch Completed", accent_color="#4ade80", compact=True)
        
        self.failed_card = StatCard("异常作业", "0", subtitle="需要关注", accent_color="#f87171", compact=True)
        
        # 环境统计
        self.env_ready_card = StatCard("就绪环境", "0", subtitle="可用实例", accent_color="#60a5fa", compact=True)
        
        self.env_busy_card = StatCard("忙碌环境", "0", subtitle="正在使用", accent_color="#a78bfa", compact=True)
        
        # 模块统计
        self.modules_card = StatCard("已加载模块", "0", subtitle="已启用", accent_color="#34d399", compact=True)
        self._stat_cards = [
            self.running_card,
            self.completed_card,
            self.failed_card,
            self.env_ready_card,
            self.env_busy_card,
            self.modules_card,
        ]
        self._card_columns = 0
        self._apply_card_layout()
        
        layout.addLayout(self.cards_grid)
        
        # 实时日志区域
        log_title = QLabel("📋 系统实时日志")
        log_title.setStyleSheet("font-size: 15px; font-weight: bold; color: white;")
        layout.addWidget(log_title)
        
        self.log_console = LogConsoleWidget()
        self.log_console.setMinimumHeight(520)
        self.log_console.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        # 全局模式，不设置 filtered_task_id
        layout.addWidget(self.log_console, stretch=1)

    def _apply_card_layout(self) -> None:
        columns = 6
        if columns == self._card_columns:
            return
        self._card_columns = columns
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        for column in range(len(self._stat_cards)):
            self.cards_grid.setColumnStretch(column, 0)
        for index, card in enumerate(self._stat_cards):
            row = index // columns
            column = index % columns
            self.cards_grid.addWidget(card, row, column)
            self.cards_grid.setColumnStretch(column, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_card_layout()
    
    def _setup_timer(self):
        """设置自动刷新定时器。"""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_data)
        self._timer.start(5000)  # 每 5 秒刷新

    def _cancel_pending_load(self) -> None:
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()

    def _on_load_done(self, task: asyncio.Task[None]) -> None:
        if self._load_task is task:
            self._load_task = None

    def load_data(self):
        """加载统计数据。"""
        self._load_seq += 1
        seq = self._load_seq
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        coro = self._load_data_async(seq)
        try:
            task = asyncio.create_task(coro)
        except RuntimeError:
            coro.close()
            return
        self._load_task = task
        task.add_done_callback(self._on_load_done)

    async def _load_data_async(self, seq: int):
        if seq != self._load_seq:
            return
        self._load_env_stats()
        self._load_module_stats()
        await self._load_job_stats(seq)
    
    async def _load_job_stats(self, seq: int):
        """加载作业统计。"""
        try:
            service = get_task_service()
            jobs = await service.list_jobs()
            if seq != self._load_seq:
                return
            
            active = sum(1 for j in jobs if j.state == JobState.ACTIVE)
            completed = sum(1 for j in jobs if j.state == JobState.COMPLETED)
            error = sum(1 for j in jobs if j.state == JobState.ERROR)
            
            self.running_card.set_value(str(active))
            self.completed_card.set_value(str(completed))
            self.failed_card.set_value(str(error))
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
