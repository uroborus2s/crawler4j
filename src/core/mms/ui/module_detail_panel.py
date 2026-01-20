"""模块详情面板。

在模块列表右侧显示选中模块的详情和配置。
"""

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ModuleDetailPanel(QFrame):
    """模块详情面板。
    
    显示选中模块的:
        - 基本信息
        - 工作流列表
        - 配置编辑器
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._module = None
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            ModuleDetailPanel {
                background: rgba(25, 25, 35, 0.9);
                border-left: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 使用 StackedWidget 切换空状态和详情
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # 空状态
        self.empty_widget = self._create_empty_state()
        self.stack.addWidget(self.empty_widget)
        
        # 详情视图
        self.detail_widget = self._create_detail_view()
        self.stack.addWidget(self.detail_widget)
        
        # 默认显示空状态
        self.stack.setCurrentWidget(self.empty_widget)
    
    def _create_empty_state(self) -> QWidget:
        """创建空状态视图。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel("📦")
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        
        text = QLabel("选择一个模块查看详情")
        text.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 14px;")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        
        return widget
    
    def _create_detail_view(self) -> QWidget:
        """创建详情视图。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 标题栏
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(self.title_label)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        
        # 描述
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
        content_layout.addWidget(self.desc_label)
        
        # 元信息
        self.meta_widget = QWidget()
        meta_layout = QHBoxLayout(self.meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(20)
        
        self.version_label = QLabel()
        self.version_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 13px;")
        meta_layout.addWidget(self.version_label)
        
        self.author_label = QLabel()
        self.author_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 13px;")
        meta_layout.addWidget(self.author_label)
        
        self.source_label = QLabel()
        self.source_label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 13px;")
        meta_layout.addWidget(self.source_label)
        
        meta_layout.addStretch()
        content_layout.addWidget(self.meta_widget)
        
        # 工作流区域
        self.workflows_card = self._create_workflows_card()
        content_layout.addWidget(self.workflows_card)
        
        # 配置区域
        self.config_card = self._create_config_card()
        content_layout.addWidget(self.config_card)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return widget
    
    def _create_workflows_card(self) -> QFrame:
        """创建工作流卡片。"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        title = QLabel("📋 工作流")
        title.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        
        self.workflows_container = QVBoxLayout()
        self.workflows_container.setSpacing(6)
        layout.addLayout(self.workflows_container)
        
        return card
    
    def _create_config_card(self) -> QFrame:
        """创建配置卡片。"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        title = QLabel("⚙️ 配置")
        title.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        self.save_config_btn = QPushButton("保存")
        self.save_config_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white; border: none;
                padding: 6px 14px; border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.save_config_btn.clicked.connect(self._save_config)
        header.addWidget(self.save_config_btn)
        
        layout.addLayout(header)
        
        self.config_editor = QTextEdit()
        self.config_editor.setStyleSheet("""
            QTextEdit {
                background: rgba(0, 0, 0, 0.3);
                color: #4ade80;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 4px;
                font-family: 'Menlo', 'Monaco', monospace;
                font-size: 13px;
                padding: 8px;
            }
        """)
        self.config_editor.setMinimumHeight(150)
        layout.addWidget(self.config_editor)
        
        return card
    
    def set_module(self, module):
        """设置要显示的模块。"""
        self._module = module
        
        if module is None:
            self.stack.setCurrentWidget(self.empty_widget)
            return
        
        self.stack.setCurrentWidget(self.detail_widget)
        
        # 更新标题
        icon = "📦"
        if module.manifest.ui_extension.nav_item:
            icon = module.manifest.ui_extension.nav_item.icon
        display = module.manifest.display_name or module.name
        self.title_label.setText(f"{icon} {display}")
        
        # 更新描述
        self.desc_label.setText(module.manifest.description or "暂无描述")
        
        # 更新元信息
        self.version_label.setText(f"版本: {module.manifest.version}")
        self.author_label.setText(f"作者: {module.manifest.author or '未知'}")
        source_text = "内置" if module.source.value == "builtin" else "外部"
        self.source_label.setText(f"来源: {source_text}")
        
        # 更新工作流列表
        self._update_workflows(module.manifest.workflows)
        
        # 更新配置
        self._update_config(module)
    
    def _update_workflows(self, workflows):
        """更新工作流列表。"""
        # 清除现有项
        while self.workflows_container.count():
            item = self.workflows_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not workflows:
            empty = QLabel("暂无工作流")
            empty.setStyleSheet("color: rgba(255,255,255,0.5);")
            self.workflows_container.addWidget(empty)
            return
        
        for wf in workflows:
            wf_item = QWidget()
            wf_layout = QHBoxLayout(wf_item)
            wf_layout.setContentsMargins(0, 4, 0, 4)
            
            name_label = QLabel(f"• {wf.display_name or wf.name}")
            name_label.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 13px;")
            wf_layout.addWidget(name_label)
            
            if wf.description:
                desc = QLabel(f"— {wf.description}")
                desc.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
                wf_layout.addWidget(desc)
            
            wf_layout.addStretch()
            
            run_btn = QPushButton("▶")
            run_btn.setFixedSize(26, 26)
            run_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(74, 222, 128, 0.3);
                    color: #4ade80; border: none; border-radius: 4px;
                }
                QPushButton:hover { background: rgba(74, 222, 128, 0.5); }
            """)
            run_btn.setToolTip("运行工作流")
            wf_layout.addWidget(run_btn)
            
            self.workflows_container.addWidget(wf_item)
    
    def _update_config(self, module):
        """更新配置编辑器。"""
        from src.core.persistence import get_kv_store
        
        kv = get_kv_store()
        config = kv.get(f"module:{module.name}:config")
        
        # 如果没有保存的配置，使用 manifest 中的默认值
        if not config:
            config = module.manifest.config_schema or {}
        
        self.config_editor.setPlainText(
            json.dumps(config, indent=2, ensure_ascii=False)
        )
    
    def _save_config(self):
        """保存配置。"""
        if not self._module:
            return
        
        try:
            config_text = self.config_editor.toPlainText()
            config = json.loads(config_text)
            
            from src.core.persistence import get_kv_store
            kv = get_kv_store()
            kv.set(f"module:{self._module.name}:config", config)
            
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "成功", "配置已保存")
        except json.JSONDecodeError as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "错误", f"JSON 格式错误: {e}")
