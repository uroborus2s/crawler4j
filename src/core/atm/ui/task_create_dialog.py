"""新建任务弹窗。

提供创建自动化任务的界面，支持：
    - 任务名称输入
    - 策略选择下拉框
    - Cron 定时配置 (可选)
"""

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.models import TriggerConfig, TriggerType
from src.core.tsm import TaskStrategy, get_strategy_loader
from src.ui.components.combo_box import StyledComboBox as QComboBox


class TaskCreateDialog(QDialog):
    """新建任务弹窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strategies: list[TaskStrategy] = []
        self._selected_strategy_id: str = ""
        self._setup_ui()
        self._load_strategies()

    def _setup_ui(self):
        self.setWindowTitle("新建自动化任务")
        self.setMinimumSize(450, 350)
        self.setStyleSheet("""
            QDialog {
                background: rgb(30, 30, 40);
            }
            QLabel { color: white; }
            QLineEdit {
                background: rgba(50, 50, 60, 0.9);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 4px;
                padding: 10px;
                min-width: 250px;
            }
            QCheckBox { color: white; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 标题
        title = QLabel("新建自动化任务")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)

        # 表单
        form = QFormLayout()
        form.setSpacing(16)

        # 任务名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如: 每日抢票任务")
        form.addRow("任务名称:", self.name_edit)

        # 策略选择
        self.strategy_combo = QComboBox()
        self.strategy_combo.setMinimumWidth(250)
        form.addRow("选择策略:", self.strategy_combo)

        # 策略预览
        self.strategy_preview = QLabel()
        self.strategy_preview.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 12px;")
        self.strategy_preview.setWordWrap(True)
        form.addRow("", self.strategy_preview)

        # 触发方式
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItem("手动执行", "manual")
        self.trigger_combo.addItem("Cron 定时", TriggerType.CRON.value)
        self.trigger_combo.addItem("固定间隔", TriggerType.INTERVAL.value)
        self.trigger_combo.addItem("随机间隔", TriggerType.RANDOM.value)
        self.trigger_combo.currentIndexChanged.connect(self._on_trigger_changed)
        form.addRow("触发方式:", self.trigger_combo)

        # 触发参数 (Stacked)
        self.trigger_stack = QStackedWidget()
        
        # page 0: manual (empty)
        self.trigger_stack.addWidget(QWidget())
        
        # page 1: cron
        page_cron = QWidget()
        layout_cron = QFormLayout(page_cron)
        layout_cron.setContentsMargins(0, 0, 0, 0)
        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText("0 8 * * *")
        layout_cron.addRow("Cron 表达式:", self.cron_edit)
        self.trigger_stack.addWidget(page_cron)
        
        # page 2: interval
        page_interval = QWidget()
        layout_interval = QFormLayout(page_interval)
        layout_interval.setContentsMargins(0, 0, 0, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 86400 * 30) # 1s to 30 days
        self.interval_spin.setValue(60)
        self.interval_spin.setSuffix(" 秒")
        layout_interval.addRow("执行间隔:", self.interval_spin)
        self.trigger_stack.addWidget(page_interval)
        
        # page 3: random
        page_random = QWidget()
        layout_random = QFormLayout(page_random)
        layout_random.setContentsMargins(0, 0, 0, 0)
        
        self.rand_interval_spin = QSpinBox()
        self.rand_interval_spin.setRange(1, 86400 * 30)
        self.rand_interval_spin.setValue(60)
        self.rand_interval_spin.setSuffix(" 秒")
        layout_random.addRow("基准间隔:", self.rand_interval_spin)
        
        self.rand_jitter_spin = QSpinBox()
        self.rand_jitter_spin.setRange(1, 3600)
        self.rand_jitter_spin.setValue(10)
        self.rand_jitter_spin.setSuffix(" 秒")
        layout_random.addRow("随机浮动(±):", self.rand_jitter_spin)
        
        self.trigger_stack.addWidget(page_random)
        
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

        create_btn = QPushButton("创建")
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

    def _load_strategies(self):
        """加载策略列表。"""
        loader = get_strategy_loader()
        self._strategies = loader.list_all()

        self.strategy_combo.clear()
        for strategy in self._strategies:
            display_name = f"{strategy.name} ({strategy.scaling.max_concurrency} 并发)"
            self.strategy_combo.addItem(display_name, strategy.id)

        if not self._strategies:
            self.strategy_combo.addItem("-- 暂无策略，请先创建 --", "")
            self.strategy_preview.setText("⚠️ 请先在『策略管理』中创建策略")

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
            lines.append(f"执行: {strategy.execution.module}/{strategy.execution.workflow or 'default'}")
            lines.append(f"超时: {strategy.execution.timeout}s")
        self.strategy_preview.setText(" | ".join(lines))

    def _on_trigger_changed(self, index: int):
        """触发方式切换。"""
        # manual=0, cron=1, interval=2, random=3
        # StackedWidget index matches combo index logic
        self.trigger_stack.setCurrentIndex(index)

    def _on_create(self):
        """创建任务。"""
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return

        if not self._selected_strategy_id:
            return

        self.accept()

    def get_task_data(self) -> dict:
        """获取任务创建数据。"""
        trigger_type_val = self.trigger_combo.currentData()
        trigger_config = None
        
        if trigger_type_val == TriggerType.CRON.value:
            trigger_config = TriggerConfig(
                type=TriggerType.CRON,
                cron_expr=self.cron_edit.text().strip()
            )
        elif trigger_type_val == TriggerType.INTERVAL.value:
            trigger_config = TriggerConfig(
                type=TriggerType.INTERVAL,
                interval_seconds=self.interval_spin.value()
            )
        elif trigger_type_val == TriggerType.RANDOM.value:
             trigger_config = TriggerConfig(
                type=TriggerType.RANDOM,
                interval_seconds=self.rand_interval_spin.value(),
                random_range=self.rand_jitter_spin.value()
            )

        return {
            "name": self.name_edit.text().strip(),
            "strategy_id": self._selected_strategy_id,
            "trigger_config": trigger_config,
        }
