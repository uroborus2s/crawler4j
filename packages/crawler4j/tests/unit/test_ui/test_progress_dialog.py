import asyncio

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QProgressBar

from src.ui.components.progress_dialog import ProgressDialog


def test_progress_dialog_has_native_title_bar_and_indeterminate_bar(qtbot):
    dialog = ProgressDialog("正在处理", "正在启动环境，请稍候...")
    qtbot.addWidget(dialog)

    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.windowTitle() == "正在处理"
    assert dialog.findChild(QLabel, "progressMessage").text() == "正在启动环境，请稍候..."

    bar = dialog.findChild(QProgressBar, "progressBar")
    assert bar is not None
    assert bar.minimum() == 0
    assert bar.maximum() == 0


@pytest.mark.asyncio
async def test_progress_dialog_open_progress_uses_show_without_exec(qtbot, monkeypatch):
    shown: list[ProgressDialog] = []

    def fail_exec(self):
        raise AssertionError("blocking exec should not be used")

    def fake_show(self):
        shown.append(self)
        qtbot.addWidget(self)
        asyncio.get_running_loop().call_soon(
            lambda: self.done(int(QDialog.DialogCode.Accepted))
        )

    monkeypatch.setattr(ProgressDialog, "exec", fail_exec)
    monkeypatch.setattr(ProgressDialog, "show", fake_show)

    dialog = ProgressDialog.open_progress(None, "处理中", "正在加载...")

    assert shown == [dialog]
    assert dialog.windowTitle() == "处理中"
    assert dialog.isModal() is False
