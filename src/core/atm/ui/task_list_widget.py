"""任务(Job)列表组件。

显示作业配置及其状态，支持 创建/启动/暂停/删除 操作。
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

from src.core.atm.models import Job, JobState, JobType
from src.core.atm.service import get_task_service
from src.core.foundation.event_bus import Event
from src.core.tsm.loader import get_strategy_loader


@dataclass
class JobDisplayItem:
    """Job 显示项包装。"""
    raw: Job
    display_status_text: str
    display_status_color: str


class TaskListWidget(QWidget):
    """任务(Job)列表组件。"""

    task_selected = pyqtSignal(str)

    COLUMNS = ["作业名称", "类型", "策略ID", "目标并发", "触发规则", "状态", "操作"]
    
    STATUS_COLORS = {
        JobState.ACTIVE: "#facc15",    # Yellow
        JobState.PAUSED: "#9ca3af",    # Grey
        JobState.COMPLETED: "#4ade80", # Green
        JobState.ERROR: "#f87171",     # Red
    }

    STATUS_TEXT = {
        JobState.ACTIVE: "运行中",
        JobState.PAUSED: "已暂停",
        JobState.COMPLETED: "已完成",
        JobState.ERROR: "异常",
    }

    TYPE_TEXT = {
        JobType.BATCH: "批处理",
        JobType.SERVICE: "常驻服务",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[Job] = []

        self._setup_ui()

        # 初始加载 (Delay to ensure loop is running)
        QTimer.singleShot(0, self.load_data)

        # 订阅事件 (TODO: Add JOB events)
        # bus = get_event_bus()
        # bus.subscribe(EventType.TASK_CONFIG_CREATED, self._on_task_changed)

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

        self.create_btn = QPushButton("+ 新建作业")
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
        self.create_btn.clicked.connect(self._on_create_job)
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

        columns_config = [
            ("name", "作业名称", -1),
            ("type", "类型", 100),
            ("strategy", "策略名称", 120),
            ("concurrency", "目标并发", 80),
            ("trigger", "触发规则", 120),
            ("status", "状态", 80),
            ("actions", "操作", 180),
        ]

        self.table = SkyDataTable(columns=columns_config)
        self.table.set_render_callback(self._render_row)
        self.table.cell_clicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def load_data(self):
        """加载数据。"""
        asyncio.create_task(self._load_data_async())

    async def _load_data_async(self):
        """异步加载数据。"""
        self.table.set_loading(True)
        self.error_label.hide()

        try:
            service = get_task_service()
            self._jobs = await service.list_jobs()

            display_items = []
            for job in self._jobs:
                status_text = self.STATUS_TEXT.get(job.state, job.state.value)
                status_color = self.STATUS_COLORS.get(job.state, "#9ca3af")
                
                display_items.append(JobDisplayItem(
                    raw=job,
                    display_status_text=status_text,
                    display_status_color=status_color
                ))

            self.table.set_data(display_items)

        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
        finally:
            self.table.set_loading(False)

    def _render_row(self, row: int, item: JobDisplayItem, table):
        """渲染单行。"""
        job = item.raw

        # 0. 名称
        name_item = QTableWidgetItem(job.name)
        name_item.setData(Qt.ItemDataRole.UserRole, job.id)
        table.setItem(row, 0, name_item)

        # 1. 类型
        type_str = self.TYPE_TEXT.get(job.type, job.type.value)
        table.setItem(row, 1, QTableWidgetItem(type_str))

        # 2. 策略
        strategy_text = job.strategy_id
        strategy = get_strategy_loader().get(job.strategy_id)
        if strategy:
            strategy_text = strategy.name
        
        strategy_item = QTableWidgetItem(strategy_text)
        strategy_item.setToolTip(f"ID: {job.strategy_id}")
        table.setItem(row, 2, strategy_item)
        
        # 3. 并发
        table.setItem(row, 3, QTableWidgetItem(str(job.concurrency_target)))

        # 4. Trigger
        trigger_text = job.trigger.type.value
        if job.trigger.cron_expr:
            trigger_text += f" ({job.trigger.cron_expr})"
        table.setItem(row, 4, QTableWidgetItem(trigger_text))

        # 5. 状态
        status_item = QTableWidgetItem(item.display_status_text)
        status_item.setForeground(QColor(item.display_status_color))
        table.setItem(row, 5, status_item)

        # 6. 操作按钮
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(8)

        if job.state == JobState.ACTIVE:
            # 运行中 -> 显示"暂停"
            stop_btn = QPushButton("⏸ 暂停")
            stop_btn.setStyleSheet("background: #fb923c; color: white; border: none; padding: 4px 10px; border-radius: 4px;")
            stop_btn.clicked.connect(lambda _, jid=job.id: self._pause_job(jid))
            action_layout.addWidget(stop_btn)
        else:
            # 暂停/其他 -> 显示"启动"
            run_btn = QPushButton("▶ 启动")
            run_btn.setStyleSheet("background: #60a5fa; color: white; border: none; padding: 4px 10px; border-radius: 4px;")
            run_btn.clicked.connect(lambda _, jid=job.id: self._start_job(jid))
            action_layout.addWidget(run_btn)

        # 编辑按钮
        edit_btn = QPushButton("✏️")
        edit_btn.setStyleSheet("background: transparent; color: #9ca3af; border: 1px solid #4b5563; padding: 4px 8px; border-radius: 4px;")
        edit_btn.clicked.connect(lambda _, jid=job.id: self._edit_job(jid))
        action_layout.addWidget(edit_btn)

        # 删除按钮
        del_btn = QPushButton("🗑")
        del_btn.setStyleSheet("background: transparent; color: #9ca3af; border: 1px solid #4b5563; padding: 4px 8px; border-radius: 4px;")
        del_btn.clicked.connect(lambda _, jid=job.id: self._delete_job(jid))
        action_layout.addWidget(del_btn)

        action_layout.addStretch()
        table.setCellWidget(row, 6, action_widget)

    def _start_job(self, job_id: str):
        asyncio.create_task(self._async_op(job_id, "start"))

    def _pause_job(self, job_id: str):
        asyncio.create_task(self._async_op(job_id, "pause"))

    def _delete_job(self, job_id: str):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除该作业吗？关联的任务记录可能会被清理。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            asyncio.create_task(self._async_op(job_id, "delete"))

    async def _async_op(self, job_id: str, op: str):
        service = get_task_service()
        try:
            if op == "start":
                await service.start_job(job_id)
            elif op == "pause":
                await service.pause_job(job_id)
            elif op == "delete":
                await service.delete_job(job_id)
            
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "操作失败", str(e))

    def _edit_job(self, job_id: str):
        """编辑作业。"""
        # Find job instance
        job = next((j for j in self._jobs if j.id == job_id), None)
        if not job:
            return

        from src.core.atm.ui.task_create_dialog import TaskCreateDialog
        dialog = TaskCreateDialog(parent=self, job=job)
        if dialog.exec() == dialog.DialogCode.Accepted:
            data = dialog.get_job_data()
            asyncio.create_task(self._async_update_job(job_id, data))

    async def _async_update_job(self, job_id: str, data: dict):
        try:
            # Pop job_type if present and map to job_type arg if needed, 
            # or just pass data if keys match.
            # Service.update_job args: job_id, name, job_type, trigger_config, strategy_id, params, concurrency
            
            # Map 'job_type' key from dialog to 'job_type' arg in service
            # Dialog returns 'job_type', Service expects 'job_type'.
            
            await get_task_service().update_job(job_id, **data)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "更新失败", str(e))

    def _on_create_job(self):
        from src.core.atm.ui.task_create_dialog import TaskCreateDialog
        dialog = TaskCreateDialog(parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            data = dialog.get_job_data()
            asyncio.create_task(self._async_create_job(data))

    async def _async_create_job(self, data):
        try:
            await get_task_service().create_job(**data)
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))
    
    def _on_cell_clicked(self, row: int, col: int):
        # 忽略操作列
        if col == 6:
            return
            
        # 获取作业ID
        name_item = self.table.item(row, 0)
        if not name_item:
            return
        job_id = name_item.data(Qt.ItemDataRole.UserRole)
        
        # 打开详情
        from src.core.atm.ui.task_detail_dialog import JobDetailDialog
        dialog = JobDetailDialog(job_id, parent=self)
        dialog.exec()
