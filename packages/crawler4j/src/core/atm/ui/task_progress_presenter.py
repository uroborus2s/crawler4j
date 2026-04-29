"""Shared task startup progress presenter."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget

from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.ui.components.progress_dialog import ProgressDialog


@dataclass
class _QueuedJob:
    label: str
    count: int


class TaskProgressPresenter:
    """Display task startup and queued-import progress from task events."""

    EVENTS = (
        EventType.TASK_PROGRESS,
        EventType.TASK_STARTED,
        EventType.TASK_FINISHED,
        EventType.TASK_FAILED,
        EventType.TASK_CANCELLED,
    )

    def __init__(self, parent: QWidget, *, subscribe: bool = True) -> None:
        self.parent = parent
        self._progress_dialog: ProgressDialog | None = None
        self._requesting_jobs: dict[str, str] = {}
        self._starting_tasks: dict[str, str] = {}
        self._queued_jobs: dict[str, _QueuedJob] = {}
        self._subscribed = False
        if subscribe:
            self.subscribe()
        parent.destroyed.connect(lambda *_args: self.close())

    def subscribe(self) -> None:
        if self._subscribed:
            return
        bus = get_event_bus()
        bus.subscribe(EventType.TASK_PROGRESS, self._on_task_progress)
        bus.subscribe(EventType.TASK_STARTED, self._on_task_started)
        bus.subscribe(EventType.TASK_FINISHED, self._on_task_terminal)
        bus.subscribe(EventType.TASK_FAILED, self._on_task_terminal)
        bus.subscribe(EventType.TASK_CANCELLED, self._on_task_terminal)
        self._subscribed = True

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        bus = get_event_bus()
        bus.unsubscribe(EventType.TASK_PROGRESS, self._on_task_progress)
        bus.unsubscribe(EventType.TASK_STARTED, self._on_task_started)
        bus.unsubscribe(EventType.TASK_FINISHED, self._on_task_terminal)
        bus.unsubscribe(EventType.TASK_FAILED, self._on_task_terminal)
        bus.unsubscribe(EventType.TASK_CANCELLED, self._on_task_terminal)
        self._subscribed = False

    def close(self) -> None:
        self.unsubscribe()
        self._requesting_jobs.clear()
        self._starting_tasks.clear()
        self._queued_jobs.clear()
        self._close_dialog()

    def _on_task_progress(self, event: Event) -> None:
        phase = str(event.data.get("phase") or "").strip()
        if phase == "requesting":
            self._apply_requesting_progress(event)
        elif phase == "environment_starting":
            self._apply_environment_starting_progress(event)
        elif phase == "queued":
            self._apply_queued_progress(event)
        self._sync_dialog()

    def _apply_requesting_progress(self, event: Event) -> None:
        job_id = str(event.data.get("job_id") or "").strip()
        if not job_id:
            return
        active = bool(event.data.get("active", True))
        if active:
            self._requesting_jobs[job_id] = self._label_from_event(event, fallback=job_id)
        else:
            self._requesting_jobs.pop(job_id, None)

    def _apply_environment_starting_progress(self, event: Event) -> None:
        task_id = self._task_id_from_event(event)
        if not task_id:
            return
        job_id = str(event.data.get("job_id") or "").strip()
        if job_id:
            self._requesting_jobs.pop(job_id, None)
        self._starting_tasks[task_id] = self._label_from_event(event, fallback=task_id)

    def _apply_queued_progress(self, event: Event) -> None:
        job_id = str(event.data.get("job_id") or "").strip()
        if not job_id:
            return
        count = int(event.data.get("queued_count") or 0)
        if count > 0:
            self._queued_jobs[job_id] = _QueuedJob(
                label=self._label_from_event(event, fallback=job_id),
                count=count,
            )
        else:
            self._queued_jobs.pop(job_id, None)

    def _on_task_started(self, event: Event) -> None:
        self._forget_event_task(event)
        job_id = str(event.data.get("job_id") or "").strip()
        if job_id:
            self._requesting_jobs.pop(job_id, None)
        self._sync_dialog()

    def _on_task_terminal(self, event: Event) -> None:
        self._forget_event_task(event)
        job_id = str(event.data.get("job_id") or "").strip()
        if job_id:
            self._requesting_jobs.pop(job_id, None)
        self._sync_dialog()

    def _forget_event_task(self, event: Event) -> None:
        task_id = self._task_id_from_event(event)
        if task_id:
            self._starting_tasks.pop(task_id, None)

    def _sync_dialog(self) -> None:
        message = self._build_message()
        if not message:
            self._close_dialog()
            return
        if self._progress_dialog is None:
            self._progress_dialog = ProgressDialog.open_progress(
                self.parent,
                "任务进度",
                message,
            )
            self._progress_dialog.finished.connect(
                lambda *_args, dialog=self._progress_dialog: self._forget_dialog(dialog)
            )
        else:
            self._progress_dialog.set_message(message)

    def _build_message(self) -> str:
        requesting_count = len(self._requesting_jobs)
        starting_count = len(self._starting_tasks)
        queued_count = sum(job.count for job in self._queued_jobs.values())
        parts: list[str] = []

        if requesting_count == 1 and starting_count == 0:
            label = next(iter(self._requesting_jobs.values()))
            parts.append(f"正在提交执行请求：{label}。")
        elif requesting_count > 1 and starting_count == 0:
            parts.append(f"正在提交 {requesting_count} 条执行请求。")

        if starting_count == 1:
            label = next(iter(self._starting_tasks.values()))
            parts.append(f"环境启动中：{label}。启动完成后会自动切回执行中。")
        elif starting_count > 1:
            parts.append(f"有 {starting_count} 个任务正在启动环境。")

        if queued_count:
            if len(self._queued_jobs) == 1:
                queued_job = next(iter(self._queued_jobs.values()))
                parts.append(f"{queued_job.label} 还有 {queued_job.count} 个环境排队等待并发窗口。")
            else:
                parts.append(f"另有 {queued_count} 个环境排队等待并发窗口。")

        return "\n".join(parts)

    def _forget_dialog(self, dialog: ProgressDialog) -> None:
        if self._progress_dialog is dialog:
            self._progress_dialog = None

    def _close_dialog(self) -> None:
        if self._progress_dialog is None:
            return
        dialog = self._progress_dialog
        self._progress_dialog = None
        dialog.close_progress()

    @staticmethod
    def _task_id_from_event(event: Event) -> str:
        return str(event.data.get("task_id") or event.task_run_id or "").strip()

    @staticmethod
    def _label_from_event(event: Event, *, fallback: str) -> str:
        return (
            str(event.data.get("job_name") or "").strip()
            or str(event.data.get("message") or "").strip()
            or fallback
        )
