"""Minimal hosted page renderer."""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.mms.models import ModuleInfo
from src.core.mms.ui.module_ui_runtime import ModuleUIRuntimeBridge
from src.core.persistence import get_module_data_store
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result


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
        self._data_store = get_module_data_store()

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
            button.clicked.connect(lambda _checked=False, current_action=dict(action): self._handle_button_action(current_action))
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

        table = SkyDataTable(
            {
                "columns": list(component.get("columns") or []),
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

        table.set_query({"params": dict(self._navigation_params)})
        table.request_refresh()

        table_id = str(component.get("table_id") or title or f"table_{len(self._data_table_widgets) + 1}")
        self._data_table_widgets[table_id] = table
        layout.addWidget(table)
        return wrapper

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
            else:
                handler_name = str(data_source.get("handler") or "").strip()
                if not handler_name:
                    raise ValueError("query_handler 数据源必须提供 handler")
                result = self._normalize_inline_query_result(
                    self._bridge.call_local_hook(
                        handler_name,
                        str(component.get("table_id") or ""),
                        merged_query,
                        dict(self._navigation_params) if self._navigation_params else None,
                        runtime_extra={
                            "page_id": self._page_id,
                            "table_id": str(component.get("table_id") or ""),
                            "params": dict(self._navigation_params) if self._navigation_params else None,
                        },
                    )
                )
        except Exception as exc:
            table.apply_error(request_id, str(exc))
            return
        table.apply_result(request_id, result)

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
        params = dict(self._navigation_params) if self._navigation_params else None
        payload = self._bridge.call_local_hook(
            handler_name,
            self._page_id,
            params,
            runtime_extra={
                "page_id": self._page_id,
                "params": params,
            },
        )
        return payload if isinstance(payload, dict) else {}

    def _handle_button_action(self, action: dict[str, Any]) -> None:
        page_id = str(action.get("page_id") or "").strip()
        params = self._resolve_action_params(action, self._payload)
        self._open_page(page_id, params or None)

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
            self._bridge.call_local_hook(
                "declare_ui",
                runtime_extra={
                    "page_id": self._page_id,
                    "params": dict(self._navigation_params) if self._navigation_params else None,
                },
            )
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
