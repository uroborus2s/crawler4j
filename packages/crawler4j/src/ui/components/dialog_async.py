"""Async helpers for public dialog components."""

from __future__ import annotations

import asyncio

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from src.ui.components.dialog_window import configure_titled_dialog


async def open_dialog_async(
    dialog: QDialog,
    *,
    modality: Qt.WindowModality = Qt.WindowModality.ApplicationModal,
) -> int:
    """Open a dialog without starting a nested Qt event loop."""

    loop = asyncio.get_running_loop()
    result_future: asyncio.Future[int] = loop.create_future()

    def _resolve(result: int) -> None:
        if not result_future.done():
            result_future.set_result(int(result))

    dialog.finished.connect(_resolve)
    configure_titled_dialog(dialog)
    dialog.setWindowModality(modality)
    dialog.setModal(modality != Qt.WindowModality.NonModal)
    dialog.show()
    try:
        return int(await result_future)
    finally:
        try:
            dialog.finished.disconnect(_resolve)
        except TypeError:
            pass
