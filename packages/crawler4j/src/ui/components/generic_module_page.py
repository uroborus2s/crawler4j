"""通用模块页面。

当模块未提供 UI 扩展或 UI 加载失败时，显示此默认页面。
"""

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class GenericModulePage(QWidget):
    """通用模块页面。
    
    规格 5.5.3.4: 模块未提供 UI 或加载失败时的降级页面。
    
    显示内容:
        - 模块基本信息 (name/version/author/description)
        - 工作流列表
        - 配置编辑器 (JSON 格式)
    """
    
    def __init__(self, module_info, parent=None):
        """初始化通用模块页。
        
        Args:
            module_info: ModuleInfo 实例
            parent: 父组件
        """
        super().__init__(parent)
        self._module = module_info
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # 标题
        header = self._create_header()
        layout.addWidget(header)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # 模块信息卡片
        info_card = self._create_info_card()
        content_layout.addWidget(info_card)
        
        # 工作流列表
        if self._module.manifest.workflows:
            workflows_card = self._create_workflows_card()
            content_layout.addWidget(workflows_card)
        
        # 配置编辑器
        config_card = self._create_config_card()
        content_layout.addWidget(config_card)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_header(self) -> QWidget:
        """创建标题栏。"""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 图标和标题
        icon = self._module.manifest.ui_extension.nav_item.icon if self._module.manifest.ui_extension.nav_item else "📦"
        title = QLabel(f"{icon} {self._module.manifest.display_name or self._module.name}")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # 版本标签
        version = QLabel(f"v{self._module.manifest.version}")
        version.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 14px;")
        layout.addWidget(version)
        
        return header
    
    def _create_info_card(self) -> QFrame:
        """创建信息卡片。"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        
        # 描述
        if self._module.manifest.description:
            desc = QLabel(self._module.manifest.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 14px;")
            layout.addWidget(desc)
        
        # 元信息
        info_layout = QHBoxLayout()
        info_layout.setSpacing(24)
        
        meta = [
            ("作者", self._module.manifest.author or "未知"),
            ("来源", "内置" if self._module.source.value == "builtin" else "外部"),
        ]
        
        for label, value in meta:
            item = QLabel(f"<span style='color:rgba(255,255,255,0.5)'>{label}:</span> {value}")
            item.setStyleSheet("color: white; font-size: 13px;")
            info_layout.addWidget(item)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        return card
    
    def _create_workflows_card(self) -> QFrame:
        """创建工作流列表卡片。"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        
        title = QLabel("📋 工作流")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        for wf in self._module.manifest.workflows:
            wf_widget = QWidget()
            wf_layout = QHBoxLayout(wf_widget)
            wf_layout.setContentsMargins(0, 4, 0, 4)
            
            name = QLabel(f"• {wf.display_name or wf.name}")
            name.setStyleSheet("color: rgba(255,255,255,0.9); font-size: 14px;")
            wf_layout.addWidget(name)
            
            if wf.description:
                desc = QLabel(f"— {wf.description}")
                desc.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 13px;")
                wf_layout.addWidget(desc)
            
            wf_layout.addStretch()
            
            # 运行按钮
            run_btn = QPushButton("▶")
            run_btn.setFixedSize(28, 28)
            run_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(74, 222, 128, 0.3);
                    color: #4ade80;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover { background: rgba(74, 222, 128, 0.5); }
            """)
            run_btn.setToolTip("运行工作流")
            wf_layout.addWidget(run_btn)
            
            layout.addWidget(wf_widget)
        
        return card
    
    def _create_config_card(self) -> QFrame:
        """创建配置编辑器卡片。"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        title = QLabel("⚙️ 配置")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        header.addWidget(save_btn)
        layout.addLayout(header)
        
        # JSON 编辑器
        import json
        from src.core.mms.settings_store import get_module_settings_store

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
        self.config_editor.setMinimumHeight(200)
        
        # 加载配置
        config_data = get_module_settings_store().read_module_settings(self._module.name)
        self.config_editor.setPlainText(json.dumps(config_data, indent=2, ensure_ascii=False))
        
        layout.addWidget(self.config_editor)
        
        return card
    
    def load_data(self):
        """刷新页面数据。"""
        pass  # 暂不实现
