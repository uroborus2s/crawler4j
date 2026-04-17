"""模块详情页配置页面。"""

from __future__ import annotations

import yaml

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.mms.settings_store import get_module_settings_store
from src.ui.components.combo_box import StyledComboBox as QComboBox


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

    def _create_editor(self) -> QTextEdit:
        editor = QTextEdit()
        editor.setStyleSheet(
            """
            QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                color: #4ade80;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px;
                font-family: 'Menlo', 'Monaco', monospace;
                font-size: 13px;
                padding: 8px;
            }
            """
        )
        editor.setAcceptRichText(False)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setMinimumHeight(120)
        return editor

    def _create_module_config_card(self) -> QWidget:
        self.module_config_section = self._create_section("⚙️ 模块配置")
        layout = self.module_config_section._section_layout
        header = self.module_config_section._section_header

        self.restore_module_config_btn = QPushButton("恢复模块默认")
        self.restore_module_config_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(245, 158, 11, 0.22);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.35);
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(245, 158, 11, 0.3); }
            """
        )
        self.restore_module_config_btn.clicked.connect(self._restore_module_defaults)
        header.addWidget(self.restore_module_config_btn)

        self.save_module_config_btn = QPushButton("保存模块配置")
        self.save_module_config_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            """
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

        self.restore_workflow_config_btn = QPushButton("恢复 Workflow 默认")
        self.restore_workflow_config_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(245, 158, 11, 0.22);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.35);
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(245, 158, 11, 0.3); }
            """
        )
        self.restore_workflow_config_btn.clicked.connect(self._restore_workflow_defaults)
        header.addWidget(self.restore_workflow_config_btn)

        self.save_workflow_config_btn = QPushButton("保存 Workflow 配置")
        self.save_workflow_config_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            """
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
        return yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ).strip()

    def _parse_editor_dict(self, editor: QTextEdit, scope_name: str) -> dict:
        raw = editor.toPlainText()
        stripped = raw.strip()
        if not stripped:
            return {}
        if stripped.startswith("{"):
            raise ValueError(f"{scope_name} 只支持 YAML 块格式，不支持 JSON/花括号对象字面量")
        try:
            payload = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ValueError(f"{scope_name} YAML 格式错误: {exc}") from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise ValueError(f"{scope_name} 必须是 YAML 映射对象")
        return payload

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
        reply = QMessageBox.warning(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

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
        workflows = list(self._module.manifest.workflows or [])
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
        except ValueError as exc:
            QMessageBox.warning(self, "错误", str(exc))
            return

        self._store.write_module_settings(self._module.name, payload)
        self.module_config_editor.setPlainText(self._dump(payload))
        QMessageBox.information(self, "成功", "模块配置已保存")

    def _save_workflow_config(self) -> None:
        if not self._module:
            return
        workflow_name = self._selected_workflow_name()
        if not workflow_name:
            return

        try:
            payload = self._parse_editor_dict(self.workflow_config_editor, "Workflow 配置")
        except ValueError as exc:
            QMessageBox.warning(self, "错误", str(exc))
            return

        self._store.write_workflow_settings(self._module.name, workflow_name, payload)
        self.workflow_config_editor.setPlainText(self._dump(payload))
        QMessageBox.information(self, "成功", f"Workflow 配置已保存: {workflow_name}")

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
        QMessageBox.information(self, "成功", "模块配置已恢复为默认值")

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
        QMessageBox.information(self, "成功", f"Workflow 配置已恢复为默认值: {workflow_name}")
