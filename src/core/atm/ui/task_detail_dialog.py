"""作业(Job)详情对话框。

显示作业配置信息及下属任务(Task)列表。
"""

import asyncio
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.service import get_task_service
from src.ui.components.table import SkyTableWidget


class JobDetailDialog(QDialog):
    """作业详情对话框。"""
    
    def __init__(self, job_id: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self.setWindowTitle("作业详情 (V2)")
        self.resize(1000, 700)
        self.setModal(True)
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部信息栏
        info_layout = QHBoxLayout()
        self.name_label = QLabel("作业名称: Loading...")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(self.name_label)
        
        self.id_label = QLabel(f"ID: {self.job_id}")
        self.id_label.setStyleSheet("color: gray;")
        info_layout.addWidget(self.id_label)
        
        info_layout.addStretch()
        
        self.strategy_label = QLabel("策略: -")
        info_layout.addWidget(self.strategy_label)
        
        layout.addLayout(info_layout)
        
        # 选项卡
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: 任务列表
        self.tasks_tab = QWidget()
        self._setup_tasks_tab()
        self.tabs.addTab(self.tasks_tab, "任务实例 (Tasks)")
        
        # Tab 2: 作业配置
        self.config_tab = QWidget()
        self._setup_config_tab()
        self.tabs.addTab(self.config_tab, "作业配置")
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _setup_tasks_tab(self):
        layout = QVBoxLayout(self.tasks_tab)
        
        # Refresh Btn
        refresh_btn = QPushButton("🔄 刷新列表")
        refresh_btn.clicked.connect(lambda: self._load_data())
        layout.addWidget(refresh_btn)

        # Task Table
        self.task_table = SkyTableWidget()
        columns = ["Task ID", "状态", "环境ID", "环境租约", "开始时间", "结束时间", "结果/错误"]
        self.task_table.setColumnCount(len(columns))
        self.task_table.setHorizontalHeaderLabels(columns)
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.task_table.cellClicked.connect(self._on_task_selected)
        
        layout.addWidget(self.task_table, stretch=1)
        
        # Task Details
        layout.addWidget(QLabel("选中任务详情:"))
        self.task_detail_text = QTextEdit()
        self.task_detail_text.setReadOnly(True)
        self.task_detail_text.setPlaceholderText("点击上方任务查看详情...")
        layout.addWidget(self.task_detail_text, stretch=1)

    def _setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        layout.addWidget(self.config_text)

    def _load_data(self):
        asyncio.create_task(self._load_data_async())

    async def _load_data_async(self):
        try:
            service = get_task_service()
            job = await service.get_job(self.job_id)
            if not job:
                self.name_label.setText("作业不存在")
                return
            
            self._update_info(job)
            
            tasks = await service.list_tasks(self.job_id)
            # Sort by created_at desc
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            self._render_tasks(tasks)
        except Exception as e:
            self.name_label.setText(f"Error: {e}")

    def _render_tasks(self, tasks: list[Task]):
        self.task_table.setRowCount(0)
        for task in tasks:
            row = self.task_table.rowCount()
            self.task_table.insertRow(row)
            
            # ID
            id_item = QTableWidgetItem(task.id[:8])
            id_item.setData(Qt.ItemDataRole.UserRole, task) # Meta data store task object
            self.task_table.setItem(row, 0, id_item)
            
            # Status
            self.task_table.setItem(row, 1, QTableWidgetItem(task.status.value))
            
            # Env
            self.task_table.setItem(row, 2, QTableWidgetItem(str(task.env_id or "-")))
            
            # Lease
            self.task_table.setItem(row, 3, QTableWidgetItem(str(task.lease_id or "-")[:8]))
            
            # Start
            start_str = "-"
            if task.started_at:
                start_str = datetime.fromtimestamp(task.started_at).strftime("%H:%M:%S")
            self.task_table.setItem(row, 4, QTableWidgetItem(start_str))
            
            # End
            end_str = "-"
            if task.finished_at:
                end_str = datetime.fromtimestamp(task.finished_at).strftime("%H:%M:%S")
            self.task_table.setItem(row, 5, QTableWidgetItem(end_str))
            
            # Result
            msg = task.message or task.error or "-"
            self.task_table.setItem(row, 6, QTableWidgetItem(msg))

    def _update_info(self, job: Job):
        self.name_label.setText(f"作业名称: {job.name}")
        self.strategy_label.setText(f"策略: {job.strategy_id} | 并发: {job.concurrency_target}")
        
        info = f"Type: {job.type.value}\n"
        info += f"Trigger: {job.trigger}\n"
        info += f"Params: {job.params}\n"
        info += f"Created: {datetime.fromtimestamp(job.created_at)}\n"
        self.config_text.setText(info)
    
    def _on_task_selected(self, row, col):
        item = self.task_table.item(row, 0)
        task = item.data(Qt.ItemDataRole.UserRole)
        if task:
            details = f"Task ID: {task.id}\n"
            details += f"Status: {task.status.value}\n"
            details += f"Environment: {task.env_id}\n"
            details += f"Lease: {task.lease_id}\n"
            details += f"Message: {task.message}\n"
            details += f"Error: {task.error}\n"
            self.task_detail_text.setText(details)
