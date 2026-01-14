"""任务详情对话框。

显示任务配置信息及运行历史（日志、结果）。
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
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import AutomationTask, TaskRun, TaskStatus
from src.core.atm.service import get_task_service
from src.ui.components.table import SkyTableWidget


class TaskDetailDialog(QDialog):
    """任务详情对话框。"""
    
    def __init__(self, task_id: str, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.setWindowTitle("任务详情")
        self.resize(900, 600)
        self.setModal(True)
        
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 顶部信息栏
        info_layout = QHBoxLayout()
        self.name_label = QLabel("任务名称: Loading...")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        info_layout.addWidget(self.name_label)
        
        self.id_label = QLabel(f"ID: {self.task_id}")
        self.id_label.setStyleSheet("color: gray;")
        info_layout.addWidget(self.id_label)
        
        info_layout.addStretch()
        
        self.strategy_label = QLabel("策略: -")
        info_layout.addWidget(self.strategy_label)
        
        layout.addLayout(info_layout)
        
        # 选项卡：运行历史 | 任务配置
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: 运行历史
        self.history_tab = QWidget()
        self._setup_history_tab()
        self.tabs.addTab(self.history_tab, "运行历史")
        
        # Tab 2: 配置 (Read-only for now)
        self.config_tab = QWidget()
        self._setup_config_tab()
        self.tabs.addTab(self.config_tab, "配置信息")
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _setup_history_tab(self):
        layout = QVBoxLayout(self.history_tab)
        
        # History Table
        self.run_table = SkyTableWidget()
        columns = ["运行ID", "状态", "开始时间", "耗时", "环境ID", "结果摘要"]
        self.run_table.setColumnCount(len(columns))
        self.run_table.setHorizontalHeaderLabels(columns)
        self.run_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.run_table.cellClicked.connect(self._on_run_selected)
        
        layout.addWidget(self.run_table, stretch=1)
        
        # Run Details (Log/Error)
        layout.addWidget(QLabel("选中运行详情:"))
        self.run_detail_text = QTextEdit()
        self.run_detail_text.setReadOnly(True)
        self.run_detail_text.setPlaceholderText("点击上方记录查看详情...")
        layout.addWidget(self.run_detail_text, stretch=1)

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
            task = await service.get_task(self.task_id)
            if not task:
                self.name_label.setText("任务不存在")
                return
            
            self._update_info(task)
            
            runs = await service.list_task_runs(self.task_id, limit=50)
            self._render_history(runs)
        except Exception as e:
            self.name_label.setText(f"Error: {e}")

    def _render_history(self, runs: list[TaskRun]):
        self.run_table.setRowCount(0)
        for run in runs:
            row = self.run_table.rowCount()
            self.run_table.insertRow(row)
            
            # IDs
            id_item = QTableWidgetItem(run.id[:8])
            id_item.setData(Qt.ItemDataRole.UserRole, run.id)
            self.run_table.setItem(row, 0, id_item)
            
            # Status
            status_item = QTableWidgetItem(run.status.value)
            # Simple color mapping could be added here
            self.run_table.setItem(row, 1, status_item)
            
            # Time
            start_str = datetime.fromtimestamp(run.start_time).strftime("%m-%d %H:%M:%S")
            self.run_table.setItem(row, 2, QTableWidgetItem(start_str))
            
            # Duration
            duration = "-"
            if run.end_time:
                duration = f"{run.end_time - run.start_time}s"
            self.run_table.setItem(row, 3, QTableWidgetItem(duration))
            
            # Env
            self.run_table.setItem(row, 4, QTableWidgetItem(str(run.env_id or "-")))
            
            # Result
            res = "Success" if run.result and run.result.success else ("Failed" if run.error else "-")
            self.run_table.setItem(row, 5, QTableWidgetItem(res))

    def _update_info(self, task: AutomationTask):
        self.name_label.setText(f"任务名称: {task.name}")
        max_runs = str(task.max_executions) if task.max_executions is not None else "∞"
        self.strategy_label.setText(f"策略: {task.strategy_id} | Cron: {task.cron_expression or '无'} | 剩余次数: {max_runs}")
        self.config_text.setText(f"Defaults: {task.default_params}")
    
    def _on_run_selected(self, row, col):
        run_id = self.run_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        asyncio.create_task(self._load_run_detail(run_id))

    async def _load_run_detail(self, run_id):
        try:
            service = get_task_service()
            run = await service.get_run(run_id)
            if run:
                details = f"ID: {run.id}\nStatus: {run.status.value}\n"
                details += f"Trigger: {run.trigger_type}\n"
                details += f"Error: {run.error}\n" if run.error else ""
                details += f"Result: {run.result}\n" if run.result else ""
                self.run_detail_text.setText(details)
        except Exception as e:
            self.run_detail_text.setText(str(e))
