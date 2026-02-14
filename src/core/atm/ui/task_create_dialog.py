"""新建任务(Job)弹窗。

提供创建作业的界面，支持：
    - 作业名称
    - 作业类型 (Batch/Service)
    - 策略选择
    - 并发数配置
    - 触发器配置
"""

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import Job, JobType, TriggerType
from src.core.tsm import get_strategy_loader
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class TaskCreateDialog(QDialog):
    """新建作业弹窗。"""

    def __init__(self, parent=None, job: Job | None = None):
        super().__init__(parent)
        self._strategies = []
        self._selected_strategy_id: str = ""
        self._job = job  # Existing job for editing
        self._setup_ui()
        self._load_strategies()
        
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
        self.type_combo.addItem("批处理 (Batch)", JobType.BATCH.value)
        self.type_combo.addItem("常驻服务 (Service)", JobType.SERVICE.value)
        form.addRow("作业类型:", self.type_combo)

        # 3. 策略选择
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(250)
        form.addRow("选择策略:", self.strategy_combo)

        # 策略预览
        self.strategy_preview = QLabel()
        self.strategy_preview.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        self.strategy_preview.setWordWrap(True)
        form.addRow("", self.strategy_preview)
        
        # 4. 并发配置
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 100)
        self.concurrency_spin.setValue(1)
        self.concurrency_spin.setSuffix(" 个实例")
        form.addRow("目标并发:", self.concurrency_spin)

        # 5. 触发方式
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("手动触发", "manual")
        self.trigger_combo.addItem("Cron 定时", TriggerType.CRON.value)
        # Service type acts as "Always On" if manual+active, so Trigger mainly for Batch or scheduled restart?
        # For simplicity, keep options.
        self.trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        form.addRow("触发方式:", self.trigger_combo)

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

        # 监听策略选择变化
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)

    def _init_form_data(self):
        """初始化表单数据 (编辑模式)。"""
        job = self._job
        self.setWindowTitle(f"编辑任务: {job.name}")
        
        self.name_edit.setText(job.name)
        
        # Type
        index = self.type_combo.findData(job.type.value)
        if index >= 0:
            self.type_combo.setCurrentIndex(index)
            
        # Strategy (will be set in _load_strategies or after)
        # We need to set it after loading strategies.
        
        # Concurrency
        self.concurrency_spin.setValue(job.concurrency_target)
        
        # Trigger
        if job.trigger.type == TriggerType.CRON:
            idx = self.trigger_combo.findData(TriggerType.CRON.value)
            self.trigger_combo.setCurrentIndex(idx)
            self.cron_edit.setText(job.trigger.cron_expr or "")
        else:
            idx = self.trigger_combo.findData("manual")
            self.trigger_combo.setCurrentIndex(idx)

    def _load_strategies(self):
        """加载策略列表。"""
        loader = get_strategy_loader()
        self._strategies = loader.list_all()

        self.strategy_combo.clear()
        for strategy in self._strategies:
            # 策略本身有 max_concurrency，但 V2 中由 Job 控制
            display_name = f"{strategy.name}"
            self.strategy_combo.addItem(display_name, strategy.id)

        if not self._strategies:
            self.strategy_combo.addItem("-- 暂无策略，请先创建 --", "")
            self.strategy_preview.setText("⚠️ 请先在『策略管理』中创建策略")
            
        # If editing, select the current strategy
        if self._job:
            index = self.strategy_combo.findData(self._job.strategy_id)
            if index >= 0:
                self.strategy_combo.setCurrentIndex(index)

    def _on_strategy_changed(self, index: int):
        """策略选择变化。"""
        if index < 0 or index >= len(self._strategies):
            self._selected_strategy_id = ""
            self.strategy_preview.setText("")
            return

        strategy = self._strategies[index]
        self._selected_strategy_id = strategy.id

        # 预览信息
        lines = []
        lines.append(f"环境: {strategy.selector.env_type.value}")
        if strategy.execution:
            lines.append(f"执行: {strategy.execution.module}")
        self.strategy_preview.setText(" | ".join(lines))

    def _on_trigger_changed(self, index: int):
        self.trigger_stack.setCurrentIndex(index)

    def _on_create(self):
        """创建任务。"""
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return

        if not self._selected_strategy_id:
            return

        self.accept()

    def get_job_data(self) -> dict:
        """获取 Job 创建数据。"""
        trigger_type_val = self.trigger_combo.currentData()
        trigger_config = {}
        
        if trigger_type_val == TriggerType.CRON.value:
            trigger_config = {
                "type": TriggerType.CRON.value,
                "cron_expr": self.cron_edit.text().strip()
            }
        else:
            trigger_config = {"type": "manual"}

        return {
            "name": self.name_edit.text().strip(),
            "strategy_id": self._selected_strategy_id,
            "job_type": self.type_combo.currentData(),
            "concurrency": self.concurrency_spin.value(),
            "trigger_config": trigger_config,
        }
