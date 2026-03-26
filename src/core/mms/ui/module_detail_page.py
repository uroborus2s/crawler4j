"""模块详情页。

采用主从导航模式：左侧二级菜单，右侧内容区。
固定菜单（基本信息、任务链）+ 模块自定义菜单。
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.mms.models import ModuleInfo, ModuleSource


class ModuleDetailPage(QWidget):
    """模块详情页。
    
    主从导航模式：
        - 左侧: 二级菜单 (固定 + 自定义)
        - 右侧: 内容区 (根据菜单切换)
    """
    
    back_requested = pyqtSignal()  # 返回列表页信号
    
    BASE_MENU = [
        ("info", "📋", "基本信息"),
        ("workflows", "⚡", "任务链"),
        ("strategy", "⚙️", "策略配置"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._module: ModuleInfo | None = None
        self._menu_pages: dict[str, QWidget] = {}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 顶部栏
        self.header = self._create_header()
        layout.addWidget(self.header)
        
        # 主内容区
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        
        # 左侧菜单
        self.sidebar = self._create_sidebar()
        content.addWidget(self.sidebar)
        
        # 右侧内容栈
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: #1a1a24;")
        content.addWidget(self.content_stack)
        
        content_widget = QWidget()
        content_widget.setLayout(content)
        layout.addWidget(content_widget)
    
    def _create_header(self) -> QFrame:
        """创建顶部栏。"""
        header = QFrame()
        header.setFixedHeight(56)
        header.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.95);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # 返回按钮
        back_btn = QPushButton("← 返回")
        back_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.8);
                border: none;
                padding: 8px 12px;
                font-size: 14px;
            }
            QPushButton:hover {
                color: white;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_btn)
        
        # 模块标题
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-left: 16px;")
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        return header
    
    def _create_sidebar(self) -> QFrame:
        """创建左侧菜单。"""
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("""
            QFrame {
                background: rgba(25, 25, 35, 0.95);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)
        
        self.menu_list = QListWidget()
        self.menu_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }
            QListWidget::item {
                padding: 12px 16px;
                color: rgba(255, 255, 255, 0.7);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            QListWidget::item:selected {
                background: rgba(99, 102, 241, 0.3);
                color: white;
            }
        """)
        self.menu_list.currentRowChanged.connect(self._on_menu_changed)
        
        layout.addWidget(self.menu_list)
        layout.addStretch()
        
        return sidebar
    
    def set_module(self, module: ModuleInfo):
        """设置要显示的模块。"""
        self._module = module
        
        # 更新标题
        icon = "📦"
        if module.manifest.ui_extension.nav_item:
            icon = module.manifest.ui_extension.nav_item.icon
        display = module.manifest.display_name or module.name
        self.title_label.setText(f"{icon} {display}")
        
        # 更新状态
        status_colors = {
            "enabled": "#4ade80",
            "disabled": "#9ca3af",
        }
        status_text = {
            "enabled": "🟢 已启用",
            "disabled": "🔴 已禁用",
        }
        color = status_colors.get(module.status.value, "#9ca3af")
        text = status_text.get(module.status.value, module.status.value)
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 13px; color: {color};")
        # 重建菜单
        self._build_menu()
        
        # 选中第一项
        if self.menu_list.count() > 0:
            self.menu_list.setCurrentRow(0)
    
    def _build_menu(self):
        """构建菜单列表。"""
        self.menu_list.clear()
        self._menu_pages.clear()
        
        # 清除旧页面
        while self.content_stack.count() > 0:
            widget = self.content_stack.widget(0)
            self.content_stack.removeWidget(widget)
            widget.deleteLater()
        
        # 固定菜单
        for menu_id, icon, label in self.BASE_MENU:
            item = QListWidgetItem(f"{icon} {label}")
            item.setData(Qt.ItemDataRole.UserRole, menu_id)
            self.menu_list.addItem(item)
            
            # 创建对应页面
            page = self._create_fixed_page(menu_id)
            self._menu_pages[menu_id] = page
            self.content_stack.addWidget(page)
        
        # 自定义菜单
        if self._module:
            detail_menu = self._module.manifest.ui_extension.detail_menu
            if detail_menu:
                # 分隔符
                separator = QListWidgetItem("────────")
                separator.setData(Qt.ItemDataRole.UserRole, "__sep__")
                separator.setFlags(separator.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.menu_list.addItem(separator)
                
                for menu_item in detail_menu:
                    item = QListWidgetItem(f"{menu_item.icon} {menu_item.label}")
                    item.setData(Qt.ItemDataRole.UserRole, menu_item.id)
                    self.menu_list.addItem(item)
                    
                    # 创建自定义页面
                    page = self._create_custom_page(menu_item)
                    self._menu_pages[menu_item.id] = page
                    self.content_stack.addWidget(page)
    
    def _create_fixed_page(self, menu_id: str) -> QWidget:
        """创建固定页面。"""
        if menu_id == "info":
            return self._create_info_page()
        elif menu_id == "workflows":
            return self._create_workflows_page()
        elif menu_id == "strategy":
            return self._create_strategy_page()
        return QWidget()
    
    def _create_info_page(self) -> QWidget:
        """创建基本信息页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        if not self._module:
            return page
        
        manifest = self._module.manifest
        
        # 描述
        if manifest.description:
            desc = QLabel(manifest.description)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 15px;")
            layout.addWidget(desc)
        
        # 元信息卡片
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border-radius: 8px;
                padding: 16px;
            }
        """)
        card_layout = QVBoxLayout(info_card)
        card_layout.setSpacing(12)
        
        info_items = [
            ("版本", manifest.version),
            ("作者", manifest.author or "未知"),
            (
                "来源",
                "内置"
                if self._module.source == ModuleSource.BUILTIN
                else "开发链接"
                if self._module.source == ModuleSource.DEV_LINK
                else "外部",
            ),
            ("SDK 版本", manifest.sdk_version_range),
        ]
        
        for label, value in info_items:
            row = QHBoxLayout()
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 13px; min-width: 80px;")
            row.addWidget(label_widget)
            
            value_widget = QLabel(value)
            value_widget.setStyleSheet("color: white; font-size: 13px;")
            row.addWidget(value_widget)
            row.addStretch()
            
            card_layout.addLayout(row)
        
        # 安装路径
        if self._module.path:
            row = QHBoxLayout()
            label_widget = QLabel("路径:")
            label_widget.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 13px; min-width: 80px;")
            row.addWidget(label_widget)
            
            path_widget = QLabel(str(self._module.path))
            path_widget.setStyleSheet("color: #60a5fa; font-size: 12px; font-family: monospace;")
            path_widget.setWordWrap(True)
            row.addWidget(path_widget)
            row.addStretch()
            
            card_layout.addLayout(row)

        if self._module.source == ModuleSource.DEV_LINK:
            notice = QLabel(
                "当前模块来自开发链接，可用于 ATM 里的任务调试。"
                "移除开发链接后会回退到正式模块（如果存在）。"
            )
            notice.setWordWrap(True)
            notice.setStyleSheet("color: rgba(255,255,255,0.72); font-size: 13px;")
            card_layout.addWidget(notice)

            remove_btn = QPushButton("移除开发链接")
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(248, 113, 113, 0.85);
                    color: white;
                    border: none;
                    padding: 8px 14px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { background: rgba(248, 113, 113, 1); }
            """)
            remove_btn.clicked.connect(self._remove_dev_link)
            card_layout.addWidget(remove_btn)
        
        layout.addWidget(info_card)
        layout.addStretch()
        
        return page
    
    def _create_workflows_page(self) -> QWidget:
        """创建任务链页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        if not self._module:
            return page
        
        workflows = self._module.manifest.workflows
        
        if not workflows:
            empty = QLabel("暂无任务链")
            empty.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 14px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
            layout.addStretch()
            return page
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        
        for wf in workflows:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: rgba(30, 30, 40, 0.8);
                    border-radius: 8px;
                    padding: 16px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(8)
            
            # 标题行
            title_row = QHBoxLayout()
            title = QLabel(wf.display_name or wf.name)
            title.setStyleSheet("color: white; font-size: 15px; font-weight: bold;")
            title_row.addWidget(title)
            title_row.addStretch()

            card_layout.addLayout(title_row)
            
            # 描述
            if wf.description:
                desc = QLabel(wf.description)
                desc.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 13px;")
                desc.setWordWrap(True)
                card_layout.addWidget(desc)
            
            content_layout.addWidget(card)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        return page

    def _create_strategy_page(self) -> QWidget:
        """创建策略配置页面（YAML 编辑器）。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # 标题
        header = QHBoxLayout()
        title = QLabel("策略配置")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        # 保存按钮
        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
        """)
        save_btn.clicked.connect(lambda: self._save_strategy())
        header.addWidget(save_btn)
        
        layout.addLayout(header)
        
        # 提示
        hint = QLabel("编辑模块的策略配置文件 (YAML 格式)")
        hint.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 13px;")
        layout.addWidget(hint)
        
        # YAML 编辑器
        self.strategy_editor = QTextEdit()
        self.strategy_editor.setStyleSheet("""
            QTextEdit {
                background: rgba(20, 20, 30, 0.9);
                color: #e0e0e0;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 12px;
                font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
                font-size: 13px;
            }
        """)
        self.strategy_editor.setPlaceholderText("# 策略配置\nreliability:\n  max_retries: 3\n  backoff_factor: 2.0\n")
        
        # 加载模块当前策略
        if self._module:
            strategy_yaml = self._load_module_strategy()
            self.strategy_editor.setPlainText(strategy_yaml)
        
        layout.addWidget(self.strategy_editor)
        
        return page
    
    def _load_module_strategy(self) -> str:
        """加载模块策略配置。"""
        if not self._module or not self._module.path:
            return ""
        
        strategy_path = self._module.path / "strategy.yaml"
        if strategy_path.exists():
            try:
                return strategy_path.read_text(encoding="utf-8")
            except Exception:
                pass
        
        # 返回默认模板
        return f"""# {self._module.name} 策略配置
