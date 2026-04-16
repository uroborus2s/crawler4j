"""Core 通用模块数据表页面。"""

from __future__ import annotations

from typing import Any

from crawler4j_contracts import TaskContext

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.runtime_capabilities import build_runtime_capabilities
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleSource
from src.core.mms.service import get_module_service
from src.core.mms.settings_store import get_module_settings_store
from src.core.persistence import get_kv_store, get_module_data_store
from src.ui.components.table import SkyTableWidget


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


class _RecordEditDialog(QDialog):
    def __init__(self, columns: list[dict[str, Any]], record: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("记录编辑")
        self.resize(420, 280)
        self.setMinimumWidth(420)

        self._columns = columns
        self._record = record or {}
        self._widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        for col in columns:
            key = str(col.get("key", "")).strip()
            if not key:
                continue
            label = str(col.get("label") or key)
            widget = self._build_widget(col, self._record.get(key, col.get("default")))
            self._widgets[key] = widget
            form.addRow(f"{label}:", widget)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._apply_style(buttons)

    def _apply_style(self, buttons: QDialogButtonBox):
        self.setStyleSheet(
            """
            QDialog {
                background-color: #181c32;
            }
            QLabel {
                color: #eaf0ff;
                font-size: 14px;
                font-weight: 500;
            }
            QLineEdit, QComboBox {
                background-color: #0f1326;
                color: #f5f7ff;
                border: 1px solid rgba(134, 148, 214, 0.62);
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 30px;
                selection-background-color: #4f7cff;
                selection-color: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #7ea2ff;
                background-color: #141a34;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
                background: rgba(255, 255, 255, 0.06);
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1d2445;
                color: #f5f7ff;
                border: 1px solid rgba(134, 148, 214, 0.62);
                selection-background-color: #4f7cff;
                selection-color: white;
            }
            QCheckBox {
                color: #eaf0ff;
                spacing: 8px;
            }
            QDialogButtonBox QPushButton {
                background: rgba(108, 123, 193, 0.26);
                color: #eef3ff;
                border: 1px solid rgba(125, 145, 220, 0.58);
                border-radius: 6px;
                padding: 7px 18px;
                min-width: 88px;
                font-weight: 600;
            }
            QDialogButtonBox QPushButton:hover {
                background: rgba(108, 123, 193, 0.42);
            }
            QDialogButtonBox QPushButton:pressed {
                background: rgba(108, 123, 193, 0.58);
            }
            """
        )

        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn:
            ok_btn.setText("确定")
        if cancel_btn:
            cancel_btn.setText("取消")

    def _build_widget(self, col: dict[str, Any], value: Any) -> QWidget:
        col_type = str(col.get("type", "text")).lower()
        if col_type == "select":
            combo = QComboBox()
            for option in col.get("options", []):
                combo.addItem(str(option))
            if value is not None:
                combo.setCurrentText(str(value))
            return combo

        if col_type == "bool":
            checkbox = QCheckBox()
            checkbox.setChecked(bool(value))
            return checkbox

        edit = QLineEdit("" if value is None else str(value))
        return edit

    def get_value(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for col in self._columns:
            key = str(col.get("key", "")).strip()
            if not key:
                continue
            col_type = str(col.get("type", "text")).lower()
            widget = self._widgets.get(key)
            if not widget:
                continue
            if isinstance(widget, QComboBox):
                payload[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                payload[key] = widget.isChecked()
            elif isinstance(widget, QLineEdit):
                raw = widget.text().strip()
                if col_type == "number":
                    try:
                        payload[key] = float(raw) if raw else 0
                    except ValueError:
                        payload[key] = raw
                elif col_type == "int":
                    try:
                        payload[key] = int(raw) if raw else 0
                    except ValueError:
                        payload[key] = raw
                else:
                    payload[key] = raw
        return payload


class ModuleDataTablePage(QWidget):
    """模块声明式数据表页面。"""

    def __init__(self, module_name: str, view_id: str, parent=None):
        super().__init__(parent)
        self._module_name = module_name
        self._view_id = view_id
        self._kv = get_kv_store()
        self._data_store = get_module_data_store()
        self._mms = get_module_service()

        self._schema: dict[str, Any] = {}
        self._records: list[dict[str, Any]] = []
        self._columns_by_key: dict[str, dict[str, Any]] = {}
        self._visible_columns: list[dict[str, Any]] = []

        self._setup_ui()
        self.refresh()

    def _dataset(self) -> str:
        return str(self._schema.get("dataset") or self._view_id)

    def _primary_key(self) -> str:
        return str(self._schema.get("primary_key") or "id")

    def _lock_scope(self) -> str:
        return str(self._schema.get("lock_scope") or self._dataset())

    def _lock_key_field(self) -> str:
        return str(self._schema.get("lock_key") or "")

    def _lock_store_key(self, lock_value: str) -> str:
        return f"module:{self._module_name}:lock:{self._lock_scope()}:{lock_value}"

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.title_label = QLabel("数据表")
        self.title_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        header.addWidget(self.title_label)
        header.addStretch()

        self.add_btn = QPushButton("新增")
        self.edit_btn = QPushButton("编辑")
        self.delete_btn = QPushButton("删除")
        self.refresh_btn = QPushButton("刷新")
        for btn in [self.add_btn, self.edit_btn, self.delete_btn, self.refresh_btn]:
            btn.setStyleSheet(
                """
                QPushButton {
                    background: rgba(99, 102, 241, 0.75);
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 6px 12px;
                }
                QPushButton:hover { background: rgba(99, 102, 241, 0.95); }
                """
            )
            header.addWidget(btn)

        layout.addLayout(header)

        self.table = SkyTableWidget()
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.table)

        self.tip_label = QLabel("视图由模块在 hooks 中声明，Core 仅提供通用渲染与基础存储。")
        self.tip_label.setStyleSheet("color: rgba(255,255,255,0.55); font-size: 12px;")
        layout.addWidget(self.tip_label)

        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        self.refresh_btn.clicked.connect(self.refresh)

    def _build_task_context(self) -> TaskContext:
        config = get_module_settings_store().read_module_settings(self._module_name)
        module = self._mms.registry.get_module(self._module_name)
        runtime: dict[str, Any] = {}
        if module and module.source == ModuleSource.DEV_LINK:
            runtime["devel_mode"] = True
        return TaskContext(
            env_id=0,
            task_name=self._module_name,
            config=config,
            logger=logger,
            tools=build_runtime_capabilities(self._module_name).tools,
            runtime=runtime,
        )

    def _call_module_handler(self, handler_name: str, *args: Any) -> Any:
        context = self._build_task_context()
        return self._mms.call_local_hook(self._module_name, handler_name, context, *args)

    def _schema_handler(self, key: str) -> str:
        raw = self._schema.get(key)
        if not isinstance(raw, str):
            return ""
        return raw.strip()

    def _load_schema(self):
        self._call_module_handler("declare_ui")
        schema = self._data_store.read_data_table_schema(self._module_name, self._view_id)
        if not isinstance(schema, dict):
            schema = {}
        self._schema = schema
        self.title_label.setText(str(schema.get("title") or self._view_id))

        columns = schema.get("columns")
        if not isinstance(columns, list):
            columns = []

        normalized_cols = []
        for col in columns:
            if not isinstance(col, dict):
                continue
            key = str(col.get("key", "")).strip()
            if not key:
                continue
            normalized_cols.append(dict(col))

        self._columns_by_key = {
            str(col.get("key")): col
            for col in normalized_cols
        }

        display_fields = schema.get("display_fields")
        if isinstance(display_fields, list) and display_fields:
            self._visible_columns = [
                self._columns_by_key[field]
                for field in display_fields
                if isinstance(field, str) and field in self._columns_by_key
            ]
            return

        self._visible_columns = [
            col
            for col in normalized_cols
            if col.get("visible", True) is not False
        ]

    def _load_records(self):
        self._records = self._data_store.read_dataset(self._module_name, self._dataset())

    def _save_records(self):
        self._data_store.write_dataset(self._module_name, self._dataset(), self._records)

    def _is_row_locked(self, row: dict[str, Any]) -> bool:
        lock_key_field = self._lock_key_field()
        if not lock_key_field:
            return False
        lock_value = str(row.get(lock_key_field, "")).strip()
        if not lock_value:
            return False
        return self._kv.exists(self._lock_store_key(lock_value))

    def _effective_columns(self) -> list[dict[str, Any]]:
        if self._visible_columns:
            return list(self._visible_columns)
        if self._records:
            return [{"key": k, "label": k} for k in self._records[0].keys()]
        return [{"key": self._primary_key(), "label": self._primary_key()}]

    def _form_columns(self, *, mode: str) -> list[dict[str, Any]]:
        schema_key = "create_fields" if mode == "create" else "update_fields"
        declared_fields = self._schema.get(schema_key)
        if isinstance(declared_fields, list) and declared_fields:
            columns = [
                self._columns_by_key[field]
                for field in declared_fields
                if isinstance(field, str) and field in self._columns_by_key
            ]
            if columns:
                return columns

        return [
            dict(col)
            for col in self._effective_columns()
            if not col.get("readonly", False)
        ]

    def _render(self):
        columns = self._effective_columns()
        show_lock_col = bool(self._lock_key_field())

        headers = [str(col.get("label") or col.get("key")) for col in columns]
        if show_lock_col:
            headers.append("占用中")

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self._records))

        for row_index, row in enumerate(self._records):
            for col_index, col in enumerate(columns):
                key = str(col.get("key"))
                value = row.get(key, "")
                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, col_index, item)

            if show_lock_col:
                locked_item = QTableWidgetItem("是" if self._is_row_locked(row) else "否")
                locked_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, len(columns), locked_item)

    def refresh(self):
        try:
            self._load_schema()
            self.tip_label.setText("视图由模块声明并由 Core 通用页面渲染。")
        except Exception as exc:
            self._schema = {}
            self._records = []
            self._visible_columns = []
            self.title_label.setText(str(self._view_id))
            self.tip_label.setText(f"视图声明失败: {exc}")
            self._render()
            return
        self._load_records()
        self._render()

    def _selected_row(self) -> int:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return -1
        return int(selected[0].row())

    def _validate_required(self, payload: dict[str, Any], columns: list[dict[str, Any]]) -> tuple[bool, str]:
        for col in columns:
            if not col.get("required", False):
                continue
            key = str(col.get("key", ""))
            val = payload.get(key)
            if val is None or str(val).strip() == "":
                label = str(col.get("label") or key)
                return False, f"{label} 不能为空"
        return True, ""

    def _on_add(self):
        create_handler = self._schema_handler("create_handler")
        if create_handler:
            columns = self._form_columns(mode="create")
        else:
            columns = self._effective_columns()

        dialog = _RecordEditDialog(columns, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.get_value()
        ok, message = self._validate_required(payload, columns)
        if not ok:
            QMessageBox.warning(self, "校验失败", message)
            return

        if create_handler:
            try:
                self._call_module_handler(create_handler, payload)
            except Exception as exc:
                QMessageBox.warning(self, "新增失败", str(exc))
                return
            self.refresh()
            return

        pk = self._primary_key()
        pk_value = str(payload.get(pk, "")).strip()
        if not pk_value:
            pk_value = f"ui-{len(self._records) + 1}"
            payload[pk] = pk_value

        conflict = any(str(item.get(pk, "")) == pk_value for item in self._records)
        if conflict:
            QMessageBox.warning(self, "校验失败", f"{pk} 已存在")
            return

        self._records.append(payload)
        self._save_records()
        self._render()

    def _on_edit(self):
        row_index = self._selected_row()
        if row_index < 0 or row_index >= len(self._records):
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return

        old = dict(self._records[row_index])
        update_handler = self._schema_handler("update_handler")
        if update_handler:
            columns = self._form_columns(mode="update")
        else:
            columns = self._effective_columns()

        dialog = _RecordEditDialog(columns, old, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        payload = dialog.get_value()
        ok, message = self._validate_required(payload, columns)
        if not ok:
            QMessageBox.warning(self, "校验失败", message)
            return

        if update_handler:
            pk = self._primary_key()
            pk_value = str(old.get(pk, "")).strip()
            if not pk_value:
                QMessageBox.warning(self, "编辑失败", f"{pk} 不能为空")
                return
            try:
                self._call_module_handler(update_handler, pk_value, payload)
            except Exception as exc:
                QMessageBox.warning(self, "编辑失败", str(exc))
                return
            self.refresh()
            return

        pk = self._primary_key()
        old_pk = str(old.get(pk, ""))
        new_pk = str(payload.get(pk, "")).strip()
        if not new_pk:
            QMessageBox.warning(self, "校验失败", f"{pk} 不能为空")
            return

        conflict = any(idx != row_index and str(item.get(pk, "")) == new_pk for idx, item in enumerate(self._records))
        if conflict:
            QMessageBox.warning(self, "校验失败", f"{pk} 已存在")
            return

        if old_pk != new_pk and self._lock_key_field() == pk and self._kv.exists(self._lock_store_key(old_pk)):
            QMessageBox.warning(self, "编辑失败", "记录处于占用状态，不能修改主键")
            return

        self._records[row_index] = payload
        self._save_records()
        self._render()

    def _on_delete(self):
        row_index = self._selected_row()
        if row_index < 0 or row_index >= len(self._records):
            QMessageBox.information(self, "提示", "请先选择一条记录")
            return

        row = self._records[row_index]
        if self._is_row_locked(row):
            QMessageBox.warning(self, "删除失败", "记录正在占用中，无法删除")
            return

        self._records.pop(row_index)
        self._save_records()
        self._render()
