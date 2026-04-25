from __future__ import annotations

import pytest

from src.ui.components.button import StyledButton
from src.ui.components.line_edit import StyledLineEdit
from src.core.mms.ui.module_install_dialog import ModuleInstallDialog


def test_module_install_dialog_returns_repo_token_request(qtbot):
    dialog = ModuleInstallDialog()
    qtbot.addWidget(dialog)

    dialog.tabs.setCurrentIndex(1)
    dialog.repo_input.setText("example/private-repo")
    dialog.repo_token_input.setText("ghp_secret_token_1234")
    dialog.repo_remember_check.setChecked(True)

    request = dialog.get_request()

    assert request.install_kind == "github_release"
    assert request.source == "example/private-repo"
    assert request.github_token == "ghp_secret_token_1234"
    assert request.remember_github_token is True


def test_module_install_dialog_requires_token_when_remember_checked(qtbot):
    dialog = ModuleInstallDialog()
    qtbot.addWidget(dialog)

    dialog.tabs.setCurrentIndex(1)
    dialog.repo_input.setText("example/private-repo")
    dialog.repo_remember_check.setChecked(True)

    with pytest.raises(ValueError) as exc_info:
        dialog.get_request()

    assert "必须先输入 Token" in str(exc_info.value)


def test_module_install_dialog_uses_clear_repo_token_wording(qtbot):
    dialog = ModuleInstallDialog()
    qtbot.addWidget(dialog)

    assert dialog.local_remember_check.text() == "保存这个 Token，后续更新这个模块时自动使用"
    assert dialog.repo_remember_check.text() == "保存这个 Token，后续更新这个仓库时自动使用"


def test_module_install_dialog_uses_public_form_controls(qtbot):
    dialog = ModuleInstallDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.local_path_input, StyledLineEdit)
    assert isinstance(dialog.local_token_input, StyledLineEdit)
    assert isinstance(dialog.repo_input, StyledLineEdit)
    assert isinstance(dialog.repo_token_input, StyledLineEdit)
    assert isinstance(dialog.findChild(StyledButton, "moduleInstallBrowseButton"), StyledButton)
    assert isinstance(dialog.findChild(StyledButton, "moduleInstallCancelButton"), StyledButton)
    assert isinstance(dialog.findChild(StyledButton, "moduleInstallStartButton"), StyledButton)


def test_module_install_dialog_validation_uses_public_message_dialog(qtbot, monkeypatch):
    import src.core.mms.ui.module_install_dialog as module_install_dialog

    dialog = ModuleInstallDialog()
    qtbot.addWidget(dialog)
    captured: list[tuple[str, str]] = []

    monkeypatch.setattr(
        module_install_dialog.MessageDialog,
        "warning",
        lambda parent, title, message, **kwargs: captured.append((title, message)),
    )

    dialog._accept_if_valid()

    assert captured == [("输入无效", "请选择本地 ZIP 安装包")]
