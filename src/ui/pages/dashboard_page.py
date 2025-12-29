"""Dashboard page.

The main control console for managing automation tasks.
"""

import asyncio

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.config import config
from src.core.events import get_event_bus
from src.core.scheduler import Scheduler
from src.ui.widgets.log_viewer import LogViewer
from src.ui.widgets.toast import Toast
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


class DashboardPage(QWidget):
    """Dashboard / Console page.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────────┐
    │  控制面板 [开始] [停止] [重置] [并发: 5▼]                        │
    ├─────────────────────────────────────────────────────────────────┤
    │  运行中的环境                                                    │
    │  [Table: ID | 携程账号 | 劳保账号 | 状态 | 进度]                 │
    ├─────────────────────────────────────────────────────────────────┤
    │  实时日志                                                        │
    │  [Log Viewer]                                                    │
    └─────────────────────────────────────────────────────────────────┘
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scheduler = Scheduler()
        self.env_repo = EnvironmentRepository()
        self._is_running = False
        self._scheduler_task = None
        
        self._setup_ui()
        self._connect_signals()
        self._load_data()
    
    def _setup_ui(self):
        """Setup the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Control panel
        control_group = QGroupBox("控制面板")
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(12)
        
        # Start button
        self.start_btn = QPushButton("▶ 开始任务")
        self.start_btn.setObjectName("success")
        self.start_btn.setMinimumWidth(120)
        control_layout.addWidget(self.start_btn)
        
        # Stop button
        self.stop_btn = QPushButton("⏹ 停止任务")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(120)
        control_layout.addWidget(self.stop_btn)
        
        # Reset button
        self.reset_btn = QPushButton("⟳ 重置统计")
        self.reset_btn.setMinimumWidth(100)
        control_layout.addWidget(self.reset_btn)
        
        control_layout.addStretch()
        
        # Concurrency selector (Sync with current config)
        control_layout.addWidget(QLabel("并发:"))
        self.concurrency_combo = QComboBox()
        for i in range(1, 21):
            self.concurrency_combo.addItem(str(i), i)
        self.concurrency_combo.setCurrentText(str(config.concurrency_limit))
        self.concurrency_combo.setMinimumWidth(70)
        control_layout.addWidget(self.concurrency_combo)
        
        layout.addWidget(control_group)
        
        # Splitter for table and logs
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Environment table
        env_group = QGroupBox("运行中的环境")
        env_layout = QVBoxLayout(env_group)
        
        # Stats label
        self.env_stats = QLabel("共 0 个环境，运行中: 0")
        self.env_stats.setStyleSheet("color: #a6adc8;")
        env_layout.addWidget(self.env_stats)
        
        # Table
        self.env_table = QTableWidget()
        self.env_table.setColumnCount(5)
        self.env_table.setHorizontalHeaderLabels([
            "ID", "携程账号", "劳保账号", "状态", "进度"
        ])
        self.env_table.setAlternatingRowColors(True)
        self.env_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.env_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        v_header = self.env_table.verticalHeader()
        if v_header:
            v_header.setVisible(False)
        
        # Column widths
        header = self.env_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.env_table.setColumnWidth(0, 80)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            self.env_table.setColumnWidth(3, 100)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.env_table.setColumnWidth(4, 90)
        
        env_layout.addWidget(self.env_table)
        splitter.addWidget(env_group)
        
        # Log viewer
        log_group = QGroupBox("实时日志")
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = LogViewer()
        log_layout.addWidget(self.log_viewer)
        splitter.addWidget(log_group)
        
        # Set splitter sizes
        splitter.setSizes([300, 200])
        
        layout.addWidget(splitter, 1)

    def _connect_signals(self):
        """Connect signals and slots."""
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.reset_btn.clicked.connect(self._on_reset)
        self.concurrency_combo.currentIndexChanged.connect(self._on_concurrency_changed)
        
        # Connect logger
        logger.signals.log_added.connect(self.log_viewer.add_log)
        
        # Connect event bus for live updates
        bus = get_event_bus()
        bus.environment_status_changed.connect(self._on_env_status_changed)
        bus.labor_stats_updated.connect(lambda _: self._load_data())
    
    def _load_data(self):
        """Load environmental data from repository."""
        envs = self.env_repo.get_all(limit=100)
        
        # Map to display format
        ctrip_repo = CtripAccountRepository()
        labor_repo = LaborAccountRepository()
        
        self.env_table.setRowCount(len(envs))
        running_count = 0
        
        for row, env in enumerate(envs):
            # Fetch phone numbers
            ctrip = ctrip_repo.get_by_id(env["ctrip_account_id"])
            labor = labor_repo.get_by_id(env["labor_account_id"])
            
            # ID
            self.env_table.setItem(row, 0, QTableWidgetItem(f"ENV-{env['id']}"))
            
            # Phone numbers (masked)
            if ctrip:
                ctrip_phone = f"{ctrip.get('country_code', '+86')} {ctrip.get('phone_number', '')}"
                if len(ctrip.get('phone_number', '')) >= 7:
                    ctrip_phone = f"{ctrip.get('country_code', '+86')} {ctrip.get('phone_number', '')[:3]}****{ctrip.get('phone_number', '')[-4:]}"
                self.env_table.setItem(row, 1, QTableWidgetItem(ctrip_phone))
            else:
                self.env_table.setItem(row, 1, QTableWidgetItem("-"))
            
            self.env_table.setItem(row, 2, QTableWidgetItem(labor["phone"] if labor else "-"))
            
            # Status
            status = env.get("status", "idle")
            status_display = self._get_status_display(status)
            self.env_table.setItem(row, 3, QTableWidgetItem(status_display))
            
            # Progress (tasks completed / total)
            completed = labor.get("completed_count", 0) if labor else 0
            self.env_table.setItem(row, 4, QTableWidgetItem(f"{completed} done"))
            
            if status == "running":
                running_count += 1
                
        self.env_stats.setText(f"共 {len(envs)} 个环境，运行中: {running_count}")

    def _get_status_display(self, status: str) -> str:
        """Get display string for status."""
        status_map = {
            "idle": "⚪ 空闲",
            "running": "🟢 运行中",
            "logging_in": "🟡 登录中",
            "searching": "🔵 搜索中",
            "submitting": "🟢 提交中",
            "error": "🔴 错误",
        }
        return status_map.get(status, status)
    
    def _on_start(self):
        """Handle start button click."""
        if self._is_running:
            return
        
        # Create task in the integrated qasync event loop
        self._scheduler_task = asyncio.create_task(self.scheduler.start())
        
        self._is_running = True
        self._update_button_states()
        logger.info("任务调度器已开启")
        Toast.success(self, "自动化任务已开始")
    
    def _on_stop(self):
        """Handle stop button click."""
        if not self._is_running:
            return
            
        self.scheduler.stop()
        self._is_running = False
        self._update_button_states()
        logger.info("正在停止所有任务...")
        Toast.info(self, "正在停止任务...")
    
    def _on_reset(self):
        """Handle reset button click."""
        self.log_viewer.clear()
        # Potential: reset all environment statuses in DB if crashed?
        # For now just UI clear
        logger.info("控制台日志面板已清空")
        Toast.info(self, "日志已清空")
    
    def _on_concurrency_changed(self, index: int):
        """Handle concurrency change."""
        value = self.concurrency_combo.itemData(index)
        config.concurrency_limit = value
        logger.info(f"核心调整：最大并发数已设为 {value}")
    
    def _update_button_states(self):
        """Update button enabled states."""
        self.start_btn.setEnabled(not self._is_running)
        self.stop_btn.setEnabled(self._is_running)
        
        if self._is_running:
            self.start_btn.setText("⏳ 运行中")
            self.start_btn.setStyleSheet("background-color: #45475a;") # Dull it
        else:
            self.start_btn.setText("▶ 开始任务")
            self.start_btn.setStyleSheet("") # Restore primary success color

    def _on_env_status_changed(self, data: dict):
        """Slot for environment status changes."""
        # For now, full reload is safest to maintain sync with Repo
        self._load_data()
