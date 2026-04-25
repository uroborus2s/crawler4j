import asyncio

import pytest
from PyQt6.QtWidgets import QDialog, QPushButton

from src.ui.components.choice_dialog import ChoiceDialog, DialogChoice
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.dialog_async import open_dialog_async
from src.ui.components.message_dialog import MessageDialog


@pytest.mark.asyncio
async def test_open_dialog_async_uses_open_without_nested_exec(qtbot):
    class FakeDialog(QDialog):
        def __init__(self):
            super().__init__()
            self.open_called = False
            self.exec_called = False

        def exec(self):  # type: ignore[override]
            self.exec_called = True
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            self.open_called = True
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    dialog = FakeDialog()
    qtbot.addWidget(dialog)

    result = await open_dialog_async(dialog)

    assert result == int(QDialog.DialogCode.Accepted)
    assert dialog.open_called is True
    assert dialog.exec_called is False


@pytest.mark.asyncio
async def test_message_dialog_async_entrypoint_uses_open(qtbot, monkeypatch):
    def fail_exec(self):
        raise AssertionError("blocking exec should not be used")

    def fake_open(self):
        qtbot.addWidget(self)
        asyncio.get_running_loop().call_soon(
            lambda: self.done(int(QDialog.DialogCode.Accepted))
        )

    monkeypatch.setattr(MessageDialog, "exec", fail_exec)
    monkeypatch.setattr(MessageDialog, "open", fake_open)

    result = await MessageDialog.warning_async(None, "标题", "内容")

    assert result == int(QDialog.DialogCode.Accepted)


@pytest.mark.asyncio
async def test_confirm_dialog_async_entrypoint_returns_bool(qtbot, monkeypatch):
    def fail_exec(self):
        raise AssertionError("blocking exec should not be used")

    def fake_open(self):
        qtbot.addWidget(self)
        asyncio.get_running_loop().call_soon(
            lambda: self.done(int(QDialog.DialogCode.Accepted))
        )

    monkeypatch.setattr(ConfirmDialog, "exec", fail_exec)
    monkeypatch.setattr(ConfirmDialog, "open", fake_open)

    assert await ConfirmDialog.confirm_async(None, "确认", "继续吗？") is True


@pytest.mark.asyncio
async def test_choice_dialog_async_returns_selected_choice(qtbot, monkeypatch):
    def fail_exec(self):
        raise AssertionError("blocking exec should not be used")

    def fake_open(self):
        qtbot.addWidget(self)
        button = self.findChild(QPushButton, "choiceButton_destroy")
        assert button is not None
        asyncio.get_running_loop().call_soon(button.click)

    monkeypatch.setattr(ChoiceDialog, "exec", fail_exec)
    monkeypatch.setattr(ChoiceDialog, "open", fake_open)

    selected = await ChoiceDialog.choose_async(
        None,
        "中止任务",
        "请选择处理方式",
        choices=[
            DialogChoice("recycle", "保留环境中止", "warning"),
            DialogChoice("destroy", "删除环境中止", "danger"),
        ],
    )

    assert selected == "destroy"
