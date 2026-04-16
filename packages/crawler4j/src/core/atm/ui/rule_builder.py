"""运行模板可视化规则构建器。

实现基于 AST 的递归规则编辑器:
    - RuleBuilder: 主入口
    - RuleGroupWidget: 递归组容器 (AND/OR)
    - RuleRowWidget: 单行条件编辑器
"""


from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.core.atm.run_profile import (
    ComparisonOp,
    LogicOp,
    MatchCondition,
    MatchGroup,
    ValueType,
)
from src.ui.components.combo_box import StyledComboBox as QComboBox


class RuleRowWidget(QFrame):
    """单行规则编辑器: Field Op Value"""

    def __init__(self, condition: MatchCondition | None = None, parent=None):
        super().__init__(parent)
        self._condition = condition
        self._setup_ui()
        if condition:
            self._load_data(condition)
        else:
            # Default
            self._on_type_changed(ValueType.STATIC)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Field
        self.field_edit = QLineEdit()
        self.field_edit.setPlaceholderText("Field (e.g. status)")
        layout.addWidget(self.field_edit, 2)

        # 2. Operator
        self.op_combo = QComboBox()
        self.op_combo.addItems([o.value for o in ComparisonOp])
        self.op_combo.setFixedWidth(80)
        layout.addWidget(self.op_combo)

        # 3. Value Type Toggle
        self.type_btn = QToolButton()
        self.type_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.type_btn.setText("123")  # Icon text
        self.type_btn.setToolTip("切换值类型")
        self.type_btn.clicked.connect(self._toggle_type)
        layout.addWidget(self.type_btn)
        
        # Reset min-width from parent dialog to avoid layout breaking
        self.setStyleSheet("""
            QLineEdit { min-width: 100px; }
        """)
        self.setMinimumHeight(40) # Give plenty of vertical space for inputs and borders
        
        self._current_type = ValueType.STATIC

        # 4. Value Input Stack
        self.value_stack = QStackedWidget()
        
        # Static Input
        self.val_static = QLineEdit()
        self.val_static.setPlaceholderText("Value")
        self.value_stack.addWidget(self.val_static)
        
        # Field Input
        self.val_field = QComboBox() # Or LineEdit with completion
        self.val_field.setEditable(True)
        self.val_field.setPlaceholderText("Target Field")
        self.value_stack.addWidget(self.val_field)
        
        # Param Input
        self.val_param = QLineEdit()
        self.val_param.setPlaceholderText("$param_name")
        self.value_stack.addWidget(self.val_param)
        
        layout.addWidget(self.value_stack, 3)

        # 5. Delete
        self.del_btn = QToolButton()
        self.del_btn.setText("✕")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("""
            QToolButton {
                color: #ef4444;
                border: none;
                font-size: 16px;
                font-weight: bold;
                background: transparent;
            }
            QToolButton:hover {
                background: rgba(239, 68, 68, 0.1);
                border-radius: 14px;
            }
        """)
        # Connected by parent
        layout.addWidget(self.del_btn)

    def _toggle_type(self):
        # Cyclical toggle: Static -> Field -> Param -> Static
        if self._current_type == ValueType.STATIC:
            self._on_type_changed(ValueType.FIELD)
        elif self._current_type == ValueType.FIELD:
            self._on_type_changed(ValueType.PARAM)
        else:
            self._on_type_changed(ValueType.STATIC)

    def _on_type_changed(self, vtype: ValueType):
        self._current_type = vtype
        if vtype == ValueType.STATIC:
            self.type_btn.setText("Str")
            self.type_btn.setStyleSheet("color: white;")
            self.value_stack.setCurrentIndex(0)
        elif vtype == ValueType.FIELD:
            self.type_btn.setText("Ref")
            self.type_btn.setStyleSheet("color: #60a5fa;")
            self.value_stack.setCurrentIndex(1)
        elif vtype == ValueType.PARAM:
            self.type_btn.setText("Var")
            self.type_btn.setStyleSheet("color: #facc15;")
            self.value_stack.setCurrentIndex(2)

    def _load_data(self, c: MatchCondition):
        self.field_edit.setText(c.field)
        self.op_combo.setCurrentText(c.op.value)
        self._on_type_changed(c.value_type)
        
        val_str = str(c.value)
        if c.value_type == ValueType.STATIC:
            self.val_static.setText(val_str)
        elif c.value_type == ValueType.FIELD:
            self.val_field.setCurrentText(val_str)
        elif c.value_type == ValueType.PARAM:
            self.val_param.setText(val_str)

    def get_data(self) -> MatchCondition:
        val = ""
        idx = self.value_stack.currentIndex()
        if idx == 0: 
            val = self.val_static.text()
        elif idx == 1: 
            val = self.val_field.currentText()
        elif idx == 2: 
            val = self.val_param.text()
        
        # Simple type inference for static?
        # For now keep as string, backend handles type cast if needed
        # Or try parse int/bool
        if self._current_type == ValueType.STATIC:
            if val.lower() == "true": 
                val = True
            elif val.lower() == "false": 
                val = False
            elif val.isdigit(): 
                val = int(val)
        
        return MatchCondition(
            field=self.field_edit.text(),
            op=ComparisonOp(self.op_combo.currentText()),
            value=val,
            value_type=self._current_type
        )


