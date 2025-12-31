"""Create environment dialog.

Dialog for manually binding a Ctrip account and creating browser profiles.
"""

from PyQt6.QtCore import Qt, QTimer
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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.utils.fingerprint_generator import FingerprintGenerator
from src.utils.storage import CtripAccountRepository


class CreateEnvDialog(QDialog):
    """Dialog for creating an environment binding and browser profile."""

    def __init__(self, parent=None, edit_mode=False, env_data=None):
        super().__init__(parent)

        self.ctrip_repo = CtripAccountRepository()
        self.result_data: dict | None = None
        self.account_map = {}

        self.setWindowTitle("创建环境" if not edit_mode else "编辑环境")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(550)

        # PNG: Base64 encoded 16x16 white arrow (matches #cdd6f4)
        # Bypasses SVG rendering issues on macOS
        arrow_svg_b64 = (
            "url(data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAPElEQVR4nGNgGAUDDxjRBc5 "
            "e+/KfkCZjLR64PiZ8koQ0YzUAnyHYxJkYKARMuCTQbSPkNZyAmEBlGOEAAHnLChz59FxpAA "
            "AAAElFTkSuQmCC)"
        )

        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1e1e2e;
                color: #cdd6f4;
            }}
            QLabel {{
                color: #cdd6f4;
                font-size: 13px;
                background-color: transparent;
            }}
            QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                selection-background-color: #585b70;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
                border: 1px solid #89b4fa;
            }}
            
            /* COMBOBOX STYLING */
            QComboBox {{
                padding-right: 30px; /* Space for the arrow */
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left-width: 1px;
                border-left-color: #45475a;
                border-left-style: solid; /* Default visible border for button */
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                background: #313244; /* Match background */
            }}
            QComboBox::down-arrow {{
                image: {arrow_svg_b64};
                width: 14px;
                height: 14px;
            }}
            /* Specific tweaks for Editable ComboBox */
            QComboBox:editable {{
                background: #313244;
            }}
            
            QGroupBox {{
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 12px;
                font-weight: bold;
                color: #fab387;
                background-color: transparent;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
            }}
            QPushButton#primary {{
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton#primary:hover {{
                background-color: #b4befe;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)

        # Current fingerprint config
        self.fingerprint_config = {}

        self._setup_ui()
        self._load_accounts()
        self._generate_random_fingerprint()  # Initial random

    def _setup_ui(self):
        """Setup the dialog UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # 1. Basic Info
        basic_group = QGroupBox("基础设置")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        basic_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # 窗口名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("自定义浏览器窗口名称")
        self.name_input.setMaxLength(50)
        basic_layout.addRow("窗口名称", self.name_input)

        # 标签 (暂未实现，占位)
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("请选择标签")
        self.tag_combo.setEnabled(False)
        basic_layout.addRow("标签", self.tag_combo)

        # 选择分组
        self.group_input = QComboBox()
        self.group_input.setEditable(True)
        self.group_input.setPlaceholderText("选择分组")
        self.group_input.addItem("默认分组")
        basic_layout.addRow("选择分组", self.group_input)

        # 平台
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["Ctrip", "Other"])
        basic_layout.addRow("平台", self.platform_combo)

        # 用户名 (Ctrip Account Selection)
        self.ctrip_combo = QComboBox()
        self.ctrip_combo.setEditable(True)  # Enable searching
        self.ctrip_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        le = self.ctrip_combo.lineEdit()
        if le:
            le.setPlaceholderText("请选择账号")
        basic_layout.addRow("用户名", self.ctrip_combo)

        # 每日最大打开次数
        self.daily_limit_input = QSpinBox()
        self.daily_limit_input.setRange(0, 9999)
        self.daily_limit_input.setValue(0)
        self.daily_limit_input.setSuffix(" 次")
        self.daily_limit_input.setSpecialValueText("无限制")  # 0 shows "无限制"
        basic_layout.addRow("每日限制", self.daily_limit_input)

        layout.addWidget(basic_group)

        # 3. Proxy Settings
        proxy_group = QGroupBox("代理设置")
        proxy_layout = QVBoxLayout(proxy_group)

        # Proxy Type
        type_layout = QHBoxLayout()
        self.proxy_type_group = QButtonGroup(self)

        self.auto_proxy_radio = QRadioButton("自动从 IP 池获取 (推荐)")
        self.no_proxy_radio = QRadioButton("不使用代理")
        self.custom_proxy_radio = QRadioButton("手动设置")

        self.proxy_type_group.addButton(self.auto_proxy_radio, 3)
        self.proxy_type_group.addButton(self.no_proxy_radio, 1)
        self.proxy_type_group.addButton(self.custom_proxy_radio, 2)

        type_layout.addWidget(self.auto_proxy_radio)
        type_layout.addWidget(self.no_proxy_radio)
        type_layout.addWidget(self.custom_proxy_radio)

        type_layout.addStretch()
        self.auto_proxy_radio.setChecked(True)

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

        self.proxy_details.hide()
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
        self.fp_display.setMaximumHeight(100)
        self.fp_display.setStyleSheet(
            "background-color: #1e1e2e; color: #a6e3a1; font-family: monospace; border: 1px solid #45475a;"
        )
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
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a; 
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        btn_layout.addWidget(cancel_btn)

        self.create_btn = QPushButton("立即创建")
        self.create_btn.setObjectName("primary")
        self.create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(self.create_btn)

        main_layout.addWidget(btn_container)

    def _load_accounts(self):
        """Load available accounts."""
        # Ctrip - 仅加载空闲账号，必选
        idle_accounts = self.ctrip_repo.get_idle()
        self.ctrip_combo.clear()  # Clear specific manual items first
        if not idle_accounts:
            self.ctrip_combo.addItem("无可用账号", None)
            self.ctrip_combo.setCurrentIndex(0)
            self.ctrip_combo.setEnabled(False)
        else:
            for acc in idle_accounts:
                account_type = acc.get("account_type", "manual")
                sms_type = acc.get(
                    "sms_verify_type", acc.get("sms_platform_type", "manual")
                )
                display = f"{acc['phone_number']} ({account_type}, {sms_type})"
                self.ctrip_combo.addItem(display, acc["id"])

                # Cache account data
                self.account_map[acc["id"]] = acc

            # Reset selection and text
            self.ctrip_combo.setCurrentIndex(-1)
            le = self.ctrip_combo.lineEdit()
            if le:
                le.setPlaceholderText("请选择账号")
            self.ctrip_combo.setEnabled(True)

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
            self._show_error("请输入窗口名称")
            return

        # 携程账号必选
        ctrip_id = self.ctrip_combo.currentData()
        if ctrip_id is None:
            self._show_error("请选择一个携程账号（用户名）")
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
        self._show_error("")  # Clear error

        QTimer.singleShot(
            100, lambda: self._perform_creation(name, proxy_mode, proxy_config)
        )

    def _perform_creation(self, name, proxy_mode, proxy_config):
        """Perform creation step (API call handled in parent for 'auto')."""
        try:
            # Note: If 'auto', we return early and let parent handle API and Storage
            # If 'custom' or 'noproxy', we can do it normally OR delegate everything to parent.
            # To simplify, we'll delegate EVERYTHING to parent (EnvironmentsPage)
            # So here we just pack the data.

            self.result_data = {
                "name": name,
                "group_id": self.group_input.currentText().strip(),  # Use currentText for editable combo
                "ctrip_account_id": self.ctrip_combo.currentData(),
                "labor_account_id": None,  # Explicitly None for auto-bind logic downstream
                "proxy_mode": proxy_mode,
                "proxy_config": proxy_config,
                "fingerprint_config": self.fingerprint_config,
                "platform": self.platform_combo.currentText(),
                "daily_open_limit": self.daily_limit_input.value(),
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
