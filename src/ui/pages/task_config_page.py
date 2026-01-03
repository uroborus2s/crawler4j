"""任务配置页面。

提供任务模板和任务配置的可视化管理。
"""

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.plugins import (
    TaskConfig,
    TaskConfigRepository,
    TaskTemplate,
    TaskTemplateRepository,
)
from src.plugins.script_manager import get_script_manager
from src.ui.widgets.toast import Toast


class TaskConfigPage(QWidget):
    """任务配置管理页面。

    功能：
    1. 左侧：任务模板列表
    2. 右侧：任务配置列表和编辑
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template_repo = TaskTemplateRepository()
        self._config_repo = TaskConfigRepository()
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """设置页面UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        header = QHBoxLayout()
        title = QLabel("📋 任务配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # 脚本目录管理按钮
        add_dir_btn = QPushButton("📁 添加脚本目录")
        add_dir_btn.clicked.connect(self._on_add_script_dir)
        header.addWidget(add_dir_btn)
        
        # 重载按钮
        reload_btn = QPushButton("🔄 重载脚本")
        reload_btn.clicked.connect(self._on_reload_scripts)
        header.addWidget(reload_btn)
        
        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # 主内容区域（分割器）
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ===== 左侧：任务模板 =====
        left_panel = QGroupBox("任务模板")
        left_layout = QVBoxLayout(left_panel)

        self.template_list = QListWidget()
        self.template_list.setMinimumWidth(250)
        self.template_list.currentItemChanged.connect(self._on_template_selected)
        left_layout.addWidget(self.template_list)

        splitter.addWidget(left_panel)

        # ===== 右侧：任务配置 =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 配置列表
        config_group = QGroupBox("任务配置")
        config_layout = QVBoxLayout(config_group)

        # 工具栏
        toolbar = QHBoxLayout()
        self.new_config_btn = QPushButton("+ 新建配置")
        self.new_config_btn.clicked.connect(self._on_new_config)
        self.new_config_btn.setEnabled(False)
        toolbar.addWidget(self.new_config_btn)
        toolbar.addStretch()
        config_layout.addLayout(toolbar)

        self.config_list = QListWidget()
        self.config_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.config_list.customContextMenuRequested.connect(self._show_config_menu)
        self.config_list.itemDoubleClicked.connect(self._on_edit_config)
        config_layout.addWidget(self.config_list)

        right_layout.addWidget(config_group)

        # 模板详情
        detail_group = QGroupBox("模板详情")
        detail_layout = QFormLayout(detail_group)

        self.detail_name = QLabel("-")
        self.detail_type = QLabel("-")
        self.detail_desc = QLabel("-")
        self.detail_desc.setWordWrap(True)

        detail_layout.addRow("名称:", self.detail_name)
        detail_layout.addRow("插件类型:", self.detail_type)
        detail_layout.addRow("描述:", self.detail_desc)

        right_layout.addWidget(detail_group)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])

        layout.addWidget(splitter, 1)

    def _load_data(self):
        """加载数据。"""
        # 加载模板
        self.template_list.clear()
        templates = self._template_repo.get_enabled()
        
        for t in templates:
            template = TaskTemplate.from_dict(t)
            item = QListWidgetItem(f"{'🔒' if template.is_system else '📄'} {template.display_name}")
            item.setData(Qt.ItemDataRole.UserRole, template)
            self.template_list.addItem(item)

        # 加载配置
        self._load_configs()

    def _load_configs(self, template_id: int | None = None):
        """加载任务配置。"""
        self.config_list.clear()
        configs = self._config_repo.get_enabled()
        
        for c in configs:
            if template_id and c.get("template_id") != template_id:
                continue
            config = TaskConfig.from_dict(c)
            status = "✅" if config.enabled else "⏸️"
            item = QListWidgetItem(f"{status} {config.name}")
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.config_list.addItem(item)

    def _on_template_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """模板选择变化。"""
        if not current:
            self.new_config_btn.setEnabled(False)
            self.detail_name.setText("-")
            self.detail_type.setText("-")
            self.detail_desc.setText("-")
            return

        template: TaskTemplate = current.data(Qt.ItemDataRole.UserRole)
        self.new_config_btn.setEnabled(True)
        
        self.detail_name.setText(template.display_name)
        self.detail_type.setText(template.plugin_type)
        self.detail_desc.setText(template.description or "无描述")

        # 过滤配置列表
        self._load_configs(template.id)

    def _show_config_menu(self, pos):
        """显示配置右键菜单。"""
        item = self.config_list.itemAt(pos)
        if not item:
            return

        config: TaskConfig = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        edit_action = menu.addAction("✏️ 编辑")
        edit_action.triggered.connect(lambda: self._on_edit_config(item))
        
        toggle_action = menu.addAction("⏸️ 禁用" if config.enabled else "▶️ 启用")
        toggle_action.triggered.connect(lambda: self._toggle_config(config))
        
        menu.addSeparator()
        
        delete_action = menu.addAction("🗑️ 删除")
        delete_action.triggered.connect(lambda: self._delete_config(config))

        menu.exec(self.config_list.mapToGlobal(pos))

    def _on_new_config(self):
        """新建配置。"""
        current = self.template_list.currentItem()
        if not current:
            Toast.error(self, "请先选择一个模板")
            return

        template: TaskTemplate = current.data(Qt.ItemDataRole.UserRole)
        dialog = TaskConfigDialog(self, template=template)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config_data = dialog.get_config()
            self._config_repo.create(
                name=config_data["name"],
                template_id=template.id,
                config=config_data["config"],
            )
            Toast.success(self, "配置已创建")
            self._load_configs(template.id)

    def _on_edit_config(self, item: QListWidgetItem):
        """编辑配置。"""
        config: TaskConfig = item.data(Qt.ItemDataRole.UserRole)
        dialog = TaskConfigDialog(self, config=config)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config_data = dialog.get_config()
            self._config_repo.update(config.id, {
                "name": config_data["name"],
                "config": config_data["config"],
            })
            Toast.success(self, "配置已更新")
            self._load_data()

    def _toggle_config(self, config: TaskConfig):
        """切换配置启用状态。"""
        self._config_repo.update(config.id, {"enabled": 0 if config.enabled else 1})
        self._load_data()

    def _delete_config(self, config: TaskConfig):
        """删除配置。"""
        from src.ui.widgets.confirm_dialog import ConfirmDialog
        if ConfirmDialog.confirm(self, "删除配置", f"确定要删除配置 '{config.name}' 吗？"):
            self._config_repo.delete(config.id)
            Toast.success(self, "配置已删除")
            self._load_data()

    def _on_add_script_dir(self):
        """添加脚本目录。"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择脚本目录",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if dir_path:
            manager = get_script_manager()
            if manager.add_directory(dir_path):
                count = manager.load_all()
                Toast.success(self, f"已添加目录并加载 {count} 个脚本")
            else:
                Toast.warning(self, "目录已存在或无效")

    def _on_reload_scripts(self):
        """重载所有脚本。"""
        manager = get_script_manager()
        count = manager.reload_all()
        Toast.success(self, f"已重载 {count} 个脚本")


class TaskConfigDialog(QDialog):
    """任务配置编辑对话框。"""

    def __init__(
        self, 
        parent=None, 
        template: TaskTemplate | None = None,
        config: TaskConfig | None = None,
    ):
        super().__init__(parent)
        self.template = template
        self.config = config
        self._setup_ui()

    def _setup_ui(self):
        """设置对话框UI。"""
        self.setWindowTitle("编辑任务配置" if self.config else "新建任务配置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 基本信息
        form = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("配置名称")
        if self.config:
            self.name_input.setText(self.config.name)
        form.addRow("名称:", self.name_input)

        layout.addLayout(form)

        # 配置参数
        config_group = QGroupBox("配置参数 (JSON)")
        config_layout = QVBoxLayout(config_group)
        
        self.config_editor = QTextEdit()
        self.config_editor.setPlaceholderText('{"key": "value"}')
        
        # 加载现有配置或模板默认配置
        if self.config:
            self.config_editor.setText(json.dumps(self.config.config, indent=2, ensure_ascii=False))
        elif self.template and self.template.default_config:
            self.config_editor.setText(json.dumps(self.template.default_config, indent=2, ensure_ascii=False))
        
        config_layout.addWidget(self.config_editor)
        layout.addWidget(config_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        """验证并接受。"""
        if not self.name_input.text().strip():
            Toast.error(self, "请输入配置名称")
            return

        try:
            config_text = self.config_editor.toPlainText().strip()
            if config_text:
                json.loads(config_text)
        except json.JSONDecodeError as e:
            Toast.error(self, f"JSON格式错误: {e}")
            return

        self.accept()

    def get_config(self) -> dict:
        """获取配置数据。"""
        config_text = self.config_editor.toPlainText().strip()
        return {
            "name": self.name_input.text().strip(),
            "config": json.loads(config_text) if config_text else {},
        }
