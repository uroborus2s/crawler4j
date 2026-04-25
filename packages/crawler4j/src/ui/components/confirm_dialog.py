"""Confirm dialog widget.

Provides confirmation dialogs for dangerous operations.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui.components.button import StyledButton
from src.ui.components.dialog_async import open_dialog_async


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
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
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
            QLabel#confirmTitle {
                color: #f7f7fb;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#confirmMessage {
                color: rgba(255, 255, 255, 0.72);
                font-size: 14px;
                line-height: 1.45;
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
        title_label = QLabel(title)
        title_label.setObjectName("confirmTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

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

        cancel_btn = StyledButton(
            cancel_text,
            variant="secondary",
            min_height=40,
            min_width=96,
            horizontal_padding=20,
        )
        cancel_btn.setObjectName("confirmCancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        confirm_btn = StyledButton(
            confirm_text,
            variant="danger" if danger else "success",
            min_height=40,
            min_width=96,
            horizontal_padding=20,
        )
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
    async def confirm_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_text: str = "确认",
        cancel_text: str = "取消",
        danger: bool = False,
    ) -> bool:
        """Open confirmation dialog without a nested event loop."""
        dialog = cls(title, message, confirm_text, cancel_text, danger, parent)
        return await open_dialog_async(dialog) == int(QDialog.DialogCode.Accepted)

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

    @classmethod
    async def delete_confirm_async(cls, parent: QWidget | None, item_name: str) -> bool:
        """Async convenience method for delete confirmation."""
        return await cls.confirm_async(
            parent,
            "确认删除",
            f"确定要删除 {item_name} 吗？此操作不可恢复。",
            confirm_text="删除",
            danger=True,
        )
