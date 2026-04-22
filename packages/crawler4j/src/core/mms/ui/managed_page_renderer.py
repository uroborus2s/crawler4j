"""模块宿主页最小渲染器。"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.mms.models import ModuleInfo
from src.core.mms.ui.module_ui_runtime import ModuleUIRuntimeBridge
from src.core.persistence import get_module_data_store
from src.ui.components.table import SkyTableWidget


class ManagedPageRenderer(QWidget):
    """渲染 `ui.declare_page` 声明的最小宿主页。"""

    def __init__(
        self,
        module_name: str,
        page_id: str,
        *,
        module_info: ModuleInfo | None = None,
        open_entry_callback: Callable[[str], Any] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._module_name = module_name
        self._page_id = page_id
        self._open_entry_callback = open_entry_callback
        self._bridge = ModuleUIRuntimeBridge(module_name, module_info=module_info)
        self._data_store = get_module_data_store()

        self._schema: dict[str, Any] = {}
        self._payload: dict[str, Any] = {}
        self._data_table_widgets: dict[str, SkyTableWidget] = {}

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)
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

    def _resolve_binding(self, binding: str) -> Any:
        current: Any = self._payload
        for part in binding.split("."):
            if isinstance(current, dict):
                current = current.get(part)
                continue
            return None
        return current

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

    def _build_button(self, component: dict[str, Any]) -> QPushButton:
        button = QPushButton(str(component.get("label") or "按钮"))
        button.setStyleSheet(
            """
            QPushButton {
                background: rgba(99, 102, 241, 0.75);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 0.95); }
            """
        )
        action = component.get("action", {})
        if action.get("type") == "reload":
            button.clicked.connect(self.refresh)
        else:
            entry = str(action.get("entry") or "").strip()
            button.clicked.connect(lambda _checked=False, target=entry: self._open_entry(target))
        return button

    def _build_data_table(self, component: dict[str, Any]) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = str(component.get("title") or "").strip()
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;")
            layout.addWidget(title_label)

        table = SkyTableWidget()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        rows = component.get("rows")
        binding = str(component.get("binding") or "").strip()
        if binding:
            bound_rows = self._resolve_binding(binding)
            if isinstance(bound_rows, list):
                rows = bound_rows
        if not isinstance(rows, list):
            rows = []

        columns = component.get("columns")
        if not isinstance(columns, list) or not columns:
            first_row = rows[0] if rows else {}
            columns = [
                {"key": str(key), "label": str(key)}
                for key in first_row.keys()
            ]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([str(column.get("label") or column.get("key")) for column in columns])
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            row_data = row if isinstance(row, dict) else {}
            for col_index, column in enumerate(columns):
                value = row_data.get(str(column.get("key") or ""), "")
                item = QTableWidgetItem("" if value is None else str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, col_index, item)

        table_key = title or f"table_{len(self._data_table_widgets) + 1}"
        self._data_table_widgets[table_key] = table
        layout.addWidget(table)

        if not rows:
            empty = QLabel(str(component.get("empty_text") or "暂无数据"))
            empty.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
            layout.addWidget(empty)

        return wrapper

    def _build_section(self, component: dict[str, Any]) -> QWidget:
        frame = QFrame()
        variant = str(component.get("variant") or "group").strip().lower()
        styles = {
            "plain": "QFrame { background: transparent; border: none; }",
            "group": (
                "QFrame { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
                " border-radius: 10px; }"
            ),
            "card": (
                "QFrame { background: rgba(20, 25, 40, 0.85); border: 1px solid rgba(99,102,241,0.22);"
                " border-radius: 12px; }"
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

    def _build_component(self, component: dict[str, Any]) -> QWidget:
        component_type = str(component.get("type") or "").strip()
        if component_type == "Text":
            return self._build_text(component)
        if component_type == "Button":
            return self._build_button(component)
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
        payload = self._bridge.call_local_hook(
            handler_name,
            self._page_id,
            None,
            runtime_extra={"page_id": self._page_id},
        )
        return payload if isinstance(payload, dict) else {}

    def _open_entry(self, entry: str) -> None:
        if not self._open_entry_callback:
            self._status_label.setText(f"未配置页面跳转处理器: {entry}")
            return
        self._open_entry_callback(entry)

    def refresh(self) -> None:
        self._status_label.setText("")
        self._data_table_widgets = {}
        try:
            self._bridge.declare_ui()
            self._schema = self._data_store.read_page_schema(self._module_name, self._page_id)
            if not self._schema:
                raise ValueError(f"未声明页面 schema: {self._page_id}")
            self._payload = self._load_page_payload()
        except Exception as exc:
            self._schema = {}
            self._payload = {}
            self._clear_content()
            self._content_layout.addWidget(QLabel(f"页面加载失败: {exc}"))
            self._status_label.setText(str(exc))
            return

        self._clear_content()
        self._content_layout.addWidget(
            self._build_layout_widget(self._schema.get("children", []), self._schema.get("layout", {}))
        )
