"""Hooks编辑器对话框。

提供环境生命周期Hooks的可视化编辑。
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.plugins import (
    EnvironmentHook,
    EnvironmentHooksRepository,
    HandlerType,
    HookType,
)
from src.plugins.hooks import PREDEFINED_ACTIONS
from src.ui.widgets.toast import Toast


class HooksEditorDialog(QDialog):
    """Hooks编辑器对话框。
    
    功能：
    1. 查看环境的hooks列表
    2. 添加/编辑/删除hooks
    3. 支持预定义动作和自定义代码
    """

    def __init__(self, parent=None, environment_id: int | None = None):
        super().__init__(parent)
        self.environment_id = environment_id
        self._repo = EnvironmentHooksRepository()
        self._setup_ui()
        self._load_hooks()

    def _setup_ui(self):
        """设置对话框UI。"""
        title = "全局Hooks编辑" if self.environment_id is None else f"环境 ENV-{self.environment_id} Hooks编辑"
        self.setWindowTitle(title)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)

        layout = QVBoxLayout(self)

        # 说明
        info = QLabel("💡 Hooks在环境生命周期的关键点执行，可用于日志记录、事件通知等。")
        info.setWordWrap(True)
        info.setStyleSheet("color: #a6adc8; margin-bottom: 10px;")
        layout.addWidget(info)

        # Hooks列表
        list_group = QGroupBox("已配置的Hooks")
        list_layout = QVBoxLayout(list_group)

        self.hooks_list = QListWidget()
        self.hooks_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hooks_list.customContextMenuRequested.connect(self._show_context_menu)
        self.hooks_list.itemDoubleClicked.connect(self._on_edit_hook)
        list_layout.addWidget(self.hooks_list)

        # 工具栏
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加Hook")
        self.add_btn.clicked.connect(self._on_add_hook)
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        list_layout.addLayout(toolbar)

        layout.addWidget(list_group)

        # 预定义动作说明
        actions_group = QGroupBox("可用的预定义动作")
        actions_layout = QVBoxLayout(actions_group)
        
        actions_text = "\n".join([
            f"• {name}: {func.__doc__ or '无描述'}" 
            for name, func in PREDEFINED_ACTIONS.items()
        ])
        actions_label = QLabel(actions_text)
        actions_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        actions_label.setWordWrap(True)
        actions_layout.addWidget(actions_label)
        
        layout.addWidget(actions_group)

        # 关闭按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_hooks(self):
        """加载Hooks列表。"""
        self.hooks_list.clear()
        hooks = self._repo.get_by_environment(self.environment_id)

        for h in hooks:
            hook = EnvironmentHook.from_dict(h)
            status = "✅" if hook.enabled else "⏸️"
            type_icon = "🔧" if hook.handler_type == HandlerType.PREDEFINED else "📝"
            
            text = f"{status} {type_icon} [{hook.hook_type.value}] {hook.handler_code[:30]}..."
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, hook)
            self.hooks_list.addItem(item)

    def _show_context_menu(self, pos):
        """显示右键菜单。"""
        item = self.hooks_list.itemAt(pos)
        if not item:
            return

        hook: EnvironmentHook = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        edit_action = menu.addAction("✏️ 编辑")
        edit_action.triggered.connect(lambda: self._on_edit_hook(item))

        toggle_action = menu.addAction("⏸️ 禁用" if hook.enabled else "▶️ 启用")
        toggle_action.triggered.connect(lambda: self._toggle_hook(hook))

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ 删除")
        delete_action.triggered.connect(lambda: self._delete_hook(hook))

        menu.exec(self.hooks_list.mapToGlobal(pos))

    def _on_add_hook(self):
        """添加新Hook。"""
        dialog = HookEditDialog(self, environment_id=self.environment_id)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_hook_data()
            self._repo.create(
                hook_type=data["hook_type"],
                handler_code=data["handler_code"],
                environment_id=self.environment_id,
                handler_type=data["handler_type"],
                priority=data["priority"],
            )
            Toast.success(self, "Hook已添加")
            self._load_hooks()

    def _on_edit_hook(self, item: QListWidgetItem):
        """编辑Hook。"""
        hook: EnvironmentHook = item.data(Qt.ItemDataRole.UserRole)
        dialog = HookEditDialog(self, hook=hook)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_hook_data()
            self._repo.update(hook.id, {
                "hook_type": data["hook_type"],
                "handler_type": data["handler_type"],
                "handler_code": data["handler_code"],
                "priority": data["priority"],
            })
            Toast.success(self, "Hook已更新")
            self._load_hooks()

    def _toggle_hook(self, hook: EnvironmentHook):
        """切换Hook启用状态。"""
        self._repo.update(hook.id, {"enabled": 0 if hook.enabled else 1})
        self._load_hooks()

    def _delete_hook(self, hook: EnvironmentHook):
        """删除Hook。"""
        from src.ui.widgets.confirm_dialog import ConfirmDialog
        if ConfirmDialog.confirm(self, "删除Hook", "确定要删除这个Hook吗？"):
            self._repo.delete(hook.id)
            Toast.success(self, "Hook已删除")
            self._load_hooks()


class HookEditDialog(QDialog):
    """单个Hook编辑对话框。"""

    def __init__(
        self, 
        parent=None, 
        hook: EnvironmentHook | None = None,
        environment_id: int | None = None,
    ):
        super().__init__(parent)
        self.hook = hook
        self.environment_id = environment_id
        self._setup_ui()

    def _setup_ui(self):
        """设置对话框UI。"""
        self.setWindowTitle("编辑Hook" if self.hook else "添加Hook")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Hook类型
        self.type_combo = QComboBox()
        for ht in HookType:
            self.type_combo.addItem(ht.value, ht)
        if self.hook:
            index = self.type_combo.findData(self.hook.hook_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
        form.addRow("触发时机:", self.type_combo)

        # 处理器类型
        self.handler_type_combo = QComboBox()
        self.handler_type_combo.addItem("预定义动作", HandlerType.PREDEFINED)
        self.handler_type_combo.addItem("自定义代码", HandlerType.CUSTOM)
        self.handler_type_combo.currentIndexChanged.connect(self._on_handler_type_changed)
        if self.hook:
            index = self.handler_type_combo.findData(self.hook.handler_type)
            if index >= 0:
                self.handler_type_combo.setCurrentIndex(index)
        form.addRow("处理器类型:", self.handler_type_combo)

        # 预定义动作选择
        self.action_combo = QComboBox()
        for name in PREDEFINED_ACTIONS.keys():
            self.action_combo.addItem(name)
        form.addRow("预定义动作:", self.action_combo)

        # 自定义代码
        self.code_editor = QTextEdit()
        self.code_editor.setPlaceholderText("# Python代码\nlogger.info('Hello')")
        self.code_editor.setMaximumHeight(150)
        if self.hook and self.hook.handler_type == HandlerType.CUSTOM:
            self.code_editor.setText(self.hook.handler_code)
        form.addRow("自定义代码:", self.code_editor)

        # 优先级
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(0, 100)
        self.priority_spin.setValue(self.hook.priority if self.hook else 0)
        form.addRow("优先级:", self.priority_spin)

        layout.addLayout(form)

        # 初始化显示状态
        self._on_handler_type_changed()
        
        # 如果是编辑模式且是预定义动作
        if self.hook and self.hook.handler_type == HandlerType.PREDEFINED:
            index = self.action_combo.findText(self.hook.handler_code)
            if index >= 0:
                self.action_combo.setCurrentIndex(index)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_handler_type_changed(self):
        """切换处理器类型时更新UI。"""
        is_predefined = self.handler_type_combo.currentData() == HandlerType.PREDEFINED
        self.action_combo.setVisible(is_predefined)
        self.code_editor.setVisible(not is_predefined)

    def get_hook_data(self) -> dict:
        """获取Hook数据。"""
        handler_type = self.handler_type_combo.currentData()
        if handler_type == HandlerType.PREDEFINED:
            handler_code = self.action_combo.currentText()
        else:
            handler_code = self.code_editor.toPlainText()

        return {
            "hook_type": self.type_combo.currentData().value,
            "handler_type": handler_type.value,
            "handler_code": handler_code,
            "priority": self.priority_spin.value(),
        }
