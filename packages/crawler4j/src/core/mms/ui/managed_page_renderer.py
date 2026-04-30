"""Minimal hosted page renderer."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.persistence import get_module_data_store
from src.core.mms.models import ModuleInfo
from src.core.mms.ui.module_ui_runtime import ModuleUIRuntimeBridge
from src.ui.components.button import StyledButton, create_action_button, normalize_button_variant
from src.ui.components.card import Card
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.message_dialog import MessageDialog

CRUD_ROW_ACTION_EDIT = "__crud_update__"
CRUD_ROW_ACTION_DELETE = "__crud_delete__"
CRUD_ACTION_COLUMN_KEY = "__crud_actions__"


def _runtime_surface_full():
    from src.core.atm.runtime_capabilities import RUNTIME_SURFACE_FULL

    return RUNTIME_SURFACE_FULL


def _runtime_surface_hosted_ui_action():
    from src.core.atm.runtime_capabilities import RUNTIME_SURFACE_HOSTED_UI_ACTION

    return RUNTIME_SURFACE_HOSTED_UI_ACTION


class ManagedPageRenderer(QWidget):
    """Render `ui.declare_page` declared hosted pages."""

    def __init__(
        self,
        module_name: str,
        page_id: str,
        *,
        module_info: ModuleInfo | None = None,
        open_page_callback: Callable[..., Any] | None = None,
        initial_params: dict[str, Any] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._module_name = module_name
        self._page_id = page_id
        self._open_page_callback = open_page_callback
        self._bridge = ModuleUIRuntimeBridge(module_name, module_info=module_info)

        self._schema: dict[str, Any] = {}
        self._payload: dict[str, Any] = {}
        self._data_table_widgets: dict[str, SkyDataTable] = {}
        self._navigation_params = self._normalize_navigation_params(initial_params)

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)
        self._apply_scroll_policy({})
        layout.addWidget(self._scroll)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: rgba(255,255,255,0.62); font-size: 12px;")
        layout.addWidget(self._status_label)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _normalize_navigation_params(params: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(params, dict):
            return {}
        return dict(params)

    def set_navigation_params(self, params: dict[str, Any] | None, *, auto_refresh: bool = True) -> None:
        self._navigation_params = self._normalize_navigation_params(params)
        if auto_refresh:
            self.refresh()

    def _resolve_binding(self, binding: str) -> Any:
        current: Any = self._payload
        for part in binding.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            return None
        return current

    @staticmethod
    def _resolve_action_binding(source: Any, binding: str) -> Any:
        current: Any = source
        for part in binding.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            return None
        return current

    def _resolve_action_params(self, action: dict[str, Any], source: Any) -> dict[str, Any]:
        raw_params = action.get("params")
        if not isinstance(raw_params, dict):
            return {}
        resolved: dict[str, Any] = {}
        for key, spec in raw_params.items():
            if isinstance(spec, dict) and "binding" in spec:
                resolved[str(key)] = self._resolve_action_binding(source, str(spec.get("binding") or ""))
                continue
            if isinstance(spec, dict) and "value" in spec:
                resolved[str(key)] = spec.get("value")
                continue
            resolved[str(key)] = spec
        return resolved

    def _apply_scroll_policy(self, schema: dict[str, Any]) -> None:
        scroll = schema.get("scroll") if isinstance(schema, dict) else {}
        if not isinstance(scroll, dict):
            scroll = {}
        vertical = str(scroll.get("vertical") or "auto").strip().lower()
        vertical_policy = (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if vertical == "hidden"
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setVerticalScrollBarPolicy(vertical_policy)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _build_layout_widget(self, children: list[dict[str, Any]], layout_spec: dict[str, Any]) -> QWidget:
        container = QWidget()
        kind = str(layout_spec.get("kind") or "").strip().lower()
        direction = str(layout_spec.get("direction") or "column").strip().lower()
        gap = int(layout_spec.get("gap", 12))

        if kind == "grid":
            columns = int(layout_spec.get("columns", 1))
            layout = QGridLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setHorizontalSpacing(gap)
            layout.setVerticalSpacing(gap)
            for index, child in enumerate(children):
                layout.addWidget(self._build_component(child), index // columns, index % columns)
            return container

        if direction == "row":
            layout = QHBoxLayout(container)
        else:
            layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(gap)
        for child in children:
            layout.addWidget(self._build_component(child))
        return container

    def _build_text(self, component: dict[str, Any]) -> QLabel:
        text = str(component.get("text") or "")
        binding = str(component.get("binding") or "").strip()
        if binding:
            value = self._resolve_binding(binding)
            if value is not None:
                text = "" if value is None else str(value)

        label = QLabel(text)
        label.setWordWrap(True)
        styles = {
            "title": "color: white; font-size: 22px; font-weight: 700;",
            "subtitle": "color: rgba(255,255,255,0.88); font-size: 16px; font-weight: 600;",
            "body": "color: rgba(255,255,255,0.78); font-size: 14px;",
            "meta": "color: rgba(255,255,255,0.56); font-size: 12px;",
        }
        label.setStyleSheet(styles.get(str(component.get("style") or "body"), styles["body"]))
        return label

    def _build_button(self, component: dict[str, Any]) -> StyledButton:
        label = str(component.get("label") or "").strip()
        icon = str(component.get("icon") or "").strip()
        text = f"{icon} {label}".strip() if label else icon or "按钮"
        size = str(component.get("size") or "md").strip().lower()
        variant = str(component.get("variant") or "primary").strip().lower()
        button = StyledButton(
            text,
            variant=normalize_button_variant(variant, default="primary"),
            min_height=34 if size == "icon" else 30 if size == "sm" else 36,
            min_width=34 if size == "icon" else None,
            horizontal_padding=0 if size == "icon" else 10 if size == "sm" else 14,
        )
        aria_label = str(component.get("aria_label") or label or icon or "").strip()
        if aria_label:
            button.setToolTip(aria_label)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if size == "icon":
            button.setFixedSize(34, 34)
        action = component.get("action", {})
        if action.get("type") == "reload":
            button.clicked.connect(self.refresh)
        else:
            button.clicked.connect(lambda _checked=False, current_action=dict(action): self._handle_button_action(current_action))
        return button

    def _build_data_table(self, component: dict[str, Any]) -> QWidget:
        component = self._prepare_table_component(component)
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = str(component.get("title") or "").strip()
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;")
            header.addWidget(title_label)
        header.addStretch()

        table = SkyDataTable(
            {
                "columns": self._visible_table_columns(component),
                "features": dict(component.get("features") or {}),
                "empty_text": str(component.get("empty_text") or "暂无数据"),
                "selection_mode": "single",
            }
        )
        table.query_requested.connect(
            lambda request_id, query, table_widget=table, spec=dict(component): self._on_inline_table_query(
                table_widget,
                spec,
                request_id,
                query,
            )
        )
        row_action = component.get("row_action")
        if isinstance(row_action, dict):
            table.row_clicked.connect(lambda row, action=dict(row_action): self._handle_row_action(action, row))
        if self._build_crud_row_actions(component):
            table.row_action_requested.connect(
                lambda action_id, row, table_widget=table, spec=dict(component): self._handle_crud_row_action(
                    spec,
                    table_widget,
                    action_id,
                    row,
                )
            )

        self._build_crud_toolbar(component, table)
        if title:
            layout.addLayout(header)

        table.set_query({"params": dict(self._navigation_params)})
        table.request_refresh()

        table_id = str(component.get("table_id") or title or f"table_{len(self._data_table_widgets) + 1}")
        self._data_table_widgets[table_id] = table
        layout.addWidget(table)
        return wrapper

    def _visible_table_columns(self, component: dict[str, Any]) -> list[dict[str, Any]]:
        columns = [dict(column) for column in list(component.get("columns") or []) if isinstance(column, dict)]
        visible_columns = [column for column in columns if column.get("visible", True) is not False]
        return visible_columns or columns

    def _prepare_table_component(self, component: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(component)
        columns = [dict(column) for column in list(component.get("columns") or []) if isinstance(column, dict)]
        if self._build_crud_row_actions(component) and not self._has_visible_action_column(columns):
            columns.append(
                {
                    "key": CRUD_ACTION_COLUMN_KEY,
                    "label": "操作",
                    "type": "actions",
                    "width": 180,
                    "sortable": False,
                    "searchable": False,
                }
            )
        prepared["columns"] = columns
        return prepared

    @staticmethod
    def _crud_config(component: dict[str, Any]) -> dict[str, Any]:
        crud = component.get("crud")
        return dict(crud) if isinstance(crud, dict) else {}

    def _crud_toolbar_actions(self, component: dict[str, Any]) -> dict[str, bool]:
        crud = self._crud_config(component)
        render = str(crud.get("render") or "toolbar").strip().lower() or "toolbar"
        toolbar = dict(crud.get("toolbar") or {}) if isinstance(crud.get("toolbar"), dict) else {}
        handlers = {
            "create": bool(str(crud.get("create_handler") or "").strip()),
            "update": bool(str(crud.get("update_handler") or "").strip()),
            "delete": bool(str(crud.get("delete_handler") or "").strip()),
        }
        actions = {
            "create": handlers["create"],
            "update": handlers["update"] and render != "row_actions",
            "delete": handlers["delete"] and render != "row_actions",
        }
        for action_name in ("create", "update", "delete"):
            if action_name in toolbar:
                actions[action_name] = handlers[action_name] and bool(toolbar[action_name])
        return actions

    def _build_crud_row_actions(self, component: dict[str, Any]) -> bool:
        crud = self._crud_config(component)
        if str(crud.get("render") or "toolbar").strip().lower() != "row_actions":
            return False
        toolbar_actions = self._crud_toolbar_actions(component)
        has_update_action = bool(str(crud.get("update_handler") or "").strip()) and not toolbar_actions["update"]
        has_delete_action = bool(str(crud.get("delete_handler") or "").strip()) and not toolbar_actions["delete"]
        return has_update_action or has_delete_action

    @staticmethod
    def _has_visible_action_column(columns: list[dict[str, Any]]) -> bool:
        for column in columns:
            if not isinstance(column, dict):
                continue
            if str(column.get("type") or "").strip().lower() != "actions":
                continue
            if column.get("visible", True) is False:
                continue
            if str(column.get("key") or "").strip():
                return True
        return False

    @staticmethod
    def _action_column_key(columns: list[dict[str, Any]]) -> str:
        for column in columns:
            if not isinstance(column, dict):
                continue
            if str(column.get("type") or "").strip().lower() != "actions":
                continue
            if column.get("visible", True) is False:
                continue
            key = str(column.get("key") or "").strip()
            if key:
                return key
        return CRUD_ACTION_COLUMN_KEY

    def _crud_row_action_specs(self, component: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._build_crud_row_actions(component):
            return []
        crud = self._crud_config(component)
        toolbar_actions = self._crud_toolbar_actions(component)
        actions: list[dict[str, Any]] = []
        if bool(str(crud.get("update_handler") or "").strip()) and not toolbar_actions["update"]:
            actions.append({"id": CRUD_ROW_ACTION_EDIT, "label": "编辑", "variant": "secondary"})
        if bool(str(crud.get("delete_handler") or "").strip()) and not toolbar_actions["delete"]:
            actions.append({"id": CRUD_ROW_ACTION_DELETE, "label": "删除", "variant": "danger"})
        return actions

    def _attach_crud_row_actions(self, component: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        actions = self._crud_row_action_specs(component)
        rows = result.get("rows") if isinstance(result, dict) else None
        if not actions or not isinstance(rows, list):
            return result

        action_key = self._action_column_key(list(component.get("columns") or []))
        updated_rows: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            updated_row = dict(row)
            existing_actions = updated_row.get(action_key)
            merged_actions = [dict(item) for item in existing_actions if isinstance(item, dict)] if isinstance(existing_actions, list) else []
            merged_actions.extend(dict(action) for action in actions)
            updated_row[action_key] = merged_actions
            updated_rows.append(updated_row)

        updated_result = dict(result)
        updated_result["rows"] = updated_rows
        return updated_result

    def _build_crud_toolbar(
        self,
        component: dict[str, Any],
        table: SkyDataTable,
    ) -> bool:
        crud = component.get("crud")
        if not isinstance(crud, dict):
            return False

        toolbar_actions = self._crud_toolbar_actions(component)
        if not any(toolbar_actions.values()):
            return False
        toolbar = getattr(table, "_toolbar", None)
        if not isinstance(toolbar, QHBoxLayout):
            return False

        edit_button: StyledButton | None = None
        delete_button: StyledButton | None = None

        if toolbar_actions["create"]:
            create_button = create_action_button("新增", variant="primary", min_height=34)
            create_button.clicked.connect(lambda _checked=False: self._handle_create_action(component, table))
            toolbar.addWidget(create_button)
        if toolbar_actions["update"]:
            edit_button = create_action_button("编辑", variant="secondary", min_height=34)
            edit_button.clicked.connect(lambda _checked=False: self._handle_update_action(component, table))
            toolbar.addWidget(edit_button)
        if toolbar_actions["delete"]:
            delete_button = create_action_button("删除", variant="danger", min_height=34)
            delete_button.clicked.connect(lambda _checked=False: self._handle_delete_action(component, table))
            toolbar.addWidget(delete_button)

        for button in (edit_button, delete_button):
            if button is not None:
                button.setEnabled(False)

        def _sync_buttons(rows: list[dict[str, Any]]) -> None:
            enabled = bool(rows)
            if edit_button is not None:
                edit_button.setEnabled(enabled)
            if delete_button is not None:
                delete_button.setEnabled(enabled)

        table.selection_changed.connect(_sync_buttons)
        _sync_buttons(table.selected_rows())
        return True

    def _handle_crud_row_action(
        self,
        component: dict[str, Any],
        table: SkyDataTable,
        action_id: str,
        row: dict[str, Any],
    ) -> None:
        del row
        if action_id == CRUD_ROW_ACTION_EDIT:
            self._handle_update_action(component, table)
            return
        if action_id == CRUD_ROW_ACTION_DELETE:
            self._handle_delete_action(component, table)
            return

    def _handle_create_action(self, component: dict[str, Any], table: SkyDataTable) -> None:
        crud = dict(component.get("crud") or {})
        handler_name = str(crud.get("create_handler") or "").strip()
        if not handler_name:
            return
        payload = self._prompt_crud_form_payload(component, mode="create")
        if payload is None:
            return
        try:
            self._bridge.call_local_hook(
                handler_name,
                payload,
                capability_surface=_runtime_surface_full(),
            )
        except Exception as exc:
            MessageDialog.warning(self, "新增失败", str(exc))
            return
        table.request_refresh()

    def _handle_update_action(self, component: dict[str, Any], table: SkyDataTable) -> None:
        crud = dict(component.get("crud") or {})
        handler_name = str(crud.get("update_handler") or "").strip()
        primary_key = str(crud.get("primary_key") or "").strip()
        selected_row = table.selected_row()
        if not handler_name or not primary_key or not isinstance(selected_row, dict):
            return
        row_key = selected_row.get(primary_key)
        if row_key in (None, ""):
            MessageDialog.warning(self, "编辑失败", f"当前记录缺少主键字段: {primary_key}")
            return
        payload = self._prompt_crud_form_payload(component, mode="update", row=selected_row)
        if payload is None:
            return
        try:
            self._bridge.call_local_hook(
                handler_name,
                row_key,
                payload,
                capability_surface=_runtime_surface_full(),
            )
        except Exception as exc:
            MessageDialog.warning(self, "编辑失败", str(exc))
            return
        table.request_refresh()

    def _handle_delete_action(self, component: dict[str, Any], table: SkyDataTable) -> None:
        crud = dict(component.get("crud") or {})
        handler_name = str(crud.get("delete_handler") or "").strip()
        primary_key = str(crud.get("primary_key") or "").strip()
        selected_row = table.selected_row()
        if not handler_name or not primary_key or not isinstance(selected_row, dict):
            return
        row_key = selected_row.get(primary_key)
        if row_key in (None, ""):
            MessageDialog.warning(self, "删除失败", f"当前记录缺少主键字段: {primary_key}")
            return
        item_name = str(selected_row.get("name") or selected_row.get("account") or selected_row.get(primary_key) or "当前记录")
        if not ConfirmDialog.delete_confirm(self, item_name):
            return
        try:
            self._bridge.call_local_hook(
                handler_name,
                row_key,
                capability_surface=_runtime_surface_full(),
            )
        except Exception as exc:
            MessageDialog.warning(self, "删除失败", str(exc))
            return
        table.request_refresh()

    def _prompt_crud_form_payload(
        self,
        component: dict[str, Any],
        *,
        mode: str,
        row: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        crud = dict(component.get("crud") or {})
        form = dict(crud.get("form") or {})
        field_names = list(form.get("create_columns" if mode == "create" else "update_columns") or [])
        if not field_names:
            return {}

        columns_by_key = {
            str(column.get("key") or ""): dict(column)
            for column in list(component.get("columns") or [])
            if isinstance(column, dict)
        }
        dialog = QDialog(self)
        title = str(component.get("title") or "数据表")
        dialog.setWindowTitle(f"{'新增' if mode == 'create' else '编辑'}{title}")
        configure_titled_dialog(dialog)
        dialog.setModal(True)
        dialog.setMinimumWidth(460)
        dialog.setStyleSheet(
            """
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                background-color: transparent;
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        widgets: dict[str, tuple[QWidget, dict[str, Any]]] = {}

        for field_name in field_names:
            column = dict(columns_by_key.get(str(field_name), {"key": str(field_name), "label": str(field_name)}))
            label = str(column.get("label") or field_name)
            widget = self._build_crud_input_widget(column, value=(row or {}).get(field_name))
            widgets[str(field_name)] = (widget, column)
            form_layout.addRow(f"{label}：", widget)

        layout.addLayout(form_layout)
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()

        cancel_button = StyledButton("取消", variant="secondary", min_height=40, min_width=92)
        cancel_button.setObjectName("managedCrudCancelButton")
        cancel_button.clicked.connect(dialog.reject)
        button_row.addWidget(cancel_button)

        ok_button = StyledButton("确认", variant="success", min_height=40, min_width=92)
        ok_button.setObjectName("managedCrudConfirmButton")
        ok_button.setDefault(True)
        ok_button.clicked.connect(dialog.accept)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        payload: dict[str, Any] = {}
        for field_name, (widget, column) in widgets.items():
            value = self._read_crud_input_value(widget, column)
            if column.get("required") and value in (None, ""):
                MessageDialog.warning(self, "表单不完整", f"{column.get('label') or field_name} 不能为空")
                return None
            payload[field_name] = value
        return payload

    def _build_crud_input_widget(self, column: dict[str, Any], *, value: Any) -> QWidget:
        column_type = str(column.get("type") or "text").strip().lower()
        if column_type == "select":
            combo = StyledComboBox()
            options = list(column.get("options") or [])
            if not column.get("required"):
                combo.addItem("", None)
            for option in options:
                combo.addItem(str(option), option)
            current_index = combo.findData(value)
            if current_index < 0 and value not in (None, ""):
                combo.addItem(str(value), value)
                current_index = combo.findData(value)
            if current_index >= 0:
                combo.setCurrentIndex(current_index)
            return combo

        if column_type == "bool":
            combo = StyledComboBox()
            if not column.get("required"):
                combo.addItem("", None)
            combo.addItem("是", True)
            combo.addItem("否", False)
            current_index = combo.findData(value)
            if current_index >= 0:
                combo.setCurrentIndex(current_index)
            return combo

        line_edit = StyledLineEdit()
        if value not in (None, ""):
            line_edit.setText(str(value))
        key = str(column.get("key") or "").strip().lower()
        if key == "password" or key.endswith("_token"):
            line_edit.setEchoMode(StyledLineEdit.EchoMode.Password)
        return line_edit

    def _read_crud_input_value(self, widget: QWidget, column: dict[str, Any]) -> Any:
        column_type = str(column.get("type") or "text").strip().lower()
        if isinstance(widget, StyledComboBox):
            value = widget.currentData()
            if value is None and column.get("required"):
                value = widget.currentText().strip()
            return value

        if not isinstance(widget, StyledLineEdit):
            return None
        text = widget.text().strip()
        if not text:
            return None
        if column_type == "int":
            return int(text)
        if column_type == "number":
            return float(text)
        if column_type == "bool":
            return text.lower() in {"1", "true", "yes", "on", "是"}
        return text

    def _normalize_inline_query_result(self, raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("query_handler 必须返回对象")
        rows = raw.get("rows")
        if not isinstance(rows, list):
            raise ValueError("query_handler 返回值必须包含 rows 数组")
        normalized_rows = [dict(row) for row in rows if isinstance(row, dict)]
        return {
            "rows": normalized_rows,
            "total": int(raw.get("total", len(normalized_rows))),
            "page": int(raw.get("page", 1)),
            "page_size": int(raw.get("page_size", 20)),
            "sort": list(raw.get("sort") or []),
        }

    def _on_inline_table_query(
        self,
        table: SkyDataTable,
        component: dict[str, Any],
        request_id: int,
        query: dict[str, Any],
    ) -> None:
        data_source = component.get("data_source") or {}
        source_type = str(data_source.get("type") or "").strip().lower()
        merged_query = dict(query or {})
        merged_query["params"] = dict(self._navigation_params)
        try:
            if source_type == "binding":
                rows = self._resolve_binding(str(data_source.get("binding") or ""))
                if not isinstance(rows, list):
                    rows = []
                result = resolve_local_data_table_result(
                    [dict(row) for row in rows if isinstance(row, dict)],
                    columns=list(component.get("columns") or []),
                    query=merged_query,
                )
            elif source_type == "rows":
                rows = data_source.get("rows")
                if not isinstance(rows, list):
                    rows = []
                result = resolve_local_data_table_result(
                    [dict(row) for row in rows if isinstance(row, dict)],
                    columns=list(component.get("columns") or []),
                    query=merged_query,
                )
            elif source_type == "managed_resource":
                resource_id = str(data_source.get("resource_id") or "").strip()
                if not resource_id:
                    raise ValueError("managed_resource 数据源必须提供 resource_id")
                rows = get_module_data_store().list_records(
                    self._module_name,
                    resource_id,
                    limit=1000,
                    offset=0,
                )
                result = resolve_local_data_table_result(
                    [dict(row) for row in rows if isinstance(row, dict)],
                    columns=list(component.get("columns") or []),
                    query=merged_query,
                )
            else:
                handler_name = str(data_source.get("handler") or "").strip()
                if not handler_name:
                    raise ValueError("query_handler 数据源必须提供 handler")
                result = self._normalize_inline_query_result(
                    self._bridge.call_query_handler(
                        handler_name,
                        str(component.get("table_id") or ""),
                        merged_query,
                        dict(self._navigation_params) if self._navigation_params else None,
                        page_id=self._page_id,
                    )
                )
        except Exception as exc:
            table.apply_error(request_id, str(exc))
            return
        result = self._attach_crud_row_actions(component, result)
        table.apply_result(request_id, result)

    def _build_section(self, component: dict[str, Any]) -> QWidget:
        variant = str(component.get("variant") or "group").strip().lower()
        if variant == "card":
            return self._build_card(component)

        frame = QFrame()
        styles = {
            "plain": "QFrame { background: transparent; border: none; }",
            "group": (
                "QFrame { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                " border-radius: 10px; }"
            ),
        }
        frame.setStyleSheet(styles.get(variant, styles["group"]))

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = str(component.get("title") or "").strip()
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("color: rgba(255,255,255,0.92); font-size: 15px; font-weight: 600;")
            layout.addWidget(title_label)

        layout.addWidget(self._build_layout_widget(component.get("children", []), component.get("layout", {})))
        return frame

    def _build_card(self, component: dict[str, Any]) -> QWidget:
        title = str(component.get("title") or "").strip()
        layout_spec = dict(component.get("layout") or {})
        min_height = component.get("min_height")
        padding = component.get("padding")
        card = Card(
            title=title,
            variant="card",
            gap=int(layout_spec.get("gap", 12)),
            title_align=str(component.get("title_align") or "left").strip().lower(),
            content_align=str(component.get("content_align") or "left").strip().lower(),
            content_vertical_align=str(component.get("content_vertical_align") or "top").strip().lower(),
            min_height=int(min_height) if min_height is not None else None,
            padding=int(padding) if padding is not None else (18, 16, 18, 16),
        )
        card.content_layout.addWidget(
            self._build_layout_widget(component.get("children", []), layout_spec)
        )
        return card

    def _build_component(self, component: dict[str, Any]) -> QWidget:
        component_type = str(component.get("type") or "").strip()
        if component_type == "Text":
            return self._build_text(component)
        if component_type == "Button":
            return self._build_button(component)
        if component_type == "Card":
            return self._build_card(component)
        if component_type == "Section":
            return self._build_section(component)
        if component_type == "DataTable":
            return self._build_data_table(component)
        fallback = QLabel(f"不支持的组件: {component_type or '<empty>'}")
        fallback.setStyleSheet("color: #f87171; font-size: 12px;")
        return fallback

    def _load_page_payload(self) -> dict[str, Any]:
        handler_name = str(self._schema.get("load_handler") or "").strip()
        if not handler_name:
            return {}
        params = dict(self._navigation_params) if self._navigation_params else None
        payload = self._bridge.call_page_handler(
            handler_name,
            self._page_id,
            params,
        )
        return payload if isinstance(payload, dict) else {}

    def _handle_button_action(self, action: dict[str, Any]) -> None:
        action_type = str(action.get("type") or "").strip()
        if action_type == "page_action":
            self._handle_page_action(action)
            return
        page_id = str(action.get("page_id") or "").strip()
        params = self._resolve_action_params(action, self._payload)
        self._open_page(page_id, params or None)

    def _handle_page_action(self, action: dict[str, Any]) -> None:
        action_name = str(action.get("name") or "").strip()
        if not action_name:
            return
        params = self._resolve_action_params(action, self._payload)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                self._bridge.call_page_action(
                    action_name,
                    params,
                    capability_surface=_runtime_surface_hosted_ui_action(),
                )
            except Exception as exc:
                MessageDialog.warning(self, "操作失败", str(exc))
            return

        task = loop.create_task(
            self._bridge.call_page_action_async(
                action_name,
                params,
                capability_surface=_runtime_surface_hosted_ui_action(),
            )
        )
        task.add_done_callback(self._handle_page_action_task_result)

    def _handle_page_action_task_result(self, task) -> None:
        try:
            task.result()
        except Exception as exc:
            MessageDialog.warning(self, "操作失败", str(exc))

    def _handle_row_action(self, action: dict[str, Any], row: dict[str, Any]) -> None:
        page_id = str(action.get("page_id") or "").strip()
        params = self._resolve_action_params(action, row)
        self._open_page(page_id, params or None)

    def _open_page(self, page_id: str, params: dict[str, Any] | None = None) -> None:
        if not self._open_page_callback:
            self._status_label.setText(f"未配置页面跳转处理器: {page_id}")
            return
        try:
            self._open_page_callback(page_id, params)
        except TypeError:
            self._open_page_callback(page_id)

    def refresh(self) -> None:
        self._status_label.setText("")
        self._data_table_widgets = {}
        try:
            self._bridge.declare_ui(
                page_id=self._page_id,
                params=dict(self._navigation_params) if self._navigation_params else None,
            )
            self._schema = self._bridge.get_declared_page(self._page_id)
            if not self._schema:
                raise ValueError(f"未声明页面 schema: {self._page_id}")
            self._payload = self._load_page_payload()
        except Exception as exc:
            self._schema = {}
            self._payload = {}
            self._apply_scroll_policy({})
            self._clear_content()
            self._content_layout.addWidget(QLabel(f"页面加载失败: {exc}"))
            self._status_label.setText(str(exc))
            return

        self._apply_scroll_policy(self._schema)
        self._clear_content()
        self._content_layout.addWidget(
            self._build_layout_widget(self._schema.get("children", []), self._schema.get("layout", {}))
        )
