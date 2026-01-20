"""任务列表组件。

显示任务配置及其运行状态，支持 创建/运行/停止/刷新 操作。
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import AutomationTask, TaskStatus
from src.core.atm.service import get_task_service
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.ui.components.data_table import SkyDataTable


@dataclass
class TaskDisplayItem:
    """任务显示项包装。"""
    raw: AutomationTask
    display_last_run: str
    display_duration: str
    display_status: TaskStatus
    display_status_text: str


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
        TaskStatus.CANCELLED: "#9ca3af",
    }

    STATUS_TEXT = {
        TaskStatus.IDLE: "空闲",
        TaskStatus.STARTING: "启动中",
        TaskStatus.RUNNING: "运行中",
        TaskStatus.SUCCEEDED: "成功",
        TaskStatus.FAILED: "失败",
        TaskStatus.CANCELLED: "已取消",
        TaskStatus.CANCELLED: "已取消",
    }

    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: list[AutomationTask] = []
        
        self._setup_ui()
        
        # 初始加载 (Delay to ensure loop is running)
        QTimer.singleShot(0, self.load_data)
        
        # 订阅事件
        bus = get_event_bus()
        bus.subscribe(EventType.TASK_CONFIG_CREATED, self._on_task_changed)
        bus.subscribe(EventType.TASK_CONFIG_DELETED, self._on_task_changed)
        bus.subscribe(EventType.TASK_STARTED, self._on_task_changed)
        bus.subscribe(EventType.TASK_FINISHED, self._on_task_changed)
        bus.subscribe(EventType.TASK_FAILED, self._on_task_changed)
        bus.subscribe(EventType.TASK_CANCELLED, self._on_task_changed)

    def _on_task_changed(self, event: Event):

        """事件回调：刷新列表。"""
        self.load_data()
    
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

        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            QPushButton:disabled { background: rgba(99, 102, 241, 0.3); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # 表格 (SkyDataTable)
        from src.ui.components.data_table import SkyDataTable
        
        columns = [
            ("name", "任务名称", -1),
            ("strategy_id", "策略ID", 100),
            ("cron", "Cron", 100),
            ("last_run", "最后运行时间", 140),
            ("duration", "耗时", 80),
            ("status", "状态", 80),
            ("actions", "操作", 180),
        ]
        
        self.table = SkyDataTable(columns=columns)
        self.table.set_render_callback(self._render_row)
        layout.addWidget(self.table)
        
    def load_data(self):
        """加载任务数据 (Async wrapper)。"""
        asyncio.create_task(self._load_data_async())

    # Removed TaskDisplayItem and TaskListWidget redefinition to merge class body
    # ... (keeps existing)

    async def _load_data_async(self):
        """异步加载数据。"""
        self.table.set_loading(True)
        self.error_label.hide()
        
        try:
            service = get_task_service()
            self._tasks = await service.list_tasks()  # async await
            
            task_display_items = []
            for task in self._tasks:
                last_run = await service.get_last_run(task.id)
                status = last_run.status if last_run else TaskStatus.IDLE
                
                # 计算显示数据
                start_time_str = "-"
                duration_str = "-"
                
                if last_run and last_run.start_time:
                    start_dt = datetime.fromtimestamp(last_run.start_time)
                    start_time_str = start_dt.strftime("%m-%d %H:%M:%S")
                    
                    if last_run.end_time:
                        duration = last_run.end_time - last_run.start_time
                        duration_str = f"{duration}s"
                    elif status == TaskStatus.RUNNING:
                        try:
                            duration = int(datetime.now().timestamp() - last_run.start_time)
                            duration_str = f"{duration}s..."
                        except:
                            duration_str = "-"
                
                status_text = self.STATUS_TEXT.get(status, status.value)
                
                task_display_items.append(TaskDisplayItem(
                    raw=task,
                    display_last_run=start_time_str,
                    display_duration=duration_str,
                    display_status=status,
                    display_status_text=status_text
                ))
            
            self.table.set_data(task_display_items)
        
        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
        finally:
             self.table.set_loading(False)

    def _render_row(self, row: int, item: TaskDisplayItem, table):
        """渲染单行。"""
        task = item.raw
        
        # 0. 任务名称
        name_item = QTableWidgetItem(task.name)
        name_item.setData(Qt.ItemDataRole.UserRole, task.id)
        table.setItem(row, 0, name_item)
        
        # 1. 策略ID
        table.setItem(row, 1, QTableWidgetItem(task.strategy_id))
        
        # 2. Cron
        table.setItem(row, 2, QTableWidgetItem(task.cron_expression or "-"))
        
        # 3. 最后运行时间
        table.setItem(row, 3, QTableWidgetItem(item.display_last_run))
        
        # 4. 耗时
        table.setItem(row, 4, QTableWidgetItem(item.display_duration))
        
        # 5. 状态
        status = item.display_status
        status_text = item.display_status_text
        
        status_item = QTableWidgetItem(status_text)
        if status in self.STATUS_COLORS:
            status_item.setForeground(QColor(self.STATUS_COLORS[status]))
        table.setItem(row, 5, status_item)
        
        # 6. 操作按钮
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
        table.setCellWidget(row, 6, action_widget)
            
    # _stop_task, _run_task, _delete_task, ... (保持不变，省略未修改部分)

    
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
            asyncio.create_task(self._async_delete_task(task_id))

    async def _async_delete_task(self, task_id: str):
        try:
            success = await get_task_service().delete_task(task_id)
            if not success:
               QMessageBox.warning(self, "错误", "删除失败")
            # load_data is triggered by event bus
        except Exception as e:
            QMessageBox.warning(self, "错误", f"删除异常: {e}")

    
    def _on_cell_clicked(self, row: int, col: int):
        # 忽略操作列
        if col == 6:
            return
            
        # 获取任务ID
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        task_id = name_item.data(Qt.ItemDataRole.UserRole)
        
        # 打开详情
        from src.core.atm.ui.task_detail_dialog import TaskDetailDialog
        dialog = TaskDetailDialog(task_id, parent=self)
        dialog.exec()

    def _on_create_task(self):
        """新建任务。"""
        from src.core.atm.ui.task_create_dialog import TaskCreateDialog

        dialog = TaskCreateDialog(parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            asyncio.create_task(self._async_create_task(data))

    async def _async_create_task(self, data):
        try:
            await get_task_service().create_task(
                name=data['name'], 
                strategy_id=data['strategy_id'],
                cron=data.get('cron')
            )
            # No need to manual refresh, EventBus will trigger it
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

