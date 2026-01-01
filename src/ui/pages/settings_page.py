"""Settings page.

Global application settings.
"""

import platform
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config import config
from src.core.browser_detector import BrowserDetector
from src.ui.widgets.confirm_dialog import ConfirmDialog
from src.ui.widgets.toast import Toast


class SettingsPage(QWidget):
    """Settings page.

    Sections:
    - Browser settings (type, API URL, connection test)
    - Task settings (concurrency, interval, retry)
    - Default SMS platform settings
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._setup_ui()
        self._connect_signals()
        self._load_settings()

    def _connect_signals(self):
        """Connect global signals."""
        from src.core.events import get_event_bus
        bean = get_event_bus()
        bean.event_emitted.connect(self._on_event)

    def _on_event(self, event):
        """Handle events."""
        from src.core.events import EventType
        if event.type == EventType.SETTINGS_UPDATED:
            data = event.data or {}
            if "concurrency_limit" in data and data.get("source") != "settings":
                 new_val = int(data["concurrency_limit"])
                 self.concurrency_spin.setValue(new_val)

    def _setup_ui(self):
        """Setup the page UI."""
        # Custom style for GroupBox to place title inside
        self.setStyleSheet("""
            QGroupBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 10px; /* Leave space for title if outside, but we want inside */
                padding-top: 35px; /* Reserve space for title */
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: padding;
                subcontrol-position: top left;
                left: 15px;
                top: 10px;
                background-color: transparent;
                color: #cdd6f4;
            }
            QFormLayout {
                margin: 0px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        title = QLabel("设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Browser settings
        browser_group = QGroupBox("浏览器设置")
        browser_layout = QVBoxLayout(browser_group)

        # Browser type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("浏览器类型:"))

        self.browser_group = QButtonGroup(self)
        self.bit_radio = QRadioButton("BitBrowser")
        self.virtual_radio = QRadioButton("VirtualBrowser")
        self.browser_group.addButton(self.bit_radio, 0)
        self.browser_group.addButton(self.virtual_radio, 1)
        type_layout.addWidget(self.bit_radio)
        type_layout.addWidget(self.virtual_radio)
        type_layout.addStretch()

        # Install status
        self.install_status = QLabel("检测中...")
        type_layout.addWidget(self.install_status)

        # Manual path select
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("安装路径:"))
        self.path_display = QLabel("未设置 (自动检测)")
        self.path_display.setStyleSheet("color: #a6adc8; font-style: italic;")
        path_layout.addWidget(self.path_display, 1)

        self.browse_btn = QPushButton("手动选择...")
        self.browse_btn.setMinimumWidth(100)
        self.browse_btn.clicked.connect(self._on_browse_path)
        path_layout.addWidget(self.browse_btn)

        browser_layout.addLayout(path_layout)
        browser_layout.addLayout(type_layout)

        # API URL
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("API 地址:"))
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("http://127.0.0.1:54345")
        url_layout.addWidget(self.api_url_input, 1)

        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        url_layout.addWidget(self.test_btn)

        browser_layout.addLayout(url_layout)
        layout.addWidget(browser_group)

        # Task settings
        task_group = QGroupBox("任务设置")
        task_layout = QFormLayout(task_group)
        task_layout.setSpacing(12)
        task_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 20)
        self.concurrency_spin.setValue(10)
        self.concurrency_spin.setMinimumWidth(100)
        task_layout.addRow("最大并发数:", self.concurrency_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setMinimumWidth(100)
        task_layout.addRow("任务间隔:", self.interval_spin)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 5)
        self.retry_spin.setValue(3)
        self.retry_spin.setMinimumWidth(100)
        task_layout.addRow("失败重试次数:", self.retry_spin)

        layout.addWidget(task_group)
        
        layout.addWidget(task_group)

        # SMS & Automation Limits Group
        sms_container = QGroupBox("接码平台与限制设置")
        container_layout = QHBoxLayout(sms_container)
        container_layout.setSpacing(20)

        # Left Column: SMS Platform Settings
        sms_layout = QFormLayout()
        sms_layout.setContentsMargins(0, 0, 0, 0)
        sms_layout.setSpacing(12)

        # 接口域名
        self.sms_host_input = QLineEdit()
        self.sms_host_input.setPlaceholderText("例如: 3.112.30.233:8000")
        self.sms_host_input.setMinimumWidth(200)
        sms_layout.addRow("接口域名", self.sms_host_input)

        # 用户名
        self.sms_username_input = QLineEdit()
        self.sms_username_input.setPlaceholderText("接码平台用户名")
        self.sms_username_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.sms_username_input.setMinimumWidth(200)
        sms_layout.addRow("用户名", self.sms_username_input)

        # 密码
        self.sms_password_input = QLineEdit()
        self.sms_password_input.setPlaceholderText("接码平台密码")
        self.sms_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.sms_password_input.setMinimumWidth(200)
        sms_layout.addRow("密码", self.sms_password_input)

        # 产品ID
        self.sms_product_id_input = QLineEdit()
        self.sms_product_id_input.setPlaceholderText("例如: 236")
        self.sms_product_id_input.setMinimumWidth(200)
        sms_layout.addRow("产品ID", self.sms_product_id_input)

        container_layout.addLayout(sms_layout, 1)

        # Right Column: Automation Limits
        limit_layout = QFormLayout()
        limit_layout.setContentsMargins(0, 0, 0, 0)
        limit_layout.setSpacing(12)

        # Limit spinbox
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 200)
        self.limit_spin.setValue(50)
        self.limit_spin.setMinimumWidth(120)
        self.limit_spin.setSuffix(" 个/天")
        limit_layout.addRow("每日自动创建:", self.limit_spin)

        # Current status
        self.limit_status_label = QLabel("今日已创建: 0")
        self.limit_status_label.setStyleSheet("color: #a6adc8; font-weight: bold;")
        limit_layout.addRow("当前状态:", self.limit_status_label)

        # Reset button
        self.reset_limit_btn = QPushButton("重置计数")
        self.reset_limit_btn.setFixedWidth(100)
        self.reset_limit_btn.setStyleSheet("padding: 4px;")
        self.reset_limit_btn.clicked.connect(self._reset_limit_count)
        limit_layout.addRow("", self.reset_limit_btn)

        container_layout.addLayout(limit_layout, 1)

        layout.addWidget(sms_container)

        # Buttons
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()

        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset_defaults)
        buttons.addWidget(reset_btn)

        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save_settings)
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

        # Connect browser type change
        self.browser_group.buttonClicked.connect(self._on_browser_type_changed)

    def _load_settings(self):
        """Load current settings."""
        # Browser type
        if config.browser_type == "virtualbrowser":
            self.virtual_radio.setChecked(True)
        else:
            self.bit_radio.setChecked(True)

        self.api_url_input.setText(config.browser_api_url)

        # Task settings
        self.concurrency_spin.setValue(config.concurrency_limit)
        self.interval_spin.setValue(config.task_interval)
        self.retry_spin.setValue(config.retry_count)
        
        # Limit settings
        if hasattr(self, "limit_spin"):
            self.limit_spin.setValue(config.daily_auto_env_creation_limit)
            self._update_limit_status()

        # SMS settings
        self.sms_host_input.setText(config.sms_platform_host)
        self.sms_username_input.setText(config.sms_platform_username)
        self.sms_password_input.setText(config.sms_platform_password)
        self.sms_product_id_input.setText(config.sms_platform_product_id)

        # Check browser installation and update path display
        self._update_path_display()
        self._check_browser_install()
        
    def _update_limit_status(self):
        """Update the daily limit usage label."""
        if not hasattr(self, "limit_status_label"):
            return
            
        from src.utils.storage import SettingsRepository
        repo = SettingsRepository()
        current = repo.get_sms_creation_count_today()
        self.limit_status_label.setText(f"今日已创建: {current}")
        
    def _reset_limit_count(self):
        """Reset the daily creation count."""
        if ConfirmDialog.confirm(self, "重置计数", "确定要重置今日接码创建计数吗？"):
            from src.utils.storage import SettingsRepository
            SettingsRepository().reset_sms_creation_count()
            self._update_limit_status()
            Toast.success(self, "计数已重置")

    def _on_browser_type_changed(self):
        """Handle browser type change."""
        self._update_path_display()
        self._check_browser_install()

    def _update_path_display(self):
        """Update the manual path display based on selected browser type."""
        browser_type = (
            "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
        )
        manual_path = (
            config.virtualbrowser_path
            if browser_type == "virtualbrowser"
            else config.bitbrowser_path
        )

        if manual_path:
            self.path_display.setText(manual_path)
            self.path_display.setStyleSheet("color: #cdd6f4; font-style: normal;")
        else:
            self.path_display.setText("未设置 (自动检测)")
            self.path_display.setStyleSheet("color: #a6adc8; font-style: italic;")

    def _on_browse_path(self):
        """Manually select browser installation path."""
        browser_type = (
            "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
        )
        file_filter = (
            "Applications (*.app)"
            if platform.system() == "Darwin"
            else "Executable (*.exe)"
        )

        path, _ = QFileDialog.getOpenFileName(
            self,
            f"选择 {browser_type} 安装位置",
            "/Applications" if platform.system() == "Darwin" else "C:/Program Files",
            file_filter,
        )

        if path:
            if browser_type == "bitbrowser":
                config.bitbrowser_path = path
            else:
                config.virtualbrowser_path = path

            self._update_path_display()
            self._check_browser_install()

    def _check_browser_install(self):
        """Check if selected browser is installed."""
        browser_type = (
            "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
        )

        # Check manual path first
        manual_path = self.path_display.text()
        if manual_path != "未设置 (自动检测)" and Path(manual_path).exists():
            is_installed = True
        else:
            is_installed = BrowserDetector.is_installed(browser_type)

        if is_installed:
            self.install_status.setText("🟢 已安装")
            self.install_status.setStyleSheet("color: #a6e3a1;")
        else:
            self.install_status.setText("🔴 未安装")
            self.install_status.setStyleSheet("color: #f38ba8;")

    def _test_connection(self):
        """Test browser API connection."""
        url = self.api_url_input.text().strip()
        if not url:
            Toast.error(self, "请输入 API 地址")
            return

        self.test_btn.setText("测试中...")
        self.test_btn.setEnabled(False)

        # Simple connection test
        success = BrowserDetector.test_api_connection(url)

        self.test_btn.setText("测试连接")
        self.test_btn.setEnabled(True)

        if success:
            Toast.success(self, "连接成功")
        else:
            # Determine path for auto-launch
            browser_type = (
                "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
            )

            # 1. Try manual path from config
            launch_path = (
                config.virtualbrowser_path
                if browser_type == "virtualbrowser"
                else config.bitbrowser_path
            )

            # 2. If no manual path, try auto-detection
            if not launch_path or not Path(launch_path).exists():
                detected_path = BrowserDetector.get_installation_path(browser_type)
                if detected_path:
                    launch_path = str(detected_path)

            if launch_path and Path(launch_path).exists():
                if ConfirmDialog.confirm(
                    self,
                    "连接失败",
                    f"未检测到 {browser_type} API 服务。\n是否尝试启动客户端？\n路径: {launch_path}",
                ):
                    try:
                        QDesktopServices.openUrl(QUrl.fromLocalFile(launch_path))
                        Toast.info(self, "正在启动客户端，请稍候再试...")
                    except Exception as e:
                        Toast.error(self, f"启动失败: {str(e)}")
            else:
                Toast.error(
                    self, "连接失败，无法在标准位置找到应用，请手动设置安装路径。"
                )

    def _save_settings(self):
        """Save all settings."""
        # Browser settings
        config.browser_type = (
            "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
        )
        config.browser_api_url = self.api_url_input.text().strip()

        # Task settings
        config.concurrency_limit = self.concurrency_spin.value()
        config.task_interval = self.interval_spin.value()
        config.retry_count = self.retry_spin.value()
        
        # Limit settings
        if hasattr(self, "limit_spin"):
            config.daily_auto_env_creation_limit = self.limit_spin.value()

        # SMS settings
        config.sms_platform_host = self.sms_host_input.text().strip()
        config.sms_platform_username = self.sms_username_input.text().strip()
        config.sms_platform_password = self.sms_password_input.text()
        config.sms_platform_product_id = self.sms_product_id_input.text().strip()

        Toast.success(self, "设置已保存")
        
        # Emit update event to sync with other pages
        from src.core.events import EventType, get_event_bus
        get_event_bus().emit(
            EventType.SETTINGS_UPDATED, 
            {
                "concurrency_limit": config.concurrency_limit,
                "source": "settings"
            }
        )

    def _reset_defaults(self):
        """Reset to default values."""
        self.bit_radio.setChecked(True)
        self.api_url_input.setText("http://127.0.0.1:54345")
        self.concurrency_spin.setValue(10)
        self.interval_spin.setValue(5)
        self.retry_spin.setValue(3)
        if hasattr(self, "limit_spin"):
            self.limit_spin.setValue(50)
        self.sms_host_input.clear()
        self.sms_username_input.clear()
        self.sms_password_input.clear()
        self.sms_product_id_input.clear()

        Toast.info(self, "已恢复默认设置")
