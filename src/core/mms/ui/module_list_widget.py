"""模块列表组件。

显示已注册的模块及其状态。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import ModuleStatus, get_module_registry


class ModuleListWidget(QWidget):
    """模块列表组件。"""
    
    module_selected = pyqtSignal(str)
    
    COLUMNS = ["名称", "显示名", "版本", "状态", "操作"]
    STATUS_COLORS = {
        ModuleStatus.ENABLED: "#4ade80",
        ModuleStatus.DISABLED: "#9ca3af",
        ModuleStatus.INCOMPATIBLE: "#facc15",
        ModuleStatus.INVALID: "#f87171",
    }
    STATUS_TEXT = {
        ModuleStatus.ENABLED: "已启用",
        ModuleStatus.DISABLED: "已禁用",
        ModuleStatus.INCOMPATIBLE: "不兼容",
        ModuleStatus.INVALID: "无效",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("模块管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Loading 指示器
        self.loading_bar = QProgressBar()
        self.loading_bar.setMaximum(0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(3)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)
        
        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.8);
                color: white;
                border: none;
                gridline-color: rgba(255, 255, 255, 0.1);
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: rgba(50, 50, 60, 0.9);
                color: white;
                padding: 10px;
                border: none;
            }
        """)
        
        layout.addWidget(self.table)
        
        # 统计
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    def load_data(self):
        """加载模块数据。"""
        self.loading_bar.show()
        self.error_label.hide()
        
        try:
            registry = get_module_registry()
            modules = registry.list_modules()
            self._render_modules(modules)
        except Exception as e:
            self.loading_bar.hide()
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        
        self.loading_bar.hide()
    
    def _render_modules(self, modules: list):
        """渲染模块列表。"""
        self.table.setRowCount(0)
        
        enabled_count = 0
        for module in modules:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # 名称
            name_item = QTableWidgetItem(module.name)
            name_item.setData(Qt.ItemDataRole.UserRole, module.name)
            self.table.setItem(row, 0, name_item)
            
            # 显示名
            display = module.manifest.display_name or module.name
            self.table.setItem(row, 1, QTableWidgetItem(display))
            
            # 版本
            self.table.setItem(row, 2, QTableWidgetItem(module.manifest.version))
            
            # 状态
            status_text = self.STATUS_TEXT.get(module.status, module.status.value)
            status_item = QTableWidgetItem(status_text)
            if module.status in self.STATUS_COLORS:
                status_item.setForeground(QColor(self.STATUS_COLORS[module.status]))
            self.table.setItem(row, 3, status_item)
            
            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            
            if module.status == ModuleStatus.ENABLED:
                btn = QPushButton("禁用")
                btn.setStyleSheet("background: #f87171; color: white; border: none; padding: 4px 8px; border-radius: 2px;")
                btn.clicked.connect(lambda _, n=module.name: self._disable_module(n))
            else:
                btn = QPushButton("启用")
                btn.setStyleSheet("background: #4ade80; color: black; border: none; padding: 4px 8px; border-radius: 2px;")
                btn.clicked.connect(lambda _, n=module.name: self._enable_module(n))
            
            if module.status in {ModuleStatus.INVALID, ModuleStatus.INCOMPATIBLE}:
                btn.setEnabled(False)
            
            action_layout.addWidget(btn)
            self.table.setCellWidget(row, 4, action_widget)
            
            if module.status == ModuleStatus.ENABLED:
                enabled_count += 1
        
        self.stats_label.setText(f"共 {len(modules)} 个模块，{enabled_count} 个启用")
    
    def _enable_module(self, name: str):
        """启用模块。"""
        try:
            registry = get_module_registry()
            registry.enable_module(name)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启用失败: {e}")
    
    def _disable_module(self, name: str):
        """禁用模块。"""
        try:
            registry = get_module_registry()
            registry.disable_module(name)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"禁用失败: {e}")
    
    def _on_cell_clicked(self, row: int, col: int):
        name_item = self.table.item(row, 0)
        if name_item:
            module_name = name_item.data(Qt.ItemDataRole.UserRole)
            self.module_selected.emit(module_name)