class RuleGroupWidget(QFrame):
    """递归规则组容器。"""
    changed = pyqtSignal() # Notify height changes to parent

    def __init__(self, group: MatchGroup | None = None, parent=None, level=0):
        super().__init__(parent)
        self._level = level
        self._setup_ui()
        if group:
            self._load_data(group)

    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            RuleGroupWidget {{
                background: rgba(255, 255, 255, {0.05 if self._level > 0 else 0});
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                margin-top: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) # More breathing room
        layout.setSpacing(10) # Distinct separation between rules

        # 1. Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        
        # Logic Toggle
        self.logic_btn = QPushButton("AND")
        self.logic_btn.setCheckable(True)
        self.logic_btn.setFixedSize(50, 24)
        self.logic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logic_btn.setStyleSheet("""
            QPushButton { background: #10b981; color: white; border-radius: 12px; font-weight: bold; }
            QPushButton:checked { background: #8b5cf6; text: "OR"; }
        """)
        self.logic_btn.clicked.connect(self._toggle_logic)
        header.addWidget(self.logic_btn)
        
        header.addStretch()
        
        # Actions
        add_rule_btn = QPushButton("+ Rule")
        add_rule_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_rule_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a5b4fc;
                border: 1px solid rgba(165, 180, 252, 0.3);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(165, 180, 252, 0.1);
                border-color: #a5b4fc;
            }
        """)
        add_rule_btn.clicked.connect(self._add_rule)
        header.addWidget(add_rule_btn)
        
        add_group_btn = QPushButton("+ Group")
        add_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_group_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #fca5a5;
                border: 1px solid rgba(252, 165, 165, 0.3);
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(252, 165, 165, 0.1);
                border-color: #fca5a5;
            }
        """)
        add_group_btn.clicked.connect(self._add_group)
        header.addWidget(add_group_btn)
        
        if self._level > 0:
            del_group_btn = QToolButton()
            del_group_btn.setText("✕")
            del_group_btn.setToolTip("Delete Group")
            del_group_btn.setFixedSize(28, 28)
            del_group_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_group_btn.setStyleSheet("""
                QToolButton {
                    color: #ef4444;
                    border: none;
                    background: transparent;
                    font-weight: bold;
                    font-size: 16px;
                }
                QToolButton:hover {
                    background: rgba(239, 68, 68, 0.1);
                    border-radius: 14px;
                }
            """)
            del_group_btn.clicked.connect(self._delete_self)
            header.addWidget(del_group_btn)
            
        layout.addLayout(header)

        # 2. Children Container
        self.children_layout = QVBoxLayout()
        self.children_layout.setSpacing(4)
        layout.addLayout(self.children_layout)
        
        self._widgets = []

    def _toggle_logic(self, checked):
        if checked:
            self.logic_btn.setText("OR")
        else:
            self.logic_btn.setText("AND")

    def _add_rule(self, condition: MatchCondition | None = None):
        row = RuleRowWidget(condition)
        row.del_btn.clicked.connect(lambda: self._remove_child(row))
        self.children_layout.addWidget(row)
        self._widgets.append(row)
        self.changed.emit()

    def _add_group(self, group: MatchGroup | None = None):
        widget = RuleGroupWidget(group, level=self._level + 1)
        # connect delete signal logic...
        # Since RuleGroupWidget doesn't emit signal effectively, we pass a callback or use closure
        # Or better: monkeypatch delete
        widget._delete_self = lambda: self._remove_child(widget)
        widget.changed.connect(self.changed.emit) # Propagate
        self.children_layout.addWidget(widget)
        self._widgets.append(widget)
        self.changed.emit()

    def _delete_self(self):
        # Override by parent to remove from layout
        self.deleteLater()

    def _remove_child(self, widget):
        widget.deleteLater()
        if widget in self._widgets:
            self._widgets.remove(widget)
        self.changed.emit()

    def _load_data(self, group: MatchGroup):
        self.logic_btn.setChecked(group.logic == LogicOp.OR)
        self._toggle_logic(group.logic == LogicOp.OR)
        
        for item in group.conditions:
            if isinstance(item, MatchCondition):
                self._add_rule(item)
            elif isinstance(item, MatchGroup):
                self._add_group(item)

    def get_data(self) -> MatchGroup:
        logic = LogicOp.OR if self.logic_btn.isChecked() else LogicOp.AND
        conditions = []
        for w in self._widgets:
            if isinstance(w, RuleRowWidget):
                conditions.append(w.get_data())
            elif isinstance(w, RuleGroupWidget):
                conditions.append(w.get_data())
        return MatchGroup(logic=logic, conditions=conditions)


class RuleBuilder(QWidget):
    """规则构建器组件 (Main Wrapper)。"""
    
    def __init__(self, group: MatchGroup | None = None, parent=None):
        super().__init__(parent)
        self._root_group = group or MatchGroup(logic=LogicOp.AND, conditions=[])
        self.setMinimumHeight(80) # A safe base height
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.root_widget = RuleGroupWidget(self._root_group)
        self.root_widget.changed.connect(self._update_geometry)
        layout.addWidget(self.root_widget)
        layout.addStretch()
        
        # Initial trigger
        self._update_geometry()

    def _update_geometry(self):
        """Force the widget to grow based on its actual content size."""
        if self.root_widget.layout():
            self.root_widget.layout().activate()
        
        hint = self.root_widget.sizeHint().height()
        new_h = max(hint + 50, 150) # Very generous buffer to prevent any cutting off
        
        # Use setMinimumHeight to FORCE the parent layout (like QScrollArea) 
        # to respect the needed space.
        self.setMinimumHeight(new_h)
        self.updateGeometry() # Notify layout system
        
        # If we have a parent that needs immediate update
        p = self.parentWidget()
        if p:
            p.updateGeometry()

    def get_rule_group(self) -> MatchGroup:
        return self.root_widget.get_data()

    def set_rule_group(self, group: MatchGroup):
        # Re-create root
        pass
