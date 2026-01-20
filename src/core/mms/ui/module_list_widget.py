"""模块列表页。

全屏表格显示模块列表，点击详情按钮进入模块详情页。
"""

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import ModuleSource, ModuleStatus, get_module_registry
from src.core.mms.models import ModuleInfo
from src.core.mms.ui.install_preview_dialog import InstallPreviewDialog
from src.ui.components.data_table import SkyDataTable


@dataclass
class ModuleDisplayItem:
    """模块显示项包装。"""
    raw: ModuleInfo
    display_name_str: str


class ModuleListWidget(QWidget):
    """模块列表页。
    
    全屏展示模块表格，点击"详情"跳转到详情页。
    """
    
    open_detail = pyqtSignal(object)  # 打开详情页信号 (ModuleInfo)
    
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
        
        # 表格 (SkyDataTable)
        
        columns = [
            ("name", "名称", 160),
            ("display_name", "显示名", 260),
            ("version", "版本", 120),
            ("status", "状态", 120),
            ("actions", "操作", None),
        ]
        
        self.table = SkyDataTable(columns=columns)
        self.table.set_render_callback(self._render_row)
        layout.addWidget(self.table)
        
        # 统计
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    # Removed ModuleDisplayItem and ModuleListWidget redefinition to merge class body
    # ... (keeps existing)

    def load_data(self):
        """加载模块数据。"""
        self.table.set_loading(True)
        self.error_label.hide()
        
        try:
            registry = get_module_registry()
            modules = registry.list_modules()
            self._modules = modules
            
            display_items = []
            for m in modules:
                display_name = m.manifest.display_name or m.name
                display_items.append(ModuleDisplayItem(
                    raw=m,
                    display_name_str=display_name
                ))
            
            self.table.set_data(display_items)
            
        except Exception as e:
            self.table.set_loading(False)
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        
        self.table.set_loading(False)
    
    def _render_row(self, row: int, item: ModuleDisplayItem, table):
        """渲染模块行。"""
        module = item.raw
        table.setRowHeight(row, 52)
        
        # 0. 名称
        name_item = QTableWidgetItem(module.name)
        name_item.setData(Qt.ItemDataRole.UserRole, module)  # 存储模块对象
        table.setItem(row, 0, name_item)
        
        # 1. 显示名
        table.setItem(row, 1, QTableWidgetItem(item.display_name_str))
        
        # 2. 版本
        table.setItem(row, 2, QTableWidgetItem(module.manifest.version))
        
        # 3. 状态
        status_text = self.STATUS_TEXT.get(module.status, module.status.value)
        status_item = QTableWidgetItem(status_text)
        if module.status in self.STATUS_COLORS:
            status_item.setForeground(QColor(self.STATUS_COLORS[module.status]))
        table.setItem(row, 3, status_item)
        
        # 4. 操作按钮
        action_widget = self._create_action_widget(module)
        table.setCellWidget(row, 4, action_widget)
        
        # 更新统计 (在 render_callback 中做统计不合适，应该在 load_data 后或 set_data 时做)
        # SkyDataTable 已经在底部栏显示总数。我们这里的 stats_label 有点多余。
        # 但我们想显示 "启用数"。
        # 可以在 load_data 中一次性统计。
        
        # enabled_count = sum(1 for m in self._modules if m.status == ModuleStatus.ENABLED)
        # self.stats_label.setText(f"共 {len(self._modules)} 个模块，{enabled_count} 个启用")
    
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
