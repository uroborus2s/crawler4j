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
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        self._setup_ui(title, message, confirm_text, cancel_text, danger)
    
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
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title_label)
        header.addStretch()
        
        layout.addLayout(header)
        
        # Message
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(message_label)
        
        # Spacer
        layout.addSpacing(8)
        
        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setMinimumWidth(80)
        if danger:
            confirm_btn.setObjectName("danger")
        else:
            confirm_btn.setObjectName("primary")
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
