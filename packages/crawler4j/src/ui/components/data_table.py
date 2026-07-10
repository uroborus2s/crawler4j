"""Shared pure-UI data table component."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.button import create_action_button
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.data_table_query import normalize_cell_value


class SkyDataTable(QWidget):
    """Unified pure-UI table with search, sort, pagination, and row events."""

    query_requested = pyqtSignal(int, dict)
    row_clicked = pyqtSignal(dict)
    row_action_requested = pyqtSignal(str, dict)
    selection_changed = pyqtSignal(list)

    DEFAULT_PAGE_SIZE_OPTIONS = [10, 20, 50, 100]
    DEFAULT_ROW_HEIGHT = 44
    ACTION_ROW_HEIGHT = 52

    def __init__(self, schema: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self._schema: dict[str, Any] = {}
        self._columns: list[dict[str, Any]] = []
        self._rows: list[dict[str, Any]] = []
        self._total = 0
        self._query: dict[str, Any] = {}
        self._latest_request_id = 0
        self._pending_request_id = 0
        self._loading = False
        self._error_message = ""
        self._filter_combos: dict[str, StyledComboBox] = {}
        self._filter_widgets: list[QWidget] = []
        self._syncing_controls = False

        self._setup_ui()
        self.set_schema(schema or {})

    def __getattr__(self, name: str):
        table = self.__dict__.get("table")
        if table is not None and hasattr(table, name):
            return getattr(table, name)
        raise AttributeError(f"{self.__class__.__name__!s} object has no attribute {name!r}")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)
        self.search_input = StyledLineEdit()
        self.search_input.setPlaceholderText("搜索…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMaximumWidth(280)
        self.search_input.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_input)
        toolbar.addStretch()

        self._sort_label = QLabel("排序")
        self._sort_label.setStyleSheet("color: rgba(255,255,255,0.64); font-size: 12px;")
        self.sort_field_combo = StyledComboBox()
        self.sort_field_combo.setMinimumWidth(136)
        self.sort_field_combo.currentIndexChanged.connect(self._on_sort_control_changed)
        self.sort_direction_combo = StyledComboBox()
        self.sort_direction_combo.setMinimumWidth(92)
        self.sort_direction_combo.currentIndexChanged.connect(self._on_sort_control_changed)
        for widget in (self._sort_label, self.sort_field_combo, self.sort_direction_combo):
            widget.hide()
            toolbar.addWidget(widget)

        self._toolbar = toolbar
        layout.addLayout(toolbar)

        self.loading_bar = QProgressBar()
        self.loading_bar.setFixedHeight(2)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet(
            """
            QProgressBar {
                background: transparent;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #60a5fa, stop:1 #22c55e);
            }
            """
        )
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #f87171; font-size: 12px;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        self._empty_label = QLabel("暂无数据")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: rgba(255,255,255,0.56); font-size: 12px; padding: 8px 0;")
        self._empty_label.hide()

        self.table = QTableWidget()
        self._apply_table_style()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.itemSelectionChanged.connect(self._emit_selection_changed)
        header = self.table.horizontalHeader()
        header.sectionClicked.connect(self._on_header_clicked)
        header.setSectionsClickable(True)
        layout.addWidget(self.table)
        layout.addWidget(self._empty_label)

        pagination = QHBoxLayout()
        pagination.setContentsMargins(0, 0, 0, 0)
        pagination.setSpacing(8)
        self.info_label = QLabel("共 0 条")
        self.info_label.setStyleSheet("color: rgba(255,255,255,0.56); font-size: 12px;")
        pagination.addWidget(self.info_label)
        pagination.addStretch()

        self.page_size_combo = StyledComboBox()
        self.page_size_combo.setMinimumWidth(92)
        self.page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)
        pagination.addWidget(self.page_size_combo)

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self._next_page)
        for button in (self.prev_btn, self.next_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                """
                QPushButton {
                    background: rgba(255,255,255,0.08);
                    color: white;
                    border: 1px solid rgba(255,255,255,0.12);
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background: rgba(96,165,250,0.22);
                    border-color: rgba(96,165,250,0.45);
                }
                QPushButton:disabled {
                    color: rgba(255,255,255,0.3);
                    background: rgba(255,255,255,0.03);
                    border-color: rgba(255,255,255,0.08);
                }
                """
            )
            pagination.addWidget(button)

        self.page_label = QLabel("1 / 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(72)
        self.page_label.setStyleSheet("color: rgba(255,255,255,0.78); font-size: 12px; font-weight: 600;")
        pagination.addWidget(self.page_label)

        self._pagination = pagination
        layout.addLayout(pagination)

    def _apply_table_style(self) -> None:
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self.DEFAULT_ROW_HEIGHT)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.85);
                alternate-background-color: rgba(40, 40, 50, 0.4);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                gridline-color: rgba(255, 255, 255, 0.05);
                selection-background-color: rgba(99, 102, 241, 0.3);
                selection-color: #ffffff;
                outline: none;
            }
            QTableWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            }
            QHeaderView::section {
                background-color: rgba(45, 45, 55, 0.95);
                color: rgba(255, 255, 255, 0.8);
                padding: 8px 12px;
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: 2px solid rgba(99, 102, 241, 0.3);
                font-weight: bold;
            }
            QHeaderView::section:vertical {
                background-color: rgba(50, 50, 60, 0.9);
                color: rgba(255, 255, 255, 0.5);
                border-right: 2px solid rgba(99, 102, 241, 0.2);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(30, 30, 40, 0.5);
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.1);
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

    def set_schema(self, schema: dict[str, Any]) -> None:
        self._schema = self._normalize_schema(schema)
        self._columns = list(self._schema.get("columns", []))
        self._configure_columns()
        self._configure_feature_widgets()
        self.set_query(self._build_default_query())
        self._render_rows()

    def _normalize_schema(self, raw: dict[str, Any]) -> dict[str, Any]:
        columns: list[dict[str, Any]] = []
        for column in raw.get("columns", []) if isinstance(raw, dict) else []:
            if not isinstance(column, dict):
                continue
            key = str(column.get("key") or "").strip()
            if not key:
                continue
            column_type = str(column.get("type") or "text").strip().lower()
            columns.append(
                {
                    "key": key,
                    "label": str(column.get("label") or key).strip() or key,
                    "type": column_type,
                    "sortable": column_type != "actions" and column.get("sortable") is True,
                    "searchable": column_type != "actions" and column.get("searchable") is True,
                    "width": int(column["width"]) if column.get("width") is not None else None,
                    "stretch": bool(column.get("stretch", False)),
                    "align": str(column.get("align") or "left").strip().lower(),
                    "options": [str(option) for option in column.get("options") or []]
                    if column_type == "select"
                    else [],
                }
            )

        features = raw.get("features") if isinstance(raw, dict) else {}
        if not isinstance(features, dict):
            features = {}

        search_feature = features.get("search")
        if not isinstance(search_feature, dict):
            search_feature = {}
        sort_feature = features.get("sort")
        if not isinstance(sort_feature, dict):
            sort_feature = {}
        pagination_feature = features.get("pagination")
        if not isinstance(pagination_feature, dict):
            pagination_feature = {}
        loading_feature = features.get("loading")
        if not isinstance(loading_feature, dict):
            loading_feature = {}

        selection_mode = str(raw.get("selection_mode") or "single").strip().lower() if isinstance(raw, dict) else "single"
        if selection_mode not in {"none", "single", "multi"}:
            selection_mode = "single"

        has_action_column = any(column["type"] == "actions" for column in columns)
        default_row_height = self.ACTION_ROW_HEIGHT if has_action_column else self.DEFAULT_ROW_HEIGHT
        if isinstance(raw, dict) and raw.get("row_height") is not None:
            row_height = int(raw.get("row_height", default_row_height))
        else:
            row_height = default_row_height
        if has_action_column:
            row_height = max(row_height, self.ACTION_ROW_HEIGHT)

        return {
            "columns": columns,
            "row_height": row_height,
            "empty_text": str(raw.get("empty_text") or "暂无数据").strip() if isinstance(raw, dict) else "暂无数据",
            "selection_mode": selection_mode,
            "features": {
                "search": {
                    "enabled": bool(search_feature.get("enabled", True)),
                    "placeholder": str(search_feature.get("placeholder") or "搜索…").strip() or "搜索…",
                },
                "sort": {
                    "enabled": bool(sort_feature.get("enabled", True)),
                    "default": list(sort_feature.get("default") or []),
                },
                "pagination": {
                    "enabled": bool(pagination_feature.get("enabled", True)),
                    "page_size": max(1, int(pagination_feature.get("page_size", 20))),
                    "page_size_options": [
                        max(1, int(option))
                        for option in (pagination_feature.get("page_size_options") or self.DEFAULT_PAGE_SIZE_OPTIONS)
                    ],
                },
                "loading": {
                    "inline": bool(loading_feature.get("inline", True)),
                    "disable_interaction": bool(loading_feature.get("disable_interaction", True)),
                },
            },
        }

    def _build_default_query(self) -> dict[str, Any]:
        pagination = self._schema["features"]["pagination"]
        return {
            "search_text": "",
            "sort": list(self._schema["features"]["sort"]["default"]),
            "page": 1,
            "page_size": int(pagination["page_size"]),
            "params": {},
        }

    def _configure_feature_widgets(self) -> None:
        search_feature = self._schema["features"]["search"]
        pagination = self._schema["features"]["pagination"]
        self.search_input.setVisible(bool(search_feature["enabled"]))
        self.search_input.setPlaceholderText(str(search_feature["placeholder"]))
        self._configure_filter_controls()
        self._configure_sort_controls()

        options = list(dict.fromkeys(pagination["page_size_options"]))
        if int(pagination["page_size"]) not in options:
            options.append(int(pagination["page_size"]))
        options.sort()
        self.page_size_combo.blockSignals(True)
        self.page_size_combo.clear()
        for option in options:
            self.page_size_combo.addItem(f"{option} / 页", option)
        index = self.page_size_combo.findData(int(pagination["page_size"]))
        if index >= 0:
            self.page_size_combo.setCurrentIndex(index)
        self.page_size_combo.blockSignals(False)
        pagination_visible = bool(pagination["enabled"])
        self.page_size_combo.setVisible(pagination_visible)
        self.prev_btn.setVisible(pagination_visible)
        self.next_btn.setVisible(pagination_visible)
        self.page_label.setVisible(pagination_visible)
        self.loading_bar.setVisible(bool(self._loading and self._schema["features"]["loading"]["inline"]))

    def _configure_filter_controls(self) -> None:
        self._clear_filter_controls()
        for column in self._select_filter_columns():
            label = QLabel(str(column["label"]))
            label.setStyleSheet("color: rgba(255,255,255,0.64); font-size: 12px;")
            combo = StyledComboBox()
            combo.setMinimumWidth(120)
            options = list(column.get("options") or [])
            if not any(self._is_all_filter_value(option) for option in options):
                combo.addItem("全部", None)
            for option in options:
                combo.addItem(str(option), option)
            combo.currentIndexChanged.connect(self._on_filter_changed)
            self._insert_filter_widget(label)
            self._insert_filter_widget(combo)
            self._filter_combos[str(column["key"])] = combo

    def _clear_filter_controls(self) -> None:
        for widget in self._filter_widgets:
            self._toolbar.removeWidget(widget)
            widget.deleteLater()
        self._filter_widgets = []
        self._filter_combos = {}

    def _insert_filter_widget(self, widget: QWidget) -> None:
        insert_at = self._toolbar.count()
        for index in range(self._toolbar.count()):
            item = self._toolbar.itemAt(index)
            if item is not None and item.spacerItem() is not None:
                insert_at = index
                break
        self._toolbar.insertWidget(insert_at, widget)
        self._filter_widgets.append(widget)

    def _select_filter_columns(self) -> list[dict[str, Any]]:
        return [
            column
            for column in self._columns
            if column.get("type") == "select" and column.get("searchable") is True and column.get("options")
        ]

    def _configure_sort_controls(self) -> None:
        sortable_columns = self._sortable_columns()
        visible = bool(self._schema["features"]["sort"]["enabled"] and sortable_columns)
        for widget in (self._sort_label, self.sort_field_combo, self.sort_direction_combo):
            widget.setVisible(visible)

        self._syncing_controls = True
        self.sort_field_combo.blockSignals(True)
        self.sort_direction_combo.blockSignals(True)
        try:
            self.sort_field_combo.clear()
            self.sort_field_combo.addItem("默认排序", "")
            for column in sortable_columns:
                self.sort_field_combo.addItem(str(column["label"]), str(column["key"]))

            self.sort_direction_combo.clear()
            self.sort_direction_combo.addItem("升序", "asc")
            self.sort_direction_combo.addItem("降序", "desc")
        finally:
            self.sort_direction_combo.blockSignals(False)
            self.sort_field_combo.blockSignals(False)
            self._syncing_controls = False

        self._sync_sort_controls()

    def _sortable_columns(self) -> list[dict[str, Any]]:
        return [
            column
            for column in self._columns
            if column.get("type") != "actions" and column.get("sortable") is True
        ]

    def _configure_columns(self) -> None:
        self.table.setColumnCount(len(self._columns))
        self._update_header_labels()
        self.table.verticalHeader().setDefaultSectionSize(int(self._schema.get("row_height", 44)))
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for index, column in enumerate(self._columns):
            if column["stretch"]:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
                continue
            if column["width"] is not None:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)
                self.table.setColumnWidth(index, int(column["width"]))
                continue
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)

        selection_mode = self._schema.get("selection_mode", "single")
        if selection_mode == "none":
            self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        elif selection_mode == "multi":
            self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def _update_header_labels(self) -> None:
        current_sort = self._current_sort()
        labels: list[str] = []
        for column in self._columns:
            label = str(column["label"])
            if current_sort and column["key"] == current_sort["field"]:
                label = f"{label} {'↑' if current_sort['direction'] == 'asc' else '↓'}"
            labels.append(label)
        self.table.setHorizontalHeaderLabels(labels)

    def set_query(self, query: dict[str, Any]) -> None:
        current = self._build_default_query()
        current.update(self._query or {})
        incoming = dict(query or {})
        current["search_text"] = str(incoming.get("search_text", current["search_text"]) or "")
        current["sort"] = list(incoming.get("sort", current["sort"]) or [])
        current["page"] = max(1, int(incoming.get("page", current["page"])))
        current["page_size"] = max(1, int(incoming.get("page_size", current["page_size"])))
        current["params"] = dict(incoming.get("params", current.get("params", {})) or {})
        self._query = current

        self.search_input.blockSignals(True)
        self.search_input.setText(current["search_text"])
        self.search_input.blockSignals(False)

        index = self.page_size_combo.findData(current["page_size"])
        if index >= 0:
            self.page_size_combo.blockSignals(True)
            self.page_size_combo.setCurrentIndex(index)
            self.page_size_combo.blockSignals(False)

        self._sync_filter_controls()
        self._sync_sort_controls()
        self._update_header_labels()
        self._update_pagination_labels()

    def request_refresh(self) -> None:
        self.table.clearSelection()
        self._latest_request_id += 1
        self._pending_request_id = self._latest_request_id
        self.set_loading(True)
        self._error_message = ""
        self._error_label.hide()
        self.query_requested.emit(self._pending_request_id, dict(self._query))

    def refresh(self) -> None:
        self.request_refresh()

    def apply_result(self, request_id: int, result: dict[str, Any]) -> None:
        if request_id != self._pending_request_id:
            return

        rows = result.get("rows") if isinstance(result, dict) else []
        if not isinstance(rows, list):
            rows = []
        self._rows = [dict(row) for row in rows if isinstance(row, dict)]
        self._total = max(0, int(result.get("total", len(self._rows)))) if isinstance(result, dict) else len(self._rows)
        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": result.get("sort", self._query.get("sort", [])) if isinstance(result, dict) else self._query.get("sort", []),
                "page": result.get("page", self._query.get("page", 1)) if isinstance(result, dict) else self._query.get("page", 1),
                "page_size": result.get("page_size", self._query.get("page_size", 20)) if isinstance(result, dict) else self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.set_loading(False)
        self._render_rows()

    def apply_error(self, request_id: int, message: str) -> None:
        if request_id != self._pending_request_id:
            return
        self.set_loading(False)
        self._error_message = str(message or "").strip() or "加载失败"
        self._error_label.setText(self._error_message)
        self._error_label.show()

    def show_error(self, message: str) -> None:
        self._error_message = str(message or "").strip() or "加载失败"
        self.set_loading(False)
        self._error_label.setText(self._error_message)
        self._error_label.show()

    def set_loading(self, loading: bool) -> None:
        self._loading = bool(loading)
        loading_feature = self._schema["features"]["loading"]
        if self._loading and bool(loading_feature["inline"]):
            self.loading_bar.setMaximum(0)
            self.loading_bar.show()
        else:
            self.loading_bar.hide()
        self.table.setEnabled(not self._loading or not bool(loading_feature["disable_interaction"]))
        self._empty_label.setVisible(not self._loading and not self._rows)

    def selected_row(self) -> dict[str, Any] | None:
        selected_rows = self.selected_rows()
        return selected_rows[0] if selected_rows else None

    def selected_rows(self) -> list[dict[str, Any]]:
        selection_model = self.table.selectionModel()
        if selection_model is None:
            return []
        selected: list[dict[str, Any]] = []
        for model_index in selection_model.selectedRows():
            row_index = int(model_index.row())
            if 0 <= row_index < len(self._rows):
                selected.append(self._rows[row_index])
        return selected

    def displayed_rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def _render_rows(self) -> None:
        self.table.setRowCount(len(self._rows))
        self.table.clearContents()
        row_height = int(self._schema.get("row_height", self.DEFAULT_ROW_HEIGHT))
        for row_index, row in enumerate(self._rows):
            self.table.setRowHeight(row_index, row_height)
            for column_index, column in enumerate(self._columns):
                self._render_cell(row_index, column_index, column, row)
        self._empty_label.setText(str(self._schema.get("empty_text") or "暂无数据"))
        self._empty_label.setVisible(not self._loading and not self._rows)
        self._update_pagination_labels()

    def _render_cell(self, row_index: int, column_index: int, column: dict[str, Any], row: dict[str, Any]) -> None:
        key = str(column["key"])
        column_type = str(column["type"])
        value = row.get(key)
        if column_type == "actions":
            self.table.setCellWidget(row_index, column_index, self._build_actions_widget(row_index, row, value))
            return

        cell = normalize_cell_value(value, column_type=column_type)
        item = QTableWidgetItem(str(cell["text"]))
        tooltip = str(cell.get("tooltip") or "").strip()
        if tooltip:
            item.setToolTip(tooltip)
        item.setTextAlignment(self._alignment_for_column(column))
        self._apply_tone(item, str(cell.get("tone") or ""))
        self.table.setItem(row_index, column_index, item)

    def _build_actions_widget(self, row_index: int, row: dict[str, Any], value: Any) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        actions = value if isinstance(value, list) else []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_id = str(action.get("id") or "").strip()
            if not action_id:
                continue
            button = create_action_button(
                str(action.get("label") or action_id),
                variant=str(action.get("variant") or "secondary"),
            )
            button.setEnabled(bool(action.get("enabled", True)))
            tooltip = str(action.get("tooltip") or "").strip()
            if tooltip:
                button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _checked=False, idx=row_index, action_name=action_id, row_payload=dict(row): self._on_action_clicked(
                    idx,
                    action_name,
                    row_payload,
                )
            )
            layout.addWidget(button)
        layout.addStretch()
        return widget

    def _apply_tone(self, item: QTableWidgetItem, tone: str) -> None:
        if not tone:
            return
        palette = {
            "success": "#4ade80",
            "warning": "#facc15",
            "danger": "#f87171",
            "info": "#60a5fa",
            "neutral": "#cbd5e1",
            "accent": "#a78bfa",
        }
        color = palette.get(tone)
        if color:
            item.setForeground(QColor(color))
        font = QFont(item.font())
        font.setBold(True)
        item.setFont(font)

    def _alignment_for_column(self, column: dict[str, Any]) -> Qt.AlignmentFlag:
        align = str(column.get("align") or "left").lower()
        if align == "center":
            return Qt.AlignmentFlag.AlignCenter
        if align == "right":
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    def _on_search_changed(self, text: str) -> None:
        self.set_query(
            {
                "search_text": str(text or ""),
                "sort": self._query.get("sort", []),
                "page": 1,
                "page_size": self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _on_filter_changed(self) -> None:
        if self._syncing_controls:
            return
        params = dict(self._query.get("params") or {})
        for field in self._filter_combos:
            params.pop(field, None)
        for field, combo in self._filter_combos.items():
            value = combo.currentData()
            if value is None:
                value = combo.currentText().strip()
            if self._is_all_filter_value(value):
                continue
            params[field] = value

        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": self._query.get("sort", []),
                "page": 1,
                "page_size": self._query.get("page_size", 20),
                "params": params,
            }
        )
        self.request_refresh()

    def _on_sort_control_changed(self) -> None:
        if self._syncing_controls:
            return
        field = str(self.sort_field_combo.currentData() or "").strip()
        if not field and self.sender() is self.sort_direction_combo:
            return
        direction = str(self.sort_direction_combo.currentData() or "asc").strip().lower()
        if direction not in {"asc", "desc"}:
            direction = "asc"
        next_sort = [{"field": field, "direction": direction}] if field else []
        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": next_sort,
                "page": 1,
                "page_size": self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _on_page_size_changed(self) -> None:
        page_size = self.page_size_combo.currentData()
        if page_size is None:
            return
        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": self._query.get("sort", []),
                "page": 1,
                "page_size": int(page_size),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _prev_page(self) -> None:
        if int(self._query.get("page", 1)) <= 1:
            return
        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": self._query.get("sort", []),
                "page": int(self._query.get("page", 1)) - 1,
                "page_size": self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _next_page(self) -> None:
        total_pages = self._total_pages()
        if int(self._query.get("page", 1)) >= total_pages:
            return
        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": self._query.get("sort", []),
                "page": int(self._query.get("page", 1)) + 1,
                "page_size": self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _on_header_clicked(self, section: int) -> None:
        if section < 0 or section >= len(self._columns):
            return
        if not self._schema["features"]["sort"]["enabled"]:
            return
        column = self._columns[section]
        if not column.get("sortable", False):
            return

        current_sort = self._current_sort()
        next_sort: list[dict[str, Any]]
        if current_sort and current_sort["field"] == column["key"]:
            if current_sort["direction"] == "asc":
                next_sort = [{"field": column["key"], "direction": "desc"}]
            else:
                next_sort = []
        else:
            next_sort = [{"field": column["key"], "direction": "asc"}]

        self.set_query(
            {
                "search_text": self._query.get("search_text", ""),
                "sort": next_sort,
                "page": 1,
                "page_size": self._query.get("page_size", 20),
                "params": self._query.get("params", {}),
            }
        )
        self.request_refresh()

    def _current_sort(self) -> dict[str, Any] | None:
        sort_specs = self._query.get("sort")
        if not isinstance(sort_specs, list) or not sort_specs:
            return None
        first = sort_specs[0]
        if not isinstance(first, dict):
            return None
        field = str(first.get("field") or "").strip()
        direction = str(first.get("direction") or "asc").strip().lower()
        if not field or direction not in {"asc", "desc"}:
            return None
        return {"field": field, "direction": direction}

    def _sync_filter_controls(self) -> None:
        if not self._filter_combos:
            return
        params = dict(self._query.get("params") or {})
        self._syncing_controls = True
        try:
            for field, combo in self._filter_combos.items():
                value = params.get(field)
                index = self._find_filter_combo_index(combo, value)
                combo.blockSignals(True)
                try:
                    if index < 0 and value is not None:
                        combo.addItem(str(value), value)
                        index = combo.findData(value)
                    combo.setCurrentIndex(max(0, index))
                finally:
                    combo.blockSignals(False)
        finally:
            self._syncing_controls = False

    def _sync_sort_controls(self) -> None:
        self._syncing_controls = True
        self.sort_field_combo.blockSignals(True)
        self.sort_direction_combo.blockSignals(True)
        try:
            current_sort = self._current_sort()
            field = str(current_sort.get("field") if current_sort else "")
            direction = str(current_sort.get("direction") if current_sort else "asc")

            field_index = self.sort_field_combo.findData(field)
            self.sort_field_combo.setCurrentIndex(field_index if field_index >= 0 else 0)

            direction_index = self.sort_direction_combo.findData(direction)
            self.sort_direction_combo.setCurrentIndex(direction_index if direction_index >= 0 else 0)
        finally:
            self.sort_direction_combo.blockSignals(False)
            self.sort_field_combo.blockSignals(False)
            self._syncing_controls = False

    def _find_filter_combo_index(self, combo: StyledComboBox, value: Any) -> int:
        if self._is_all_filter_value(value):
            for index in range(combo.count()):
                if self._is_all_filter_value(combo.itemData(index)):
                    return index
                if self._is_all_filter_value(combo.itemText(index)):
                    return index
            return 0
        index = combo.findData(value)
        if index >= 0:
            return index
        value_text = str(value)
        for index in range(combo.count()):
            if combo.itemText(index) == value_text:
                return index
        return -1

    @staticmethod
    def _is_all_filter_value(value: Any) -> bool:
        if value is None:
            return True
        return str(value).strip().lower() in {"", "不限", "全部", "all", "__all__"}

    def _update_pagination_labels(self) -> None:
        total_pages = self._total_pages()
        current_page = min(max(1, int(self._query.get("page", 1))), total_pages)
        self.info_label.setText(f"共 {self._total} 条")
        self.page_label.setText(f"{current_page} / {total_pages}")
        self.prev_btn.setEnabled(current_page > 1)
        self.next_btn.setEnabled(current_page < total_pages)

    def _total_pages(self) -> int:
        page_size = max(1, int(self._query.get("page_size", 20)))
        return max(1, (int(self._total) + page_size - 1) // page_size)

    def _on_cell_clicked(self, row_index: int, _column_index: int) -> None:
        if 0 <= row_index < len(self._rows):
            self.row_clicked.emit(self._rows[row_index])

    def _on_action_clicked(self, row_index: int, action_id: str, row_payload: dict[str, Any]) -> None:
        self.table.selectRow(row_index)
        self.row_action_requested.emit(action_id, row_payload)
        self._emit_selection_changed()

    def _emit_selection_changed(self) -> None:
        self.selection_changed.emit(self.selected_rows())
