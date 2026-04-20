import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.release_service import ModulePackagePreview, ModuleUpdateInfo
from src.core.mms.models import UpgradeSourceInfo
from src.core.mms.ui.module_list_widget import ModuleListWidget


def _make_module(tmp_path: Path, *, source: ModuleSource) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module", display_name="Demo Module"),
        source=source,
        path=module_dir,
    )


def test_refresh_button_forces_registry_refresh(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget.refresh_btn.click()

    assert refresh_calls == [1]


def test_dev_link_row_uses_remove_action(qtbot, tmp_path):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    action_widget = widget._create_action_widget(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    texts = [button.text() for button in action_widget.findChildren(QPushButton)]

    assert "移除开发链接" in texts
    assert "🗑️" not in texts


def test_remove_dev_link_calls_registry_and_refreshes(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    remove_calls: list[str] = []
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
        remove_dev_link=lambda name: remove_calls.append(name) or True,
        get_module=lambda name: None,
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    info_messages: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.information",
        lambda *args: info_messages.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)
    widget._remove_dev_link("demo_module")

    assert remove_calls == ["demo_module"]
    assert refresh_calls == [1]
    assert any("已移除开发链接" in message for message in info_messages)


def test_external_module_row_shows_upgrade_button_when_update_available(qtbot, tmp_path):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    widget._update_states[module.name] = ModuleUpdateInfo(
        module_name=module.name,
        current_version="1.0.0",
        latest_version="1.1.0",
        has_update=True,
    )

    action_widget = widget._create_action_widget(module)
    texts = [button.text() for button in action_widget.findChildren(QPushButton)]

    assert "升级" in texts


def test_uninstall_module_shows_warning_when_registry_refuses(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
        uninstall=lambda name: False,
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    warnings: list[str] = []
    infos: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.warning",
        lambda *args: warnings.append(args[2]),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.information",
        lambda *args: infos.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget._uninstall_module("demo_module")

    assert warnings == ["未能卸载模块: demo_module"]
    assert infos == []
    assert refresh_calls == []


def test_uninstall_module_refreshes_only_after_success(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    refresh_calls: list[int] = []
    uninstall_calls: list[str] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
        uninstall=lambda name: uninstall_calls.append(name) or True,
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    infos: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.information",
        lambda *args: infos.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget._uninstall_module("demo_module")

    assert uninstall_calls == ["demo_module"]
    assert infos == ["已卸载模块: demo_module"]
    assert refresh_calls == [1]


@pytest.mark.asyncio
async def test_install_module_async_persists_repo_token_when_requested(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    module.manifest.upgrade_source = UpgradeSourceInfo(repo="example/private-repo")
    archive_path = tmp_path / "demo_module-1.0.0.zip"
    archive_path.write_text("fake zip", encoding="utf-8")
    saved_tokens: list[tuple[str, str]] = []

    class FakeDialog(QDialog):
        class DialogCode:
            Accepted = int(QDialog.DialogCode.Accepted)

        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent") or None)

        def exec(self):  # type: ignore[override]
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    registry = SimpleNamespace(
        install=lambda source: module,
        refresh=lambda: None,
        list_modules=lambda: [module],
    )
    async def fake_check_for_update(target_module):  # noqa: ARG001
        return ModuleUpdateInfo(
            module_name=module.name,
            current_version=str(module.manifest.version or ""),
            latest_version=str(module.manifest.version or ""),
            has_update=False,
        )

    service = SimpleNamespace(
        prepare_github_install=lambda source, github_token=None: ModulePackagePreview(
            install_kind="github_release",
            manifest=module.manifest,
            warnings=[],
            archive_path=archive_path,
            source_label="GitHub Release",
            release=None,
        ),
        check_for_update=fake_check_for_update,
    )

    async def fake_prepare(repo, github_token=None):  # noqa: ARG001
        return service.prepare_github_install(repo, github_token=github_token)

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.get_module_release_service",
        lambda: SimpleNamespace(
            prepare_github_install=fake_prepare,
            check_for_update=service.check_for_update,
        ),
    )
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_github_credential_store", lambda: SimpleNamespace(set_token=lambda repo, token: saved_tokens.append((repo, token))))
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.InstallPreviewDialog", FakeDialog)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.open",
        lambda box: asyncio.get_running_loop().call_soon(box.accept),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    await widget._install_module_async(
        SimpleNamespace(
            install_kind="github_release",
            source="example/private-repo",
            github_token="ghp_secret_token_1234",
            remember_github_token=True,
        )
    )

    assert saved_tokens == [("example/private-repo", "ghp_secret_token_1234")]


@pytest.mark.asyncio
async def test_exec_dialog_async_uses_open_without_nested_exec(qtbot):
    class FakeDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.open_called = False
            self.exec_called = False

        def exec(self):  # type: ignore[override]
            self.exec_called = True
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            self.open_called = True
            asyncio.get_running_loop().call_soon(lambda: self.done(int(QDialog.DialogCode.Accepted)))

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    dialog = FakeDialog(widget)
    result = await widget._exec_dialog_async(dialog)

    assert result == int(QDialog.DialogCode.Accepted)
    assert dialog.open_called is True
    assert dialog.exec_called is False


@pytest.mark.asyncio
async def test_register_dev_link_async_uses_non_blocking_dialogs(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    module.manifest.upgrade_source = UpgradeSourceInfo(repo="example/demo_module")
    register_calls: list[str] = []
    refresh_calls: list[int] = []
    shown_messages: list[tuple[str, str]] = []

    class FakeDialog(QDialog):
        class DialogCode:
            Accepted = int(QDialog.DialogCode.Accepted)

        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent") or None)

        def exec(self):  # type: ignore[override]
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    async def fake_prepare_dev_link(path: str):
        return module.manifest, ["repo warning"]

    registry = SimpleNamespace(
        register_dev_link=lambda path: register_calls.append(path) or module,
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
    )

    def fake_message_open(box):
        shown_messages.append((box.windowTitle(), box.text()))
        asyncio.get_running_loop().call_soon(box.accept)

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.get_module_release_service",
        lambda: SimpleNamespace(prepare_dev_link=fake_prepare_dev_link),
    )
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.InstallPreviewDialog", FakeDialog)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.information",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("blocking static information dialog should not be used")
        ),
    )
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.QMessageBox.open", fake_message_open)

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    await widget._register_dev_link_async(str(module.path))

    assert register_calls == [str(module.path)]
    assert refresh_calls == [1]
    assert len(shown_messages) == 1
    assert shown_messages[0][1] == (
        "已添加开发模块: demo_module\n当前模块来源会切换为“开发链接”，可在 ATM 中发起任务调试。"
    )
