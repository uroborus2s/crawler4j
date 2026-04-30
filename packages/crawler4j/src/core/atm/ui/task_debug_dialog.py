"""Task-centric debug dialog."""

from __future__ import annotations

import asyncio
import json

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)

from src.core.atm.job_runtime import describe_job_runtime
from src.core.atm.models import Job
from src.core.atm.run_profile import AcquisitionMode
from src.core.debug.models import DebugSession, DebugSessionRequest, DebugSessionState
from src.core.debug.resolver import JobDebugTarget
from src.core.debug.service import DebugService, get_debug_service
from src.core.debug.vscode import ensure_vscode_attach_config
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo
from src.core.atm.run_profile import RunProfile
from src.ui.components.button import StyledButton
from src.ui.components.check_box import StyledCheckBox as QCheckBox
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.message_dialog import MessageDialog
from src.ui.components.spin_box import StyledSpinBox
from src.ui.components.text_edit import StyledTextEdit


class JobDebugDialog(QDialog):
    """基于 Job + RunProfile 的任务调试对话框。"""

    def __init__(
        self,
        job: Job,
        run_profile: RunProfile,
        module: ModuleInfo,
        *,
        debug_service: DebugService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._job = job
        self._run_profile = run_profile
        self._module = module
        self._service = debug_service or get_debug_service()
        self._current_session_id: str | None = None
        self._current_session: DebugSession | None = None
        self._refresh_in_flight = False
        self._runtime_label, self._runtime_tooltip = describe_job_runtime(job)
        self._target = JobDebugTarget(
            job=job,
            run_profile=run_profile,
            module=module,
            workflow=run_profile.execution.workflow if run_profile.execution else "default",
            hooks_module=(run_profile.execution.hooks_module if run_profile.execution else "") or module.name,
            execution_params=dict((run_profile.execution.params if run_profile.execution else {}) or {}),
            job_params=dict(job.params or {}),
            runtime_params={
                **((run_profile.execution.params if run_profile.execution else {}) or {}),
                **(job.params or {}),
            },
            object_bindings=dict(run_profile.execution.object_bindings if run_profile.execution else {}),
            object_params=dict(run_profile.execution.object_params if run_profile.execution else {}),
            timeout=run_profile.execution.timeout if run_profile.execution else 0,
            wait_timeout=run_profile.resource.acquisition.wait_timeout,
        )
        self.setWindowTitle(f"任务调试 - {job.name}")
        configure_titled_dialog(self)
        self._setup_ui()
        self._fit_to_screen()
        self._load_defaults()
        self._setup_polling()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1a1b26;
                color: #e5e7eb;
            }
            QLabel {
                color: #e5e7eb;
                background: transparent;
            }
            """
        )
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root_layout.addWidget(self.scroll_area, 1)

        content = QFrame(self.scroll_area)
        content.setStyleSheet("QFrame { background: transparent; }")
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(f"任务调试: {self._job.name}")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()

        self.start_btn = StyledButton("开始调试", variant="primary", min_height=36, min_width=108)
        self.restart_btn = StyledButton("重新开始", variant="primary", min_height=36, min_width=108)
        self.stop_btn = StyledButton("停止", variant="danger", min_height=36, min_width=96)
        self.vscode_btn = StyledButton("生成 VS Code 配置", variant="secondary", min_height=36, min_width=156)
        self.copy_attach_btn = StyledButton("复制附加地址", variant="secondary", min_height=36, min_width=128)
        header.addWidget(self.start_btn)
        header.addWidget(self.restart_btn)
        header.addWidget(self.stop_btn)
        layout.addLayout(header)

        summary_card = QFrame()
        summary_card.setStyleSheet(
            """
            QFrame {
                background: rgba(30, 30, 40, 0.85);
                border-radius: 8px;
                padding: 12px;
            }
            QLabel { color: white; }
            """
        )
        summary_layout = QGridLayout(summary_card)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setHorizontalSpacing(16)
        summary_layout.setVerticalSpacing(8)
        summary_items = [
            ("作业 ID", self._job.id),
            ("运行配置", self._runtime_label),
            ("模块", self._target.module.name),
            ("工作流", self._target.workflow or "default"),
            (
                "资源",
                self._run_profile.resource.acquisition.provider
                if self._run_profile.resource.acquisition.mode == AcquisitionMode.CREATE
                else (
                    self._run_profile.resource.acquisition.env_id
                    or self._run_profile.resource.acquisition.candidates
                    or "-"
                ),
            ),
            ("获取模式", self._run_profile.resource.acquisition.mode.value),
        ]
        for idx, (label_text, value_text) in enumerate(summary_items):
            row = idx // 2
            col = (idx % 2) * 2
            summary_layout.addWidget(QLabel(label_text), row, col)
            value = QLabel(str(value_text))
            value.setStyleSheet("color: rgba(255,255,255,0.78);")
            if label_text == "运行配置":
                value.setToolTip(self._runtime_tooltip)
            summary_layout.addWidget(value, row, col + 1)
        layout.addWidget(summary_card)

        config_card = QFrame()
        config_card.setStyleSheet(
            """
            QFrame {
                background: rgba(30, 30, 40, 0.85);
                border-radius: 8px;
                padding: 12px;
            }
            QLabel { color: white; }
            """
        )
        form = QFormLayout(config_card)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)

        self.attach_port_spin = StyledSpinBox()
        self.attach_port_spin.setRange(1, 65535)
        self.attach_port_spin.setValue(5678)

        self.timeout_spin = StyledSpinBox()
        self.timeout_spin.setRange(0, 24 * 60 * 60)
        self.timeout_spin.setSuffix(" s")

        self.wait_for_attach_checkbox = QCheckBox("等待 IDE 附加")
        self.wait_for_attach_checkbox.setChecked(True)
        self.stop_on_entry_checkbox = QCheckBox("启动后立即断住")
        self.keep_environment_checkbox = QCheckBox("调试后保留环境")

        self.params_editor = StyledTextEdit(monospace=True)
        self.params_editor.setMinimumHeight(180)

        form.addRow("附加端口", self.attach_port_spin)
        form.addRow("执行超时", self.timeout_spin)
        form.addRow("运行态参数", self.params_editor)
        form.addRow("", self.wait_for_attach_checkbox)
        form.addRow("", self.stop_on_entry_checkbox)
        form.addRow("", self.keep_environment_checkbox)
        layout.addWidget(config_card)

        action_row = QHBoxLayout()
        action_row.addWidget(self.vscode_btn)
        action_row.addWidget(self.copy_attach_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        status_card = QFrame()
        status_card.setStyleSheet(
            """
            QFrame {
                background: rgba(24, 24, 32, 0.85);
                border-radius: 8px;
                padding: 12px;
            }
            QLabel { color: white; }
            """
        )
        status_layout = QGridLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setHorizontalSpacing(16)
        status_layout.setVerticalSpacing(8)

        self.state_value = QLabel("-")
        self.attach_value = QLabel("-")
        self.pid_value = QLabel("-")
        self.env_value = QLabel("-")
        self.error_value = QLabel("-")
        self.error_value.setWordWrap(True)

        status_layout.addWidget(QLabel("状态"), 0, 0)
        status_layout.addWidget(self.state_value, 0, 1)
        status_layout.addWidget(QLabel("附加地址"), 1, 0)
        status_layout.addWidget(self.attach_value, 1, 1)
        status_layout.addWidget(QLabel("Worker PID"), 2, 0)
        status_layout.addWidget(self.pid_value, 2, 1)
        status_layout.addWidget(QLabel("环境 ID"), 3, 0)
        status_layout.addWidget(self.env_value, 3, 1)
        status_layout.addWidget(QLabel("最近错误"), 4, 0)
        status_layout.addWidget(self.error_value, 4, 1)
        layout.addWidget(status_card)

        self.logs_view = StyledTextEdit(
            monospace=True,
            background="rgba(12, 12, 18, 0.96)",
            hover_background="rgba(18, 18, 28, 0.98)",
            focus_background="rgba(18, 18, 28, 0.98)",
            font_size=12,
            border_radius=8,
        )
        self.logs_view.setReadOnly(True)
        self.logs_view.setMinimumHeight(160)
        self.logs_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.logs_view, 1)

        footer = QFrame(self)
        footer.setStyleSheet("QFrame { background: transparent; }")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 0, 20, 20)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()
        self.close_btn = StyledButton("关闭", variant="secondary", min_height=36, min_width=92)
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)
        root_layout.addWidget(footer)

        self.start_btn.clicked.connect(lambda: self._run_async(self._start_debug()))
        self.restart_btn.clicked.connect(lambda: self._run_async(self._restart_debug()))
        self.stop_btn.clicked.connect(lambda: self._run_async(self._stop_debug()))
        self.vscode_btn.clicked.connect(self.generate_vscode_config)
        self.copy_attach_btn.clicked.connect(self.copy_attach_address)

        self._update_action_states()

    def _setup_polling(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_later)
        self._timer.start(1000)

    def _load_defaults(self) -> None:
        self.timeout_spin.setValue(self._target.timeout)
        self.params_editor.setPlainText(json.dumps(self._target.runtime_params, ensure_ascii=False, indent=2))

    def build_request(self) -> DebugSessionRequest:
        raw = self.params_editor.toPlainText().strip() or "{}"
        try:
            params = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"调试参数不是合法 JSON: {exc}") from exc

        if not isinstance(params, dict):
            raise ValueError("调试参数必须是 JSON 对象")

        return DebugSessionRequest(
            job_id=self._job.id,
            params=params,
            timeout=self.timeout_spin.value(),
            attach_port=self.attach_port_spin.value(),
            wait_for_attach=self.wait_for_attach_checkbox.isChecked(),
            stop_on_entry=self.stop_on_entry_checkbox.isChecked(),
            keep_environment=self.keep_environment_checkbox.isChecked(),
        )

    def refresh_later(self) -> None:
        if self._refresh_in_flight:
            return
        self._run_async(self._refresh())

    async def _refresh(self) -> None:
        self._refresh_in_flight = True
        try:
            if not self._current_session_id:
                sessions = await self._service.list_sessions()
                matches = [session for session in sessions if session.job_id == self._job.id]
                if matches:
                    matches.sort(key=lambda item: (item.created_at, item.started_at or 0), reverse=True)
                    self._current_session_id = matches[0].id

            if self._current_session_id:
                session = await self._service.get_session(self._current_session_id)
                self._apply_session(session)
        except Exception as exc:
            logger.error(f"[TaskDebugDialog] refresh failed: {exc}")
        finally:
            self._refresh_in_flight = False

    async def _start_debug(self) -> None:
        try:
            request = self.build_request()
            session = await self._service.create_session(request)
            self._current_session_id = session.id
            await self._service.start_session(session.id)
            await self._refresh()
        except Exception as exc:
            MessageDialog.warning(self, "开始调试失败", str(exc))

    async def _restart_debug(self) -> None:
        try:
            request = self.build_request()
            if self._current_session_id:
                await self._service.stop_session(self._current_session_id)
            session = await self._service.create_session(request)
            self._current_session_id = session.id
            await self._service.start_session(session.id)
            await self._refresh()
        except Exception as exc:
            MessageDialog.warning(self, "重启调试失败", str(exc))

    async def _stop_debug(self) -> None:
        try:
            if self._current_session_id:
                await self._service.stop_session(self._current_session_id)
            await self._refresh()
        except Exception as exc:
            MessageDialog.warning(self, "停止调试失败", str(exc))

    def generate_vscode_config(self) -> None:
        try:
            if not self._module.path:
                raise ValueError("模块路径不可用")
            attach_host, attach_port = self._resolve_vscode_attach_target()
            launch_path = ensure_vscode_attach_config(
                self._module.path,
                host=attach_host,
                port=attach_port,
            )
            MessageDialog.information(self, "已生成 VS Code 配置", f"已写入:\n{launch_path}")
        except Exception as exc:
            MessageDialog.warning(self, "生成配置失败", str(exc))

    def _resolve_vscode_attach_target(self) -> tuple[str, int]:
        session = self._current_session
        if session and not session.is_final() and session.attach_port > 0:
            return session.attach_host, session.attach_port

        request = self.build_request()
        return request.attach_host, request.attach_port

    def copy_attach_address(self) -> None:
        QApplication.clipboard().setText(self.attach_value.text() if self.attach_value.text() != "-" else "")

    def _apply_session(self, session: DebugSession | None) -> None:
        self._current_session = session
        if not session:
            self.state_value.setText("-")
            self.attach_value.setText("-")
            self.pid_value.setText("-")
            self.env_value.setText("-")
            self.error_value.setText("-")
            self._update_logs_view([])
            self._update_action_states()
            return

        self.state_value.setText(session.state.value)
        self.attach_value.setText(f"{session.attach_host}:{session.attach_port}")
        self.pid_value.setText(str(session.worker_pid or "-"))
        self.env_value.setText(str(session.env_id or "-"))
        self.error_value.setText(session.last_error or "-")
        self._update_logs_view(session.logs[-200:])
        self._update_action_states(session)

    def _update_action_states(self, session: DebugSession | None = None) -> None:
        state = session.state if session else None
        running = state in {
            DebugSessionState.STARTING,
            DebugSessionState.WAITING_FOR_ATTACH,
            DebugSessionState.RUNNING,
            DebugSessionState.STOPPING,
        }
        self.start_btn.setEnabled(not running)
        self.restart_btn.setEnabled(self._current_session_id is not None)
        self.stop_btn.setEnabled(running)
        self.copy_attach_btn.setEnabled(bool(session and session.attach_port))

    def _update_logs_view(self, logs: list[str]) -> None:
        new_text = "\n".join(logs)
        if self.logs_view.toPlainText() == new_text:
            return

        scrollbar = self.logs_view.verticalScrollBar()
        previous_value = scrollbar.value()
        previous_maximum = scrollbar.maximum()
        was_following_latest = previous_maximum <= 0 or previous_value >= max(0, previous_maximum - 4)

        self.logs_view.setPlainText(new_text)

        scrollbar = self.logs_view.verticalScrollBar()
        if was_following_latest:
            scrollbar.setValue(scrollbar.maximum())
            return

        scrollbar.setValue(min(previous_value, scrollbar.maximum()))

    def _run_async(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return
        loop.create_task(coro)

    def _fit_to_screen(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if not screen:
            self.resize(1100, 820)
            return

        available = screen.availableGeometry()
        max_width = min(available.width(), max(640, available.width() - 48))
        max_height = min(available.height(), max(480, available.height() - 48))
        target_width = min(1100, max_width)
        target_height = min(820, max_height)

        self.setMaximumSize(max_width, max_height)
        self.resize(target_width, target_height)
