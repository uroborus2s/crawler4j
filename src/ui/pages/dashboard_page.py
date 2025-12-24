"""Dashboard page.

The main control console for managing automation tasks.
"""

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QAbstractItemView,
)

from src.ui.widgets.log_viewer import LogViewer
from src.ui.widgets.toast import Toast
from src.core.events import event_bus, EventType
from src.utils.logger import logger


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
        
        self._is_running = False
        self._environments: list[dict] = []
        
        self._setup_ui()
        self._connect_signals()
    
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
        
        # Concurrency selector
        control_layout.addWidget(QLabel("并发:"))
        self.concurrency_combo = QComboBox()
        for i in range(1, 21):
            self.concurrency_combo.addItem(str(i), i)
        self.concurrency_combo.setCurrentText("10")
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
        self.env_table.verticalHeader().setVisible(False)
        
        # Column widths
        header = self.env_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.env_table.setColumnWidth(0, 80)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.env_table.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.env_table.setColumnWidth(4, 80)
        
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
        
        # Connect event bus
        event_bus.scheduler_status_changed.connect(self._on_scheduler_status)
        event_bus.environment_status_changed.connect(self._on_env_status)
    
    def _on_start(self):
        """Handle start button click."""
        self._is_running = True
        self._update_button_states()
        
        # Emit event
        event_bus.emit(EventType.SCHEDULER_STARTED)
        
        # Log
        logger.info("调度器已启动")
        Toast.success(self, "任务已启动")
    
    def _on_stop(self):
        """Handle stop button click."""
        self._is_running = False
        self._update_button_states()
        
        # Emit event
        event_bus.emit(EventType.SCHEDULER_STOPPED)
        
        # Log
        logger.info("调度器已停止")
        Toast.info(self, "任务已停止")
    
    def _on_reset(self):
        """Handle reset button click."""
        # Clear logs
        self.log_viewer.clear()
        
        # Log
        logger.info("统计数据已重置")
        Toast.info(self, "统计已重置")
    
    def _on_concurrency_changed(self, index: int):
        """Handle concurrency change."""
        value = self.concurrency_combo.itemData(index)
        event_bus.emit(EventType.CONCURRENCY_CHANGED, {"value": value})
        logger.info(f"并发数已调整为 {value}")
    
    def _update_button_states(self):
        """Update button enabled states."""
        self.start_btn.setEnabled(not self._is_running)
        self.stop_btn.setEnabled(self._is_running)
        
        if self._is_running:
            self.start_btn.setText("⏳ 运行中...")
        else:
            self.start_btn.setText("▶ 开始任务")
    
    @pyqtSlot(bool)
    def _on_scheduler_status(self, is_running: bool):
        """Handle scheduler status change from event bus."""
        self._is_running = is_running
        self._update_button_states()
    
    @pyqtSlot(int, str)
    def _on_env_status(self, env_id: int, status: str):
        """Handle environment status change from event bus."""
        self._refresh_env_table()
    
    def set_environments(self, environments: list[dict]):
        """Set the environment list data.
        
        Args:
            environments: List of environment dicts with keys:
                id, ctrip_phone, labor_phone, status, progress
        """
        self._environments = environments
        self._refresh_env_table()
    
    def _refresh_env_table(self):
        """Refresh the environment table display."""
        self.env_table.setRowCount(len(self._environments))
        
        running_count = 0
        for row, env in enumerate(self._environments):
            # ID
            self.env_table.setItem(row, 0, QTableWidgetItem(f"ENV-{env.get('id', '')}"))
            
            # Ctrip phone
            self.env_table.setItem(row, 1, QTableWidgetItem(env.get("ctrip_phone", "")))
            
            # Labor phone
            self.env_table.setItem(row, 2, QTableWidgetItem(env.get("labor_phone", "")))
            
            # Status with color
            status = env.get("status", "idle")
            status_display = self._get_status_display(status)
            status_item = QTableWidgetItem(status_display)
            self.env_table.setItem(row, 3, status_item)
            
            # Progress
            self.env_table.setItem(row, 4, QTableWidgetItem(env.get("progress", "0/0")))
            
            if status == "running":
                running_count += 1
        
        # Update stats
        self.env_stats.setText(f"共 {len(self._environments)} 个环境，运行中: {running_count}")
    
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
    
    def add_demo_data(self):
        """Add demo data for testing."""
        demo_envs = [
            {"id": 1, "ctrip_phone": "138****1234", "labor_phone": "user001", "status": "running", "progress": "3/5"},
            {"id": 2, "ctrip_phone": "139****5678", "labor_phone": "user002", "status": "searching", "progress": "4/5"},
            {"id": 3, "ctrip_phone": "137****9012", "labor_phone": "user003", "status": "logging_in", "progress": "1/5"},
        ]
        self.set_environments(demo_envs)
        
        # Add demo logs
        logger.info("环境 ENV-1 开始携程搜索，关键词: 北京酒店", environment_id=1)
        logger.info("环境 ENV-2 提交答案成功，题目ID: 12345", environment_id=2)
        logger.warning("环境 ENV-3 登录验证码触发，正在接码...", environment_id=3)
