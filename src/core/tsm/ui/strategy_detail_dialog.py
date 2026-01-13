"""策略详情编辑弹窗 (V2)。

支持 Tab 页式布局编辑 V2 策略模型：
    - 基础信息
    - 资源选择 (Selector)
    - 弹性伸缩 (Scaling)
    - 执行目标 (Execution)
    - 容错与清理 (Retry & Teardown)

特性更新:
    - 支持指纹浏览器 (BitBrowser/VirtualBrowser) 分级选择
    - 支持从 MMS 模块中动态加载工作流列表
    - 优化 UI 布局，加长输入框
"""

from typing import cast

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import get_module_registry
from src.core.tsm import (
    EnvType,
    ExecutionContext,
    MatchGroup,
    ResourceSelector,
    RetryPolicy,
    ScalingMode,
    ScalingPolicy,
    SelectionStrategy,
    TaskStrategy,
    TeardownAction,
    TeardownPolicy,
)
from src.core.tsm.ui.rule_builder import RuleBuilder


class WorkflowSelector(QWidget):
    """工作流选择组合控件 (Module + Workflow)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_modules()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) # Remove spacing to behave like a single control when module is hidden

        # 模块下拉框
        self.module_combo = QComboBox()
        self.module_combo.setPlaceholderText("选择模块")
        # Module combo should not take too much space if visible alongside workflow
        self.module_combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.module_combo.setMinimumWidth(120)
        self.module_combo.currentTextChanged.connect(self._on_module_changed)
        layout.addWidget(self.module_combo)
        
        # Spacer if both are visible
        self.spacer = QWidget()
        self.spacer.setFixedWidth(8)
        self.spacer.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.spacer)

        # 工作流下拉框
        self.workflow_combo = QComboBox()
        self.workflow_combo.setPlaceholderText("选择工作流")
        self.workflow_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.workflow_combo)

    def set_module_filter(self, module_name: str | None):
        """设置模块过滤器。如果设置，隐藏模块选择框并只显示该模块的工作流。"""
        self._filter_module = module_name
        has_filter = bool(module_name)
        self.module_combo.setVisible(not has_filter)
        self.spacer.setVisible(not has_filter)
        
        if module_name:
            # Force module selection
            index = self.module_combo.findText(module_name)
            if index >= 0:
                self.module_combo.setCurrentIndex(index)
            # Reload workflows immediately
            self._on_module_changed(module_name)
        else:
            if self.module_combo.count() > 0:
                self.module_combo.setCurrentIndex(0)

    def _load_modules(self):
        try:
            registry = get_module_registry()
            # Force refresh might be needed if registry is empty
            if not registry.list_modules():
                registry.refresh() 
            
            modules = registry.list_modules()
            self.module_combo.clear()
            self.module_combo.addItem("", "")  # Empty default
            for m in modules:
                self.module_combo.addItem(m.name, m)
        except Exception:
            pass  # MMS might not be ready

    def _on_module_changed(self, module_name):
        self.workflow_combo.clear()
        if not module_name:
            return
            
        try:
            registry = get_module_registry()
            module = registry.get_module(module_name)
            if module and module.manifest.workflows:
                for wf in module.manifest.workflows:
                    self.workflow_combo.addItem(wf.name)
            elif not module:
                # Try refresh ?
                registry.refresh()
                module = registry.get_module(module_name)
                if module and module.manifest.workflows:
                     for wf in module.manifest.workflows:
                        self.workflow_combo.addItem(wf.name)
        except Exception:
            pass

    def get_value(self) -> tuple[str, str]:
        """返回 (module, workflow)"""
        return self.module_combo.currentText(), self.workflow_combo.currentText()

    def set_value(self, module: str, workflow: str):
        index = self.module_combo.findText(module)
        if index >= 0:
            self.module_combo.setCurrentIndex(index)
            # workflow triggers update, but async delay might be needed? 
            # Direct/sync update is fine here as data is local
            wf_index = self.workflow_combo.findText(workflow)
            if wf_index >= 0:
                self.workflow_combo.setCurrentIndex(wf_index)
        else:
             # Handle custom text if not in list? For now just set
             pass


class StrategyDetailDialog(QDialog):
    """策略详情编辑弹窗 (V2)。"""

    def __init__(self, strategy: TaskStrategy | None = None, parent=None):
        super().__init__(parent)
        self._strategy = strategy or TaskStrategy(
            id="new_strategy",
            name="New Strategy",
            selector=ResourceSelector(env_type=EnvType.CHROME),
        )
        self._is_new = strategy is None
        self._setup_ui()
        self._load_strategy()

    def _setup_ui(self):
        self.setWindowTitle("新建策略" if self._is_new else "编辑策略")
        self.resize(800, 700) # Increased size
        self.setStyleSheet("""
            QDialog { background: rgb(30, 30, 40); }
            QLabel { color: rgba(255, 255, 255, 0.9); font-size: 13px; }
            QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
                background: rgba(40, 40, 50, 0.9);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 25px;
                min-width: 280px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
                border-color: #6366f1;
                background: rgba(50, 50, 60, 1);
            }
            QGroupBox {
                color: #a5b4fc;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 20px;
                padding: 20px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTabWidget::pane { border: none; }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                padding: 8px 24px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected { background: #6366f1; color: white; font-weight: bold; }
            QTabBar::tab:hover { background: rgba(255, 255, 255, 0.1); }
            
            QComboBox QAbstractItemView {
                background: rgb(40, 40, 50);
                border: 1px solid rgba(255, 255, 255, 0.1);
                selection-background-color: #6366f1;
                selection-color: white;
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min_height: 30px; /* Increase item height */
                padding: 5px 10px;
                font-size: 14px; /* Larger font */
                border-radius: 4px; /* Rounded highlight */
                margin-bottom: 2px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            QComboBox QAbstractItemView::item:selected {
                background: #6366f1;
            }

            /* QSpinBox Buttons Styling */
            QSpinBox::up-button, QSpinBox::down-button {
                width: 24px;
                background: rgba(255, 255, 255, 0.05);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            QSpinBox::up-button {
                border-top-right-radius: 4px;
                margin-bottom: 0px;
            }
            QSpinBox::down-button {
                border-bottom-right-radius: 4px;
                margin-top: 0px;
            }
            QSpinBox::up-arrow {
                image: url(src/ui/assets/arrow_up.svg);
                width: 14px;
                height: 14px;
            }
            QSpinBox::down-arrow {
                image: url(src/ui/assets/arrow_down.svg);
                width: 14px;
                height: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 模式切换
        mode_layout = QHBoxLayout()
        self.form_btn = QPushButton("📝 表单配置")
        self.yaml_btn = QPushButton("📄 YAML 源码")
        
        for btn in [self.form_btn, self.yaml_btn]:
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.05);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    padding: 6px 16px;
                    border-radius: 4px;
                }
                QPushButton:checked { background: #4f46e5; border-color: #4f46e5; }
            """)
        
        self.form_btn.setChecked(True)
        self.form_btn.clicked.connect(lambda: self._switch_mode("form"))
        self.yaml_btn.clicked.connect(lambda: self._switch_mode("yaml"))

        mode_layout.addWidget(self.form_btn)
        mode_layout.addWidget(self.yaml_btn)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 堆叠挂件
        self.stack = QStackedWidget()
        
        # 1. 表单模式
        self.form_tabs = QTabWidget()
        self._setup_form_tabs()
        self.stack.addWidget(self.form_tabs)

        # 2. YAML 模式
        self.yaml_widget = self._create_yaml_widget()
        self.stack.addWidget(self.yaml_widget)

        layout.addWidget(self.stack, 1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.setStyleSheet("background: rgba(255,255,255,0.1); border:none; color:white; border-radius:4px;")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("保存策略")
        save_btn.setFixedSize(100, 32)
        save_btn.setStyleSheet("background: #10b981; border:none; color:white; font-weight:bold; border-radius:4px;")
        save_btn.clicked.connect(self._on_save)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _setup_form_tabs(self):
        self.tab_basic = QWidget()
        self._setup_basic_tab(self.tab_basic)
        self.form_tabs.addTab(self.tab_basic, "基础与资源")

        self.tab_scaling = QWidget()
        self._setup_scaling_tab(self.tab_scaling)
        self.form_tabs.addTab(self.tab_scaling, "弹性伸缩")

        self.tab_exec = QWidget()
        self._setup_execution_tab(self.tab_exec)
        self.form_tabs.addTab(self.tab_exec, "执行配置")
        
        self.tab_teardown = QWidget()
        self._setup_teardown_tab(self.tab_teardown)
        self.form_tabs.addTab(self.tab_teardown, "容错与清理")

    def _create_form_layout(self, parent):
        form = QFormLayout(parent)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(20)
        return form

    def _setup_basic_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # 基础信息
        basic_group = QGroupBox("基础信息")
        form = self._create_form_layout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("策略名称")
        form.addRow("策略名称:", self.name_edit)
        
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("简要描述策略用途")
        form.addRow("描述:", self.desc_edit)
        
        form.addRow("描述:", self.desc_edit)

        # 全局模块选择
        self.module_link_combo = QComboBox()
        self.module_link_combo.setPlaceholderText("选择关联模块 (可选)")
        self.module_link_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Match other inputs
        # Load modules
        try:
            registry = get_module_registry()
            self.module_link_combo.addItem("通用策略 (无特定模块)", "")
            for m in registry.list_modules():
                self.module_link_combo.addItem(m.name, m.name)
        except Exception:
            pass
        self.module_link_combo.currentTextChanged.connect(self._on_global_module_changed)
        form.addRow("所属模块:", self.module_link_combo)
        
        layout.addWidget(basic_group)

        # 资源选择
        sel_group = QGroupBox("资源定义 (Resource)")
        form = self._create_form_layout(sel_group)
        
        # -- 资源类型分级选择 --
        res_layout = QHBoxLayout()
        res_layout.setContentsMargins(0, 0, 0, 0)
        
        self.env_category_combo = QComboBox()
        self.env_category_combo.addItems(["标准浏览器 (Chrome)", "安卓设备 (Android)", "指纹浏览器 (Fingerprint)", "调试 (Debug)"])
        self.env_category_combo.currentIndexChanged.connect(self._on_category_changed)
        res_layout.addWidget(self.env_category_combo, 1) # stretch 1
        
        self.env_provider_label = QLabel("Provider:")
        self.env_provider_combo = QComboBox()
        self.env_provider_combo.addItems(["BitBrowser (BT)", "VirtualBrowser"])
        self.env_provider_label.hide()
        self.env_provider_combo.hide()
        res_layout.addWidget(self.env_provider_label)
        res_layout.addWidget(self.env_provider_combo, 1)
        
        form.addRow("环境类型:", res_layout)
        
        # ---------------------
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems([s.value for s in SelectionStrategy])
        form.addRow("排序策略:", self.sort_combo)
        
        self.wait_timeout_spin = QSpinBox()
        self.wait_timeout_spin.setRange(0, 3600)
        self.wait_timeout_spin.setSuffix(" s")
        self.wait_timeout_spin.setSpecialValueText("不等待")
        form.addRow("等待超时:", self.wait_timeout_spin)
        
        layout.addWidget(sel_group)
        
        # 匹配规则
        match_group = QGroupBox("匹配规则 (Selector)")
        vbox = QVBoxLayout(match_group)
        vbox.setSpacing(8)
        
        lbl1 = QLabel("匹配标签 (Match Labels):")
        vbox.addWidget(lbl1)
        self.labels_edit = QPlainTextEdit()
        self.labels_edit.setPlaceholderText("key: value (每行一个，例如 region: cn)")
        self.labels_edit.setMinimumHeight(60)
        self.labels_edit.setMaximumHeight(100)
        vbox.addWidget(self.labels_edit)

        lbl2 = QLabel("条件表达式 (Match Rules):")
        vbox.addWidget(lbl2)
        
        # Rule Builder Stack (Visual vs Text)
        self.rule_stack = QStackedWidget()
        
        # 1. Visual Builder
        self.rule_builder = RuleBuilder()
        self.rule_stack.addWidget(self.rule_builder)
        
        # 2. Raw Text (Legacy/Advanced)
        self.exprs_edit = QPlainTextEdit()
        self.exprs_edit.setPlaceholderText("e.g. cookies.health > 80 (One per line, legacy)")
        self.exprs_edit.setMinimumHeight(150)
        self.rule_stack.addWidget(self.exprs_edit)
        
        vbox.addWidget(self.rule_stack)
        
        # Switcher
        rule_mode_layout = QHBoxLayout()
        self.rule_mode_btn = QPushButton("Switch to Raw Text")
        self.rule_mode_btn.setCheckable(True)
        self.rule_mode_btn.clicked.connect(self._toggle_rule_mode)
        rule_mode_layout.addStretch()
        rule_mode_layout.addWidget(self.rule_mode_btn)
        vbox.addLayout(rule_mode_layout)

        layout.addWidget(match_group)
        layout.addStretch()

    def _setup_scaling_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        scale_group = QGroupBox("弹性策略 (Scaling Policy)")
        form = self._create_form_layout(scale_group)
        
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItems([m.value for m in ScalingMode])
        form.addRow("伸缩模式:", self.scale_mode_combo)
        
        self.max_concurrency_spin = QSpinBox()
        self.max_concurrency_spin.setRange(1, 1000)
        form.addRow("最大并发:", self.max_concurrency_spin)
        
        self.min_idle_spin = QSpinBox()
        self.min_idle_spin.setRange(0, 100)
        form.addRow("预热空闲:", self.min_idle_spin)
        
        self.creation_timeout_spin = QSpinBox()
        self.creation_timeout_spin.setRange(0, 3600)
        self.creation_timeout_spin.setSuffix(" s")
        form.addRow("创建超时:", self.creation_timeout_spin)

        # 初始化工作流 (使用 Selector)
        self.init_workflow_selector = WorkflowSelector()
        form.addRow("初始化工作流:", self.init_workflow_selector)
        
        layout.addWidget(scale_group)
        layout.addStretch()

    def _setup_execution_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        exec_group = QGroupBox("执行目标 (Execution Context)")
        form = self._create_form_layout(exec_group)
        
        # 目标 (使用 Selector)
        self.exec_workflow_selector = WorkflowSelector()
        form.addRow("执行目标:", self.exec_workflow_selector)
        
        self.exec_timeout_spin = QSpinBox()
        self.exec_timeout_spin.setRange(0, 7200)
        self.exec_timeout_spin.setSuffix(" s")
        form.addRow("最大执行时长:", self.exec_timeout_spin)
        
        layout.addWidget(exec_group)
        layout.addStretch()

    def _setup_teardown_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        retry_group = QGroupBox("重试策略 (Retry Policy)")
        form = self._create_form_layout(retry_group)
        
        self.max_attempts_spin = QSpinBox()
        self.max_attempts_spin.setRange(1, 10)
        form.addRow("最大尝试次数:", self.max_attempts_spin)
        
        self.new_env_check = QCheckBox("重试时更换环境 (Switch Environment)")
        self.new_env_check.setStyleSheet("color: white;")
        form.addRow("", self.new_env_check)
        
        layout.addWidget(retry_group)
        
        teardown_group = QGroupBox("清理策略 (Teardown Policy)")
        form = self._create_form_layout(teardown_group)
        
        self.td_success_combo = QComboBox()
        self.td_success_combo.addItems([t.value for t in TeardownAction])
        form.addRow("任务成功时:", self.td_success_combo)
        
        self.td_failure_combo = QComboBox()
        self.td_failure_combo.addItems([t.value for t in TeardownAction])
        form.addRow("任务失败时:", self.td_failure_combo)
        
        self.td_timeout_combo = QComboBox()
        self.td_timeout_combo.addItems([t.value for t in TeardownAction])
        form.addRow("任务超时时:", self.td_timeout_combo)
        
        layout.addWidget(teardown_group)
        layout.addStretch()

    def _on_global_module_changed(self, module_name):
        # Filter other selectors
        mod_val = self.module_link_combo.currentData() # name or empty
        self.init_workflow_selector.set_module_filter(mod_val)
        self.exec_workflow_selector.set_module_filter(mod_val)

    def _create_yaml_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.yaml_editor = QPlainTextEdit()
        self.yaml_editor.setStyleSheet("font-family: monospace; background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.yaml_editor)
        return widget

    def _on_category_changed(self, index):
        # 简单逻辑: 0=Chrome, 1=Android, 2=Fingerprint, 3=Debug
        is_fingerprint = (index == 2)
        self.env_provider_label.setVisible(is_fingerprint)
        self.env_provider_combo.setVisible(is_fingerprint)

    def _switch_mode(self, mode):
        if mode == "form":
            self._yaml_to_form()
            self.stack.setCurrentIndex(0)
            self.form_btn.setChecked(True)
            self.yaml_btn.setChecked(False)
        else:
            self._form_to_yaml()
            self.stack.setCurrentIndex(1)
            self.form_btn.setChecked(False)
            self.yaml_btn.setChecked(True)

    def _toggle_rule_mode(self, checked):
        if checked:
            self.rule_mode_btn.setText("Switch to Visual Builder")
            self.rule_stack.setCurrentIndex(1)
        else:
            self.rule_mode_btn.setText("Switch to Raw Text")
            self.rule_stack.setCurrentIndex(0)

    def _load_strategy(self):
        s = self._strategy
        # ... (Previous code)
        
        # Resource Logic
        etype = s.selector.env_type
        if etype == EnvType.CHROME:
            self.env_category_combo.setCurrentIndex(0)
        elif etype == EnvType.ANDROID:
            self.env_category_combo.setCurrentIndex(1)
        elif etype in (EnvType.BIT_BROWSER, EnvType.VIRTUAL_BROWSER):
            self.env_category_combo.setCurrentIndex(2)
            if etype == EnvType.BIT_BROWSER:
                self.env_provider_combo.setCurrentIndex(0)
            else:
                self.env_provider_combo.setCurrentIndex(1)
        else: # Debug
            self.env_category_combo.setCurrentIndex(3)

        self.sort_combo.setCurrentText(s.selector.sort_strategy.value)
        self.wait_timeout_spin.setValue(s.selector.wait_timeout)
        
        labels_txt = "\n".join([f"{k}: {v}" for k, v in s.selector.match_labels.items()])
        self.labels_edit.setPlainText(labels_txt)
        
        # Load Match Rules (New AST)
        # We need to recreate rule builder with data
        # Since RuleBuilder currently only takes data in init, we might need a setter
        # For simplicity in this interaction, let's assume RuleBuilder recreates root widget internally or we rebuild it
        # Actually our RuleBuilder only supports init, let's replace it
        if s.selector.match_rules:
            self.rule_stack.removeWidget(self.rule_builder)
            self.rule_builder = RuleBuilder(s.selector.match_rules)
            self.rule_stack.insertWidget(0, self.rule_builder)
            self.rule_stack.setCurrentIndex(0)
            self.rule_mode_btn.setChecked(False)
        else:
            # Fallback to expressions
            self.exprs_edit.setPlainText("\n".join(s.selector.match_expressions))
            self.rule_stack.setCurrentIndex(1 if s.selector.match_expressions else 0)
            self.rule_mode_btn.setChecked(bool(s.selector.match_expressions))

        # Scaling
        self.scale_mode_combo.setCurrentText(s.scaling.mode.value)
        self.max_concurrency_spin.setValue(s.scaling.max_concurrency)
        self.min_idle_spin.setValue(s.scaling.min_idle)
        self.creation_timeout_spin.setValue(s.scaling.creation_timeout)
        
        # Scale Init Workflow (Parsing "module/workflow")
        init_wf = s.scaling.init_workflow or ""
        if "/" in init_wf:
            mod, wf = init_wf.split("/", 1)
            self.init_workflow_selector.set_value(mod, wf)
        
        # Execution
        if s.execution:
            self.exec_workflow_selector.set_value(s.execution.module, s.execution.workflow)
            self.exec_timeout_spin.setValue(s.execution.timeout)
            
            # Infer Global Module from existing execution if not set
            if s.execution.module:
                idx = self.module_link_combo.findData(s.execution.module)
                if idx >= 0:
                     self.module_link_combo.setCurrentIndex(idx)

            
        # Retry & Teardown
        self.max_attempts_spin.setValue(s.retry.max_attempts)
        self.new_env_check.setChecked(s.retry.new_env_on_retry)
        
        self.td_success_combo.setCurrentText(s.teardown.on_success.value)
        self.td_failure_combo.setCurrentText(s.teardown.on_failure.value)
        self.td_timeout_combo.setCurrentText(s.teardown.on_timeout.value)

    def _build_strategy_from_form(self) -> TaskStrategy:
        # Resource EnvType Logic
        cat_idx = self.env_category_combo.currentIndex()
        if cat_idx == 0:
            env_type = EnvType.CHROME
        elif cat_idx == 1:
            env_type = EnvType.ANDROID
        elif cat_idx == 2:
            prov_idx = self.env_provider_combo.currentIndex()
            env_type = EnvType.BIT_BROWSER if prov_idx == 0 else EnvType.VIRTUAL_BROWSER
        else:
            env_type = EnvType.DEBUG_DUMMY
            
        # Parse labels
        labels = {}
        for line in self.labels_edit.toPlainText().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                labels[k.strip()] = v.strip()
        
        # Parse Rules
        match_rules = None
        match_exprs = []
        
        if self.rule_stack.currentIndex() == 0:
            # Visual Builder
            match_rules = self.rule_builder.get_rule_group()
        else:
            # Raw Text
            match_exprs = [l.strip() for l in self.exprs_edit.toPlainText().splitlines() if l.strip()]
        
        selector = ResourceSelector(
            env_type=env_type,
            match_labels=labels,
            match_expressions=match_exprs,
            match_rules=match_rules,
            sort_strategy=SelectionStrategy(self.sort_combo.currentText()),
            wait_timeout=self.wait_timeout_spin.value(),
        )
        
        # Init workflow
        imod, iwf = self.init_workflow_selector.get_value()
        init_workflow_str = f"{imod}/{iwf}" if imod and iwf else None

        scaling = ScalingPolicy(
            mode=ScalingMode(self.scale_mode_combo.currentText()),
            max_concurrency=self.max_concurrency_spin.value(),
            min_idle=self.min_idle_spin.value(),
            creation_timeout=self.creation_timeout_spin.value(),
            init_workflow=init_workflow_str,
        )
        
        # Execution
        emod, ewf = self.exec_workflow_selector.get_value()
        execution = None
        if emod:
            execution = ExecutionContext(
                module=emod,
                workflow=ewf or "default",
                timeout=self.exec_timeout_spin.value(),
            )
            
        retry = RetryPolicy(
            max_attempts=self.max_attempts_spin.value(),
            new_env_on_retry=self.new_env_check.isChecked(),
        )
        
        teardown = TeardownPolicy(
            on_success=TeardownAction(self.td_success_combo.currentText()),
            on_failure=TeardownAction(self.td_failure_combo.currentText()),
            on_timeout=TeardownAction(self.td_timeout_combo.currentText()),
        )
        
        return TaskStrategy(
            id=self._strategy.id,
            name=self.name_edit.text().strip() or "Unnamed",
            description=self.desc_edit.text().strip(),
            selector=selector,
            scaling=scaling,
            execution=execution,
            retry=retry,
            teardown=teardown,
        )

    def _form_to_yaml(self):
        try:
            s = self._build_strategy_from_form()
            self.yaml_editor.setPlainText(s.to_yaml())
        except Exception as e:
            self.yaml_editor.setPlainText(f"# Error building YAML: {e}")

    def _yaml_to_form(self):
        try:
            yaml_str = self.yaml_editor.toPlainText()
            if not yaml_str.strip(): return
            self._strategy = TaskStrategy.from_yaml(yaml_str)
            self._load_strategy()
        except Exception:
            pass

    def _on_save(self):
        if self.stack.currentIndex() == 1:
            self._yaml_to_form()
        else:
            self._strategy = self._build_strategy_from_form()
        self.accept()

    def get_strategy(self) -> TaskStrategy:
        return self._strategy
