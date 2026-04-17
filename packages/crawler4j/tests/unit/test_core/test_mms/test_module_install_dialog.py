from __future__ import annotations

import pytest

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
