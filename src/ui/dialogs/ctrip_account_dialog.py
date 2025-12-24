"""Ctrip account dialog.

Dialog for adding/editing Ctrip accounts.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
)


class CtripAccountDialog(QDialog):
    """Dialog for adding or editing a Ctrip account.
    
    Fields:
    - Phone number
    - Password
    - SMS platform type
    - SMS platform URL
    - SMS platform key
    """
    
    def __init__(self, account: dict | None = None, parent=None):
        """Initialize the dialog.
        
        Args:
            account: Existing account dict for editing, None for new.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.account = account or {}
        self.result_data: dict | None = None
        
        title = "编辑携程账号" if account else "添加携程账号"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._setup_ui()
        self._populate_data()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号")
        form.addRow("手机号:", self.phone_input)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("可选，留空则使用短信登录")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self.password_input)
        
        # SMS Platform Type
        self.sms_type_combo = QComboBox()
        self.sms_type_combo.addItems(["", "平台A", "平台B", "平台C"])
        self.sms_type_combo.setEditable(True)
        form.addRow("接码平台:", self.sms_type_combo)
        
        # SMS Platform URL
        self.sms_url_input = QLineEdit()
        self.sms_url_input.setPlaceholderText("http://api.example.com/sms")
        form.addRow("平台 URL:", self.sms_url_input)
        
        # SMS Platform Key
        self.sms_key_input = QLineEdit()
        self.sms_key_input.setPlaceholderText("API Key")
        form.addRow("平台 Key:", self.sms_key_input)
        
        layout.addLayout(form)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f38ba8;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        save_btn = QPushButton("保存")
        save_btn.setObjectName("primary")
        save_btn.setMinimumWidth(80)
        save_btn.clicked.connect(self._on_save)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
    
    def _populate_data(self):
        """Populate form with existing account data."""
        if self.account:
            self.phone_input.setText(self.account.get("phone", ""))
            self.password_input.setText(self.account.get("password", ""))
            
            sms_type = self.account.get("sms_platform_type", "")
            idx = self.sms_type_combo.findText(sms_type)
            if idx >= 0:
                self.sms_type_combo.setCurrentIndex(idx)
            else:
                self.sms_type_combo.setCurrentText(sms_type)
            
            self.sms_url_input.setText(self.account.get("sms_platform_url", ""))
            self.sms_key_input.setText(self.account.get("sms_platform_key", ""))
    
    def _on_save(self):
        """Handle save button click."""
        # Validate
        phone = self.phone_input.text().strip()
        if not phone:
            self._show_error("手机号不能为空")
            return
        
        if len(phone) < 11:
            self._show_error("请输入有效的手机号")
            return
        
        # Collect data
        self.result_data = {
            "phone": phone,
            "password": self.password_input.text(),
            "sms_platform_type": self.sms_type_combo.currentText(),
            "sms_platform_url": self.sms_url_input.text().strip(),
            "sms_platform_key": self.sms_key_input.text().strip(),
        }
        
        # Keep ID if editing
        if self.account and "id" in self.account:
            self.result_data["id"] = self.account["id"]
        
        self.accept()
    
    def _show_error(self, message: str):
        """Show error message."""
        self.error_label.setText(message)
        self.error_label.show()
    
    def get_result(self) -> dict | None:
        """Get the result data after dialog closes.
        
        Returns:
            Account dict if saved, None if cancelled.
        """
        return self.result_data
    
    @classmethod
    def add_account(cls, parent=None) -> dict | None:
        """Show dialog to add a new account.
        
        Returns:
            New account dict or None if cancelled.
        """
        dialog = cls(parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None
    
    @classmethod
    def edit_account(cls, account: dict, parent=None) -> dict | None:
        """Show dialog to edit an existing account.
        
        Returns:
            Updated account dict or None if cancelled.
        """
        dialog = cls(account=account, parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None
