"""Shared choice dialog component."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.ui.components.button import ButtonVariant, StyledButton
from src.ui.components.dialog_async import open_dialog_async


@dataclass(frozen=True, slots=True)
class DialogChoice:
    """One action in a public choice dialog."""

    id: str
    text: str
    variant: ButtonVariant = "secondary"


class ChoiceDialog(QDialog):
    """Public dialog for cases where confirmation has more than yes/no."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        choices: list[DialogChoice],
        detail: str = "",
        cancel_text: str = "取消",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.selected_choice_id: str | None = None
        self._choices = list(choices)
        self._detail = str(detail or "")

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui(message, cancel_text)

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                background: transparent;
            }
            QLabel#choiceTitle {
                color: #f7f7fb;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#choiceMessage {
                color: #f7f7fb;
                font-size: 15px;
                font-weight: 650;
                line-height: 1.45;
            }
            QLabel#choiceDetail {
                color: rgba(255, 255, 255, 0.66);
                font-size: 12px;
                line-height: 1.45;
            }
        """

    def _setup_ui(self, message: str, cancel_text: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title_label = QLabel(self.windowTitle())
        title_label.setObjectName("choiceTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setObjectName("choiceMessage")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message_label)

        if self._detail:
            detail_label = QLabel(self._detail)
            detail_label.setObjectName("choiceDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()

        cancel_button = StyledButton(
            cancel_text,
            variant="secondary",
            min_height=40,
            min_width=96,
            horizontal_padding=20,
        )
        cancel_button.setObjectName("choiceCancelButton")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)

        for choice in self._choices:
            button = StyledButton(
                choice.text,
                variant=choice.variant,
                min_height=40,
                min_width=112,
                horizontal_padding=20,
            )
            button.setObjectName(f"choiceButton_{choice.id}")
            button.clicked.connect(lambda _checked=False, item=choice: self._accept_choice(item.id))
            button_row.addWidget(button)

        layout.addLayout(button_row)

    def _accept_choice(self, choice_id: str) -> None:
        self.selected_choice_id = choice_id
        self.accept()

    @classmethod
    def choose(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        choices: list[DialogChoice],
        detail: str = "",
        cancel_text: str = "取消",
    ) -> str | None:
        dialog = cls(
            title,
            message,
            choices=choices,
            detail=detail,
            cancel_text=cancel_text,
            parent=parent,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.selected_choice_id

    @classmethod
    async def choose_async(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        choices: list[DialogChoice],
        detail: str = "",
        cancel_text: str = "取消",
    ) -> str | None:
        dialog = cls(
            title,
            message,
            choices=choices,
            detail=detail,
            cancel_text=cancel_text,
            parent=parent,
        )
        if await open_dialog_async(dialog) != int(QDialog.DialogCode.Accepted):
            return None
        return dialog.selected_choice_id
