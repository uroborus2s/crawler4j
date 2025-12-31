"""Labor account dialog.

Dialog for adding/editing Labor accounts.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)


class LaborAccountDialog(QDialog):
    """Dialog for adding or editing a Labor account.

    Fields:
    - Phone/Username
    - Password
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

        title = "编辑劳保账号" if account else "添加劳保账号"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)

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

        # Phone/Username
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("请输入手机号或用户名")
        form.addRow("账号:", self.phone_input)

        # Password
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("请输入密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self.password_input)

        layout.addLayout(form)

        # Stats display (for existing accounts)
        if self.account and self.account.get("id"):
            stats_layout = QHBoxLayout()
            stats_layout.setSpacing(16)

            completed = self.account.get("completed_count", 0)
            discarded = self.account.get("discarded_count", 0)
            approved = self.account.get("approved_count", 0)
            rejected = self.account.get("rejected_count", 0)

            stats_layout.addWidget(QLabel(f"完成: {completed}"))
            stats_layout.addWidget(QLabel(f"废弃: {discarded}"))
            stats_layout.addWidget(QLabel(f"通过: {approved}"))
            stats_layout.addWidget(QLabel(f"拒绝: {rejected}"))
            stats_layout.addStretch()

            layout.addLayout(stats_layout)

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

    def _on_save(self):
        """Handle save button click."""
        # Validate
        phone = self.phone_input.text().strip()
        password = self.password_input.text()

        if not phone:
            self._show_error("账号不能为空")
            return

        if not password:
            self._show_error("密码不能为空")
            return

        # Collect data
        self.result_data = {
            "phone": phone,
            "password": password,
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
        """Get the result data after dialog closes."""
        return self.result_data

    @classmethod
    def add_account(cls, parent=None) -> dict | None:
        """Show dialog to add a new account."""
        dialog = cls(parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None

    @classmethod
    def edit_account(cls, account: dict, parent=None) -> dict | None:
        """Show dialog to edit an existing account."""
        dialog = cls(account=account, parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_result()
        return None
