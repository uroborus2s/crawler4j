"""任务(Job)列表组件。

显示作业配置及其状态，支持 创建/启动/暂停/删除 操作。
"""

import asyncio
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.job_runtime import describe_job_runtime
from src.core.atm.models import Job, JobState, JobType, TaskStatus, TriggerType
from src.core.debug.resolver import JobDebugTarget, resolve_job_debug_target
from src.core.mms.models import ModuleSource
from src.core.atm.service import get_task_service
from src.core.foundation.event_bus import Event, EventType, get_event_bus


@dataclass
class JobDisplayItem:
    """Job 显示项包装。"""
    raw: Job
    display_status_text: str
    display_status_color: str
    active_task_count: int = 0
    run_once_phase: str = "idle"


class TaskListWidget(QWidget):
    """任务(Job)列表组件。"""

    task_selected = pyqtSignal(str)
    REFRESH_EVENTS = (
        EventType.TASK_SIGNAL,
        EventType.TASK_FINISHED,
        EventType.TASK_FAILED,
        EventType.TASK_CANCELLED,
        EventType.TASK_CONFIG_CREATED,
        EventType.TASK_CONFIG_UPDATED,
        EventType.TASK_CONFIG_DELETED,
    )

    COLUMNS = ["作业名称", "类型", "运行配置", "目标并发", "触发规则", "状态", "操作"]
    
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
        JobType.BATCH: "批次任务",
        JobType.SERVICE: "持续保活",
    }
    STARTING_STATUS_COLOR = "#60a5fa"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[Job] = []
        self._load_seq = 0
        self._load_task: asyncio.Task | None = None
        self._pending_run_once_job_ids: set[str] = set()
        self._run_once_requesting_job_ids: set[str] = set()

        self._setup_ui()
        self._subscribe_events()
        self.destroyed.connect(lambda *_args: self._unsubscribe_events())

        # 初始加载 (Delay to ensure loop is running)
        QTimer.singleShot(0, self.load_data)

    def _on_task_changed(self, event: Event):
        """事件回调：刷新列表。"""
        self.load_data()

    def _subscribe_events(self):
        bus = get_event_bus()
        for event_type in self.REFRESH_EVENTS:
            bus.subscribe(event_type, self._on_task_changed)

    def _unsubscribe_events(self):
        bus = get_event_bus()
        for event_type in self.REFRESH_EVENTS:
            bus.unsubscribe(event_type, self._on_task_changed)

    @staticmethod
    def _is_manual_batch_job(job: Job) -> bool:
        return job.type == JobType.BATCH and job.trigger.type == TriggerType.MANUAL

    def _is_run_once_busy(self, job_id: str, active_task_count: int = 0) -> bool:
        return job_id in self._pending_run_once_job_ids or active_task_count > 0

    def _release_run_once_lock(self, job_id: str):
        self._pending_run_once_job_ids.discard(job_id)
        self._run_once_requesting_job_ids.discard(job_id)

    @staticmethod
    def _normalize_state(state: JobState | str) -> JobState:
        if isinstance(state, JobState):
            return state
        try:
            return JobState(str(state))
        except Exception:
            # 非法状态值默认按暂停处理，避免 UI 动作错乱
            return JobState.PAUSED

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

        self.startup_hint = QWidget()
        startup_layout = QVBoxLayout(self.startup_hint)
        startup_layout.setContentsMargins(0, 0, 0, 0)
        startup_layout.setSpacing(6)

        self.startup_hint_label = QLabel("环境启动中，请稍候...")
        self.startup_hint_label.setStyleSheet("color: #93c5fd; font-size: 12px; font-weight: bold;")
        startup_layout.addWidget(self.startup_hint_label)

        self.startup_progress = QProgressBar()
        self.startup_progress.setMaximum(0)
        self.startup_progress.setTextVisible(False)
        self.startup_progress.setFixedHeight(3)
        self.startup_progress.setStyleSheet("""
            QProgressBar {
                background: rgba(96, 165, 250, 0.12);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60a5fa, stop:1 #22d3ee);
                border-radius: 2px;
            }
        """)
        startup_layout.addWidget(self.startup_progress)
        self.startup_hint.hide()
        layout.addWidget(self.startup_hint)

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
            ("runtime", "运行配置", 140),
            ("concurrency", "目标并发", 80),
            ("trigger", "触发规则", 120),
            ("status", "状态", 80),
            ("actions", "操作", 240),
        ]

        self.table = SkyDataTable(columns=columns_config)
        self.table.set_render_callback(self._render_row)
        self.table.cell_clicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def load_data(self):
        """加载数据。"""
        self._load_seq += 1
        seq = self._load_seq
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.create_task(self._load_data_async(seq))

    def _set_startup_indicator(self, starting_job_names: list[str]) -> None:
        if not starting_job_names:
            self.startup_hint.hide()
            return

        if len(starting_job_names) == 1:
            message = f"环境启动中：{starting_job_names[0]}。启动完成后会自动切回执行中。"
        else:
            message = f"有 {len(starting_job_names)} 条作业正在启动环境。启动完成后会自动隐藏。"
        self.startup_hint_label.setText(message)
        self.startup_hint.show()

    async def _load_data_async(self, seq: int):
        """异步加载数据。"""
        self.table.set_loading(True)
        self.error_label.hide()

        try:
            service = get_task_service()
            jobs = await service.list_jobs()
            if seq != self._load_seq:
                return

            self._jobs = jobs
            manual_jobs = [job for job in jobs if self._is_manual_batch_job(job)]
            active_task_counts: dict[str, int] = {}
            pending_task_counts: dict[str, int] = {}
            if manual_jobs:
                counts, task_lists = await asyncio.gather(
                    asyncio.gather(*(service.count_active_tasks(job.id) for job in manual_jobs)),
                    asyncio.gather(*(service.list_tasks(job.id) for job in manual_jobs)),
                )
                active_task_counts = {
                    job.id: count for job, count in zip(manual_jobs, counts, strict=False)
                }
                pending_task_counts = {
                    job.id: sum(task.status == TaskStatus.PENDING for task in tasks)
                    for job, tasks in zip(manual_jobs, task_lists, strict=False)
                }
                if seq != self._load_seq:
                    return

            display_items = []
            for job in self._jobs:
                state = self._normalize_state(job.state)
                job.state = state
                active_task_count = active_task_counts.get(job.id, 0)
                pending_task_count = pending_task_counts.get(job.id, 0)
                if (
                    job.id in self._pending_run_once_job_ids
                    and active_task_count == 0
                    and pending_task_count == 0
                    and job.id not in self._run_once_requesting_job_ids
                ):
                    self._pending_run_once_job_ids.discard(job.id)

                run_once_phase = "idle"
                if self._is_manual_batch_job(job):
                    if job.id in self._run_once_requesting_job_ids or pending_task_count > 0:
                        run_once_phase = "starting"
                    elif self._is_run_once_busy(job.id, active_task_count):
                        run_once_phase = "running"

                if run_once_phase == "starting":
                    status_text = "环境启动中"
                    status_color = self.STARTING_STATUS_COLOR
                elif run_once_phase == "running":
                    status_text = "执行中"
                    status_color = self.STATUS_COLORS[JobState.ACTIVE]
                else:
                    status_text = self.STATUS_TEXT.get(state, state.value)
                    status_color = self.STATUS_COLORS.get(state, "#9ca3af")
                
                display_items.append(JobDisplayItem(
                    raw=job,
                    display_status_text=status_text,
                    display_status_color=status_color,
                    active_task_count=active_task_count,
                    run_once_phase=run_once_phase,
                ))

            self.table.set_data(display_items)
            self._set_startup_indicator(
                [item.raw.name for item in display_items if item.run_once_phase == "starting"]
            )
        except asyncio.CancelledError:
            return

        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            self._set_startup_indicator([])
        finally:
            if seq == self._load_seq:
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

        # 2. 运行配置
        runtime_text, runtime_tooltip = describe_job_runtime(job)
        runtime_item = QTableWidgetItem(runtime_text)
        runtime_item.setToolTip(runtime_tooltip)
        table.setItem(row, 2, runtime_item)
        
        # 3. 并发
        table.setItem(row, 3, QTableWidgetItem(str(job.concurrency_target)))

        # 4. Trigger
        is_manual_batch = self._is_manual_batch_job(job)
        is_manual_batch_busy = is_manual_batch and self._is_run_once_busy(
            job.id,
            item.active_task_count,
        )
        if is_manual_batch:
            trigger_text = "手动执行一次"
        elif job.type == JobType.BATCH and job.trigger.cron_expr:
            trigger_text = f"Cron ({job.trigger.cron_expr})"
        elif job.type == JobType.BATCH:
            trigger_text = "Cron 配置缺失"
        else:
            trigger_text = "手动启动后持续保活"
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

        state = self._normalize_state(job.state)
        if is_manual_batch:
            is_starting = item.run_once_phase == "starting"
            is_running = item.run_once_phase == "running"
            run_btn = QPushButton(
                "⏳ 启动中" if is_starting else "⏳ 执行中" if is_running else "▶ 执行一次"
            )
            run_btn.setEnabled(not is_manual_batch_busy)
            if is_starting:
                run_btn.setToolTip("正在创建环境并启动浏览器，成功后会自动进入执行中。")
            elif is_running:
                run_btn.setToolTip("当前批次仍在执行或等待环境回收完成。")
            run_btn.setStyleSheet(
                "background: #2563eb; color: white; border: none; padding: 4px 10px; border-radius: 4px;"
                if is_starting
                else "background: #6b7280; color: rgba(255, 255, 255, 0.75); border: none; padding: 4px 10px; border-radius: 4px;"
                if is_running
                else "background: #60a5fa; color: white; border: none; padding: 4px 10px; border-radius: 4px;"
            )
            if not is_manual_batch_busy:
                run_btn.clicked.connect(lambda _, jid=job.id: self._run_job_once(jid))
            action_layout.addWidget(run_btn)
        elif state == JobState.ACTIVE:
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

        debug_target = self._resolve_debug_target(job)
        if debug_target and debug_target.module.source == ModuleSource.DEV_LINK:
            debug_btn = QPushButton("🐞 调试")
            debug_btn.setStyleSheet(
                "background: rgba(245, 158, 11, 0.88); color: black; border: none; padding: 4px 10px; border-radius: 4px;"
            )
            debug_btn.clicked.connect(lambda _, jid=job.id: self._open_debug_dialog(jid))
            action_layout.addWidget(debug_btn)

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

    def _run_job_once(self, job_id: str):
        if job_id in self._pending_run_once_job_ids:
            return
        self._pending_run_once_job_ids.add(job_id)
        self._run_once_requesting_job_ids.add(job_id)
        job_name = next((job.name for job in self._jobs if job.id == job_id), "当前作业")
        self._set_startup_indicator([job_name])
        self.table.refresh()
        asyncio.create_task(self._async_op(job_id, "run_once"))

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
            success = True
            if op == "start":
                success = await service.start_job(job_id)
            elif op == "pause":
                success = await service.pause_job(job_id)
            elif op == "run_once":
                success = await service.run_job_once(job_id)
            elif op == "delete":
                success = await service.delete_job(job_id)

            if not success:
                action_text = {
                    "start": "启动失败，请检查运行模板和当前任务状态。",
                    "pause": "暂停失败，请稍后重试。",
                    "run_once": "执行失败，请确认当前没有未结束的批次任务且运行模板可用。",
                    "delete": "删除失败，请稍后重试。",
                }.get(op, "操作失败")
                raise RuntimeError(action_text)
        except Exception as e:
            if op == "run_once":
                self._release_run_once_lock(job_id)
                self.table.refresh()
                self.load_data()
            QMessageBox.warning(self, "操作失败", str(e))
            return

        if op == "run_once":
            self._run_once_requesting_job_ids.discard(job_id)

        # 操作完成后立即拉取最新状态，确保按钮与数据库一致
        self._load_seq += 1
        await self._load_data_async(self._load_seq)

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

    def _resolve_debug_target(self, job: Job) -> JobDebugTarget | None:
        try:
            return resolve_job_debug_target(job)
        except Exception:
            return None

    def _open_debug_dialog(self, job_id: str):
        job = next((j for j in self._jobs if j.id == job_id), None)
        if not job:
            return

        debug_target = self._resolve_debug_target(job)
        if not debug_target or debug_target.module.source != ModuleSource.DEV_LINK:
            QMessageBox.information(self, "不可调试", "当前作业对应的不是开发链接模块，无法进入 IDE 调试。")
            return

        from src.core.atm.ui.task_debug_dialog import JobDebugDialog

        dialog = JobDebugDialog(
            job,
            debug_target.run_profile,
            debug_target.module,
            parent=self,
        )
        dialog.exec()
    
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
