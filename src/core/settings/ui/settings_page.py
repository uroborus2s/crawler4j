"""系统设置页面。

框架级别的基础设置。
"""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.persistence import get_config_store


class SettingsPage(QWidget):
    """系统设置页面。
    
    配置项：
    - 通用设置
    - 日志设置
    - 存储设置
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 通用设置
        general_group = QGroupBox("通用设置")
        general_layout = QFormLayout(general_group)
        
        self.autostart_check = QCheckBox("开机自启动")
        general_layout.addRow(self.autostart_check)
        
        self.minimize_check = QCheckBox("启动时最小化到托盘")
        general_layout.addRow(self.minimize_check)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light", "system"])
        general_layout.addRow("主题:", self.theme_combo)
        
        layout.addWidget(general_group)
        
        # 日志设置
        log_group = QGroupBox("日志设置")
        log_layout = QFormLayout(log_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText("INFO")
        log_layout.addRow("日志级别:", self.log_level_combo)
        
        self.log_retention_combo = QComboBox()
        self.log_retention_combo.addItems(["7天", "14天", "30天", "永久"])
        log_layout.addRow("日志保留:", self.log_retention_combo)
        
        layout.addWidget(log_group)
        
        # 存储设置
        storage_group = QGroupBox("存储设置")
        storage_layout = QFormLayout(storage_group)
        
        self.data_path_edit = QLineEdit()
        self.data_path_edit.setReadOnly(True)
        storage_layout.addRow("数据目录:", self.data_path_edit)
        
        layout.addWidget(storage_group)
        
        layout.addStretch()
        
        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_settings(self):
        """加载设置。"""
        store = get_config_store()
        config = store.get_module_config("system")
        
        self.autostart_check.setChecked(config.get("autostart", False))
        self.minimize_check.setChecked(config.get("minimize_on_start", False))
        self.theme_combo.setCurrentText(config.get("theme", "dark"))
        self.log_level_combo.setCurrentText(config.get("log_level", "INFO"))
        
        from src.utils.paths import get_app_data_dir
        self.data_path_edit.setText(str(get_app_data_dir()))
    
    def _save_settings(self):
        """保存设置。"""
        store = get_config_store()
        store.set_module_config("system", {
            "autostart": self.autostart_check.isChecked(),
            "minimize_on_start": self.minimize_check.isChecked(),
            "theme": self.theme_combo.currentText(),
            "log_level": self.log_level_combo.currentText(),
        })
