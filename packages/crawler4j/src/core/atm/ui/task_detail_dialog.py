"""作业(Job)详情对话框。

显示作业配置信息及下属任务(Task)列表。
"""

import asyncio
from datetime import datetime

from PyQt6.QtCore import Qt
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

from src.core.atm.job_runtime import describe_job_runtime, resolve_job_run_profile
from src.core.atm.models import Job, Task, TaskStatus
from src.core.debug.resolver import JobDebugTarget, resolve_job_debug_target
from src.core.mms.models import ModuleSource
from src.core.atm.service import get_task_service
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.atm.ui.task_confirmation_dialog import TaskConfirmationDialog
from src.ui.components.log_console import LogConsoleWidget
from src.ui.components.table import SkyTableWidget


class JobDetailDialog(QDialog):
    """作业详情对话框。"""

    TYPE_TEXT = {
        "batch": "批次任务",
        "service": "持续保活",
    }
    
    def __init__(self, job_id: str, parent=None):
        super().__init__(parent)
        self.job_id = job_id
        self._job: Job | None = None
        self._debug_target: JobDebugTarget | None = None
        self._auto_presented_confirmation_task_ids: set[str] = set()
        self.setWindowTitle("作业详情 (V2)")
        self.resize(1000, 700)
        self.setModal(True)
        
        self._setup_ui()
        self._subscribe_events()
        self.destroyed.connect(lambda *_args: self._unsubscribe_events())
        self._load_data()
        
    def _setup_ui(self):
        # Force Dark Mode
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1b26;
                color: #c0caf5;
            }
            QLabel {
                color: #c0caf5;
            }
            QTabWidget::pane {
                border: 1px solid #414868;
                background: #1a1b26;
            }
            QTabBar::tab {
                background: #24283b;
                color: #a9b1d6;
                padding: 8px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #414868;
                color: #ffffff;
            }
        """)

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
        
        self.runtime_label = QLabel("运行配置: -")
        info_layout.addWidget(self.runtime_label)

        self.debug_btn = QPushButton("🐞 调试任务")
        self.debug_btn.setStyleSheet("""
            QPushButton {
                background: rgba(245, 158, 11, 0.88);
                color: black;
                border: none;
                padding: 8px 14px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 158, 11, 1); }
            QPushButton:disabled { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.4); }
        """)
        self.debug_btn.clicked.connect(self._open_debug_dialog)
        self.debug_btn.hide()
        info_layout.addWidget(self.debug_btn)
        
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
        
        layout.addWidget(self.task_table, stretch=2)
        
        # Task Details (Log Console)
        layout.addWidget(QLabel("任务日志:"))
        self.log_console = LogConsoleWidget()
        layout.addWidget(self.log_console, stretch=1)

    def _setup_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        self.config_text = QTextEdit()
        self.config_text.setReadOnly(True)
        layout.addWidget(self.config_text)

    def _subscribe_events(self) -> None:
        get_event_bus().subscribe(EventType.TASK_SIGNAL, self._on_task_signal)

    def _unsubscribe_events(self) -> None:
        get_event_bus().unsubscribe(EventType.TASK_SIGNAL, self._on_task_signal)

    def _load_data(self):
        asyncio.create_task(self._load_data_async())

    async def _load_data_async(self):
        try:
            service = get_task_service()
            job = await service.get_job(self.job_id)
            if not job:
                self.name_label.setText("作业不存在")
                return
            self._job = job
            self._update_info(job)
            self._update_debug_target(job)
            
            tasks = await service.list_tasks(self.job_id)
            # Sort by created_at desc
            tasks.sort(key=lambda x: x.created_at, reverse=True)
            self._render_tasks(tasks)
            self._present_latest_waiting_confirmation(tasks)
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
        runtime_text, runtime_tooltip = describe_job_runtime(job)
        self.name_label.setText(f"作业名称: {job.name}")
        self.runtime_label.setText(f"运行配置: {runtime_text} | 并发: {job.concurrency_target}")
        self.runtime_label.setToolTip(runtime_tooltip)

        trigger_text = "手动启动后持续保活"
        if job.type.value == "batch":
            if job.trigger.type.value == "manual":
                trigger_text = "手动执行一次"
            else:
                trigger_text = f"Cron ({job.trigger.cron_expr})" if job.trigger.cron_expr else "未配置 Cron"

        try:
            run_profile = resolve_job_run_profile(job)
            execution_text = (
                f"{run_profile.execution.module}/{run_profile.execution.workflow or 'default'}"
                if run_profile.execution and run_profile.execution.module
                else "-"
            )
            provider_text = run_profile.resource.provider if run_profile.resource else "-"
        except Exception:
            execution_text = "-"
            provider_text = "-"

        info = f"模式: {self.TYPE_TEXT.get(job.type.value, job.type.value)}\n"
        info += f"运行配置: {runtime_text}\n"
        info += f"执行目标: {execution_text}\n"
        info += f"Provider: {provider_text}\n"
        info += f"触发: {trigger_text}\n"
        info += f"Params: {job.params}\n"
        info += f"Created: {datetime.fromtimestamp(job.created_at)}\n"
        self.config_text.setText(info)

    def _update_debug_target(self, job: Job) -> None:
        try:
            target = resolve_job_debug_target(job)
        except Exception:
            target = None

        if target and target.module.source == ModuleSource.DEV_LINK:
            self._debug_target = target
            self.debug_btn.show()
            self.debug_btn.setEnabled(True)
            self.debug_btn.setToolTip(f"打开任务调试: {target.module.name}/{target.workflow}")
            return

        self._debug_target = None
        self.debug_btn.hide()
    
    def _on_task_selected(self, row, col):
        item = self.task_table.item(row, 0)
        task = item.data(Qt.ItemDataRole.UserRole)
        if task:
            # Set filter for log console
            self.log_console.set_filter(task.id)
            if task.status == TaskStatus.WAITING_CONFIRMATION and task.signal:
                self._present_confirmation_task(task)

    def _present_latest_waiting_confirmation(self, tasks: list[Task]) -> None:
        for task in tasks:
            if task.status != TaskStatus.WAITING_CONFIRMATION or not task.signal:
                continue
            if task.id in self._auto_presented_confirmation_task_ids:
                continue
            self._auto_presented_confirmation_task_ids.add(task.id)
            self._present_confirmation_task(task)
            break

    def _present_confirmation_task(self, task: Task) -> None:
        dialog = TaskConfirmationDialog(task, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        service = get_task_service()
        if dialog.confirmed:
            asyncio.create_task(service.confirm_task_success(task.id, dialog.get_message()))
        else:
            asyncio.create_task(service.confirm_task_failure(task.id, dialog.get_message()))
        self._load_data()

    def _on_task_signal(self, event: Event) -> None:
        if event.data.get("job_id") != self.job_id:
            return
        signal = event.data.get("signal")
        if not isinstance(signal, dict):
            return
        task = Task(
            id=event.data.get("task_id") or event.task_run_id or "",
            job_id=event.data.get("job_id") or "",
            status=TaskStatus(event.data.get("status", TaskStatus.WAITING_CONFIRMATION.value)),
            env_id=event.data.get("env_id"),
            lease_id=event.data.get("lease_id"),
            message=event.data.get("message") or "",
            error=event.data.get("error") or "",
            signal=signal,
        )
        if task.id and task.id not in self._auto_presented_confirmation_task_ids:
            self._auto_presented_confirmation_task_ids.add(task.id)
        self._present_confirmation_task(task)
        self._load_data()

    def _open_debug_dialog(self):
        if not self._job or not self._debug_target or self._debug_target.module.source != ModuleSource.DEV_LINK:
            return

        from src.core.atm.ui.task_debug_dialog import JobDebugDialog

        dialog = JobDebugDialog(
            self._job,
            self._debug_target.run_profile,
            self._debug_target.module,
            parent=self,
        )
        dialog.exec()
