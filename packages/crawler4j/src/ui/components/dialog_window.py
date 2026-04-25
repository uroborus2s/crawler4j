"""Shared dialog window helpers."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog


def configure_titled_dialog(dialog: QDialog) -> None:
    """Force a dialog to use the app's native titled window shell."""

    hints = dialog.windowFlags() & ~Qt.WindowType.WindowType_Mask
    hints &= ~Qt.WindowType.FramelessWindowHint
    dialog.setWindowFlags(
        Qt.WindowType.Window
        | hints
        | Qt.WindowType.WindowTitleHint
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowCloseButtonHint
    )
