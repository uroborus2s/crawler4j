"""Schema 表单组件。

基于 JSON Schema 动态生成表单控件，实现声明式 UI。
"""

import json
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.combo_box import StyledComboBox as QComboBox


class SchemaFormWidget(QWidget):
    """基于 JSON Schema 的动态表单。
    
    规格 5.5.3.4 机制 A: 声明式 UI
    
    支持的字段类型:
        - string: QLineEdit
        - integer: QSpinBox
        - number: QDoubleSpinBox
        - boolean: QCheckBox
        - enum: QComboBox
    """
    
    config_changed = pyqtSignal(dict)  # 配置变更信号
    
    def __init__(self, module_info, schema_path: str, parent=None):
        """初始化表单。
        
        Args:
            module_info: ModuleInfo 实例
            schema_path: Schema 文件路径 (相对于模块目录)
            parent: 父组件
        """
        super().__init__(parent)
        self._module = module_info
        self._schema_path = schema_path
        self._fields: dict[str, QWidget] = {}
        self._schema: dict = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # 标题
        header = self._create_header()
        layout.addWidget(header)
        
        # 加载 Schema
        self._load_schema()
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        # 表单容器
        form_container = QFrame()
        form_container.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        form_layout = QFormLayout(form_container)
        form_layout.setSpacing(16)
        form_layout.setContentsMargins(16, 16, 16, 16)
        
        # 根据 Schema 生成表单字段
        properties = self._schema.get("properties", {})
        for field_name, field_def in properties.items():
            label = field_def.get("title", field_name)
            widget = self._create_field_widget(field_name, field_def)
            if widget:
                self._fields[field_name] = widget
                form_layout.addRow(f"{label}:", widget)
        
        scroll.setWidget(form_container)
        layout.addWidget(scroll)
        
        # 操作按钮
        actions = self._create_actions()
        layout.addWidget(actions)
    
    def _create_header(self) -> QWidget:
        """创建标题栏。"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        icon = self._module.manifest.ui_extension.nav_item.icon if self._module.manifest.ui_extension.nav_item else "⚙️"
        title = QLabel(f"{icon} {self._module.manifest.display_name or self._module.name} 配置")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        layout.addStretch()
        return header
    
    def _load_schema(self):
        """加载 Schema 文件。"""
        if not self._module.path:
            return
        
        schema_file = self._module.path / self._schema_path
        if schema_file.exists():
            try:
                self._schema = json.loads(schema_file.read_text(encoding="utf-8"))
            except Exception:
                self._schema = {}
    
    def _create_field_widget(self, name: str, field_def: dict) -> QWidget | None:
        """根据字段定义创建控件。"""
        field_type = field_def.get("type", "string")
        default = field_def.get("default")
        
        # 枚举类型
        if "enum" in field_def:
            widget = QComboBox()
            widget.addItems([str(v) for v in field_def["enum"]])
            if default and str(default) in [str(v) for v in field_def["enum"]]:
                widget.setCurrentText(str(default))
            widget.setStyleSheet(self._input_style())
            return widget
        
        # 布尔类型
        if field_type == "boolean":
            widget = QCheckBox()
            if default is not None:
                widget.setChecked(bool(default))
            return widget
        
        # 整数类型
        if field_type == "integer":
            widget = QSpinBox()
            widget.setRange(
                field_def.get("minimum", 0),
                field_def.get("maximum", 9999)
            )
            if default is not None:
                widget.setValue(int(default))
            widget.setStyleSheet(self._input_style())
            return widget
        
        # 浮点数类型
        if field_type == "number":
            widget = QDoubleSpinBox()
            widget.setRange(
                field_def.get("minimum", 0.0),
                field_def.get("maximum", 9999.0)
            )
            widget.setDecimals(field_def.get("decimals", 2))
            if default is not None:
                widget.setValue(float(default))
            widget.setStyleSheet(self._input_style())
            return widget
        
        # 默认字符串类型
        widget = QLineEdit()
        if default is not None:
            widget.setText(str(default))
        widget.setPlaceholderText(field_def.get("description", ""))
        widget.setStyleSheet(self._input_style())
        return widget
    
    def _input_style(self) -> str:
        """输入控件样式。"""
        return """
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background: rgba(0, 0, 0, 0.3);
                color: white;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 4px;
                padding: 8px;
                min-width: 200px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: rgba(99, 102, 241, 0.8);
            }
        """
    
    def _create_actions(self) -> QWidget:
        """创建操作按钮。"""
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.2); }
        """)
        reset_btn.clicked.connect(self._reset_form)
        layout.addWidget(reset_btn)
        
        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn)
        
        return actions
    
    def get_values(self) -> dict[str, Any]:
        """获取表单当前值。"""
        values = {}
        for name, widget in self._fields.items():
            if isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QComboBox):
                values[name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                values[name] = widget.text()
        return values
    
    def _reset_form(self):
        """重置表单到默认值。"""
        properties = self._schema.get("properties", {})
        for name, field_def in properties.items():
            widget = self._fields.get(name)
            if not widget:
                continue
            default = field_def.get("default")
            if default is None:
                continue
            
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(default))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(default))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(default))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(default))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(default))
    
    def _save_config(self):
        """保存配置。"""
        from src.core.persistence import get_config_store
        
        values = self.get_values()
        store = get_config_store()
        store.set_module_config(self._module.name, values)
        self.config_changed.emit(values)
    
    def load_data(self):
        """加载已保存的配置。"""
        from src.core.persistence import get_config_store
        
        store = get_config_store()
        saved = store.get_module_config(self._module.name)
        
        for name, value in saved.items():
            widget = self._fields.get(name)
            if not widget:
                continue
            
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
