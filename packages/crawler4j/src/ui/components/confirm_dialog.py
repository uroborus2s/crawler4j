"""Confirm dialog widget.

Provides confirmation dialogs for dangerous operations.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ConfirmDialog(QDialog):
    """Confirmation dialog for dangerous operations.

    Usage:
        if ConfirmDialog.confirm(parent, "确认删除?", "此操作不可逆"):
            # Perform delete
    """

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "确认",
        cancel_text: str = "取消",
        danger: bool = False,
        parent=None,
    ):
        """Initialize confirmation dialog.

        Args:
            title: Dialog title.
            message: Confirmation message.
            confirm_text: Confirm button text.
            cancel_text: Cancel button text.
            danger: If True, confirm button is styled as danger.
            parent: Parent widget.
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(self._build_stylesheet())

        self._setup_ui(title, message, confirm_text, cancel_text, danger)

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                background-color: transparent;
            }
            QLabel#confirmIcon {
                font-size: 28px;
            }
            QLabel#confirmTitle {
                color: #f5e0dc;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#confirmMessage {
                color: #bac2de;
                font-size: 13px;
                line-height: 1.45;
            }
            QPushButton {
                min-width: 88px;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#confirmCancel {
                background-color: #45475a;
                border: 1px solid #585b70;
                color: #cdd6f4;
            }
            QPushButton#confirmCancel:hover {
                background-color: #585b70;
                border-color: #6c7086;
            }
            QPushButton#confirmCancel:pressed {
                background-color: #3b3e52;
            }
            QPushButton#confirmDanger {
                background-color: rgba(243, 139, 168, 0.16);
                border: 1px solid rgba(243, 139, 168, 0.38);
                color: #f38ba8;
            }
            QPushButton#confirmDanger:hover {
                background-color: rgba(243, 139, 168, 0.24);
                border-color: rgba(243, 139, 168, 0.52);
            }
            QPushButton#confirmDanger:pressed {
                background-color: rgba(243, 139, 168, 0.30);
            }
            QPushButton#confirmPrimary {
                background-color: #89b4fa;
                border: 1px solid #89b4fa;
                color: #1e1e2e;
            }
            QPushButton#confirmPrimary:hover {
                background-color: #a6c8ff;
                border-color: #a6c8ff;
            }
            QPushButton#confirmPrimary:pressed {
                background-color: #74a7f2;
                border-color: #74a7f2;
            }
        """

    def _setup_ui(
        self,
        title: str,
        message: str,
        confirm_text: str,
        cancel_text: str,
        danger: bool,
    ):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Icon and title
        header = QHBoxLayout()

        icon = QLabel("⚠️" if danger else "❓")
        icon.setObjectName("confirmIcon")
        header.addWidget(icon)

        title_label = QLabel(title)
        title_label.setObjectName("confirmTitle")
        header.addWidget(title_label)
        header.addStretch()

        layout.addLayout(header)

        # Message
        message_label = QLabel(message)
        message_label.setObjectName("confirmMessage")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        # Spacer
        layout.addSpacing(8)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()

        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setObjectName("confirmCancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        confirm_btn = QPushButton(confirm_text)
        if danger:
            confirm_btn.setObjectName("confirmDanger")
        else:
            confirm_btn.setObjectName("confirmPrimary")
        confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(confirm_btn)

        layout.addLayout(buttons)

    @classmethod
    def confirm(
        cls,
        parent: QWidget,
        title: str,
        message: str,
        confirm_text: str = "确认",
        cancel_text: str = "取消",
        danger: bool = False,
    ) -> bool:
        """Show confirmation dialog and return result.

        Args:
            parent: Parent widget.
            title: Dialog title.
            message: Confirmation message.
            confirm_text: Confirm button text.
            cancel_text: Cancel button text.
            danger: If True, style as danger dialog.

        Returns:
            True if confirmed, False if cancelled.
        """
        dialog = cls(title, message, confirm_text, cancel_text, danger, parent)
        return dialog.exec() == QDialog.DialogCode.Accepted

    @classmethod
    def delete_confirm(cls, parent: QWidget, item_name: str) -> bool:
        """Convenience method for delete confirmation.

        Args:
            parent: Parent widget.
            item_name: Name of item being deleted.

        Returns:
            True if confirmed.
        """
        return cls.confirm(
            parent,
            "确认删除",
            f"确定要删除 {item_name} 吗？此操作不可恢复。",
            confirm_text="删除",
            danger=True,
        )
