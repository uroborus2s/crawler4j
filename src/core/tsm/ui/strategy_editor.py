"""策略编辑器页面。

支持双模式编辑：
    - 可视化表单模式
    - YAML 源码模式
"""

import yaml
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.persistence import get_kv_store
from src.ui.components.combo_box import StyledComboBox as QComboBox


class StrategyEditorPage(QWidget):
    """策略编辑器页面。
    
    SRS 5.3.6: 双模式设计 (Dual Mode)
        - 可视化模式 (Visual Form)
        - 源码模式 (YAML)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("策略配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        # 模式切换按钮
        self.form_btn = QPushButton("📝 表单")
        self.form_btn.setCheckable(True)
        self.form_btn.setChecked(True)
        self.form_btn.clicked.connect(lambda: self._switch_mode("form"))
        header.addWidget(self.form_btn)
        
        self.yaml_btn = QPushButton("📄 YAML")
        self.yaml_btn.setCheckable(True)
        self.yaml_btn.clicked.connect(lambda: self._switch_mode("yaml"))
        header.addWidget(self.yaml_btn)
        
        # 样式
        btn_style = """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
            QPushButton:checked { background: rgba(99, 102, 241, 0.8); }
        """
        self.form_btn.setStyleSheet(btn_style)
        self.yaml_btn.setStyleSheet(btn_style)
        
        layout.addLayout(header)
        
        # 内容区 - 双模式切换
        self.stack = QStackedWidget()
        
        # 表单模式
        self.form_widget = self._create_form_widget()
        self.stack.addWidget(self.form_widget)
        
        # YAML 模式
        self.yaml_widget = self._create_yaml_widget()
        self.stack.addWidget(self.yaml_widget)
        
        layout.addWidget(self.stack)
        
        # 保存按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("💾 保存策略")
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
        """)
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_form_widget(self) -> QWidget:
        """创建表单模式组件。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # 并发配置
        concurrency_group = QGroupBox("并发控制")
        concurrency_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; }")
        concurrency_layout = QFormLayout(concurrency_group)
        
        self.global_max_spin = QSpinBox()
        self.global_max_spin.setRange(1, 100)
        self.global_max_spin.setValue(10)
        concurrency_layout.addRow("全局最大并发:", self.global_max_spin)
        
        layout.addWidget(concurrency_group)
        
        # 资源供应
        provisioning_group = QGroupBox("资源供应")
        provisioning_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; }")
        provisioning_layout = QFormLayout(provisioning_group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["static", "dynamic"])
        self.mode_combo.setCurrentText("dynamic")
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
        reliability_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; }")
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
        
        return widget
    
    def _create_yaml_widget(self) -> QWidget:
        """创建 YAML 模式组件。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 16, 0, 0)
        
        # 提示
        hint = QLabel("直接编辑 YAML 配置，支持高级表达式。")
        hint.setStyleSheet("color: rgba(255, 255, 255, 0.6); margin-bottom: 8px;")
        layout.addWidget(hint)
        
        # YAML 编辑器
        self.yaml_editor = QPlainTextEdit()
        self.yaml_editor.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(20, 20, 30, 0.9);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 12px;
                font-family: 'Monaco', 'Consolas', monospace;
                font-size: 13px;
            }
        """)
        self.yaml_editor.setPlaceholderText("# 策略配置 YAML")
        layout.addWidget(self.yaml_editor)
        
        # 校验状态
        self.validate_label = QLabel()
        self.validate_label.setStyleSheet("padding: 8px;")
        layout.addWidget(self.validate_label)
        
        # 实时校验
        self.yaml_editor.textChanged.connect(self._validate_yaml)
        
        return widget
    
    def _switch_mode(self, mode: str):
        """切换编辑模式。"""
        if mode == "form":
            # 从 YAML 同步到表单
            self._yaml_to_form()
            self.stack.setCurrentIndex(0)
            self.form_btn.setChecked(True)
            self.yaml_btn.setChecked(False)
        else:
            # 从表单同步到 YAML
            self._form_to_yaml()
            self.stack.setCurrentIndex(1)
            self.form_btn.setChecked(False)
            self.yaml_btn.setChecked(True)
    
    def _form_to_yaml(self):
        """表单数据转 YAML。"""
        data = {
            "concurrency": {
                "global_max": self.global_max_spin.value(),
            },
            "provisioning": {
                "mode": self.mode_combo.currentText(),
                "reuse_policy": self.reuse_combo.currentText(),
                "auto_create_limit": self.auto_create_spin.value(),
            },
            "reliability": {
                "max_retries": self.max_retries_spin.value(),
                "timeout_seconds": self.timeout_spin.value(),
            },
        }
        yaml_str = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        self.yaml_editor.setPlainText(yaml_str)
    
    def _yaml_to_form(self):
        """YAML 转表单数据。"""
        try:
            data = yaml.safe_load(self.yaml_editor.toPlainText())
            if not data:
                return
            
            concurrency = data.get("concurrency", {})
            self.global_max_spin.setValue(concurrency.get("global_max", 10))
            
            provisioning = data.get("provisioning", {})
            self.mode_combo.setCurrentText(provisioning.get("mode", "dynamic"))
            self.reuse_combo.setCurrentText(provisioning.get("reuse_policy", "clean"))
            self.auto_create_spin.setValue(provisioning.get("auto_create_limit", 5))
            
            reliability = data.get("reliability", {})
            self.max_retries_spin.setValue(reliability.get("max_retries", 3))
            self.timeout_spin.setValue(reliability.get("timeout_seconds", 300))
        except Exception:
            pass
    
    def _validate_yaml(self):
        """校验 YAML 语法。"""
        try:
            yaml.safe_load(self.yaml_editor.toPlainText())
            self.validate_label.setText("✅ YAML 语法正确")
            self.validate_label.setStyleSheet("color: #4ade80; padding: 8px;")
        except yaml.YAMLError as e:
            self.validate_label.setText(f"❌ 语法错误: {e}")
            self.validate_label.setStyleSheet("color: #f87171; padding: 8px;")
    
    def _load_settings(self):
        """加载策略配置。"""
        kv = get_kv_store()
        config = kv.get("module:tsm:config") or {}
        
        self.global_max_spin.setValue(config.get("global_max", 10))
        self.mode_combo.setCurrentText(config.get("mode", "dynamic"))
        self.reuse_combo.setCurrentText(config.get("reuse_policy", "clean"))
        self.auto_create_spin.setValue(config.get("auto_create_limit", 5))
        self.max_retries_spin.setValue(config.get("max_retries", 3))
        self.timeout_spin.setValue(config.get("timeout", 300))
    
    def _save_settings(self):
        """保存策略配置。"""
        # 如果在 YAML 模式，先同步到表单
        if self.stack.currentIndex() == 1:
            self._yaml_to_form()
        
        kv = get_kv_store()
        kv.set("module:tsm:config", {
            "global_max": self.global_max_spin.value(),
            "mode": self.mode_combo.currentText(),
            "reuse_policy": self.reuse_combo.currentText(),
            "auto_create_limit": self.auto_create_spin.value(),
            "max_retries": self.max_retries_spin.value(),
            "timeout": self.timeout_spin.value(),
        })
        
        QMessageBox.information(self, "提示", "策略已保存")
