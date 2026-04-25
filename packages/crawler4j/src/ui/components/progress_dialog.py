"""Shared progress dialog component."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout, QWidget

from src.ui.components.dialog_window import configure_titled_dialog


class ProgressDialog(QDialog):
    """Public indeterminate progress popup with a native title bar."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        parent: QWidget | None = None,
        modal: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(str(title or "处理中"))
        self.setModal(modal)
        self.setMinimumWidth(420)
        configure_titled_dialog(self)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui(str(message or "请稍候..."))

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                background: transparent;
            }
            QLabel#progressMessage {
                color: #f7f7fb;
                font-size: 15px;
                font-weight: 700;
                line-height: 1.45;
            }
            QLabel#progressHint {
                color: rgba(255, 255, 255, 0.58);
                font-size: 12px;
            }
            QProgressBar#progressBar {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 3px;
                height: 6px;
            }
            QProgressBar#progressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #60a5fa,
                    stop:1 #10d982
                );
                border-radius: 3px;
            }
        """

    def _setup_ui(self, message: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        self.message_label = QLabel(message)
        self.message_label.setObjectName("progressMessage")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        hint = QLabel("完成后会自动关闭")
        hint.setObjectName("progressHint")
        layout.addWidget(hint)

    def set_message(self, message: str) -> None:
        self.message_label.setText(str(message or "请稍候..."))

    def show_progress(self) -> None:
        self.setWindowModality(
            Qt.WindowModality.ApplicationModal
            if self.isModal()
            else Qt.WindowModality.NonModal
        )
        self.show()
        self.raise_()
        self.activateWindow()

    def close_progress(self) -> None:
        self.accept()

    @classmethod
    def open_progress(
        cls,
        parent: QWidget | None,
        title: str,
        message: str,
        *,
        modal: bool = False,
    ) -> "ProgressDialog":
        dialog = cls(title, message, parent=parent, modal=modal)
        dialog.show_progress()
        return dialog
