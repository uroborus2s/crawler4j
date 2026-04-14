"""运行模板编辑弹窗。"""

import yaml

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import get_module_registry
from src.core.atm.run_profile import (
    AcquisitionMode,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    MatchConfig,
    RunProfile,
    ResourceConfig,
    RetryPolicy,
    SelectionStrategy,
    TeardownAction,
    TeardownPolicy,
)
from src.core.atm.ui.rule_builder import RuleBuilder
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class WorkflowSelector(QWidget):
    """工作流选择组合控件 (Module + Workflow)。"""

    def __init__(self, parent=None, show_module=True, show_none_option=False):
        super().__init__(parent)
        self._show_module = show_module
        self._show_none_option = show_none_option
        self._setup_ui()
        if show_module:
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
        # Match "Scaling Mode" combo box behavior (Preferred instead of Expanding)
        self.workflow_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.workflow_combo)
        
        if not self._show_module:
            self.module_combo.hide()
            self.spacer.hide()

    def set_module_filter(self, module_name: str | None):
        """设置模块过滤器。"""
        # Capture current selection to restore if possible
        current_wf = self.workflow_combo.currentText()
        
        self._filter_module = module_name
        
        if self._show_module:
            has_filter = bool(module_name)
            self.module_combo.setVisible(not has_filter)
            self.spacer.setVisible(not has_filter)
            
            if module_name:
                # Force module selection
                index = self.module_combo.findText(module_name)
                if index >= 0:
                    self.module_combo.setCurrentIndex(index)
                self._on_module_changed(module_name)
            else:
                if self.module_combo.count() > 0:
                    self.module_combo.setCurrentIndex(0)
        else:
            # Pure workflow mode: just load workflows for this module
             self._on_module_changed(module_name)

        # Attempt to restore selection
        if current_wf:
            idx = self.workflow_combo.findText(current_wf)
            if idx >= 0:
                self.workflow_combo.setCurrentIndex(idx)
            # Else: workflow not valid for new module, let it be cleared

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
        
        if self._show_none_option:
            self.workflow_combo.addItem("不执行 (None)", "")

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
        # If in hidden mode, maybe module combo isn't updated if set_module_filter passed a name but combo wasn't populated?
        # Actually in hidden mode we don't populate module_combo usually? 
        # Wait, set_module_filter in hidden mode just calls _on_module_changed.
        # But get_value reads module_combo.currentText().
        # We need to store the current module in a variable if hidden.
        
        wf = self.workflow_combo.currentText()
        # Handle "不执行 (None)" which has empty data if we used addItem(text, userData)
        # But wait, addItem("不执行", "") sets user data to "".
        # currentText() returns the visible text "不执行".
        # We should use currentData() if available, or check text.
        
        # Actually in _on_module_changed:
        # self.workflow_combo.addItem("不执行 (None)", "") 
        # self.workflow_combo.addItem(wf.name) <- this implies no user data was set for workflows, only text.
        # So for normal workflows, data is None. For None option, data is "".
        
        # Let's standardize:
        # For workflows, let's use text value. for None, data is "" or we check text prefix.
        
        current_data = self.workflow_combo.currentData()
        if current_data == "":
             wf = ""
        
        if not self._show_module:
            return getattr(self, "_filter_module", "") or "", wf
            
        return self.module_combo.currentText(), wf

    def set_value(self, module: str, workflow: str):
        if self._show_module:
            index = self.module_combo.findText(module)
            if index >= 0:
                self.module_combo.setCurrentIndex(index)
        else:
            # In hidden mode, we assume external filter sets the module context
            pass
            # Or should we allow set_value to override filter? 
            # User workflow: Select Global Module -> Init Workflow updates list.
            # _load_run_profile: Sets Global Module -> Filter updates -> Then sets Init Workflow value.
            # So we just need to set workflow.
            pass
            
        # Common: find workflow
        # Need to ensure items are loaded first? 
        # _on_module_changed loads items.
        # So we just find workflow text.
        wf_index = self.workflow_combo.findText(workflow)
        if wf_index >= 0:
            self.workflow_combo.setCurrentIndex(wf_index)
        else:
            # Maybe not loaded yet or custom?
            if workflow:
                 self.workflow_combo.addItem(workflow)
                 self.workflow_combo.setCurrentText(workflow)


# 排序策略显示映射 (CN)
SELECTION_STRATEGY_MAP = {
    SelectionStrategy.RANDOM: "随机选择 (Random)",
    SelectionStrategy.FIFO: "最早空闲 (FIFO)",
    SelectionStrategy.LIFO: "最近使用 (LIFO)",
    SelectionStrategy.BEST_FIT: "最佳匹配 (Best Fit)",
}

