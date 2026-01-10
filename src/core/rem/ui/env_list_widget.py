"""环境列表组件。

显示所有运行环境及其状态。
"""

import asyncio

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.rem import EnvStatus
from src.core.rem.pool import EnvPool


class DataLoaderThread(QThread):
    """数据加载线程。"""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, pool: EnvPool):
        super().__init__()
        self._pool = pool
    
    def run(self):
        try:
            # 同步获取环境列表
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            envs = loop.run_until_complete(self._pool.list_all())
            loop.close()
            self.finished.emit(envs)
        except Exception as e:
            self.error.emit(str(e))


class EnvListWidget(QWidget):
    """环境列表组件。
    
    显示环境池中所有环境的状态，支持刷新和操作。
    """
    
    # 信号
    env_selected = pyqtSignal(str)  # 选中环境ID
    
    COLUMNS = ["ID", "类型", "Provider", "状态", "任务"]
    STATUS_COLORS = {
        EnvStatus.READY: "#4ade80",      # 绿
        EnvStatus.BUSY: "#facc15",       # 黄
        EnvStatus.UNHEALTHY: "#f87171", # 红
        EnvStatus.CREATING: "#60a5fa",   # 蓝
    }
    STATUS_TEXT = {
        EnvStatus.READY: "就绪",
        EnvStatus.BUSY: "忙碌",
        EnvStatus.UNHEALTHY: "异常",
        EnvStatus.CREATING: "创建中",
        EnvStatus.PAUSED: "暂停",
        EnvStatus.TERMINATING: "终止中",
        EnvStatus.DEAD: "已销毁",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = EnvPool()
        self._loader_thread = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("运行环境")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            QPushButton:disabled { background: rgba(99, 102, 241, 0.3); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Loading 指示器
        self.loading_bar = QProgressBar()
        self.loading_bar.setMaximum(0)  # 无限循环
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(3)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)
        
        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.8);
                color: white;
                border: none;
                gridline-color: rgba(255, 255, 255, 0.1);
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: rgba(50, 50, 60, 0.9);
                color: white;
                padding: 10px;
                border: none;
            }
        """)
        
        layout.addWidget(self.table)
        
        # 统计栏
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    def load_data(self):
        """加载环境数据。"""
        self._show_loading(True)
        self.error_label.hide()
        self.refresh_btn.setEnabled(False)
        
        # 启动加载线程
        self._loader_thread = DataLoaderThread(self._pool)
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.error.connect(self._on_load_error)
        self._loader_thread.start()
    
    def _on_data_loaded(self, envs: list):
        """数据加载完成。"""
        self._show_loading(False)
        self.refresh_btn.setEnabled(True)
        
        self.table.setRowCount(0)
        
        ready_count = 0
        busy_count = 0
        
        for env in envs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ID (截断显示)
            self.table.setItem(row, 0, QTableWidgetItem(env.id[:8] + "..."))
            
            # 类型
            self.table.setItem(row, 1, QTableWidgetItem(env.kind.value))
            
            # Provider
            self.table.setItem(row, 2, QTableWidgetItem(env.provider))
            
            # 状态
            status_text = self.STATUS_TEXT.get(env.status, env.status.value)
            status_item = QTableWidgetItem(status_text)
            if env.status in self.STATUS_COLORS:
                from PyQt6.QtGui import QColor
                status_item.setForeground(QColor(self.STATUS_COLORS[env.status]))
            self.table.setItem(row, 3, status_item)
            
            # 任务
            task_id = env.task_run_id[:8] + "..." if env.task_run_id else "-"
            self.table.setItem(row, 4, QTableWidgetItem(task_id))
            
            if env.status == EnvStatus.READY:
                ready_count += 1
            elif env.status == EnvStatus.BUSY:
                busy_count += 1
        
        self._update_stats(len(envs), ready_count, busy_count)
    
    def _on_load_error(self, error: str):
        """加载出错。"""
        self._show_loading(False)
        self.refresh_btn.setEnabled(True)
        self.error_label.setText(f"❌ 加载失败: {error}")
        self.error_label.show()
    
    def _show_loading(self, show: bool):
        if show:
            self.loading_bar.show()
        else:
            self.loading_bar.hide()
    
    def _update_stats(self, total: int, ready: int, busy: int):
        self.stats_label.setText(f"总计: {total} | 就绪: {ready} | 忙碌: {busy}")
    
    def _on_cell_clicked(self, row: int, col: int):
        env_id_item = self.table.item(row, 0)
        if env_id_item:
            self.env_selected.emit(env_id_item.text())
