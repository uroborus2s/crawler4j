"""策略编辑器页面。

配置任务调度策略。
"""

from PyQt6.QtWidgets import (
    QComboBox,
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
from src.core.tsm.models import ProvisioningMode, ReusePolicy


class StrategyEditorPage(QWidget):
    """策略编辑器页面。
    
    配置项：
    - 并发控制
    - 资源供应策略
    - 可靠性设置
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 并发配置
        concurrency_group = QGroupBox("并发控制")
        concurrency_layout = QFormLayout(concurrency_group)
        
        self.global_max_spin = QSpinBox()
        self.global_max_spin.setRange(1, 100)
        self.global_max_spin.setValue(10)
        concurrency_layout.addRow("全局最大并发:", self.global_max_spin)
        
        layout.addWidget(concurrency_group)
        
        # 资源供应
        provisioning_group = QGroupBox("资源供应")
        provisioning_layout = QFormLayout(provisioning_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["static", "dynamic", "hybrid"])
        self.mode_combo.setCurrentText("hybrid")
        provisioning_layout.addRow("供应模式:", self.mode_combo)
        
        self.reuse_combo = QComboBox()
        self.reuse_combo.addItems(["dirty", "clean", "ephemeral"])
        self.reuse_combo.setCurrentText("clean")
        provisioning_layout.addRow("复用策略:", self.reuse_combo)
        
        self.auto_create_spin = QSpinBox()
        self.auto_create_spin.setRange(0, 20)
        self.auto_create_spin.setValue(5)
        provisioning_layout.addRow("自动创建上限:", self.auto_create_spin)
        
        layout.addWidget(provisioning_group)
        
        # 可靠性
        reliability_group = QGroupBox("可靠性")
        reliability_layout = QFormLayout(reliability_group)
        
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 10)
        self.max_retries_spin.setValue(3)
        reliability_layout.addRow("最大重试次数:", self.max_retries_spin)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 3600)
        self.timeout_spin.setValue(300)
        self.timeout_spin.setSuffix(" 秒")
        reliability_layout.addRow("任务超时:", self.timeout_spin)
        
        layout.addWidget(reliability_group)
        
        layout.addStretch()
        
        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("保存策略")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_settings(self):
        """加载策略配置。"""
        store = get_config_store()
        config = store.get_module_config("tsm")
        
        self.global_max_spin.setValue(config.get("global_max", 10))
        self.mode_combo.setCurrentText(config.get("mode", "hybrid"))
        self.reuse_combo.setCurrentText(config.get("reuse_policy", "clean"))
        self.auto_create_spin.setValue(config.get("auto_create_limit", 5))
        self.max_retries_spin.setValue(config.get("max_retries", 3))
        self.timeout_spin.setValue(config.get("timeout", 300))
    
    def _save_settings(self):
        """保存策略配置。"""
        store = get_config_store()
        store.set_module_config("tsm", {
            "global_max": self.global_max_spin.value(),
            "mode": self.mode_combo.currentText(),
            "reuse_policy": self.reuse_combo.currentText(),
            "auto_create_limit": self.auto_create_spin.value(),
            "max_retries": self.max_retries_spin.value(),
            "timeout": self.timeout_spin.value(),
        })
