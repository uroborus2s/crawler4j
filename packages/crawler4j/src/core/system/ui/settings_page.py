"""系统设置页面。

两栏式设计：
- 左侧导航: 分类列表
- 右侧内容: 对应分类的表单

配置分类：
- General: 通用设置
- Network: 网络设置
- Resources: 资源设置
- About: 关于
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.foundation.logging import logger
from src.core.system.preferences_service import (
    PreferenceKey,
    get_preferences_service,
)
from src.core.system.ui.about_dialog import AboutDialog
from src.core.system.version_service import get_version_service
from src.ui.app_icon import load_app_icon_pixmap
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class SettingsPage(QWidget):
    """系统设置页面。

    符合 SRS 5.10.3 UI 规范：
    - 两栏式布局
    - Auto-Save 策略
    - 重启提示
    """

    CATEGORIES = [
        ("general", "⚙️ 通用"),
        ("network", "🌐 网络"),
        ("resources", "📁 资源"),
        ("about", "ℹ️ 关于"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._preferences = get_preferences_service()
        self._pending_restart = False
        self._setup_ui()
        self._load_settings()
        self._connect_signals()

    def _setup_ui(self):
        """构建 UI 布局。"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左侧导航
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(180)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(30, 30, 40, 0.9);
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.1);
            }
            QListWidget::item {
                padding: 14px 16px;
                color: rgba(255, 255, 255, 0.7);
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QListWidget::item:selected {
                background: rgba(99, 102, 241, 0.3);
                color: white;
            }
        """)

        for cat_id, label in self.CATEGORIES:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cat_id)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)
        self.nav_list.currentItemChanged.connect(self._on_category_changed)
        layout.addWidget(self.nav_list)

        # 右侧内容区
        content_container = QWidget()
        content_container.setStyleSheet("background-color: #1a1a24;")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(24, 24, 24, 24)

        self.content_stack = QStackedWidget()
        self._pages = {}

        # General 页
        self._pages["general"] = self._create_general_page()
        self.content_stack.addWidget(self._pages["general"])

        # Network 页
        self._pages["network"] = self._create_network_page()
        self.content_stack.addWidget(self._pages["network"])

        # Resources 页
        self._pages["resources"] = self._create_resources_page()
        self.content_stack.addWidget(self._pages["resources"])

        # About 页
        self._pages["about"] = self._create_about_page()
        self.content_stack.addWidget(self._pages["about"])

        content_layout.addWidget(self.content_stack)

        # 重启提示条
        self.restart_bar = QFrame()
        self.restart_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(250, 204, 21, 0.2);
                border: 1px solid rgba(250, 204, 21, 0.5);
                border-radius: 6px;
                padding: 8px;
            }
        """)
        restart_layout = QHBoxLayout(self.restart_bar)
        restart_layout.setContentsMargins(12, 8, 12, 8)

        restart_icon = QLabel("⚠️")
        restart_layout.addWidget(restart_icon)

        restart_text = QLabel("部分设置需要重启应用后生效")
        restart_text.setStyleSheet("color: #facc15; font-size: 13px;")
        restart_layout.addWidget(restart_text)
        restart_layout.addStretch()

        self.restart_bar.hide()
        content_layout.addWidget(self.restart_bar)

        # 保存状态提示
        self.status_bar = QFrame()
        self.status_bar.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 6px;
                padding: 8px;
                margin-top: 8px;
            }
        """)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.addWidget(QLabel("✅"))
        save_label = QLabel("配置已自动保存")
        save_label.setStyleSheet("color: #34d399; font-size: 13px;")
        status_layout.addWidget(save_label)
        status_layout.addStretch()
        self.status_bar.hide()
        content_layout.addWidget(self.status_bar)

        # 底部操作栏
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.reset_btn = QPushButton("↺ 恢复默认")
        self.reset_btn.setStyleSheet(self._btn_style())
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        action_layout.addWidget(self.reset_btn)

        content_layout.addLayout(action_layout)

        layout.addWidget(content_container)

    def _create_general_page(self) -> QWidget:
        """创建通用设置页。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("通用设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        layout.addSpacing(16)

        # 外观组
        appearance_group = QGroupBox("外观")
        appearance_group.setStyleSheet(self._group_style())
        form = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self._populate_combo(self.theme_combo, [
            ("dark", "深色 (Dark)"),
            ("light", "浅色 (Light)"),
            ("system", "跟随系统"),
        ])
        form.addRow("主题:", self.theme_combo)

        self.locale_combo = QComboBox()
        self._populate_combo(self.locale_combo, [
            ("system", "跟随系统"),
            ("zh_CN", "简体中文"),
            ("en_US", "English"),
        ])
        form.addRow("语言:", self.locale_combo)

        layout.addWidget(appearance_group)

        # 启动组
        startup_group = QGroupBox("启动")
        startup_group.setStyleSheet(self._group_style())
        form2 = QFormLayout(startup_group)

        self.autostart_check = QCheckBox("开机自启动")
        form2.addRow(self.autostart_check)

        self.minimize_check = QCheckBox("启动时最小化到托盘")
        form2.addRow(self.minimize_check)

        layout.addWidget(startup_group)

        # 更新组
        update_group = QGroupBox("更新")
        update_group.setStyleSheet(self._group_style())
        form3 = QFormLayout(update_group)

        self.auto_update_check = QCheckBox("自动检查更新")
        form3.addRow(self.auto_update_check)

        layout.addWidget(update_group)

        layout.addStretch()
        return page

    def _create_network_page(self) -> QWidget:
        """创建网络设置页。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("网络设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        layout.addSpacing(16)

        # 代理组
        proxy_group = QGroupBox("代理")
        proxy_group.setStyleSheet(self._group_style())
        form = QFormLayout(proxy_group)

        self.proxy_mode_combo = QComboBox()
        self._populate_combo(self.proxy_mode_combo, [
            ("system", "跟随系统"),
            ("none", "不使用代理"),
            ("manual", "手动配置"),
        ])
        self.proxy_mode_combo.currentIndexChanged.connect(self._on_proxy_mode_changed)
        form.addRow("代理模式:", self.proxy_mode_combo)

        self.http_proxy_edit = QLineEdit()
        self.http_proxy_edit.setPlaceholderText("http://127.0.0.1:7890")
        form.addRow("HTTP 代理:", self.http_proxy_edit)

        layout.addWidget(proxy_group)

        # 指纹浏览器组
        browser_group = QGroupBox("指纹浏览器")
        browser_group.setStyleSheet(self._group_style())
        
        # 使用 TabWidget 分隔不同浏览器配置
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.1);
                background: rgba(0, 0, 0, 0.1);
                border-radius: 4px;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.7);
                padding: 8px 16px;
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: rgba(99, 102, 241, 0.3);
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background: rgba(255, 255, 255, 0.1);
            }
        """)
        
        # BitBrowser Tab
        bit_tab = QWidget()
        bit_form = QFormLayout(bit_tab)
        
        self.bit_port_spin = QSpinBox()
        self.bit_port_spin.setRange(1024, 65535)
        self.bit_port_spin.setValue(54345)
        bit_form.addRow("API 端口:", self.bit_port_spin)
        
        bit_path_layout = QHBoxLayout()
        self.bit_path_edit = QLineEdit()
        self.bit_path_edit.setPlaceholderText("BitBrowser 可执行文件路径")
        bit_path_layout.addWidget(self.bit_path_edit)
        
        bit_browse_btn = QPushButton("浏览...")
        bit_browse_btn.setStyleSheet(self._browse_btn_style())
        bit_browse_btn.clicked.connect(
            lambda: self._on_browse_browser(self.bit_path_edit, PreferenceKey.BITBROWSER_PATH)
        )
        bit_path_layout.addWidget(bit_browse_btn)
        bit_form.addRow("程序位置:", bit_path_layout)
        
        tab_widget.addTab(bit_tab, "BitBrowser")
        
        # VirtualBrowser Tab
        virt_tab = QWidget()
        virt_form = QFormLayout(virt_tab)
        
        self.virt_port_spin = QSpinBox()
        self.virt_port_spin.setRange(1024, 65535)
        self.virt_port_spin.setValue(50325)
        virt_form.addRow("API 端口:", self.virt_port_spin)
        
        self.virt_apikey_edit = QLineEdit()
        self.virt_apikey_edit.setPlaceholderText("VirtualBrowser API Key (可选)")
        virt_form.addRow("API 密钥:", self.virt_apikey_edit)
        
        virt_path_layout = QHBoxLayout()
        self.virt_path_edit = QLineEdit()
        self.virt_path_edit.setPlaceholderText("VirtualBrowser 可执行文件路径")
        virt_path_layout.addWidget(self.virt_path_edit)
        
        virt_browse_btn = QPushButton("浏览...")
        virt_browse_btn.setStyleSheet(self._browse_btn_style())
        virt_browse_btn.clicked.connect(
            lambda: self._on_browse_browser(self.virt_path_edit, PreferenceKey.VIRTUALBROWSER_PATH)
        )
        virt_path_layout.addWidget(virt_browse_btn)
        virt_form.addRow("程序位置:", virt_path_layout)
        
        tab_widget.addTab(virt_tab, "VirtualBrowser")
        
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.addWidget(tab_widget)
        
        layout.addWidget(browser_group)
        layout.addStretch()
        return page

    def _create_resources_page(self) -> QWidget:
        """创建资源设置页。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("资源设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        layout.addSpacing(16)

        # 日志组
        log_group = QGroupBox("日志")
        log_group.setStyleSheet(self._group_style())
        form3 = QFormLayout(log_group)

        self.log_level_combo = QComboBox()
        self._populate_combo(self.log_level_combo, [
            ("DEBUG", "调试 (DEBUG)"),
            ("INFO", "信息 (INFO)"),
            ("WARNING", "警告 (WARNING)"),
            ("ERROR", "错误 (ERROR)"),
        ])
        form3.addRow("日志级别:", self.log_level_combo)

        self.log_retention_spin = QSpinBox()
        self.log_retention_spin.setRange(1, 365)
        self.log_retention_spin.setValue(29)
        self.log_retention_spin.setSuffix(" 天")
        form3.addRow("日志保留:", self.log_retention_spin)

        layout.addWidget(log_group)

        layout.addStretch()
        return page

    def _create_about_page(self) -> QWidget:
        """创建关于页。"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("关于")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        layout.addWidget(title)
        layout.addSpacing(16)

        # 版本信息卡片
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 40, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
            }
        """)
        card_layout = QVBoxLayout(info_card)

        # from src.core.system.version_service import get_version_service (Moved to top)
        # service = get_version_service()
        # build_info = service.get_build_info()
        service = get_version_service()
        build_info = service.get_build_info()

        title_row = QHBoxLayout()
        title_row.setSpacing(12)

        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_pixmap = load_app_icon_pixmap(32)
        if not icon_pixmap.isNull():
            icon_label.setPixmap(icon_pixmap)
        title_row.addWidget(icon_label)

        name_label = QLabel("蛛行演略 · crawler4j")
        name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        title_row.addWidget(name_label)
        title_row.addStretch()
        card_layout.addLayout(title_row)

        version_label = QLabel(str(build_info))
        version_label.setStyleSheet("font-size: 14px; color: rgba(255, 255, 255, 0.7);")
        card_layout.addWidget(version_label)

        layout.addWidget(info_card)
        layout.addSpacing(16)

        # 操作按钮
        btn_layout = QHBoxLayout()

        about_btn = QPushButton("📋 完整信息")
        about_btn.setStyleSheet(self._btn_style())
        about_btn.clicked.connect(self._show_about_dialog)
        btn_layout.addWidget(about_btn)

        check_btn = QPushButton("🔍 检查更新")
        check_btn.setStyleSheet(self._btn_style())
        btn_layout.addWidget(check_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        return page

    def _group_style(self) -> str:
        """返回 GroupBox 样式。"""
        return """
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                color: rgba(255, 255, 255, 0.9);
                border: 1px solid;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLabel, QCheckBox {
                color: rgba(255, 255, 255, 0.8);
            }
            QLineEdit, QSpinBox {
                background: rgba(255, 255, 255, 0.1);
                padding: 0px 10px;
                color: white;
                min-width: 160px;  /* 增加最小宽度 */
                min-height: 24px;
            }
            QLineEdit:hover, QSpinBox:hover {
                border-color: rgba(99, 102, 241, 0.5);
            }
            
            /* StyledComboBox styling is handled by the component itself */
        """

    def _btn_style(self) -> str:
        """返回按钮样式。"""
        return """
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(99, 102, 241, 1);
            }
        """

    def _browse_btn_style(self) -> str:
        return """
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """

    def _populate_combo(self, combo: QComboBox, items: list[tuple[str, str]]):
        """填充下拉框 (data, display_text)。"""
        combo.clear()
        for data, text in items:
            combo.addItem(text, data)

    def _set_combo_value(self, combo: QComboBox, value: Any):
        """根据内部值选中下拉项。"""
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _get_combo_value(self, combo: QComboBox) -> Any:
        """获取当前选中的内部值。"""
        return combo.currentData()

    def _on_category_changed(self, current, previous):
        """分类切换处理。"""
        if current:
            cat_id = current.data(Qt.ItemDataRole.UserRole)
            if cat_id in self._pages:
                self.content_stack.setCurrentWidget(self._pages[cat_id])

    def _on_proxy_mode_changed(self, index: int = 0):
        """代理模式变更。"""
        mode = self.proxy_mode_combo.currentData()
        self.http_proxy_edit.setEnabled(mode == "manual")



    def _on_browse_browser(self, edit: QLineEdit, pref_key: PreferenceKey):
        """浏览浏览器路径。"""
        current = edit.text()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择浏览器可执行文件", current
        )
        if file_path:
            edit.setText(file_path)
            self._save_preference(pref_key, file_path)

    def _show_about_dialog(self):
        """显示关于弹窗。"""
        dialog = AboutDialog(self)
        dialog.exec()

    def _load_settings(self):
        """加载设置。"""
        prefs = self._preferences

        # General
        self._set_combo_value(self.theme_combo, prefs.get(PreferenceKey.THEME, "dark"))
        self._set_combo_value(self.locale_combo, prefs.get(PreferenceKey.LOCALE, "system"))
        self.autostart_check.setChecked(prefs.get(PreferenceKey.AUTOSTART, False))
        self.minimize_check.setChecked(prefs.get(PreferenceKey.MINIMIZE_ON_START, False))
        self.auto_update_check.setChecked(prefs.get(PreferenceKey.AUTO_UPDATE, True))

        # Network
        self._set_combo_value(self.proxy_mode_combo, prefs.get(PreferenceKey.PROXY_MODE, "system"))
        self.http_proxy_edit.setText(prefs.get(PreferenceKey.HTTP_PROXY, ""))
        self._on_proxy_mode_changed()

        # Browser
        self.bit_port_spin.setValue(prefs.get(PreferenceKey.BITBROWSER_PORT, 54345))
        self.bit_path_edit.setText(prefs.get(PreferenceKey.BITBROWSER_PATH, ""))
        self.virt_port_spin.setValue(prefs.get(PreferenceKey.VIRTUALBROWSER_PORT, 50325))
        self.virt_path_edit.setText(prefs.get(PreferenceKey.VIRTUALBROWSER_PATH, ""))
        self.virt_apikey_edit.setText(prefs.get(PreferenceKey.VIRTUALBROWSER_API_KEY, ""))

        # Resources
        self._set_combo_value(self.log_level_combo, prefs.get(PreferenceKey.LOG_LEVEL))
        self.log_retention_spin.setValue(prefs.get(PreferenceKey.LOG_RETENTION))

    def _connect_signals(self):
        """连接控件信号实现 Auto-Save。"""
        # General
        self.theme_combo.currentIndexChanged.connect(
            lambda: self._save_preference(PreferenceKey.THEME, self._get_combo_value(self.theme_combo))
        )
        self.locale_combo.currentIndexChanged.connect(
            lambda: self._save_preference(PreferenceKey.LOCALE, self._get_combo_value(self.locale_combo))
        )
        self.autostart_check.toggled.connect(
            lambda v: self._save_preference(PreferenceKey.AUTOSTART, v)
        )
        self.minimize_check.toggled.connect(
            lambda v: self._save_preference(PreferenceKey.MINIMIZE_ON_START, v)
        )
        self.auto_update_check.toggled.connect(
            lambda v: self._save_preference(PreferenceKey.AUTO_UPDATE, v)
        )

        # Network
        self.proxy_mode_combo.currentIndexChanged.connect(
            lambda: self._save_preference(PreferenceKey.PROXY_MODE, self._get_combo_value(self.proxy_mode_combo))
        )
        self.http_proxy_edit.editingFinished.connect(
            lambda: self._save_preference(PreferenceKey.HTTP_PROXY, self.http_proxy_edit.text())
        )

        # Browser
        self.bit_port_spin.valueChanged.connect(
            lambda v: self._save_preference(PreferenceKey.BITBROWSER_PORT, v)
        )
        self.bit_path_edit.editingFinished.connect(
            lambda: self._save_preference(PreferenceKey.BITBROWSER_PATH, self.bit_path_edit.text())
        )
        self.virt_port_spin.valueChanged.connect(
            lambda v: self._save_preference(PreferenceKey.VIRTUALBROWSER_PORT, v)
        )
        self.virt_apikey_edit.editingFinished.connect(
            lambda: self._save_preference(PreferenceKey.VIRTUALBROWSER_API_KEY, self.virt_apikey_edit.text())
        )
        self.virt_path_edit.editingFinished.connect(
            lambda: self._save_preference(PreferenceKey.VIRTUALBROWSER_PATH, self.virt_path_edit.text())
        )

        # Resources
        self.log_level_combo.currentIndexChanged.connect(
            lambda: self._save_preference(PreferenceKey.LOG_LEVEL, self._get_combo_value(self.log_level_combo))
        )
        self.log_retention_spin.valueChanged.connect(
            lambda v: self._save_preference(PreferenceKey.LOG_RETENTION, v)
        )
        
        # 监听后台变更
        self._preferences.preference_changed.connect(self._on_preference_changed)

    def _save_preference(self, key: PreferenceKey, value):
        """保存配置项。"""
        logger.debug(f"[Settings] Saving {key.value} = {value}")

        requires_restart = self._preferences.set(key, value)
        
        # 显示自动保存提示
        self.status_bar.show()
        # 2秒后自动隐藏
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.status_bar.hide())

        if requires_restart:
            self._pending_restart = True
            self.restart_bar.show()

    def _on_reset_clicked(self):
        """恢复默认设置。"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要恢复所有设置到默认值吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._preferences.reset_to_defaults()
            self._load_settings()

    def _on_preference_changed(self, key: str, value: Any, requires_restart: bool):
        """响应配置变更信号。"""
        # 简单刷新整个界面，确保一致性
        # 使用 blockSignals 防止与自动保存逻辑死循环
        self.blockSignals(True)
        try:
            self._load_settings()
        finally:
            self.blockSignals(False)

        if requires_restart:
            self.restart_bar.show()
