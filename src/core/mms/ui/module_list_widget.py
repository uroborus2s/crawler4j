"""模块列表页。

全屏表格显示模块列表，点击详情按钮进入模块详情页。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFileDialog,
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

from src.core.mms import ModuleSource, ModuleStatus, get_module_registry
from src.core.mms.models import ModuleInfo
from src.core.mms.ui.install_preview_dialog import InstallPreviewDialog


class ModuleListWidget(QWidget):
    """模块列表页。
    
    全屏展示模块表格，点击"详情"跳转到详情页。
    """
    
    open_detail = pyqtSignal(object)  # 打开详情页信号 (ModuleInfo)
    
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
        self._modules: list[ModuleInfo] = []
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
        
        # 安装按钮
        self.install_btn = QPushButton("📥 安装模块")
        self.install_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
        """)
        self.install_btn.clicked.connect(self._install_module)
        header.addWidget(self.install_btn)
        
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
        
        # 隐藏垂直表头
        vh = self.table.verticalHeader()
        if vh:
            vh.hide()
        
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(4, 180)
        
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.8);
                color: white;
                border: none;
                gridline-color: rgba(255, 255, 255, 0.1);
            }
            QTableWidget::item { 
                padding: 8px;
            }
            QHeaderView::section {
                background-color: rgba(50, 50, 60, 0.9);
                color: white;
                padding: 10px;
                border: none;
            }
            QTableCornerButton::section {
                background-color: rgba(50, 50, 60, 0.9);
                border: none;
            }
            QHeaderView {
                background-color: transparent;
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
            self._modules = modules
            self._render_modules(modules)
        except Exception as e:
            self.loading_bar.hide()
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        
        self.loading_bar.hide()
    
    def _render_modules(self, modules: list[ModuleInfo]):
        """渲染模块列表。"""
        self.table.setRowCount(0)
        
        # 垂直表头样式在 setStyleSheet 中处理
        if self.table.verticalHeader():
            self.table.verticalHeader().show()
        
        enabled_count = 0
        for module in modules:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 52)
            
            # 名称
            name_item = QTableWidgetItem(module.name)
            name_item.setData(Qt.ItemDataRole.UserRole, module)  # 存储模块对象
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
            action_widget = self._create_action_widget(module)
            self.table.setCellWidget(row, 4, action_widget)
            
            if module.status == ModuleStatus.ENABLED:
                enabled_count += 1
        
        self.stats_label.setText(f"共 {len(modules)} 个模块，{enabled_count} 个启用")
    
    def _create_action_widget(self, module: ModuleInfo) -> QWidget:
        """创建操作按钮组。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        
        # 详情按钮
        detail_btn = QPushButton("详情 →")
        detail_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        detail_btn.clicked.connect(lambda _, m=module: self.open_detail.emit(m))
        layout.addWidget(detail_btn)
        
        # 启用/禁用按钮
        if module.status == ModuleStatus.ENABLED:
            toggle_btn = QPushButton("禁用")
            toggle_btn.setStyleSheet("background: #f87171; color: white; border: none; padding: 5px 8px; border-radius: 3px;")
            toggle_btn.clicked.connect(lambda _, n=module.name: self._disable_module(n))
        else:
            toggle_btn = QPushButton("启用")
            toggle_btn.setStyleSheet("background: #4ade80; color: black; border: none; padding: 5px 8px; border-radius: 3px;")
            toggle_btn.clicked.connect(lambda _, n=module.name: self._enable_module(n))
        
        if module.status in {ModuleStatus.INVALID, ModuleStatus.INCOMPATIBLE}:
            toggle_btn.setEnabled(False)
        layout.addWidget(toggle_btn)
        
        # 卸载按钮 (仅外部模块)
        if module.source == ModuleSource.EXTERNAL:
            uninstall_btn = QPushButton("🗑️")
            uninstall_btn.setToolTip("卸载模块")
            uninstall_btn.setStyleSheet("background: #9ca3af; color: white; border: none; padding: 5px 8px; border-radius: 3px;")
            uninstall_btn.clicked.connect(lambda _, n=module.name: self._uninstall_module(n))
            layout.addWidget(uninstall_btn)
        
        return widget
    
    def _install_module(self):
        """安装模块（含预览确认）。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模块包", "", "ZIP 文件 (*.zip);;所有文件 (*)"
        )
        if not path:
            return
        
        registry = get_module_registry()
        
        try:
            manifest, warnings = registry.validate_source(path)
        except Exception as e:
            QMessageBox.warning(self, "校验失败", str(e))
            return
        
        dialog = InstallPreviewDialog(manifest, warnings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        
        try:
            module_info = registry.install(path)
            QMessageBox.information(self, "成功", f"已安装模块: {module_info.name}")
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "安装失败", str(e))
    
    def _uninstall_module(self, name: str):
        """卸载模块。"""
        reply = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载模块 '{name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            registry = get_module_registry()
            registry.uninstall(name)
            QMessageBox.information(self, "成功", f"已卸载模块: {name}")
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "卸载失败", str(e))
    
    def _enable_module(self, name: str):
        """启用模块。"""
        try:
            registry = get_module_registry()
            registry.enable_module(name)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "启用失败", str(e))
    
    def _disable_module(self, name: str):
        """禁用模块。"""
        try:
            registry = get_module_registry()
            registry.disable_module(name)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, "禁用失败", str(e))