# 清理动作显示映射 (CN)
TEARDOWN_ACTION_MAP = {
    TeardownAction.DESTROY: "销毁 (Destroy)",
    TeardownAction.RECYCLE: "回收复用 (Recycle)",
    TeardownAction.HIBERNATE: "休眠 (Hibernate)",
    TeardownAction.KEEP_ALIVE: "保持运行 (Keep Alive)",
}


class RunProfileDialog(QDialog):
    """运行模板编辑弹窗。"""

    def __init__(self, run_profile: RunProfile | None = None, parent=None, read_only: bool = False):
        super().__init__(parent)
        self._run_profile = run_profile or RunProfile(resource=ResourceConfig())
        self._is_new = run_profile is None
        self._read_only = read_only
        self._setup_ui()
        self._load_run_profile()
        
        if self._read_only:
             self._set_read_only()

    def _setup_ui(self):
        self.setWindowTitle("配置运行模板")
        
        # Responsive sizing (50% width, 90% height of screen)
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            w = int(screen_geo.width() * 0.5)
            h = int(screen_geo.height() * 0.95)
        else:
            # Fallback for headless or special cases
            w, h = 800, 700
            
        self.resize(w, h)
        
        self.setStyleSheet("""
            QDialog { background: rgb(30, 30, 40); }
            QLabel { color: rgba(255, 255, 255, 0.9); font-size: 13px; }
            QLineEdit, QSpinBox, QPlainTextEdit {
                background: rgba(40, 40, 50, 0.9);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                padding: 5px 8px;
                min-height: 25px;
                min-width: 280px;
            }
            QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
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
            
            /* StyledComboBox handles its own styling, removed duplicated QComboBox CSS here */
            /* StyledSpinBox handles its own styling, removed duplicated QSpinBox CSS here */
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
        
        save_btn = QPushButton("保存运行模板")
        save_btn.setFixedSize(100, 32)
        save_btn.setStyleSheet("background: #10b981; border:none; color:white; font-weight:bold; border-radius:4px;")
        save_btn.clicked.connect(self._on_save)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        if self._read_only:
             save_btn.hide()
             cancel_btn.setText("关闭")

        layout.addLayout(btn_layout)

    def _set_read_only(self):
        """设置只读模式。"""
        # Disable all input widgets
        for widget in self.findChildren((QLineEdit, QPlainTextEdit, QSpinBox, QCheckBox, QComboBox)):
             # QComboBox and QCheckBox use setEnabled
             if isinstance(widget, (QComboBox, QCheckBox)):
                 widget.setEnabled(False)
             elif isinstance(widget, (QLineEdit, QPlainTextEdit, QSpinBox)):
                 widget.setReadOnly(True)
        
        # Helper to disable WorkflowSelectors
        # We need to explicitly call setEnabled on them because they are complex widgets
        # Or better, let's implement set_read_only on WorkflowSelector if they are custom
        # But for now, let's just find them by type if we can, or manually access them.
        # findChildren might not find them if they are wrapped.
        
        self.exec_workflow_selector.setEnabled(False)
        self.td_success_wf.setEnabled(False)
        self.td_failure_wf.setEnabled(False)
        self.td_timeout_wf.setEnabled(False)
        
        # Rule builder?
        # self.rule_mode_btn.setEnabled(False)
        pass

    def _setup_form_tabs(self):
        self.tab_basic = QWidget()
        self._setup_basic_tab(self.tab_basic)
        self.form_tabs.addTab(self.tab_basic, "基础与资源")

        self.tab_acquisition = QWidget()
        self._setup_acquisition_tab(self.tab_acquisition)
        self.form_tabs.addTab(self.tab_acquisition, "获取与创建")

        self.tab_exec = QWidget()
        self._setup_execution_tab(self.tab_exec)
        self.form_tabs.addTab(self.tab_exec, "执行配置")
        
        self.tab_retry = QWidget()
        self._setup_retry_tab(self.tab_retry)
        self.form_tabs.addTab(self.tab_retry, "重试策略")

        self.tab_teardown = QWidget()
        self._setup_teardown_tab(self.tab_teardown)
        self.form_tabs.addTab(self.tab_teardown, "清理策略")

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
        # Master Layout for Tab (contains ScrollArea)
        main_layout = QVBoxLayout(parent)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        # Scrollable Content Widget
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        
        # Original Layout (applied to content_widget)
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        basic_group = QGroupBox("基础信息")
        form = self._create_form_layout(basic_group)
        
        # 全局模块选择
        self.module_link_combo = QComboBox()
        self.module_link_combo.setPlaceholderText("选择关联模块 (可选)")
        self.module_link_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed) # Match other inputs
        # Load modules
        try:
            registry = get_module_registry()
            self.module_link_combo.addItem("通用运行模板 (无特定模块)", "")
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
        for s in SelectionStrategy:
            self.sort_combo.addItem(SELECTION_STRATEGY_MAP.get(s, s.value), s)
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
        self.rule_stack.setCurrentWidget(self.rule_builder)
        
        # 2. Raw Text (Legacy/Advanced)
        self.exprs_edit = QPlainTextEdit()
        self.exprs_edit.setPlaceholderText("e.g. cookies.health > 80 (one expression per line)")
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
        
        # Finalize Scroll Area
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _setup_acquisition_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        acq_group = QGroupBox("资源获取策略")
        form = self._create_form_layout(acq_group)

        self.acquisition_mode_combo = QComboBox()
        self.acquisition_mode_combo.addItem("仅查找复用 (match)", AcquisitionMode.MATCH)
        self.acquisition_mode_combo.addItem("仅创建新环境 (create)", AcquisitionMode.CREATE)
        form.addRow("获取模式:", self.acquisition_mode_combo)

        self.creation_lifecycle_combo = QComboBox()
        self.creation_lifecycle_combo.addItem("任务完成即销毁 (ephemeral)", CreationLifecycle.EPHEMERAL)
        self.creation_lifecycle_combo.addItem("保留复用 (persistent)", CreationLifecycle.PERSISTENT)
        form.addRow("创建生命周期:", self.creation_lifecycle_combo)

        self.creation_params_edit = QPlainTextEdit()
        self.creation_params_edit.setPlaceholderText("YAML/JSON，例如:\nproxy:\n  protocol: SOCKS5\nfingerprint:\n  randomize_all: true")
        self.creation_params_edit.setMinimumHeight(220)
        form.addRow("创建参数:", self.creation_params_edit)

        layout.addWidget(acq_group)
        layout.addStretch()

    def _setup_execution_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        exec_group = QGroupBox("执行目标 (Execution Context)")
        form = self._create_form_layout(exec_group)
        
        # 目标 (使用 Selector, keep module selection hidden)
        self.exec_workflow_selector = WorkflowSelector(show_module=False)
        self.exec_workflow_selector.workflow_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        form.addRow("执行目标:", self.exec_workflow_selector)
        
        self.exec_timeout_spin = QSpinBox()
        self.exec_timeout_spin.setRange(0, 7200)
        self.exec_timeout_spin.setSuffix(" s")
        form.addRow("最大执行时长:", self.exec_timeout_spin)

        self.hooks_module_edit = QLineEdit()
        self.hooks_module_edit.setPlaceholderText("留空则复用执行模块，例如 demo_module 或 demo_module.tasks.sample_task")
        form.addRow("Hooks 模块:", self.hooks_module_edit)
        
        layout.addWidget(exec_group)
        layout.addStretch()

    def _setup_retry_tab(self, parent):
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
        layout.addStretch()

    def _setup_teardown_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        teardown_group = QGroupBox("清理策略 (Teardown Policy)")
        # Use GridLayout or Nested VBox for better control
        # Structure:
        # Label
        # [Action Combo] [Workflow Selector]
        
        form_layout = QVBoxLayout(teardown_group)
        form_layout.setSpacing(12)
        
        # Helper to create a row
        def create_row(label_text, combo, workflow_selector):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            lbl = QLabel(label_text)
            lbl.setFixedWidth(80) # Fixed width for label alignment
            row_layout.addWidget(lbl)
            
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_layout.addWidget(combo, 1) # Action takes available space
            
            # Workflow selector needs to be compact or integrated. 
            # WorkflowSelector is a Widget with a layout. 
            # We need to make sure it fits nicely.
            workflow_selector.workflow_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row_layout.addWidget(workflow_selector, 2) # Workflow takes more space
            
            form_layout.addWidget(row_widget)

        # Success
        self.td_success_combo = QComboBox()
        for t in TeardownAction:
            self.td_success_combo.addItem(TEARDOWN_ACTION_MAP.get(t, t.value), t)
        
        self.td_success_wf = WorkflowSelector(show_module=False, show_none_option=True)
        self.td_success_wf.workflow_combo.setPlaceholderText("执行工作流 (可选)")
        create_row("任务成功时:", self.td_success_combo, self.td_success_wf)
        
        # Failure
        self.td_failure_combo = QComboBox()
        for t in TeardownAction:
            self.td_failure_combo.addItem(TEARDOWN_ACTION_MAP.get(t, t.value), t)
            
        self.td_failure_wf = WorkflowSelector(show_module=False, show_none_option=True)
        self.td_failure_wf.workflow_combo.setPlaceholderText("执行工作流 (可选)")
        create_row("任务失败时:", self.td_failure_combo, self.td_failure_wf)

        # Timeout
        self.td_timeout_combo = QComboBox()
        for t in TeardownAction:
            self.td_timeout_combo.addItem(TEARDOWN_ACTION_MAP.get(t, t.value), t)
            
        self.td_timeout_wf = WorkflowSelector(show_module=False, show_none_option=True)
        self.td_timeout_wf.workflow_combo.setPlaceholderText("执行工作流 (可选)")
        create_row("任务超时时:", self.td_timeout_combo, self.td_timeout_wf)
        
        layout.addWidget(teardown_group)
        layout.addStretch()

    def _on_global_module_changed(self, module_name):
        # Filter other selectors
        mod_val = self.module_link_combo.currentData() # name or empty
        self.exec_workflow_selector.set_module_filter(mod_val)
        # Filter teardown selectors
        self.td_success_wf.set_module_filter(mod_val)
        self.td_failure_wf.set_module_filter(mod_val)
        self.td_timeout_wf.set_module_filter(mod_val)

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

    def _load_run_profile(self):
        s = self._run_profile
        
        # Resource Logic
        etype = s.resource.acquisition.selector.env_type
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

        # Set sort strategy by data
        idx = self.sort_combo.findData(s.resource.acquisition.selector.sort_strategy)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        else:
            idx_text = self.sort_combo.findText(s.resource.acquisition.selector.sort_strategy.value)
            self.sort_combo.setCurrentIndex(idx_text if idx_text >= 0 else 0)

        self.wait_timeout_spin.setValue(s.resource.acquisition.selector.wait_timeout)
        
        labels_txt = "\n".join([f"{k}: {v}" for k, v in s.resource.acquisition.selector.tags.items()])
        self.labels_edit.setPlainText(labels_txt)
        
        # Load Match Rules (New AST)
        # We need to recreate rule builder with data
        # Since RuleBuilder currently only takes data in init, we might need a setter
        # For simplicity in this interaction, let's assume RuleBuilder recreates root widget internally or we rebuild it
        # Actually our RuleBuilder only supports init, let's replace it
        if s.resource.acquisition.selector.match_rules:
            self.rule_stack.removeWidget(self.rule_builder)
            self.rule_builder = RuleBuilder(s.resource.acquisition.selector.match_rules)
            self.rule_stack.insertWidget(0, self.rule_builder)
            self.rule_stack.setCurrentIndex(0)
            self.rule_mode_btn.setChecked(False)
        else:
            self.exprs_edit.setPlainText("\n".join(s.resource.acquisition.selector.match_expressions))
            self.rule_stack.setCurrentIndex(1 if s.resource.acquisition.selector.match_expressions else 0)
            self.rule_mode_btn.setChecked(bool(s.resource.acquisition.selector.match_expressions))

        idx = self.acquisition_mode_combo.findData(s.resource.acquisition.mode)
        if idx >= 0:
            self.acquisition_mode_combo.setCurrentIndex(idx)

        idx = self.creation_lifecycle_combo.findData(s.resource.acquisition.creation.lifecycle)
        if idx >= 0:
            self.creation_lifecycle_combo.setCurrentIndex(idx)

        creation_params = s.resource.acquisition.creation.params
        if creation_params:
            self.creation_params_edit.setPlainText(
                yaml.safe_dump(creation_params, allow_unicode=True, sort_keys=False).strip()
            )
        else:
            self.creation_params_edit.clear()
        
        # Execution
        # 1. Infer Global Module FIRST (to prepopulate selectors)
        if s.execution and s.execution.module:
            idx = self.module_link_combo.findData(s.execution.module)
            if idx >= 0:
                    self.module_link_combo.setCurrentIndex(idx)
            else:
                # Manually set filter if not in global list (e.g. hidden module)
                self.exec_workflow_selector.set_module_filter(s.execution.module)

        # 2. Then set values
        if s.execution:
            self.exec_workflow_selector.set_value(s.execution.module, s.execution.workflow)
            self.exec_timeout_spin.setValue(s.execution.timeout)
            self.hooks_module_edit.setText(s.execution.hooks_module or "")
 
            
        # Retry & Teardown
        self.max_attempts_spin.setValue(s.retry.max_attempts)
        self.new_env_check.setChecked(s.retry.new_env_on_retry)
        
        # Teardown Actions & Workflows
        for combo, val in [
            (self.td_success_combo, s.teardown.on_success),
            (self.td_failure_combo, s.teardown.on_failure),
            (self.td_timeout_combo, s.teardown.on_timeout)
        ]:
            idx = combo.findData(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                 combo.setCurrentText(val.value)
                 
        # Helper to load workflow string "mod/wf"
        def load_wf(selector, value):
            if value and "/" in value:
                m, w = value.split("/", 1)
                selector.set_value(m, w)
        
        load_wf(self.td_success_wf, s.teardown.success_workflow)
        load_wf(self.td_failure_wf, s.teardown.failure_workflow)
        load_wf(self.td_timeout_wf, s.teardown.timeout_workflow)


    def _build_run_profile_from_form(self) -> RunProfile:
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
            match_exprs = [line.strip() for line in self.exprs_edit.toPlainText().splitlines() if line.strip()]
        
        # Get sort strategy from data (Enum)
        sort_strategy = self.sort_combo.currentData()
        if not sort_strategy:
             # Fallback if somehow missing
             sort_strategy = SelectionStrategy.FIFO

        creation_params = {}
        raw_creation_params = self.creation_params_edit.toPlainText().strip()
        if raw_creation_params:
            parsed = yaml.safe_load(raw_creation_params)
            if parsed is None:
                parsed = {}
            if not isinstance(parsed, dict):
                raise ValueError("创建参数必须是对象结构（YAML/JSON map）")
            creation_params = parsed

        resource = ResourceConfig(
            provider=("bitbrowser" if env_type == EnvType.BIT_BROWSER else "virtualbrowser" if env_type == EnvType.VIRTUAL_BROWSER else "playwright_local"),
            acquisition={
                "mode": self.acquisition_mode_combo.currentData(),
                "selector": MatchConfig(
                    env_type=env_type,
                    tags=labels,
                    match_expressions=match_exprs,
                    match_rules=match_rules,
                    sort_strategy=sort_strategy,
                    wait_timeout=self.wait_timeout_spin.value(),
                ),
                "creation": {
                    "lifecycle": self.creation_lifecycle_combo.currentData(),
                    "params": creation_params,
                },
            },
        )
        
        # Execution
        emod, ewf = self.exec_workflow_selector.get_value()
        execution = None
        if emod:
            execution = ExecutionContext(
                module=emod,
                workflow=ewf or "default",
                hooks_module=self.hooks_module_edit.text().strip(),
                timeout=self.exec_timeout_spin.value(),
            )
            
        retry = RetryPolicy(
            max_attempts=self.max_attempts_spin.value(),
            new_env_on_retry=self.new_env_check.isChecked(),
        )
        
        # Helper get workflow str
        def get_wf_str(selector):
            m, w = selector.get_value()
            return f"{m}/{w}" if m and w else None

        teardown = TeardownPolicy(
            on_success=self.td_success_combo.currentData() or TeardownAction.DESTROY,
            success_workflow=get_wf_str(self.td_success_wf),
            
            on_failure=self.td_failure_combo.currentData() or TeardownAction.DESTROY,
            failure_workflow=get_wf_str(self.td_failure_wf),
            
            on_timeout=self.td_timeout_combo.currentData() or TeardownAction.DESTROY,
            timeout_workflow=get_wf_str(self.td_timeout_wf),
        )
        
        return RunProfile(
            resource=resource,
            execution=execution,
            retry=retry,
            teardown=teardown,
        )

    def _form_to_yaml(self):
        try:
            s = self._build_run_profile_from_form()
            self.yaml_editor.setPlainText(s.to_yaml())
        except Exception as e:
            self.yaml_editor.setPlainText(f"# Error building YAML: {e}")

    def _yaml_to_form(self):
        try:
            yaml_str = self.yaml_editor.toPlainText()
            if not yaml_str.strip():
                return
            self._run_profile = RunProfile.from_yaml(yaml_str)
            self._load_run_profile()
        except Exception:
            pass

    def _on_save(self):
        if self.stack.currentIndex() == 1:
            self._yaml_to_form()
        else:
            self._run_profile = self._build_run_profile_from_form()
            
        self.accept()

    def get_run_profile(self) -> RunProfile:
        return self._run_profile
