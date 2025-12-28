"""Create environment dialog.

Dialog for manually binding a Ctrip account and a Labor account, creating browser profiles.
"""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.storage import CtripAccountRepository, LaborAccountRepository


class CreateEnvDialog(QDialog):
    """Dialog for creating an environment binding and browser profile.
    
    Features:
    - Profile basic info (Name, Group)
    - Proxy configuration
    - Account binding
    - Fingerprint randomization
    """
    
    def __init__(self, parent=None, edit_mode=False, env_data=None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget.
            edit_mode: Whether in edit mode (not fully implemented for V1).
            env_data: Existing data for edit mode.
        """
        super().__init__(parent)
        
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.result_data: dict | None = None
        
        self.setWindowTitle("创建环境" if not edit_mode else "编辑环境")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(700)
        
        # Current fingerprint config
        self.fingerprint_config = {}
        
        self._setup_ui()
        self._load_accounts()
        self._generate_random_fingerprint() # Initial random
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll Area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # 1. Basic Info
        basic_group = QGroupBox("基础设置")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("环境名称")
        basic_layout.addRow("名称:", self.name_input)
        
        # Group (simplified as text for now, could be combo)
        self.group_input = QLineEdit()
        self.group_input.setPlaceholderText("未分组")
        basic_layout.addRow("分组:", self.group_input)
        
        layout.addWidget(basic_group)
        
        # 2. Account Binding
        account_group = QGroupBox("账号绑定")
        account_layout = QFormLayout(account_group)
        
        self.ctrip_combo = QComboBox()
        account_layout.addRow("携程账号:", self.ctrip_combo)
        
        self.labor_combo = QComboBox()
        account_layout.addRow("劳保账号:", self.labor_combo)
        
        layout.addWidget(account_group)
        
        # 3. Proxy Settings
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QVBoxLayout(proxy_group)
        
        # Proxy Type
        type_layout = QHBoxLayout()
        self.proxy_type_group = QButtonGroup(self)
        
        self.auto_proxy_radio = QRadioButton("自动从 IP 池获取 (推荐)")
        self.no_proxy_radio = QRadioButton("不使用代理")
        self.custom_proxy_radio = QRadioButton("手动设置") # Keep it but de-emphasize
        
        self.proxy_type_group.addButton(self.auto_proxy_radio, 3) # Value 3 for auto
        self.proxy_type_group.addButton(self.no_proxy_radio, 1)
        self.proxy_type_group.addButton(self.custom_proxy_radio, 2)
        
        type_layout.addWidget(self.auto_proxy_radio)
        type_layout.addWidget(self.no_proxy_radio)
        type_layout.addWidget(self.custom_proxy_radio)
        
        type_layout.addStretch()
        self.auto_proxy_radio.setChecked(True) # Default to Auto
        
        proxy_layout.addLayout(type_layout)
        
        # Proxy Details
        self.proxy_details = QWidget()
        details_layout = QFormLayout(self.proxy_details)
        
        self.proxy_proto_combo = QComboBox()
        self.proxy_proto_combo.addItems(["http", "socks5", "socks4"])
        details_layout.addRow("类型:", self.proxy_proto_combo)
        
        self.proxy_host = QLineEdit()
        self.proxy_host.setPlaceholderText("127.0.0.1")
        details_layout.addRow("主机:", self.proxy_host)
        
        self.proxy_port = QLineEdit()
        self.proxy_port.setPlaceholderText("8080")
        details_layout.addRow("端口:", self.proxy_port)
        
        self.proxy_user = QLineEdit()
        details_layout.addRow("账号:", self.proxy_user)
        
        self.proxy_pass = QLineEdit()
        self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        details_layout.addRow("密码:", self.proxy_pass)
        
        self.proxy_details.hide() # Hidden by default
        proxy_layout.addWidget(self.proxy_details)
        
        self.proxy_type_group.idClicked.connect(self._on_proxy_type_changed)
        
        layout.addWidget(proxy_group)
        
        # 4. Fingerprint Settings
        fp_group = QGroupBox("指纹设置")
        fp_layout = QVBoxLayout(fp_group)
        
        # Randomize Button
        rand_layout = QHBoxLayout()
        self.rand_btn = QPushButton("🎲 随机生成指纹")
        self.rand_btn.clicked.connect(self._generate_random_fingerprint)
        rand_layout.addWidget(self.rand_btn)
        rand_layout.addStretch()
        fp_layout.addLayout(rand_layout)
        
        # Display Area
        self.fp_display = QTextEdit()
        self.fp_display.setReadOnly(True)
        self.fp_display.setMaximumHeight(150)
        self.fp_display.setStyleSheet("background-color: #1e1e2e; color: #a6e3a1; font-family: monospace;")
        fp_layout.addWidget(self.fp_display)
        
        layout.addWidget(fp_group)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)
        
        # Bottom Buttons
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(24, 16, 24, 24)
        
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f38ba8;")
        self.error_label.hide()
        btn_layout.addWidget(self.error_label)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.create_btn = QPushButton("立即创建")
        self.create_btn.setObjectName("primary")
        self.create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(self.create_btn)
        
        main_layout.addWidget(btn_container)
        
    def _load_accounts(self):
        """Load available accounts."""
        # Ctrip
        self.ctrip_combo.addItem("不绑定", None)
        ctrip_accounts = self.ctrip_repo.get_all()
        for acc in ctrip_accounts:
            self.ctrip_combo.addItem(f"{acc['phone']} (ID: {acc['id']})", acc["id"])
            
        # Labor
        self.labor_combo.addItem("不绑定", None)
        labor_accounts = self.labor_repo.get_active_unbound()
        for acc in labor_accounts:
            self.labor_combo.addItem(f"{acc['phone']} (ID: {acc['id']})", acc["id"])
            
    def _on_proxy_type_changed(self, btn_id):
        """Toggle proxy details visibility."""
        # 2 is custom proxy
        self.proxy_details.setVisible(btn_id == 2)
        
    def _generate_random_fingerprint(self):
        """Generate and display random fingerprint."""
        self.fingerprint_config = FingerprintGenerator.generate()
        
        display_text = "--- 随机指纹参数 ---\n"
        for k, v in self.fingerprint_config.items():
            display_text += f"{k}: {v}\n"
            
        self.fp_display.setText(display_text)
        
    def _on_create(self):
        """Handle creation."""
        name = self.name_input.text().strip()
        if not name:
            self._show_error("请输入环境名称")
            return
            
        # Proxy config
        proxy_config = None
        proxy_mode = "noproxy"
        
        if self.auto_proxy_radio.isChecked():
            proxy_mode = "auto"
        elif self.custom_proxy_radio.isChecked():
            proxy_mode = "custom"
            host = self.proxy_host.text().strip()
            port = self.proxy_port.text().strip()
            if not host or not port:
                self._show_error("请输入代理主机和端口")
                return
            
            proxy_config = {
                "type": self.proxy_proto_combo.currentText(),
                "host": host,
                "port": port,
                "user": self.proxy_user.text().strip(),
                "pass": self.proxy_pass.text().strip(),
            }
        
        self.create_btn.setText("创建中...")
        self.create_btn.setEnabled(False)
        self._show_error("") # Clear error
        
        # Async-like delay to allow UI update, but we are blocking for now
        # Ideally threading, but for simplicity we assume API is fast enough (<1s)
        QTimer.singleShot(100, lambda: self._perform_creation(name, proxy_mode, proxy_config))
        
    def _perform_creation(self, name, proxy_mode, proxy_config):
        """Perform creation step (API call handled in parent for 'auto')."""
        try:
            # Note: If 'auto', we return early and let parent handle API and Storage
            # If 'custom' or 'noproxy', we can do it normally OR delegate everything to parent.
            # To simplify, we'll delegate EVERYTHING to parent (EnvironmentsPage)
            # So here we just pack the data.
            
            self.result_data = {
                "name": name,
                "group_id": self.group_input.text().strip(),
                "ctrip_account_id": self.ctrip_combo.currentData(),
                "labor_account_id": self.labor_combo.currentData(),
                "proxy_mode": proxy_mode,
                "proxy_config": proxy_config,
                "fingerprint_config": self.fingerprint_config
            }
            self.accept()
            
        except Exception as e:
            self._show_error(f"创建准备失败: {str(e)}")
            self.create_btn.setText("立即创建")
            self.create_btn.setEnabled(True)
            
    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    @classmethod
    def create_env(cls, parent=None) -> dict | None:
        """Show dialog and return result."""
        dialog = cls(parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_data
        return None
