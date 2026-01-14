"""任务列表组件。

显示任务配置及其运行状态，支持 创建/运行/停止/刷新 操作。
"""

import asyncio
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import AutomationTask, TaskStatus
from src.core.atm.service import get_task_service
from src.ui.components.table import SkyTableWidget


class TaskListWidget(QWidget):
    """任务列表组件。"""
    
    task_selected = pyqtSignal(str)
    
    COLUMNS = ["任务名称", "策略ID", "Cron", "最后运行时间", "耗时", "状态", "操作"]
    STATUS_COLORS = {
        TaskStatus.IDLE: "#9ca3af",
        TaskStatus.STARTING: "#60a5fa",
        TaskStatus.RUNNING: "#facc15",
        TaskStatus.SUCCEEDED: "#4ade80",
        TaskStatus.FAILED: "#f87171",
        TaskStatus.CANCELLED: "#9ca3af",
        TaskStatus.INTERRUPTED: "#fca5a5",
    }
    STATUS_TEXT = {
        TaskStatus.IDLE: "空闲",
        TaskStatus.STARTING: "启动中",
        TaskStatus.RUNNING: "运行中",
        TaskStatus.SUCCEEDED: "成功",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELLED: "已取消",
        TaskStatus.INTERRUPTED: "已中断",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[AutomationTask] = []
        self._page = 0
        self._page_size = 20
        self._setup_ui()
        
        # 自动刷新定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start(5000)  # 5秒刷新一次
    
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
        self.table = SkyTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(6, 180)  # 操作列宽一点
        self.table.cellClicked.connect(self._on_cell_clicked)
        
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
            self._tasks = service.list_tasks()  # 获取配置列表
            self._render_page()
        except Exception as e:
            self._show_loading(False)
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        
        self._show_loading(False)

    def _auto_refresh(self):
        """自动刷新数据（静默模式）。"""
        if self.isVisible():
            self.load_data()

    def _render_page(self):
        """渲染当前页。"""
        self.table.setRowCount(0)
        service = get_task_service()
        
        start = self._page * self._page_size
        end = start + self._page_size
        page_tasks = self._tasks[start:end]
        
        running_count = 0
        
        for task in page_tasks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Fetch last run info
            last_run = service.get_last_run(task.id)
            status = last_run.status if last_run else TaskStatus.IDLE
            
            # 1. 任务名称
            name_item = QTableWidgetItem(task.name)
            name_item.setData(Qt.ItemDataRole.UserRole, task.id)
            self.table.setItem(row, 0, name_item)
            
            # 2. 策略ID
            self.table.setItem(row, 1, QTableWidgetItem(task.strategy_id))
            
            # 3. Cron
            self.table.setItem(row, 2, QTableWidgetItem(task.cron_expression or "-"))
            
            # 4. 最后运行时间 & 5. 耗时
            start_time_str = "-"
            duration_str = "-"
            
            if last_run and last_run.start_time:
                start_dt = datetime.fromtimestamp(last_run.start_time)
                start_time_str = start_dt.strftime("%m-%d %H:%M:%S")
                
                if last_run.end_time:
                    duration = last_run.end_time - last_run.start_time
                    duration_str = f"{duration}s"
                elif status == TaskStatus.RUNNING:
                    duration = int(datetime.now().timestamp() - last_run.start_time)
                    duration_str = f"{duration}s..."
            
            self.table.setItem(row, 3, QTableWidgetItem(start_time_str))
            self.table.setItem(row, 4, QTableWidgetItem(duration_str))
            
            # 6. 状态
            status_text = self.STATUS_TEXT.get(status, status.value)
            status_item = QTableWidgetItem(status_text)
            if status in self.STATUS_COLORS:
                status_item.setForeground(QColor(self.STATUS_COLORS[status]))
            self.table.setItem(row, 5, status_item)
            
            # 7. 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(8)
            
            if status == TaskStatus.RUNNING:
                # 运行中 -> 显示"停止"
                stop_btn = QPushButton("⏹ 停止")
                stop_btn.setStyleSheet("background: #f87171; color: white; border: none; padding: 4px 10px; border-radius: 4px;")
                stop_btn.clicked.connect(lambda _, tid=task.id: self._stop_task(tid))
                action_layout.addWidget(stop_btn)
                running_count += 1
            else:
                # 空闲/完成 -> 显示"运行"
                run_btn = QPushButton("▶ 运行")
                run_btn.setStyleSheet("background: #60a5fa; color: white; border: none; padding: 4px 10px; border-radius: 4px;")
                run_btn.clicked.connect(lambda _, tid=task.id: self._run_task(tid))
                action_layout.addWidget(run_btn)
            
            # 删除按钮 (总是显示)
            del_btn = QPushButton("🗑")
            del_btn.setStyleSheet("background: transparent; color: #9ca3af; border: 1px solid #4b5563; padding: 4px 8px; border-radius: 4px;")
            del_btn.clicked.connect(lambda _, tid=task.id: self._delete_task(tid))
            action_layout.addWidget(del_btn)
            
            action_layout.addStretch()
            self.table.setCellWidget(row, 6, action_widget)
        
        # 更新统计和分页
        total = len(self._tasks)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        
        self.stats_label.setText(f"共 {total} 个任务配置，{running_count} 个正在运行")
        self.page_label.setText(f"第 {self._page + 1} / {total_pages} 页")
        
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)
    
    def _run_task(self, task_id: str):
        """触发任务。"""
        try:
            # get_task_service().run_and_wait(task_id) # async wrap?
            # PyQt cannot await directly. Use asyncio.create_task helper or fire-and-forget
            # Service run_task is async.
            # Convert to sync call for UI button
            asyncio.create_task(self._async_run_task(task_id))
            self.load_data() # Optimistic update
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动失败: {e}")

    async def _async_run_task(self, task_id: str):
        try:
            await get_task_service().run_task(task_id)
            # 刷新UI (需要在主线程? PyQt signals are thread-safe)
            # self.load_data() -> this is usually safe if called from async task on same loop
        except Exception as e:
            print(f"Run Error: {e}") # TODO: Log properly

    def _stop_task(self, task_id: str):
        """停止任务。"""
        try:
            asyncio.create_task(get_task_service().stop_task(task_id))
            # self.load_data() # Refresh will happen by timer or user
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止失败: {e}")

    def _delete_task(self, task_id: str):
        """删除任务。"""
        reply = QMessageBox.question(
            self, "确认删除", 
            "确定要删除该任务吗？执行历史可能会保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if get_task_service().delete_task(task_id):
                self.load_data()
            else:
                QMessageBox.warning(self, "错误", "删除失败")

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
        # 选中行逻辑
        pass

    def _on_create_task(self):
        """新建任务。"""
        from src.core.atm.ui.task_create_dialog import TaskCreateDialog

        dialog = TaskCreateDialog(parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            try:
                get_task_service().create_task(
                    name=data['name'], 
                    strategy_id=data['strategy_id'],
                    cron=data.get('cron')
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "创建失败", str(e))

