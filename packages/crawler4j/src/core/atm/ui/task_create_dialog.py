"""新建任务(Job)弹窗。"""

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import Job, JobType, TriggerType
from src.core.atm.run_profile import AcquisitionMode, RunProfile
from src.core.atm.ui.run_profile_dialog import RunProfileDialog
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class TaskCreateDialog(QDialog):
    """新建作业弹窗。"""

    def __init__(self, parent=None, job: Job | None = None):
        super().__init__(parent)
        self._inline_run_profile: RunProfile | None = None
        self._job = job  # Existing job for editing
        self._setup_ui()
        
        if self._job:
            self._init_form_data()

    def _setup_ui(self):
        self.setWindowTitle("新建任务 (Job)")
        self.setMinimumSize(500, 450)
        self.setStyleSheet("""
            QDialog {
                background: rgb(30, 30, 40);
            }
            QLabel { color: white; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 标题
        title_text = "编辑任务 (Job)" if self._job else "新建任务 (Job)"
        title = QLabel(title_text)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(16)
        # label alignment
        # label alignment

        # 1. 任务名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如: 每日数据采集")
        form.addRow("任务名称:", self.name_edit)

        # 2. 作业类型
        self.type_combo = QComboBox()
        self.type_combo.addItem("批次任务", JobType.BATCH.value)
        self.type_combo.addItem("持续保活", JobType.SERVICE.value)
        self.type_combo.currentIndexChanged.connect(self._on_job_type_changed)
        form.addRow("作业模式:", self.type_combo)

        # 3. 运行配置
        inline_page = QWidget()
        inline_layout = QVBoxLayout(inline_page)
        inline_layout.setContentsMargins(0, 0, 0, 0)
        inline_layout.setSpacing(8)

        self.inline_preview = QLabel("尚未配置运行模板。")
        self.inline_preview.setStyleSheet("color: rgba(255, 255, 255, 0.7); font-size: 12px;")
        self.inline_preview.setWordWrap(True)
        inline_layout.addWidget(self.inline_preview)

        self.inline_config_btn = QPushButton("配置运行模板")
        self.inline_config_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.inline_config_btn.setMinimumHeight(36)
        self.inline_config_btn.clicked.connect(self._edit_inline_run_profile)
        inline_btn_row = QHBoxLayout()
        inline_btn_row.setContentsMargins(0, 0, 0, 0)
        inline_btn_row.setSpacing(0)
        inline_btn_row.addWidget(self.inline_config_btn)
        inline_btn_row.addStretch()
        inline_layout.addLayout(inline_btn_row)
        self._sync_inline_config_button_width()

        form.addRow("运行配置:", inline_page)
        
        # 4. 并发配置
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 100)
        self.concurrency_spin.setValue(1)
        self.concurrency_spin.setSuffix(" 个实例")
        form.addRow("目标并发:", self.concurrency_spin)

        # 5. 触发方式
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("执行一次", TriggerType.MANUAL.value)
        self.trigger_combo.addItem("Cron 定时", TriggerType.CRON.value)
        self.trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        form.addRow("触发方式:", self.trigger_combo)

        self.trigger_hint = QLabel()
        self.trigger_hint.setWordWrap(True)
        self.trigger_hint.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        form.addRow("", self.trigger_hint)

        # 触发参数 (Stacked)
        self.trigger_stack = QStackedWidget()
        
        # page 0: manual
        self.trigger_stack.addWidget(QWidget())
        
        # page 1: cron
        page_cron = QWidget()
        layout_cron = QFormLayout(page_cron)
        layout_cron.setContentsMargins(0, 0, 0, 0)
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("0 8 * * *")
        layout_cron.addRow("Cron 表达式:", self.cron_edit)
        self.trigger_stack.addWidget(page_cron)
        
        layout.addLayout(form)
        layout.addWidget(self.trigger_stack)
        layout.addStretch()

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 10px 24px;
                border-radius: 6px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        create_btn = QPushButton("保存" if self._job else "创建")
        create_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.9);
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(create_btn)

        layout.addLayout(btn_layout)

        self._on_job_type_changed(self.type_combo.currentIndex())

    def _init_form_data(self):
        """初始化表单数据 (编辑模式)。"""
        job = self._job
        self.setWindowTitle(f"编辑任务: {job.name}")
        
        self.name_edit.setText(job.name)
        
        # Type
        index = self.type_combo.findData(job.type.value)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
            
        if job.run_profile:
            self._inline_run_profile = job.run_profile
        self._update_inline_preview()
            
        # Concurrency
        self.concurrency_spin.setValue(job.concurrency_target)
        
        # Trigger
        self._on_job_type_changed(self.type_combo.currentIndex())
        trigger_index = self.trigger_combo.findData(job.trigger.type.value)
        if trigger_index >= 0:
            self.trigger_combo.setCurrentIndex(trigger_index)
        if job.trigger.type == TriggerType.CRON:
            self.cron_edit.setText(job.trigger.cron_expr or "")
        self._on_trigger_changed(self.trigger_combo.currentIndex())

    def _edit_inline_run_profile(self):
        dialog = RunProfileDialog(run_profile=self._inline_run_profile, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self._inline_run_profile = dialog.get_run_profile()
        self._update_inline_preview()

    def _update_inline_preview(self):
        run_profile = self._inline_run_profile
        if not run_profile:
            self.inline_preview.setText("尚未配置运行模板。点击下方按钮开始配置。")
            self.inline_config_btn.setText("配置运行模板")
            self._sync_inline_config_button_width()
            return

        acquisition_mode = run_profile.resource.acquisition.mode
        mode_text = "创建环境" if acquisition_mode == AcquisitionMode.CREATE else "选择环境"
        lines = [f"方式: {mode_text}"]
        if acquisition_mode == AcquisitionMode.CREATE:
            lines.append(f"Provider: {run_profile.resource.acquisition.provider}")
            lines.append(f"环境: {run_profile.resource.acquisition.env_type.value}")
        else:
            lines.append(f"选择器: {run_profile.resource.acquisition.selector_name or '-'}")
        if run_profile.execution:
            lines.append(f"执行: {run_profile.execution.module}/{run_profile.execution.workflow or 'default'}")
        self.inline_preview.setText(" | ".join(lines))
        self.inline_config_btn.setText("重新编辑运行模板")
        self._sync_inline_config_button_width()

    def _sync_inline_config_button_width(self) -> None:
        text = self.inline_config_btn.text().strip()
        content_width = self.inline_config_btn.fontMetrics().horizontalAdvance(text)
        self.inline_config_btn.setMinimumWidth(max(220, content_width + 48))

    def _on_trigger_changed(self, index: int):
        del index
        is_cron = self.trigger_combo.currentData() == TriggerType.CRON.value
        self.trigger_stack.setCurrentIndex(1 if is_cron else 0)
        is_batch = self.type_combo.currentData() == JobType.BATCH.value
        self.cron_edit.setEnabled(is_batch and is_cron)
        self._update_trigger_hint()

    def _update_trigger_hint(self):
        is_batch = self.type_combo.currentData() == JobType.BATCH.value
        if not is_batch:
            self.trigger_hint.setText("持续保活模式会在你点击启动后持续维持 N 个运行中的任务，直到点击暂停。")
            return

        if self.trigger_combo.currentData() == TriggerType.CRON.value:
            self.trigger_hint.setText("Cron 批次模式会在 Cron 命中时一次性启动 N 个任务；若上一批仍在运行，本次触发将跳过。")
            return

        self.trigger_hint.setText("执行一次模式会在你点击按钮后立刻启动一批任务；若上一批仍在运行，本次触发不会再次发起。")

    def _on_job_type_changed(self, index: int):
        del index
        job_type = self.type_combo.currentData()
        is_batch = job_type == JobType.BATCH.value

        self.trigger_combo.setItemText(0, "执行一次" if is_batch else "手动启动")

        if is_batch:
            self.trigger_combo.setEnabled(True)
            trigger_value = self.trigger_combo.currentData() or TriggerType.MANUAL.value
            if trigger_value not in {TriggerType.MANUAL.value, TriggerType.CRON.value}:
                trigger_value = TriggerType.MANUAL.value
        else:
            trigger_value = TriggerType.MANUAL.value
            self.trigger_combo.setEnabled(False)

        trigger_index = self.trigger_combo.findData(trigger_value)
        if trigger_index < 0:
            trigger_index = 0

        self.trigger_combo.blockSignals(True)
        self.trigger_combo.setCurrentIndex(trigger_index)
        self.trigger_combo.blockSignals(False)
        self._on_trigger_changed(trigger_index)

    def _on_create(self):
        """创建任务。"""
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return

        if not self._inline_run_profile:
            QMessageBox.warning(self, "配置不完整", "请先配置任务运行模板。")
            return

        if (
            self.type_combo.currentData() == JobType.BATCH.value
            and self.trigger_combo.currentData() == TriggerType.CRON.value
            and not self.cron_edit.text().strip()
        ):
            QMessageBox.warning(self, "配置不完整", "Cron 批次模式必须填写 Cron 表达式。")
            self.cron_edit.setFocus()
            return

        self.accept()

    def get_job_data(self) -> dict:
        """获取 Job 创建数据。"""
        job_type = self.type_combo.currentData()
        trigger_type = self.trigger_combo.currentData()
        if job_type == JobType.BATCH.value and trigger_type == TriggerType.CRON.value:
            trigger_config = {
                "type": TriggerType.CRON.value,
                "cron_expr": self.cron_edit.text().strip()
            }
        else:
            trigger_config = {"type": TriggerType.MANUAL.value}

        return {
            "name": self.name_edit.text().strip(),
            "run_profile": self._inline_run_profile.model_dump(mode="json") if self._inline_run_profile else None,
            "job_type": job_type,
            "concurrency": self.concurrency_spin.value(),
            "trigger_config": trigger_config,
        }
