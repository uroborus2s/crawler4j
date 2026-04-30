"""模块详情页配置页面。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import yaml

from src.core.mms.config_yaml_validation import YamlConfigValidationError, parse_yaml_config_mapping
from src.core.mms.registry import get_module_registry
from src.core.mms.settings_store import get_module_settings_store
from src.ui.components.button import StyledButton
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.message_dialog import MessageDialog
from src.ui.components.yaml_code_editor import YamlCodeEditor


class _IndentedSafeDumper(yaml.SafeDumper):
    """PyYAML dumper that keeps block sequences indented under their parent key."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow=flow, indentless=False)


class ModuleConfigPage(QWidget):
    """模块与 workflow 配置编辑页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._module = None
        self._store = get_module_settings_store()
        self._splitter_sizes_initialized = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.config_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.config_splitter.setChildrenCollapsible(False)
        self.config_splitter.setHandleWidth(8)
        self.config_splitter.setStyleSheet(
            """
            QSplitter::handle:vertical {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                margin: 4px 0;
            }
            QSplitter::handle:vertical:hover {
                background: rgba(99, 102, 241, 0.45);
            }
            """
        )

        self.module_config_section = self._create_module_config_card()
        self.workflow_config_section = self._create_workflow_config_card()
        self.config_splitter.addWidget(self.module_config_section)
        self.config_splitter.addWidget(self.workflow_config_section)
        self.config_splitter.setStretchFactor(0, 7)
        self.config_splitter.setStretchFactor(1, 3)
        self.config_splitter.setSizes([700, 300])

        layout.addWidget(self.config_splitter, 1)

    def _create_section(self, title_text: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel(title_text)
        title.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        section._section_layout = layout
        section._section_header = header
        return section

    def _create_editor(self) -> YamlCodeEditor:
        editor = YamlCodeEditor()
        return editor

    def _create_module_config_card(self) -> QWidget:
        self.module_config_section = self._create_section("⚙️ 模块配置")
        layout = self.module_config_section._section_layout
        header = self.module_config_section._section_header

        self.restore_module_config_btn = StyledButton(
            "恢复模块默认",
            variant="warning",
            min_height=32,
            horizontal_padding=14,
            border_radius=4,
        )
        self.restore_module_config_btn.clicked.connect(self._restore_module_defaults)
        header.addWidget(self.restore_module_config_btn)

        self.save_module_config_btn = StyledButton(
            "保存模块配置",
            variant="primary",
            min_height=32,
            horizontal_padding=14,
            border_radius=4,
        )
        self.save_module_config_btn.clicked.connect(self._save_module_config)
        header.addWidget(self.save_module_config_btn)

        self.module_config_editor = self._create_editor()
        layout.addWidget(self.module_config_editor)
        return self.module_config_section

    def _create_workflow_config_card(self) -> QWidget:
        self.workflow_config_section = self._create_section("🧭 Workflow 配置")
        layout = self.workflow_config_section._section_layout
        header = self.workflow_config_section._section_header

        self.workflow_selector = QComboBox()
        self.workflow_selector.setMinimumWidth(220)
        self.workflow_selector.currentIndexChanged.connect(self._load_selected_workflow_config)
        header.addWidget(self.workflow_selector)

        self.restore_workflow_config_btn = StyledButton(
            "恢复 Workflow 默认",
            variant="warning",
            min_height=32,
            horizontal_padding=14,
            border_radius=4,
        )
        self.restore_workflow_config_btn.clicked.connect(self._restore_workflow_defaults)
        header.addWidget(self.restore_workflow_config_btn)

        self.save_workflow_config_btn = StyledButton(
            "保存 Workflow 配置",
            variant="primary",
            min_height=32,
            horizontal_padding=14,
            border_radius=4,
        )
        self.save_workflow_config_btn.clicked.connect(self._save_workflow_config)
        header.addWidget(self.save_workflow_config_btn)

        self.workflow_hint_label = QLabel("当前模块没有可编辑的 workflow。")
        self.workflow_hint_label.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 12px;")
        layout.addWidget(self.workflow_hint_label)

        self.workflow_config_editor = self._create_editor()
        layout.addWidget(self.workflow_config_editor)
        return self.workflow_config_section

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_initial_splitter_sizes()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_initial_splitter_sizes()

    def _apply_initial_splitter_sizes(self) -> None:
        if self._splitter_sizes_initialized:
            return

        total_height = self.config_splitter.height()
        if total_height <= 0:
            return

        module_height = max(int(total_height * 0.7), 1)
        workflow_height = max(total_height - module_height, 1)
        self.config_splitter.setSizes([module_height, workflow_height])
        self._splitter_sizes_initialized = True

    def _dump(self, payload: dict) -> str:
        if not payload:
            return ""
        raw = yaml.dump(
            payload,
            Dumper=_IndentedSafeDumper,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()
        return YamlCodeEditor.normalize_yaml_layout(raw)

    def _parse_editor_dict(self, editor: YamlCodeEditor, scope_name: str) -> dict:
        return parse_yaml_config_mapping(editor.toPlainText(), scope_name=scope_name)

    def _selected_workflow_name(self) -> str:
        data = self.workflow_selector.currentData()
        if isinstance(data, str):
            return data
        return ""

    def _module_default_payload(self) -> dict:
        if not self._module:
            return {}
        return dict(self._module.manifest.config_defaults.module)

    def _workflow_default_payload(self, workflow_name: str) -> dict:
        if not self._module or not workflow_name:
            return {}
        payload = self._module.manifest.config_defaults.workflows.get(workflow_name, {})
        return dict(payload)

    def _confirm_restore(self, title: str, message: str) -> bool:
        return ConfirmDialog.confirm(
            self,
            title,
            message,
            confirm_text="恢复",
            danger=True,
        )

    def set_module(self, module) -> None:
        self._module = module
        self._reload_editors()

    def _reload_editors(self) -> None:
        if not self._module:
            self.module_config_editor.setPlainText("")
            self.workflow_selector.clear()
            self.workflow_config_editor.setPlainText("")
            self.workflow_selector.setEnabled(False)
            self.workflow_config_editor.setEnabled(False)
            self.restore_module_config_btn.setEnabled(False)
            self.restore_workflow_config_btn.setEnabled(False)
            self.save_module_config_btn.setEnabled(False)
            self.save_workflow_config_btn.setEnabled(False)
            self.workflow_hint_label.show()
            return

        self._store.ensure_config_defaults_initialized(
            self._module.name,
            self._module.manifest.config_defaults.module,
            self._module.manifest.config_defaults.workflows,
        )

        self.restore_module_config_btn.setEnabled(True)
        self.save_module_config_btn.setEnabled(True)
        self.module_config_editor.setPlainText(
            self._dump(self._store.read_module_settings(self._module.name))
        )

        self.workflow_selector.blockSignals(True)
        self.workflow_selector.clear()
        workflows = list(get_module_registry().get_workflows(self._module.name))
        for workflow in workflows:
            label = workflow.display_name or workflow.name
            self.workflow_selector.addItem(label, workflow.name)
        self.workflow_selector.blockSignals(False)

        has_workflows = bool(workflows)
        self.workflow_selector.setEnabled(has_workflows)
        self.workflow_config_editor.setEnabled(has_workflows)
        self.restore_workflow_config_btn.setEnabled(has_workflows)
        self.save_workflow_config_btn.setEnabled(has_workflows)
        self.workflow_hint_label.setVisible(not has_workflows)

        if has_workflows:
            self.workflow_selector.setCurrentIndex(0)
            self._load_selected_workflow_config()
        else:
            self.workflow_config_editor.setPlainText("")

    def _load_selected_workflow_config(self) -> None:
        if not self._module:
            self.workflow_config_editor.setPlainText("")
            return

        workflow_name = self._selected_workflow_name()
        if not workflow_name:
            self.workflow_config_editor.setPlainText("")
            return

        payload = self._store.read_workflow_settings(self._module.name, workflow_name)
        self.workflow_config_editor.setPlainText(self._dump(payload))

    def _save_module_config(self) -> None:
        if not self._module:
            return
        try:
            payload = self._parse_editor_dict(self.module_config_editor, "模块配置")
        except YamlConfigValidationError as exc:
            self.module_config_editor.mark_validation_error(line=exc.line, column=exc.column)
            MessageDialog.warning(self, "错误", str(exc))
            return

        self._store.write_module_settings(self._module.name, payload)
        self.module_config_editor.setPlainText(self._dump(payload))
        MessageDialog.information(self, "成功", "模块配置已保存")

    def _save_workflow_config(self) -> None:
        if not self._module:
            return
        workflow_name = self._selected_workflow_name()
        if not workflow_name:
            return

        try:
            payload = self._parse_editor_dict(self.workflow_config_editor, "Workflow 配置")
        except YamlConfigValidationError as exc:
            self.workflow_config_editor.mark_validation_error(line=exc.line, column=exc.column)
            MessageDialog.warning(self, "错误", str(exc))
            return

        self._store.write_workflow_settings(self._module.name, workflow_name, payload)
        self.workflow_config_editor.setPlainText(self._dump(payload))
        MessageDialog.information(self, "成功", f"Workflow 配置已保存: {workflow_name}")

    def _restore_module_defaults(self) -> None:
        if not self._module:
            return
        if not self._confirm_restore(
            "确认恢复模块默认",
            "确定要恢复模块配置到 module.yaml 中声明的默认值吗？\n当前模块配置会被覆盖，此操作不可撤销。",
        ):
            return

        payload = self._module_default_payload()
        self._store.write_module_settings(self._module.name, payload)
        self.module_config_editor.setPlainText(self._dump(payload))
        MessageDialog.information(self, "成功", "模块配置已恢复为默认值")

    def _restore_workflow_defaults(self) -> None:
        if not self._module:
            return
        workflow_name = self._selected_workflow_name()
        if not workflow_name:
            return
        if not self._confirm_restore(
            "确认恢复 Workflow 默认",
            f"确定要恢复 Workflow 配置到 module.yaml 中声明的默认值吗？\n当前 workflow 配置会被覆盖，此操作不可撤销。\n\nWorkflow: {workflow_name}",
        ):
            return

        payload = self._workflow_default_payload(workflow_name)
        self._store.write_workflow_settings(self._module.name, workflow_name, payload)
        self.workflow_config_editor.setPlainText(self._dump(payload))
        MessageDialog.information(self, "成功", f"Workflow 配置已恢复为默认值: {workflow_name}")
