"""Ctrip account dialog.

Dialog for adding/editing Ctrip accounts.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
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
        
        # Phone (Layout)
        phone_layout = QHBoxLayout()
        self.country_code_combo = QComboBox()
        self.country_code_combo.addItems(["+86", "+852", "+853", "+886", "+1"])
        self.country_code_combo.setEditable(True)
        self.country_code_combo.setFixedWidth(80)
        phone_layout.addWidget(self.country_code_combo)
        
        self.phone_number_input = QLineEdit()
        self.phone_number_input.setPlaceholderText("请输入手机号")
        phone_layout.addWidget(self.phone_number_input)
        
        form.addRow("手机号:", phone_layout)
        
        # Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("可选，留空则使用短信登录")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self.password_input)
        
        # Account Type
        self.account_type_combo = QComboBox()
        self.account_type_combo.addItems(["manual", "api"])
        form.addRow("账号类型:", self.account_type_combo)
        
        # SMS Verify Type
        self.sms_verify_combo = QComboBox()
        self.sms_verify_combo.addItems(["manual", "auto"])
        form.addRow("接码模式:", self.sms_verify_combo)
        
        # Consecutive Task Count
        self.task_count_input = QLineEdit()
        self.task_count_input.setPlaceholderText("15")
        self.task_count_input.setText("15")
        form.addRow("连续任务数:", self.task_count_input)
        
        # Task Interval Max
        self.interval_input = QLineEdit()
        self.interval_input.setPlaceholderText("2")
        self.interval_input.setText("2")
        form.addRow("任务间隔上限(分):", self.interval_input)
        
        # SMS Platform Type (legacy, for auto mode)
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
            code = self.account.get("country_code", "+86")
            idx = self.country_code_combo.findText(code)
            if idx >= 0:
                self.country_code_combo.setCurrentIndex(idx)
            else:
                self.country_code_combo.setCurrentText(code)
                
            self.phone_number_input.setText(self.account.get("phone_number", ""))
            self.password_input.setText(self.account.get("password", ""))
            
            # Account Type
            acc_type = self.account.get("account_type", "manual")
            idx = self.account_type_combo.findText(acc_type)
            if idx >= 0:
                self.account_type_combo.setCurrentIndex(idx)
            
            # SMS Verify Type
            sms_type = self.account.get("sms_verify_type", "manual")
            idx = self.sms_verify_combo.findText(sms_type)
            if idx >= 0:
                self.sms_verify_combo.setCurrentIndex(idx)
            
            # Task config
            self.task_count_input.setText(str(self.account.get("consecutive_task_count", 5)))
            self.interval_input.setText(str(self.account.get("task_interval_max", 15)))
            
            sms_platform = self.account.get("sms_platform_type", "")
            idx = self.sms_type_combo.findText(sms_platform)
            if idx >= 0:
                self.sms_type_combo.setCurrentIndex(idx)
            else:
                self.sms_type_combo.setCurrentText(sms_platform)
            
            self.sms_url_input.setText(self.account.get("sms_platform_url", ""))
            self.sms_key_input.setText(self.account.get("sms_platform_key", ""))
    
    def _on_save(self):
        """Handle save button click."""
        # Validate
        phone_number = self.phone_number_input.text().strip()
        if not phone_number:
            self._show_error("手机号不能为空")
            return
        
        # Validate task count
        try:
            task_count = int(self.task_count_input.text().strip() or "5")
        except ValueError:
            task_count = 5
        
        try:
            interval_max = int(self.interval_input.text().strip() or "15")
        except ValueError:
            interval_max = 15
        
        # Collect data
        self.result_data = {
            "country_code": self.country_code_combo.currentText().strip(),
            "phone_number": phone_number,
            "password": self.password_input.text(),
            "account_type": self.account_type_combo.currentText(),
            "sms_verify_type": self.sms_verify_combo.currentText(),
            "consecutive_task_count": task_count,
            "task_interval_max": interval_max,
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
