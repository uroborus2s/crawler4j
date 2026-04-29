"""任务(Job)列表组件。

显示作业配置及其状态，支持 创建/启动/暂停/删除 操作。
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from crawler4j_contracts import EnvAction
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.job_runtime import describe_job_runtime
from src.core.atm.models import Job, JobState, JobType, TaskStatus, TriggerType
from src.core.atm.run_profile import AcquisitionMode
from src.core.debug.resolver import JobDebugTarget, resolve_job_debug_target
from src.core.mms.models import ModuleSource
from src.core.atm.service import get_task_service
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.ui.components.button import StyledButton
from src.ui.components.choice_dialog import ChoiceDialog, DialogChoice
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import attach_display_index, resolve_local_data_table_result
from src.ui.components.message_dialog import MessageDialog


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
    TABLE_SCHEMA = {
        "columns": [
            {"key": "__index__", "label": "序号", "type": "number", "width": 72, "align": "right", "sortable": False, "searchable": False},
            {"key": "name", "label": "作业名称", "type": "text", "width": 240},
            {"key": "type", "label": "类型", "type": "text", "width": 100},
            {"key": "runtime", "label": "运行配置", "type": "text", "width": 140},
            {"key": "concurrency", "label": "目标并发", "type": "number", "width": 80, "align": "right"},
            {"key": "trigger", "label": "触发规则", "type": "text", "width": 120},
            {"key": "status", "label": "状态", "type": "text", "width": 96},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索作业、模块或触发规则"},
            "sort": {
                "enabled": True,
                "default": [{"field": "name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 20, "page_size_options": [10, 20, 50, 100]},
            "loading": {"inline": False, "disable_interaction": False},
        },
    }
    REFRESH_EVENTS = (
        EventType.TASK_STARTED,
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
        self._run_once_stopping_job_ids: set[str] = set()
        self._display_items: list[JobDisplayItem] = []
        self._table_rows: list[dict[str, Any]] = []

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
        self._run_once_stopping_job_ids.discard(job_id)

    @staticmethod
    def _can_destroy_run_once_env(job: Job) -> bool:
        run_profile = getattr(job, "run_profile", None)
        if not run_profile or not run_profile.resource:
            return False
        return run_profile.resource.acquisition.mode == AcquisitionMode.CREATE

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

        self.create_btn = StyledButton("新建作业", variant="success", min_height=36)
        self.create_btn.clicked.connect(self._on_create_job)
        header.addWidget(self.create_btn)

        self.refresh_btn = StyledButton("刷新", variant="primary", min_height=36, min_width=64)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.table.query_requested.connect(self._on_table_query_requested)
        self.table.row_clicked.connect(self._on_table_row_clicked)
        self.table.row_action_requested.connect(self._on_table_action_requested)
        layout.addWidget(self.table)

    def load_data(self):
        """加载数据。"""
        self._load_seq += 1
        seq = self._load_seq
        if self._load_task and not self._load_task.done():
            self._load_task.cancel()
        self._load_task = asyncio.create_task(self._load_data_async(seq))

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
                    self._release_run_once_lock(job.id)

                run_once_phase = "idle"
                if self._is_manual_batch_job(job):
                    if (
                        job.id in self._run_once_stopping_job_ids
                        and (job.id in self._pending_run_once_job_ids or pending_task_count > 0 or active_task_count > 0)
                    ):
                        run_once_phase = "stopping"
                    elif job.id in self._run_once_requesting_job_ids or pending_task_count > 0:
                        run_once_phase = "starting"
                    elif self._is_run_once_busy(job.id, active_task_count):
                        run_once_phase = "running"

                if run_once_phase == "starting":
                    status_text = "环境启动中"
                    status_color = self.STARTING_STATUS_COLOR
                elif run_once_phase == "stopping":
                    status_text = "中止中"
                    status_color = "#f97316"
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

            self._display_items = display_items
            self._refresh_table()
        except asyncio.CancelledError:
            return

        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
        finally:
            if seq == self._load_seq:
                self.table.set_loading(False)

    def _refresh_table(self) -> None:
        self._table_rows = [self._build_table_row(item) for item in self._display_items]
        self.table.request_refresh()

    def _build_table_row(self, item: JobDisplayItem) -> dict[str, Any]:
        job = item.raw
        type_str = self.TYPE_TEXT.get(job.type, job.type.value)
        runtime_text, runtime_tooltip = describe_job_runtime(job)

        is_manual_batch = self._is_manual_batch_job(job)
        if is_manual_batch:
            trigger_text = "手动执行一次"
        elif job.type == JobType.BATCH and job.trigger.cron_expr:
            trigger_text = f"Cron ({job.trigger.cron_expr})"
        elif job.type == JobType.BATCH:
            trigger_text = "Cron 配置缺失"
        else:
            trigger_text = "手动启动后持续保活"
        return {
            "job": job,
            "job_id": job.id,
            "name": job.name,
            "type": type_str,
            "runtime": {
                "text": runtime_text,
                "tooltip": runtime_tooltip,
            },
            "concurrency": {
                "text": str(job.concurrency_target),
                "sort_value": int(job.concurrency_target),
            },
            "trigger": trigger_text,
            "status": {
                "text": item.display_status_text,
                "tone": self._status_tone(item),
            },
            "actions": self._build_row_actions(item),
        }

    def _build_row_actions(self, item: JobDisplayItem) -> list[dict[str, Any]]:
        job = item.raw
        actions: list[dict[str, Any]] = []
        is_manual_batch = self._is_manual_batch_job(job)
        is_manual_batch_busy = is_manual_batch and self._is_run_once_busy(
            job.id,
            item.active_task_count,
        )
        state = self._normalize_state(job.state)
        if is_manual_batch:
            is_starting = item.run_once_phase == "starting"
            is_running = item.run_once_phase == "running"
            is_stopping = item.run_once_phase == "stopping"
            tooltip = "立即执行一次当前批次任务。"
            if is_starting:
                tooltip = "环境正在启动；可以手动中止并选择关闭或删除本次环境。"
            elif is_running:
                tooltip = "当前批次仍在执行；可以手动中止并选择关闭或删除本次环境。"
            elif is_stopping:
                tooltip = "已发出中止请求，等待任务执行 cleanup 并回收环境。"
            actions.append(
                {
                    "id": "stop_run_once" if is_manual_batch_busy else "run_once",
                    "label": "⏹ 中止中" if is_stopping else "⏹ 中止" if is_manual_batch_busy else "▶ 执行一次",
                    "tooltip": tooltip,
                    "enabled": not is_stopping,
                    "variant": "warning"
                    if is_manual_batch_busy and not is_stopping
                    else "secondary"
                    if is_stopping
                    else "primary",
                }
            )
        elif state == JobState.ACTIVE:
            actions.append({"id": "pause", "label": "⏸ 暂停", "variant": "warning"})
        else:
            actions.append({"id": "start", "label": "▶ 启动", "variant": "primary"})

        debug_target = self._resolve_debug_target(job)
        if debug_target and debug_target.module.source == ModuleSource.DEV_LINK:
            actions.append({"id": "debug", "label": "🐞 调试", "variant": "warning"})
        actions.append({"id": "edit", "label": "✏️", "variant": "secondary"})
        actions.append({"id": "delete", "label": "🗑", "variant": "secondary"})
        return actions

    def _status_tone(self, item: JobDisplayItem) -> str:
        if item.run_once_phase == "starting":
            return "info"
        if item.run_once_phase == "stopping":
            return "warning"
        if item.run_once_phase == "running":
            return "warning"
        state = self._normalize_state(item.raw.state)
        return {
            JobState.ACTIVE: "warning",
            JobState.PAUSED: "neutral",
            JobState.COMPLETED: "success",
            JobState.ERROR: "danger",
        }.get(state, "neutral")

    def _on_table_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._table_rows,
            columns=self.TABLE_SCHEMA["columns"],
            query=query,
        )
        self.table.apply_result(request_id, attach_display_index(result))

    def _on_table_row_clicked(self, row: dict[str, Any]) -> None:
        job_id = str(row.get("job_id") or "")
        if not job_id:
            return
        self.task_selected.emit(job_id)
        from src.core.atm.ui.task_detail_dialog import JobDetailDialog

        dialog = JobDetailDialog(job_id, parent=self)
        dialog.exec()

    def _on_table_action_requested(self, action_id: str, row: dict[str, Any]) -> None:
        job_id = str(row.get("job_id") or "")
        if not job_id:
            return
        if action_id == "run_once":
            self._run_job_once(job_id)
        elif action_id == "stop_run_once":
            self._stop_run_once(job_id)
        elif action_id == "pause":
            self._pause_job(job_id)
        elif action_id == "start":
            self._start_job(job_id)
        elif action_id == "debug":
            self._open_debug_dialog(job_id)
        elif action_id == "edit":
            self._edit_job(job_id)
        elif action_id == "delete":
            self._delete_job(job_id)

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
        self._publish_run_once_requesting(job_id, job_name, active=True)
        self._refresh_table()
        asyncio.create_task(self._async_op(job_id, "run_once"))

    @staticmethod
    def _publish_run_once_requesting(job_id: str, job_name: str, *, active: bool) -> None:
        get_event_bus().publish(
            Event(
                type=EventType.TASK_PROGRESS,
                data={
                    "phase": "requesting",
                    "job_id": job_id,
                    "job_name": job_name,
                    "active": active,
                },
            )
        )

    def _stop_run_once(self, job_id: str):
        if job_id in self._run_once_stopping_job_ids:
            return

        job = next((candidate for candidate in self._jobs if candidate.id == job_id), None)
        if not job:
            return

        choices = [
            DialogChoice("recycle", "保留环境中止", "warning"),
        ]
        if self._can_destroy_run_once_env(job):
            detail = "保留环境会关闭环境但不删除；删除环境会删除本次创建的环境。"
            choices.append(DialogChoice("destroy", "删除环境中止", "danger"))
        else:
            detail = "当前运行模板是复用环境模式，只支持关闭环境但不删除。"

        selected = ChoiceDialog.choose(
            self,
            "中止任务",
            f"要中止“{job.name}”这次手动执行吗？",
            choices=choices,
            detail=detail,
        )
        if selected is None:
            return
        if selected == "recycle":
            env_action = EnvAction.RECYCLE
        elif selected == "destroy":
            env_action = EnvAction.DESTROY
        else:
            return

        self._run_once_stopping_job_ids.add(job_id)
        self._refresh_table()
        asyncio.create_task(self._async_stop_run_once(job_id, env_action))

    def _delete_job(self, job_id: str):
        confirmed = ConfirmDialog.confirm(
            self,
            "确认删除",
            "确定要删除该作业吗？关联的任务记录可能会被清理。",
            confirm_text="删除",
            danger=True,
        )
        if confirmed:
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
                job_name = next((job.name for job in self._jobs if job.id == job_id), "当前作业")
                self._publish_run_once_requesting(job_id, job_name, active=False)
                self._release_run_once_lock(job_id)
                self._refresh_table()
                self.load_data()
            await MessageDialog.warning_async(self, "操作失败", str(e))
            return

        if op == "run_once":
            self._run_once_requesting_job_ids.discard(job_id)

        # 操作完成后立即拉取最新状态，确保按钮与数据库一致
        self._load_seq += 1
        await self._load_data_async(self._load_seq)

    async def _async_stop_run_once(self, job_id: str, env_action: EnvAction):
        service = get_task_service()
        try:
            success = await service.stop_run_once(job_id, env_action)
            if not success:
                raise RuntimeError("当前没有可中止的批次任务，或任务已经结束。")
        except Exception as e:
            self._run_once_stopping_job_ids.discard(job_id)
            self._refresh_table()
            self.load_data()
            await MessageDialog.warning_async(self, "中止失败", str(e))
            return

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
            await MessageDialog.error_async(self, "更新失败", str(e))

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
            await MessageDialog.error_async(self, "创建失败", str(e))

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
            MessageDialog.information(self, "不可调试", "当前作业对应的不是开发链接模块，无法进入 IDE 调试。")
            return

        from src.core.atm.ui.task_debug_dialog import JobDebugDialog

        dialog = JobDebugDialog(
            job,
            debug_target.run_profile,
            debug_target.module,
            parent=self,
        )
        dialog.exec()
    
