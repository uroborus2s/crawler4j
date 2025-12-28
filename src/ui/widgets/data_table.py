"""Data table widget.

A reusable table widget with pagination, search, and sorting.
"""


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DataTable(QWidget):
    """Reusable data table with pagination and search.
    
    Signals:
        row_clicked: Emitted when a row is clicked, with row data dict.
        row_double_clicked: Emitted when a row is double-clicked.
        selection_changed: Emitted when selection changes, with selected row indices.
    """
    
    row_clicked = pyqtSignal(dict)
    row_double_clicked = pyqtSignal(dict)
    selection_changed = pyqtSignal(list)
    
    def __init__(
        self,
        columns: list[tuple[str, str, int]],  # (key, header, width)
        parent=None,
    ):
        """Initialize the data table.
        
        Args:
            columns: List of (key, header_text, width) tuples.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.columns = columns
        self._data: list[dict] = []
        self._filtered_data: list[dict] = []
        self._page = 0
        self._page_size = 20
        self._search_text = ""
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the table UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索...")
        self.search_input.setMaximumWidth(250)
        toolbar.addWidget(self.search_input)
        
        toolbar.addStretch()
        
        # Page size selector
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["20", "50", "100"])
        self.page_size_combo.setMaximumWidth(80)
        toolbar.addWidget(QLabel("每页:"))
        toolbar.addWidget(self.page_size_combo)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels([col[1] for col in self.columns])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        
        # Set column widths
        header = self.table.horizontalHeader()
        for i, (_, _, width) in enumerate(self.columns):
            if width == -1:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self.table.setColumnWidth(i, width)
        
        layout.addWidget(self.table)
        
        # Pagination
        pagination = QHBoxLayout()
        pagination.setSpacing(8)
        
        self.info_label = QLabel("共 0 条")
        pagination.addWidget(self.info_label)
        
        pagination.addStretch()
        
        self.prev_btn = QPushButton("◀ 上一页")
        self.prev_btn.setMaximumWidth(100)
        pagination.addWidget(self.prev_btn)
        
        self.page_label = QLabel("1 / 1")
        self.page_label.setMinimumWidth(60)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页 ▶")
        self.next_btn.setMaximumWidth(100)
        pagination.addWidget(self.next_btn)
        
        layout.addLayout(pagination)
    
    def _connect_signals(self):
        """Connect internal signals."""
        self.search_input.textChanged.connect(self._on_search)
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_change)
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        self.table.cellClicked.connect(self._on_row_clicked)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_row_height(self, height: int):
        """Set the height of all rows."""
        self.table.verticalHeader().setDefaultSectionSize(height)
    
    def set_data(self, data: list[dict]):
        """Set the table data.
        
        Args:
            data: List of dictionaries, each representing a row.
        """
        self._data = data
        self._apply_filter()
    
    def _apply_filter(self):
        """Apply search filter and refresh display."""
        if self._search_text:
            search_lower = self._search_text.lower()
            self._filtered_data = [
                row for row in self._data
                if any(search_lower in str(v).lower() for v in row.values())
            ]
        else:
            self._filtered_data = self._data.copy()
        
        self._page = 0
        self._refresh_table()
    
    def _refresh_table(self):
        """Refresh the table display."""
        # Calculate pagination
        total = len(self._filtered_data)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        start = self._page * self._page_size
        end = min(start + self._page_size, total)
        page_data = self._filtered_data[start:end]
        
        # Update table
        self.table.setRowCount(len(page_data))
        for row_idx, row_data in enumerate(page_data):
            for col_idx, (key, _, _) in enumerate(self.columns):
                # Check for special render key in column definition? 
                # Or just check if key is a callable function in row_data? (No, mixing data and view logic)
                # Better: DataTable constructor accepts renderers.
                # BUT for now, let's allow 'actions' key to return a widget or a factory?
                # Simplify: if value is QWidget, setCellWidget. But we can't put QWidget in data list easily.
                
                # Let's rely on EnvironmentsPage to modify the table AFTER signal?
                # No, best is to allow columns definition to have a renderer.
                # Since I didn't change constructor signature, I'll check if key is 'actions'.
                
                if key == "actions" and "actions_renderer" in row_data:
                    # Expecting a factory/widget here is tricky with JSON data logic.
                    # Hack: The row_data['actions_renderer'] is a callable (self, row_data) -> QWidget
                    renderer = row_data["actions_renderer"]
                    if callable(renderer):
                        widget = renderer(row_data)
                        if widget:
                            self.table.setCellWidget(row_idx, col_idx, widget)
                            continue
                            
                value = row_data.get(key, "")
                item = QTableWidgetItem(str(value))
                self.table.setItem(row_idx, col_idx, item)
        
        # Update pagination info
        self.info_label.setText(f"共 {total} 条")
        self.page_label.setText(f"{self._page + 1} / {total_pages}")
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)
    
    def _on_search(self, text: str):
        """Handle search input change."""
        self._search_text = text
        self._apply_filter()
    
    def _on_page_size_change(self, text: str):
        """Handle page size change."""
        self._page_size = int(text)
        self._page = 0
        self._refresh_table()
    
    def _prev_page(self):
        """Go to previous page."""
        if self._page > 0:
            self._page -= 1
            self._refresh_table()
    
    def _next_page(self):
        """Go to next page."""
        total_pages = max(1, (len(self._filtered_data) + self._page_size - 1) // self._page_size)
        if self._page < total_pages - 1:
            self._page += 1
            self._refresh_table()
    
    def _on_row_clicked(self, row: int, col: int):
        """Handle row click."""
        row_data = self._get_row_data(row)
        if row_data:
            self.row_clicked.emit(row_data)
    
    def _on_row_double_clicked(self, row: int, col: int):
        """Handle row double click."""
        row_data = self._get_row_data(row)
        if row_data:
            self.row_double_clicked.emit(row_data)
    
    def _on_selection_changed(self):
        """Handle selection change."""
        selected = self.table.selectionModel().selectedRows()
        indices = [idx.row() for idx in selected]
        self.selection_changed.emit(indices)
    
    def _get_row_data(self, row: int) -> dict | None:
        """Get data for a specific row."""
        start = self._page * self._page_size
        data_idx = start + row
        if 0 <= data_idx < len(self._filtered_data):
            return self._filtered_data[data_idx]
        return None
    
    def get_selected_data(self) -> list[dict]:
        """Get data for all selected rows."""
        selected = []
        for idx in self.table.selectionModel().selectedRows():
            row_data = self._get_row_data(idx.row())
            if row_data:
                selected.append(row_data)
        return selected
    
    def refresh(self):
        """Refresh the table display."""
        self._refresh_table()