# 此配置会覆盖全局策略

reliability:
  max_retries: 3
  backoff_factor: 2.0

scheduling:
  default_priority: 100
  timeout_seconds: 300
"""
    
    def _save_strategy(self):
        """保存策略配置。"""
        if not self._module or not self._module.path:
            QMessageBox.warning(self, "保存失败", "模块路径不可用")
            return
        
        strategy_path = self._module.path / "strategy.yaml"
        try:
            content = self.strategy_editor.toPlainText()
            strategy_path.write_text(content, encoding="utf-8")
            QMessageBox.information(self, "保存成功", f"策略已保存到:\n{strategy_path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
    
    def _create_custom_page(self, menu_item) -> QWidget:
        """创建自定义页面（动态加载模块 UI）。"""
        if not self._module:
            return QWidget()

        if isinstance(menu_item.entry, str) and menu_item.entry.startswith("core:data_table:"):
            view_id = menu_item.entry.split(":", 2)[-1].strip()
            if not view_id:
                view_id = menu_item.id

            from src.core.mms.ui.module_data_table_page import ModuleDataTablePage

            return ModuleDataTablePage(self._module.name, view_id)

        # TODO: 使用 importlib 动态加载模块提供的 Widget
        # 暂时显示占位页
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel(menu_item.icon)
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        
        label = QLabel(f"{menu_item.label}\n\n(自定义页面: {menu_item.entry})")
        label.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 14px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        return page
    
    def _on_menu_changed(self, row: int):
        """菜单选择变化。"""
        if row < 0:
            return
        
        item = self.menu_list.item(row)
        if not item:
            return
        
        menu_id = item.data(Qt.ItemDataRole.UserRole)
        if menu_id == "__sep__":
            return
        
        if menu_id in self._menu_pages:
            self.content_stack.setCurrentWidget(self._menu_pages[menu_id])

    def _select_menu(self, menu_id: str):
        for row in range(self.menu_list.count()):
            item = self.menu_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == menu_id:
                self.menu_list.setCurrentRow(row)
                break

    def _remove_dev_link(self):
        if not self._module or self._module.source != ModuleSource.DEV_LINK:
            return

        reply = QMessageBox.question(
            self,
            "移除开发链接",
            f"确定要移除开发模块 '{self._module.name}' 的开发链接吗？\n本地源码目录不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from src.core.mms import get_module_registry

        registry = get_module_registry()
        if not registry.remove_dev_link(self._module.name):
            QMessageBox.warning(self, "移除失败", f"未找到开发链接: {self._module.name}")
            return

        fallback = registry.get_module(self._module.name)
        if fallback:
            self.set_module(fallback)
            source_text = "内置模块" if fallback.source == ModuleSource.BUILTIN else "正式安装模块"
            QMessageBox.information(
                self,
                "已切换",
                f"已移除开发链接，当前已回退到 {source_text}: {fallback.name}",
            )
            return

        QMessageBox.information(self, "已移除", f"已移除开发链接: {self._module.name}")
        self.back_requested.emit()
