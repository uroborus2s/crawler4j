"""已有环境导入配置弹窗。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout

from src.ui.components.button import StyledButton
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.notice_panel import NoticePanel


class ImportExistingEnvDialog(QDialog):
    """配置“从已有环境导入”并执行模块 workflow。"""

    RISK_WARNING_TEXT = "该 workflow 未标注支持“已有环境导入”，请由配置者自行判断是否适合这个场景。"
    RISK_SAFE_TEXT = "该 workflow 已声明支持“已有环境导入”场景。"
    RISK_CONTENT_PADDING = (12, 10, 12, 10)
    TABLE_SCHEMA = {
        "columns": [
            {"key": "name", "label": "环境名称", "type": "text", "width": 180},
            {"key": "external_id", "label": "外部 ID", "type": "text", "width": 130},
            {"key": "remark", "label": "备注", "type": "text", "width": 150},
            {"key": "proxy_summary", "label": "代理/IP 摘要", "type": "text", "width": 180},
            {"key": "running_status", "label": "当前运行状态", "type": "text", "width": 120},
            {"key": "last_used_at", "label": "最近使用时间", "type": "text", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索环境名称、外部 ID 或备注"},
            "sort": {
                "enabled": True,
                "default": [{"field": "name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 10, "page_size_options": [10, 20, 50]},
        },
    }

    def __init__(
        self,
        *,
        sources: list[dict[str, str]],
        modules: list[Any],
        env_options_by_source: dict[str, list[Any]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._sources = list(sources)
        self._modules = list(modules)
        self._modules_by_name = {str(module.name): module for module in self._modules}
        self._env_options_by_source = {
            str(provider): list(items)
            for provider, items in (env_options_by_source or {}).items()
        }
        self._selected_env_name = ""
        self._table_rows: list[dict[str, Any]] = []
        self._warning_height_sync_pending = False
        self._setup_ui()
        self._load_sources()
        self._load_modules()
        self._update_workflows()
        self._reload_env_rows()
        self._update_warning()
        self._update_accept_state()

    def _setup_ui(self) -> None:
        self.setWindowTitle("从已有环境导入")
        configure_titled_dialog(self)
        self.setMinimumSize(920, 620)
        self.setStyleSheet(
            """
            QDialog {
                background: rgb(30, 30, 40);
            }
            QLabel {
                color: white;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("从已有环境导入")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(14)
        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        form.addRow("环境来源:", self.source_combo)

        self.module_combo = QComboBox()
        self.module_combo.currentIndexChanged.connect(self._on_module_changed)
        form.addRow("目标模块:", self.module_combo)

        self.workflow_combo = QComboBox()
        self.workflow_combo.currentIndexChanged.connect(self._on_workflow_changed)
        form.addRow("模块工作流:", self.workflow_combo)

        warning_title = QLabel("风险提示:")
        warning_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.warning_card = NoticePanel(margins=self.RISK_CONTENT_PADDING)
        self.warning_label = self.warning_card.label
        form.addRow(warning_title, self.warning_card)
        layout.addLayout(form)

        self.table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.table.query_requested.connect(self._on_table_query_requested)
        self.table.row_clicked.connect(self._on_table_row_clicked)
        layout.addWidget(self.table)

        self.selection_label = QLabel("未同步环境列表：请选择一个环境。")
        self.selection_label.setStyleSheet("color: rgba(255, 255, 255, 0.68); font-size: 12px;")
        layout.addWidget(self.selection_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()

        cancel_btn = StyledButton(
            "取消",
            variant="secondary",
            min_height=40,
            min_width=92,
            horizontal_padding=20,
        )
        cancel_btn.setObjectName("importExistingCancelButton")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        self.submit_btn = StyledButton(
            "导入并执行",
            variant="success",
            min_height=40,
            min_width=124,
            horizontal_padding=20,
        )
        self.submit_btn.setObjectName("importExistingSubmitButton")
        self.submit_btn.clicked.connect(self.accept)
        button_row.addWidget(self.submit_btn)
        layout.addLayout(button_row)

    def _load_sources(self) -> None:
        self.source_combo.clear()
        for item in self._sources:
            self.source_combo.addItem(item["label"], item["provider"])

    def _load_modules(self) -> None:
        self.module_combo.clear()
        for module in self._modules:
            label = str(getattr(module.manifest, "display_name", "") or module.name)
            self.module_combo.addItem(label, module.name)

    def _selected_provider(self) -> str:
        data = self.source_combo.currentData()
        return str(data or "").strip()

    def _selected_module_name(self) -> str:
        data = self.module_combo.currentData()
        return str(data or "").strip()

    def _selected_workflow_name(self) -> str:
        data = self.workflow_combo.currentData()
        return str(data or "").strip()

    def _selected_workflow(self):
        module = self._modules_by_name.get(self._selected_module_name())
        if not module:
            return None
        for workflow in module.manifest.workflows:
            if workflow.name == self._selected_workflow_name():
                return workflow
        return None

    def _update_workflows(self) -> None:
        self.workflow_combo.clear()
        module = self._modules_by_name.get(self._selected_module_name())
        if not module:
            return
        for workflow in module.manifest.workflows:
            label = workflow.display_name or workflow.name
            self.workflow_combo.addItem(label, workflow.name)

    def _reload_env_rows(self) -> None:
        provider = self._selected_provider()
        items = self._env_options_by_source.get(provider, [])
        self._table_rows = [self._build_env_row(item) for item in items]
        self._selected_env_name = ""
        self.selection_label.setText(
            "未同步环境列表：请选择一个环境。" if self._table_rows else "未同步环境列表：当前来源没有可导入环境。"
        )
        self.table.request_refresh()

    def _build_env_row(self, item: Any) -> dict[str, Any]:
        last_used = "-"
        if getattr(item, "last_used_at", None):
            try:
                last_used = datetime.fromtimestamp(int(item.last_used_at)).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                last_used = "-"
        return {
            "name": str(getattr(item, "name", "") or "-"),
            "external_id": str(getattr(item, "external_id", "") or ""),
            "remark": str(getattr(item, "remark", "") or "-"),
            "proxy_summary": getattr(item, "proxy_summary_text", "-"),
            "running_status": str(getattr(item, "running_status", "") or "-"),
            "last_used_at": last_used,
            "raw": item,
        }

    def _workflow_supports_existing_env_import(self) -> bool:
        workflow = self._selected_workflow()
        if not workflow:
            return False
        scenarios = getattr(workflow, "host_scenarios", []) or []
        return "existing_env_import" in {str(item).strip() for item in scenarios}

    def _update_warning(self) -> None:
        if self._workflow_supports_existing_env_import():
            self.warning_card.set_text(self.RISK_SAFE_TEXT)
            self.warning_card.set_kind("success")
            self._schedule_warning_height_sync()
            return
        self.warning_card.set_text(self.RISK_WARNING_TEXT)
        self.warning_card.set_kind("warning")
        self._schedule_warning_height_sync()

    def _schedule_warning_height_sync(self) -> None:
        if self._warning_height_sync_pending:
            return
        self._warning_height_sync_pending = True
        QTimer.singleShot(0, self._sync_warning_height)

    def _sync_warning_height(self) -> None:
        self._warning_height_sync_pending = False
        if not hasattr(self, "warning_card"):
            return
        warning_layout = self.warning_card.layout()
        if warning_layout is None:
            return
        margins = warning_layout.contentsMargins()
        content_width = self.warning_card.width() - margins.left() - margins.right()
        if content_width <= 0:
            return
        text_height = max(
            self.warning_label.minimumSizeHint().height(),
            self.warning_label.heightForWidth(content_width),
        )
        card_height = text_height + margins.top() + margins.bottom()
        self.warning_label.setFixedHeight(text_height)
        self.warning_card.setFixedHeight(card_height)
        self.warning_label.updateGeometry()
        self.warning_card.updateGeometry()

    def _update_accept_state(self) -> None:
        module_name = self._selected_module_name()
        workflow_name = self._selected_workflow_name()
        self.submit_btn.setEnabled(bool(module_name and workflow_name and self._selected_env_name))

    def _on_source_changed(self, _index: int) -> None:
        self._reload_env_rows()
        self._update_accept_state()

    def _on_module_changed(self, _index: int) -> None:
        self._update_workflows()
        self._update_warning()
        self._update_accept_state()

    def _on_workflow_changed(self, _index: int) -> None:
        self._update_warning()
        self._update_accept_state()

    def _on_table_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._table_rows,
            columns=self.TABLE_SCHEMA["columns"],
            query=query,
        )
        self.table.apply_result(request_id, result)

    def _on_table_row_clicked(self, row: dict[str, Any]) -> None:
        self._selected_env_name = str(row.get("name") or "")
        external_id = str(row.get("external_id") or "")
        suffix = f" ({external_id})" if external_id else ""
        self.selection_label.setText(f"未同步环境列表：已选择 {self._selected_env_name}{suffix}")
        self._update_accept_state()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._schedule_warning_height_sync()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._schedule_warning_height_sync()

    def get_values(self) -> dict[str, str]:
        return {
            "provider": self._selected_provider(),
            "module_name": self._selected_module_name(),
            "workflow_name": self._selected_workflow_name(),
            "name": self._selected_env_name,
        }

    def accept(self) -> None:  # type: ignore[override]
        values = self.get_values()
        if not values["module_name"] or not values["workflow_name"] or not values["name"]:
            return
        super().accept()
