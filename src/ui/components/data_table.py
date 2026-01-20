"""高级数据表格组件 (SkyDataTable)。

包装了 SkyTableWidget，提供统一的：
- 搜索栏
- 分页控件
- 加载状态
- 操作栏
- 统一样式

Usage:
    table = SkyDataTable(
        columns=[("name", "名称", -1), ("status", "状态", 100)]
    )
    table.set_data(data_list)
    table.search_changed.connect(on_search)
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.table import SkyTableWidget


class SkyDataTable(QWidget):
    """带搜索和分页的高级数据表格。"""

    # 信号
    search_changed = pyqtSignal(str)   # 搜索文本改变
    page_changed = pyqtSignal(int)     # 页码改变
    refresh_requested = pyqtSignal()   # 请求刷新
    
    # 转发 table 信号
    cell_clicked = pyqtSignal(int, int)

    def __init__(self, columns: list[tuple[str, str, int | None]] = None, parent=None):
        """初始化。
        
        Args:
            columns: 列定义列表 [(key, label, width), ...] width=-1 for stretch
            parent: 父组件
        """
        super().__init__(parent)
        self._columns = columns or []
        self._data = []        # 所有数据 (原始)
        self._display_data = [] #当前页显示的数据
        self._filtered_data = [] # 搜索过滤后的数据
        
        self._page = 0
        self._page_size = 20
        self._search_text = ""
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. 工具栏 (Toolbar)
        self.toolbar = QHBoxLayout()
        self.toolbar.setSpacing(12)
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                padding: 6px 12px;
                color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(99, 102, 241, 0.6);
            }
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.setMaximumWidth(250)
        self.toolbar.addWidget(self.search_input)
        
        # 弹性空间，用于插入自定义按钮
        self.toolbar.addStretch()
        
        # 刷新按钮 (默认隐藏，由外部决定是否添加)
        # self.refresh_btn = QPushButton("🔄")
        
        layout.addLayout(self.toolbar)

        # 2. 进度条
        self.loading_bar = QProgressBar()
        self.loading_bar.setFixedHeight(2)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                background: transparent;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #a855f7);
            }
        """)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)

        # 3. 表格主体
        self.table = SkyTableWidget()
        if self._columns:
            self._setup_columns()
            
        self.table.cellClicked.connect(self.cell_clicked)
        layout.addWidget(self.table)
        
        # 4. 分页栏
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        
        # 统计信息
        self.info_label = QLabel("共 0 条")
        self.info_label.setStyleSheet("color: rgba(255, 255, 255, 0.5); font-size: 12px;")
        self.pagination_layout.addWidget(self.info_label)
        
        self.pagination_layout.addStretch()
        
        # 分页控件
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(32, 32)
        self.prev_btn.clicked.connect(self._prev_page)
        self._style_page_btn(self.prev_btn)
        self.pagination_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("1 / 1")
        self.page_label.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-weight: bold; padding: 0 8px;")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(60)
        self.pagination_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(32, 32)
        self.next_btn.clicked.connect(self._next_page)
        self._style_page_btn(self.next_btn)
        self.pagination_layout.addWidget(self.next_btn)
        
        layout.addLayout(self.pagination_layout)

    def _setup_columns(self):
        self.table.setColumnCount(len(self._columns))
        labels = [col[1] for col in self._columns]
        self.table.setHorizontalHeaderLabels(labels)
        
        header = self.table.horizontalHeader()
        if header:
            for i, (_, _, width) in enumerate(self._columns):
                if width == -1 or width is None:
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                else:
                    # Interactive 模式允许用户拖动调整列宽
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                    self.table.setColumnWidth(i, width)

    def _style_page_btn(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.5);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 0.3);
                border-color: rgba(99, 102, 241, 0.5);
            }
            QPushButton:disabled {
                background: transparent;
                color: rgba(255, 255, 255, 0.1);
                border-color: rgba(255, 255, 255, 0.05);
            }
        """)

    # --- Public API ---

    def set_loading(self, loading: bool):
        """设置加载状态。"""
        if loading:
            self.loading_bar.setMaximum(0) # Marquee mode
            self.loading_bar.show()
            self.table.setEnabled(False)
        else:
            self.loading_bar.hide()
            self.table.setEnabled(True)

    def set_data(self, data: list):
        """设置数据并刷新。
        
        Args:
            data: 数据列表 (dict 或 object)
        """
        self._data = data
        self._apply_filter_and_paging()

    def refresh(self):
        """手动刷新当前显示。"""
        self._apply_filter_and_paging()

    def add_widget_to_toolbar(self, widget: QWidget):
        """向工具栏添加自定义控件 (例如新建按钮)。"""
        # 插入到 stretch 之前 (index - 2 目前是 search, stretch)
        # 实际上我们希望 search 在左，Custom Action 在右
        # Toolbar layout: [Search Input] [Stretch] [Custom Actions...]
        self.toolbar.addWidget(widget)

    # --- Internal Logic ---

    def _on_search_changed(self, text: str):
        self._search_text = text.strip().lower()
        self._page = 0
        self._apply_filter_and_paging()
        self.search_changed.emit(text)

    def _apply_filter_and_paging(self):
        # 1. Client-side Filtering
        if not self._search_text:
            self._filtered_data = self._data
        else:
            self._filtered_data = []
            for item in self._data:
                # Naive generic search: verify against all values if dict, or __str__
                param_str = ""
                if isinstance(item, dict):
                    param_str = " ".join([str(v) for v in item.values()])
                else:
                    # Try to search common attrs? Or just str(item)
                    # For objects, maybe we rely on __str__ or specific fields
                    # Let's try explicit attributes if object
                    try:
                        param_str = f"{getattr(item, 'name', '')} {getattr(item, 'id', '')} {str(item)}"
                    except:
                        param_str = str(item)
                
                if self._search_text in param_str.lower():
                    self._filtered_data.append(item)

        # 2. Pagination
        total = len(self._filtered_data)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        
        # Ensure page range
        # self._page is 0-indexed
        if self._page >= total_pages:
            self._page = total_pages - 1
        if self._page < 0:
            self._page = 0
            
        start = self._page * self._page_size
        end = start + self._page_size
        self._display_data = self._filtered_data[start:end]

        # 3. Update UI Controls
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < total_pages - 1)
        self.page_label.setText(f"{self._page + 1} / {total_pages}")
        self.info_label.setText(f"共 {total} 条")

        # 4. Render Table
        self._render_table()

    def set_render_callback(self, callback):
        """设置行渲染回调函数。
        
        Args:
            callback: (row_index: int, data_item: Any, table: SkyTableWidget) -> None
        """
        self._render_callback = callback

    def _render_table(self):
        """渲染表格。"""
        if not hasattr(self, '_render_callback') or not self._render_callback:
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(self._display_data))
        
        for i, item in enumerate(self._display_data):
            self._render_callback(i, item, self.table)
    
    def item(self, row: int, column: int) -> QTableWidgetItem | None:
        """获取单元格项 (代理)。"""
        return self.table.item(row, column)

    def rowCount(self) -> int:
        """获取行数 (代理)。"""
        return self.table.rowCount()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._apply_filter_and_paging()
            self.page_changed.emit(self._page)
            
    def _next_page(self):
        self._page += 1
        self._apply_filter_and_paging()
        self.page_changed.emit(self._page)
