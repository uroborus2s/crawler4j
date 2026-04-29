"""模块详情页。

采用主从导航模式：左侧二级菜单，右侧内容区。
固定菜单（基本信息、任务链）+ 模块自定义菜单。
"""

import asyncio

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.mms.github_credentials import get_github_credential_store
from src.core.mms.models import ModuleInfo, ModuleSource, UIPageInfo
from src.core.mms.service import get_module_service
from src.core.mms.ui.dev_link_actions import remove_dev_link_and_describe
from src.core.mms.ui.module_config_page import ModuleConfigPage
from src.core.mms.ui.managed_page_renderer import ManagedPageRenderer
from src.ui.components.button import StyledButton
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.message_dialog import MessageDialog


class ModuleDetailPage(QWidget):
    """模块详情页。
    
    主从导航模式：
        - 左侧: 二级菜单 (固定 + 自定义)
        - 右侧: 内容区 (根据菜单切换)
    """
    
    back_requested = pyqtSignal()  # 返回列表页信号
    
    BASE_MENU = [
        ("info", "📋", "基本信息"),
        ("config", "⚙️", "配置"),
        ("workflows", "⚡", "任务链"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._module: ModuleInfo | None = None
        self._menu_pages: dict[str, QWidget] = {}
        self._hosted_page_infos: dict[str, UIPageInfo] = {}
        self._menu_navigation_params: dict[str, dict[str, object]] = {}
        self._pending_tasks: set[asyncio.Task] = set()
        self.repo_token_status_label: QLabel | None = None
        self.repo_token_edit: QLineEdit | None = None
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
        back_btn = StyledButton("← 返回", variant="ghost", min_height=36, min_width=92)
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
        self.menu_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.menu_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self._menu_navigation_params.clear()
        
        # 更新标题
        display = module.manifest.display_name or module.name
        self.title_label.setText(f"{self._module_icon(module)} {display}")
        
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
        self._hosted_page_infos.clear()
        
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
            if hasattr(page, "set_module") and self._module is not None:
                page.set_module(self._module)
            self._menu_pages[menu_id] = page
            self.content_stack.addWidget(page)
        
        # 模块宿主页入口
        if self._module:
            hosted_pages = list(self._module.manifest.ui_extension.pages)
            if hosted_pages:
                # 分隔符
                separator = QListWidgetItem("────────")
                separator.setData(Qt.ItemDataRole.UserRole, "__sep__")
                separator.setFlags(separator.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.menu_list.addItem(separator)
                
                for page_info in hosted_pages:
                    item = QListWidgetItem(f"{page_info.icon} {page_info.label}")
                    item.setData(Qt.ItemDataRole.UserRole, page_info.id)
                    self.menu_list.addItem(item)
                    self._hosted_page_infos[page_info.id] = page_info
    
    def _create_fixed_page(self, menu_id: str) -> QWidget:
        """创建固定页面。"""
        if menu_id == "info":
            return self._create_info_page()
        elif menu_id == "config":
            return ModuleConfigPage()
        elif menu_id == "workflows":
            return self._create_workflows_page()
        return QWidget()

    @staticmethod
    def _module_icon(module: ModuleInfo) -> str:
        pages = list(module.manifest.ui_extension.pages)
        if pages:
            return str(pages[0].icon or "📦").strip() or "📦"
        return "📦"
    
    def _create_info_page(self) -> QWidget:
        """创建基本信息页面。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        self.repo_token_status_label = None
        self.repo_token_edit = None
        
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
            ("GitHub 仓库", manifest.upgrade_source.repo or "未声明"),
            (
                "来源",
                "内置"
                if self._module.source == ModuleSource.BUILTIN
                else "开发链接"
                if self._module.source == ModuleSource.DEV_LINK
                else "外部",
            ),
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

        repo = str(manifest.upgrade_source.repo or "").strip()
        if repo:
            token_status_row = QHBoxLayout()
            token_status_label = QLabel("GitHub Token:")
            token_status_label.setStyleSheet(
                "color: rgba(255,255,255,0.5); font-size: 13px; min-width: 80px;"
            )
            token_status_row.addWidget(token_status_label)

            self.repo_token_status_label = QLabel()
            self.repo_token_status_label.setStyleSheet("color: white; font-size: 13px;")
            token_status_row.addWidget(self.repo_token_status_label)
            token_status_row.addStretch()
            card_layout.addLayout(token_status_row)

            self.repo_token_edit = QLineEdit()
            self.repo_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.repo_token_edit.setPlaceholderText("输入该仓库的 GitHub Token")
            card_layout.addWidget(self.repo_token_edit)

            token_actions = QHBoxLayout()
            save_token_btn = StyledButton("保存 Token", variant="success", min_height=34, min_width=108)
            save_token_btn.clicked.connect(self._save_repo_token)
            token_actions.addWidget(save_token_btn)

            test_token_btn = StyledButton("测试连接", variant="primary", min_height=34, min_width=108)
            test_token_btn.clicked.connect(self._test_repo_token)
            token_actions.addWidget(test_token_btn)

            clear_token_btn = StyledButton("清除 Token", variant="danger", min_height=34, min_width=108)
            clear_token_btn.clicked.connect(self._clear_repo_token)
            token_actions.addWidget(clear_token_btn)
            token_actions.addStretch()
            card_layout.addLayout(token_actions)
            self._refresh_repo_token_status()

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

            remove_btn = StyledButton("移除开发链接", variant="danger", min_height=34, min_width=136)
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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

    def _create_hosted_page(self, page_info: UIPageInfo) -> QWidget:
        """创建宿主页入口页面。"""
        if not self._module:
            return QWidget()

        initial_params = self._menu_navigation_params.get(page_info.id)
        return ManagedPageRenderer(
            self._module.name,
            page_info.id,
            module_info=self._module,
            open_page_callback=self._open_page,
            initial_params=initial_params,
        )

    def _create_custom_page_placeholder(self, page_info: UIPageInfo, title: str, message: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon = QLabel(page_info.icon)
        icon.setStyleSheet("font-size: 48px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        
        label = QLabel(f"{page_info.label}\n\n{title}")
        label.setStyleSheet("color: rgba(255,255,255,0.75); font-size: 14px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        detail = QLabel(f"{message}\n\n页面 ID: {page_info.id}")
        detail.setStyleSheet("color: rgba(255,255,255,0.5); font-size: 12px;")
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(detail)
        
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
        
        page = self._ensure_menu_page(menu_id)
        if page is not None:
            self.content_stack.setCurrentWidget(page)

    def _ensure_menu_page(self, menu_id: str) -> QWidget | None:
        page = self._menu_pages.get(menu_id)
        if page is not None:
            if menu_id in self._hosted_page_infos and hasattr(page, "refresh"):
                if hasattr(page, "set_navigation_params"):
                    page.set_navigation_params(self._menu_navigation_params.get(menu_id), auto_refresh=False)
                page.refresh()
            return page

        page_info = self._hosted_page_infos.get(menu_id)
        if page_info is None:
            return None

        page = self._create_hosted_page(page_info)
        self._menu_pages[menu_id] = page
        self.content_stack.addWidget(page)
        return page

    def _select_menu(self, menu_id: str):
        for row in range(self.menu_list.count()):
            item = self.menu_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == menu_id:
                self.menu_list.setCurrentRow(row)
                break

    @staticmethod
    def _normalize_navigation_params(params: dict[str, object] | None) -> dict[str, object]:
        if not isinstance(params, dict):
            return {}
        return dict(params)

    def _resolve_hosted_page_info(self, page_id: str) -> UIPageInfo | None:
        page_info = self._hosted_page_infos.get(page_id)
        if page_info is not None:
            return page_info
        if not self._module:
            return None

        try:
            descriptor = get_module_service().get_runtime_descriptor(
                self._module.name,
                force_reload=self._module.source != ModuleSource.BUILTIN,
            )
        except Exception:
            return None

        runtime_page = descriptor.pages.get(page_id)
        if runtime_page is None:
            return None

        spec = runtime_page.spec
        return UIPageInfo(
            id=str(spec.id or page_id).strip() or page_id,
            icon=str(spec.icon or "📋").strip() or "📋",
            label=str(spec.label or page_id).strip() or page_id,
        )

    def _open_page(self, page_id: str, params: dict[str, object] | None = None) -> None:
        normalized_page_id = str(page_id or "").strip()
        page_info = self._resolve_hosted_page_info(normalized_page_id)
        if page_info is None:
            MessageDialog.warning(self, "页面跳转失败", f"未找到宿主页: {page_id}")
            return
        self._menu_navigation_params[normalized_page_id] = self._normalize_navigation_params(params)

        if normalized_page_id not in self._hosted_page_infos:
            page = self._menu_pages.get(normalized_page_id)
            if page is None:
                page = self._create_hosted_page(page_info)
                self._menu_pages[normalized_page_id] = page
                self.content_stack.addWidget(page)
            else:
                if hasattr(page, "set_navigation_params"):
                    page.set_navigation_params(
                        self._menu_navigation_params.get(normalized_page_id),
                        auto_refresh=False,
                    )
                if hasattr(page, "refresh"):
                    page.refresh()
            self.content_stack.setCurrentWidget(page)
            return

        current_item = self.menu_list.currentItem()
        current_menu_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        if current_menu_id == normalized_page_id:
            page = self._ensure_menu_page(normalized_page_id)
            if page is not None:
                self.content_stack.setCurrentWidget(page)
            return

        self._select_menu(normalized_page_id)

    def _remove_dev_link(self):
        if not self._module or self._module.source != ModuleSource.DEV_LINK:
            return

        confirmed = ConfirmDialog.confirm(
            self,
            "移除开发链接",
            f"确定要移除开发模块 '{self._module.name}' 的开发链接吗？\n本地源码目录不会被删除。",
            confirm_text="移除",
            danger=True,
        )
        if not confirmed:
            return

        try:
            result = remove_dev_link_and_describe(self._module.name)
        except Exception as exc:
            MessageDialog.warning(self, "移除失败", str(exc))
            return

        if result.fallback:
            self.set_module(result.fallback)
            MessageDialog.information(self, result.title, result.message)
            return

        MessageDialog.information(self, result.title, result.message)
        self.back_requested.emit()

    def _track_task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    def _current_repo(self) -> str:
        if not self._module:
            raise ValueError("当前未选择模块")
        repo = str(self._module.manifest.upgrade_source.repo or "").strip()
        if not repo:
            raise ValueError("当前模块未声明 GitHub 仓库")
        from src.core.mms.release_service import ModuleReleaseService

        return ModuleReleaseService.normalize_repo(repo)

    def _refresh_repo_token_status(self) -> None:
        if not self.repo_token_status_label:
            return
        try:
            has_token = get_github_credential_store().has_token(self._current_repo())
        except Exception as exc:
            self.repo_token_status_label.setText(f"异常: {exc}")
            self.repo_token_status_label.setStyleSheet("color: #f87171; font-size: 13px;")
            return
        if has_token:
            self.repo_token_status_label.setText("已配置")
            self.repo_token_status_label.setStyleSheet("color: #4ade80; font-size: 13px;")
        else:
            self.repo_token_status_label.setText("未配置")
            self.repo_token_status_label.setStyleSheet("color: rgba(255,255,255,0.72); font-size: 13px;")

    def _save_repo_token(self) -> None:
        if not self.repo_token_edit:
            return
        token = self.repo_token_edit.text().strip()
        if not token:
            MessageDialog.warning(self, "保存失败", "请输入 GitHub Token")
            return
        try:
            repo = self._current_repo()
            get_github_credential_store().set_token(repo, token)
        except Exception as exc:
            MessageDialog.warning(self, "保存失败", str(exc))
            return
        self.repo_token_edit.clear()
        self._refresh_repo_token_status()
        MessageDialog.information(self, "保存成功", f"已保存仓库 {repo} 的 GitHub Token")

    def _clear_repo_token(self) -> None:
        try:
            repo = self._current_repo()
        except Exception as exc:
            MessageDialog.warning(self, "清除失败", str(exc))
            return
        confirmed = ConfirmDialog.confirm(
            self,
            "清除 GitHub Token",
            f"确定要清除仓库 {repo} 的 GitHub Token 吗？",
            confirm_text="清除",
            danger=True,
        )
        if not confirmed:
            return
        get_github_credential_store().clear_token(repo)
        if self.repo_token_edit:
            self.repo_token_edit.clear()
        self._refresh_repo_token_status()
        MessageDialog.information(self, "已清除", f"已清除仓库 {repo} 的 GitHub Token")

    def _test_repo_token(self) -> None:
        self._track_task(self._test_repo_token_async())

    async def _test_repo_token_async(self) -> None:
        try:
            repo = self._current_repo()
            token = self.repo_token_edit.text().strip() if self.repo_token_edit else ""
            if not token:
                token = get_github_credential_store().get_token(repo) or ""
            if not token:
                raise ValueError("请先输入或保存 GitHub Token")
            from src.core.mms.release_service import get_module_release_service

            await get_module_release_service().verify_repo_accessible(repo, github_token=token)
        except Exception as exc:
            await MessageDialog.warning_async(self, "连接失败", str(exc))
            return
        await MessageDialog.information_async(self, "连接成功", f"GitHub 仓库连接正常: {repo}")
