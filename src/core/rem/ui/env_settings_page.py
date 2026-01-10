"""环境设置页面。

配置环境池参数和 Provider 设置。
"""

from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.persistence import get_config_store


class EnvSettingsPage(QWidget):
    """环境设置页面。
    
    配置项：
    - 最大环境数
    - 默认 Provider
    - 环境池策略
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 环境池配置
        pool_group = QGroupBox("环境池配置")
        pool_layout = QFormLayout(pool_group)
        
        self.max_env_spin = QSpinBox()
        self.max_env_spin.setRange(1, 50)
        self.max_env_spin.setValue(10)
        pool_layout.addRow("最大环境数:", self.max_env_spin)
        
        self.idle_timeout_spin = QSpinBox()
        self.idle_timeout_spin.setRange(60, 3600)
        self.idle_timeout_spin.setValue(300)
        self.idle_timeout_spin.setSuffix(" 秒")
        pool_layout.addRow("空闲超时:", self.idle_timeout_spin)
        
        layout.addWidget(pool_group)
        
        # Provider 配置
        provider_group = QGroupBox("Provider 配置")
        provider_layout = QFormLayout(provider_group)
        
        provider_layout.addRow(QLabel("Playwright:"), QLabel("已启用"))
        
        layout.addWidget(provider_group)
        
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
        config = store.get_module_config("rem")
        
        self.max_env_spin.setValue(config.get("max_instances", 10))
        self.idle_timeout_spin.setValue(config.get("idle_timeout", 300))
    
    def _save_settings(self):
        """保存设置。"""
        store = get_config_store()
        store.set_module_config("rem", {
            "max_instances": self.max_env_spin.value(),
            "idle_timeout": self.idle_timeout_spin.value(),
        })
