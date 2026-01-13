"""任务列表组件。

显示任务执行状态和历史，支持停止/重试操作。
"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
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

from src.core.atm import TaskStatus, get_task_service


class TaskListWidget(QWidget):
    """任务列表组件。"""
    
    task_selected = pyqtSignal(str)
    
    COLUMNS = ["ID", "模块", "任务", "状态", "创建时间", "耗时", "操作"]
    STATUS_COLORS = {
        TaskStatus.PENDING: "#60a5fa",
        TaskStatus.QUEUED: "#a78bfa",
        TaskStatus.RUNNING: "#facc15",
        TaskStatus.SUCCEEDED: "#4ade80",
        TaskStatus.FAILED: "#f87171",
        TaskStatus.CANCELLED: "#9ca3af",
    }
    STATUS_TEXT = {
        TaskStatus.PENDING: "等待中",
        TaskStatus.QUEUED: "排队中",
        TaskStatus.RUNNING: "运行中",
        TaskStatus.SUCCEEDED: "成功",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELLED: "已取消",
        TaskStatus.INTERRUPTED: "已中断",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = []
        self._page = 0
        self._page_size = 20
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("任务监控")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.create_btn = QPushButton("+ 新建任务")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
        """)
        self.create_btn.clicked.connect(self._on_create_task)
        header.addWidget(self.create_btn)

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
        self.loading_bar.setMaximum(0)
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
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(6, 120)
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
        
        # 分页栏
        pagination = QHBoxLayout()
        
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        pagination.addWidget(self.stats_label)
        
        pagination.addStretch()
        
        self.prev_btn = QPushButton("◀ 上一页")
        self.prev_btn.clicked.connect(self._prev_page)
        self.prev_btn.setEnabled(False)
        pagination.addWidget(self.prev_btn)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setStyleSheet("color: white; padding: 0 10px;")
        pagination.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页 ▶")
        self.next_btn.clicked.connect(self._next_page)
        pagination.addWidget(self.next_btn)
        
        layout.addLayout(pagination)
    
    def load_data(self):
        """加载任务数据。"""
        self._show_loading(True)
        self.error_label.hide()
        
        try:
            service = get_task_service()
            self._tasks = service.list_recent(100)
            self._render_page()
        except Exception as e:
            self._show_loading(False)
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        
        self._show_loading(False)
    
    def _render_page(self):
        """渲染当前页。"""
        self.table.setRowCount(0)
        
        start = self._page * self._page_size
        end = start + self._page_size
        page_tasks = self._tasks[start:end]
        
        running = 0
        for task in page_tasks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ID
            id_item = QTableWidgetItem(task.id[:8] + "...")
            id_item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.table.setItem(row, 0, id_item)
            
            # 模块
            self.table.setItem(row, 1, QTableWidgetItem(task.module))
            
            # 任务名
            self.table.setItem(row, 2, QTableWidgetItem(task.name))
            
            # 状态
            status_text = self.STATUS_TEXT.get(task.status, task.status.value)
            status_item = QTableWidgetItem(status_text)
            if task.status in self.STATUS_COLORS:
                status_item.setForeground(QColor(self.STATUS_COLORS[task.status]))
            self.table.setItem(row, 3, status_item)
            
            # 创建时间
            created = datetime.fromtimestamp(task.created_at).strftime("%H:%M:%S")
            self.table.setItem(row, 4, QTableWidgetItem(created))
            
            # 耗时
            if task.started_at and task.ended_at:
                duration = task.ended_at - task.started_at
                self.table.setItem(row, 5, QTableWidgetItem(f"{duration}s"))
            elif task.started_at:
                self.table.setItem(row, 5, QTableWidgetItem("运行中..."))
            else:
                self.table.setItem(row, 5, QTableWidgetItem("-"))
            
            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)
            
            if task.status in {TaskStatus.RUNNING, TaskStatus.PENDING, TaskStatus.QUEUED}:
                stop_btn = QPushButton("⏹ 停止")
                stop_btn.setStyleSheet("background: #f87171; color: white; border: none; padding: 4px 8px; border-radius: 2px;")
                stop_btn.clicked.connect(lambda _, tid=task.id: self._stop_task(tid))
                action_layout.addWidget(stop_btn)
            elif task.status == TaskStatus.FAILED:
                retry_btn = QPushButton("🔄 重试")
                retry_btn.setStyleSheet("background: #60a5fa; color: white; border: none; padding: 4px 8px; border-radius: 2px;")
                retry_btn.clicked.connect(lambda _, tid=task.id: self._retry_task(tid))
                action_layout.addWidget(retry_btn)
            else:
                # 已完成/已取消
                action_layout.addWidget(QLabel("-"))
            
            self.table.setCellWidget(row, 6, action_widget)
            
            if task.status == TaskStatus.RUNNING:
                running += 1
        
        # 更新统计和分页
        total = len(self._tasks)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        
        self.stats_label.setText(f"共 {total} 个任务，{running} 个运行中")
        self.page_label.setText(f"第 {self._page + 1} / {total_pages} 页")
        
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)
    
    def _stop_task(self, task_id: str):
        """停止任务。"""
        try:
            service = get_task_service()
            service.stop(task_id)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止失败: {e}")
    
    def _retry_task(self, task_id: str):
        """重试任务。"""
        # TODO: 实现重试逻辑
        QMessageBox.information(self, "提示", f"重试功能开发中: {task_id[:8]}...")
    
    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()
    
    def _next_page(self):
        total_pages = (len(self._tasks) + self._page_size - 1) // self._page_size
        if self._page < total_pages - 1:
            self._page += 1
            self._render_page()
    
    def _show_loading(self, show: bool):
        if show:
            self.loading_bar.show()
            self.refresh_btn.setEnabled(False)
        else:
            self.loading_bar.hide()
            self.refresh_btn.setEnabled(True)
    
    def _on_cell_clicked(self, row: int, col: int):
        id_item = self.table.item(row, 0)
        if id_item:
            task_id = id_item.data(Qt.ItemDataRole.UserRole)
            self.task_selected.emit(task_id)

    def _on_create_task(self):
        """新建任务。"""
        from src.core.atm.ui.task_create_dialog import TaskCreateDialog

        dialog = TaskCreateDialog(parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            # TODO: 创建任务并保存
            from src.core.foundation.logging import logger
            logger.info(f"[ATM] 新建任务: {data['name']}, 策略: {data['strategy_id']}")
            self.load_data()
