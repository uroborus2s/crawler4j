"""Settings page.

Global application settings.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QLabel,
    QRadioButton,
    QButtonGroup,
)

from src.config import config
from src.core.browser_detector import BrowserDetector
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
        self._load_settings()
    
    def _setup_ui(self):
        """Setup the page UI."""
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
        
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 20)
        self.concurrency_spin.setValue(10)
        task_layout.addRow("最大并发数:", self.concurrency_spin)
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" 秒")
        task_layout.addRow("任务间隔:", self.interval_spin)
        
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 5)
        self.retry_spin.setValue(3)
        task_layout.addRow("失败重试次数:", self.retry_spin)
        
        layout.addWidget(task_group)
        
        # SMS platform settings
        sms_group = QGroupBox("接码平台默认设置")
        sms_layout = QFormLayout(sms_group)
        sms_layout.setSpacing(12)
        
        self.sms_platform_combo = QComboBox()
        self.sms_platform_combo.addItems(["", "平台A", "平台B", "平台C"])
        self.sms_platform_combo.setEditable(True)
        sms_layout.addRow("默认平台:", self.sms_platform_combo)
        
        self.sms_url_input = QLineEdit()
        self.sms_url_input.setPlaceholderText("http://api.example.com/sms")
        sms_layout.addRow("默认 API URL:", self.sms_url_input)
        
        self.sms_key_input = QLineEdit()
        self.sms_key_input.setPlaceholderText("API Key")
        self.sms_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        sms_layout.addRow("默认 API Key:", self.sms_key_input)
        
        layout.addWidget(sms_group)
        
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
        
        # SMS settings
        self.sms_platform_combo.setCurrentText(config.default_sms_platform)
        self.sms_url_input.setText(config.default_sms_url)
        self.sms_key_input.setText(config.default_sms_key)
        
        # Check browser installation
        self._check_browser_install()
    
    def _on_browser_type_changed(self):
        """Handle browser type change."""
        self._check_browser_install()
    
    def _check_browser_install(self):
        """Check if selected browser is installed."""
        browser_type = "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
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
            Toast.error(self, "连接失败，请检查浏览器是否运行")
    
    def _save_settings(self):
        """Save all settings."""
        # Browser settings
        config.browser_type = "virtualbrowser" if self.virtual_radio.isChecked() else "bitbrowser"
        config.browser_api_url = self.api_url_input.text().strip()
        
        # Task settings
        config.concurrency_limit = self.concurrency_spin.value()
        config.task_interval = self.interval_spin.value()
        config.retry_count = self.retry_spin.value()
        
        # SMS settings
        config.default_sms_platform = self.sms_platform_combo.currentText()
        config.default_sms_url = self.sms_url_input.text().strip()
        config.default_sms_key = self.sms_key_input.text()
        
        Toast.success(self, "设置已保存")
    
    def _reset_defaults(self):
        """Reset to default values."""
        self.bit_radio.setChecked(True)
        self.api_url_input.setText("http://127.0.0.1:54345")
        self.concurrency_spin.setValue(10)
        self.interval_spin.setValue(5)
        self.retry_spin.setValue(3)
        self.sms_platform_combo.setCurrentText("")
        self.sms_url_input.clear()
        self.sms_key_input.clear()
        
        Toast.info(self, "已恢复默认设置")
