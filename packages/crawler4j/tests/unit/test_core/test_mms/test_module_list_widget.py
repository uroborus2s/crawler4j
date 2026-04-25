import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QDialog

from src.core.mms.models import ModuleInfo, ModuleInstallError, ModuleManifest, ModuleParseError, ModuleSource
from src.core.mms.release_service import ModulePackagePreview, ModuleUpdateInfo
from src.core.mms.models import UpgradeSourceInfo
from src.core.mms.ui.module_list_widget import (
    ModuleDisplayItem,
    ModuleListWidget,
    build_install_exception_diagnostics,
)


def _make_module(tmp_path: Path, *, source: ModuleSource) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module", display_name="Demo Module"),
        source=source,
        path=module_dir,
    )


def test_build_install_exception_diagnostics_uses_stage_hint_from_nested_module_error():
    try:
        try:
            raise ModuleParseError(
                "",
                stage="PARSE",
                hint="请检查 module.yaml.data 和视图 SQL 输出列是否一致",
            )
        except ModuleParseError as exc:
            raise ModuleInstallError("安装失败") from exc
    except ModuleInstallError as exc:
        diagnostics = build_install_exception_diagnostics(exc)

    assert diagnostics.summary == "安装失败"
    assert diagnostics.stage == "PARSE"
    assert diagnostics.hint == "请检查 module.yaml.data 和视图 SQL 输出列是否一致"
    assert "ModuleParseError" in diagnostics.traceback_text
    assert "ModuleInstallError -> ModuleParseError" == diagnostics.chain_text


def test_build_install_exception_diagnostics_uses_non_empty_fallback_summary():
    class SilentError(Exception):
        def __str__(self) -> str:
            return ""

    try:
        raise SilentError()
    except SilentError as exc:
        diagnostics = build_install_exception_diagnostics(exc)

    assert diagnostics.summary == "SilentError（异常未提供错误消息）"
    assert diagnostics.stage == "未提供"
    assert diagnostics.hint == "未提供"
    assert "SilentError" in diagnostics.traceback_text


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

    actions = widget._build_row_actions(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    texts = [action["label"] for action in actions]

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

    monkeypatch.setattr("src.core.mms.ui.dev_link_actions.get_module_registry", lambda: registry)
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.ConfirmDialog.confirm",
        lambda *args, **kwargs: True,
    )
    info_messages: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.information",
        lambda *args: info_messages.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)
    widget._remove_dev_link("demo_module")

    assert remove_calls == ["demo_module"]
    assert refresh_calls == [1]
    assert any("已移除开发链接" in message for message in info_messages)


def test_remove_dev_link_reports_fallback_source_via_shared_helper(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    fallback = _make_module(tmp_path, source=ModuleSource.BUILTIN)
    remove_calls: list[str] = []
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
        remove_dev_link=lambda name: remove_calls.append(name) or True,
        get_module=lambda name: fallback if name == "demo_module" else None,
    )

    monkeypatch.setattr("src.core.mms.ui.dev_link_actions.get_module_registry", lambda: registry)
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.ConfirmDialog.confirm",
        lambda *args, **kwargs: True,
    )
    info_messages: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.information",
        lambda *args: info_messages.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)
    widget._remove_dev_link("demo_module")

    assert remove_calls == ["demo_module"]
    assert refresh_calls == [1]
    assert info_messages == ["已移除开发链接，当前已回退到 内置模块: demo_module"]


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

    actions = widget._build_row_actions(module)
    texts = [action["label"] for action in actions]

    assert "升级" in texts


def test_table_row_click_emits_open_detail(qtbot, tmp_path):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    widget = ModuleListWidget()
    qtbot.addWidget(widget)
    widget._display_items = [ModuleDisplayItem(raw=module, display_name_str="Demo Module")]
    opened: list[ModuleInfo] = []
    widget.open_detail.connect(opened.append)
    widget._refresh_table()

    widget._on_table_row_clicked(widget.table.displayed_rows()[0])

    assert opened == [module]


def test_module_list_widget_uses_explicit_index_column(qtbot):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    first_column = widget.TABLE_SCHEMA["columns"][0]

    assert first_column["key"] == "__index__"
    assert first_column["label"] == "序号"
    assert first_column["sortable"] is False


def test_module_list_widget_numbers_rows_across_pages(qtbot, tmp_path):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget._table_rows = [
        {
            "module_name": f"module_{index}",
            "name": f"module_{index}",
            "display_name": f"Module {index}",
            "version": {"text": "1.0.0", "sort_value": "1.0.0"},
            "status": {"text": "已启用", "tone": "success"},
            "actions": [],
        }
        for index in range(1, 5)
    ]

    widget.table.set_query({"search_text": "", "sort": [], "page": 2, "page_size": 2})
    widget.table.request_refresh()

    rows = widget.table.displayed_rows()

    assert [row["__index__"]["text"] for row in rows] == ["3", "4"]


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
        "src.core.mms.ui.module_list_widget.ConfirmDialog.confirm",
        lambda *args, **kwargs: True,
    )
    warnings: list[str] = []
    infos: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.warning",
        lambda *args: warnings.append(args[2]),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.information",
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
        "src.core.mms.ui.module_list_widget.ConfirmDialog.confirm",
        lambda *args, **kwargs: True,
    )
    infos: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.information",
        lambda *args: infos.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget._uninstall_module("demo_module")

    assert uninstall_calls == ["demo_module"]
    assert infos == ["已卸载模块: demo_module"]
    assert refresh_calls == [1]


def test_uninstall_module_warning_lists_registered_data_resources(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    registry = SimpleNamespace(
        refresh=lambda: None,
        list_modules=lambda: [module],
        uninstall=lambda name: True,
    )

    class _FakeDataStore:
        def list_data_resources(self, module_name: str):
            assert module_name == "demo_module"
            return [
                {
                    "resource_id": "accounts",
                    "storage_mode": "managed_dataset",
                    "cleanup_policy": "delete_rows",
                    "physical_table_name": "module_datasets",
                },
                {
                    "resource_id": "billing_audit",
                    "storage_mode": "custom_table",
                    "cleanup_policy": "drop_table",
                    "physical_table_name": "demo_module_billing_audit",
                },
            ]

        def list_db_views(self, module_name: str):
            assert module_name == "demo_module"
            return [
                {
                    "view_id": "billing_stats",
                    "cleanup_policy": "drop_view",
                    "physical_view_name": "demo_module_view_billing_stats",
                }
            ]

    question_texts: list[str] = []

    def _capture_confirm(parent, title, text, **kwargs):
        question_texts.append(text)
        return True

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_data_store", lambda: _FakeDataStore())
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.ConfirmDialog.confirm", _capture_confirm)
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.MessageDialog.information", lambda *args: None)

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget._uninstall_module("demo_module")

    assert "此操作不可撤销" in question_texts[0]
    assert "accounts: 删除 module_datasets 托管记录" in question_texts[0]
    assert "billing_audit: 删除自定义物理表 demo_module_billing_audit" in question_texts[0]
    assert "billing_stats: 删除数据库视图 demo_module_view_billing_stats" in question_texts[0]


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
    async def fake_show_async(*args, **kwargs):
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.show_async",
        fake_show_async,
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
async def test_install_module_async_uses_diagnostic_dialog_when_error_message_is_empty(qtbot, monkeypatch):
    observed: dict[str, object] = {}

    class SilentError(Exception):
        def __str__(self) -> str:
            return ""

    class FakeErrorDialog(QDialog):
        def __init__(self, diagnostics, parent=None):
            super().__init__(parent)
            observed["diagnostics"] = diagnostics

        def exec(self):  # type: ignore[override]
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    async def fake_prepare_local_install(source, github_token=None):  # noqa: ARG001
        raise SilentError()

    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.get_module_release_service",
        lambda: SimpleNamespace(prepare_local_install=fake_prepare_local_install),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.ModuleInstallErrorDialog",
        FakeErrorDialog,
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    await widget._install_module_async(
        SimpleNamespace(
            install_kind="local_zip",
            source="/tmp/demo_module.zip",
            github_token="",
            remember_github_token=False,
        )
    )

    diagnostics = observed["diagnostics"]
    assert diagnostics.summary == "SilentError（异常未提供错误消息）"
    assert diagnostics.stage == "未提供"
    assert diagnostics.hint == "未提供"
    assert "SilentError" in diagnostics.traceback_text


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

    async def fake_message_show_async(parent, title, text, **kwargs):
        shown_messages.append((title, text))
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.get_module_release_service",
        lambda: SimpleNamespace(prepare_dev_link=fake_prepare_dev_link),
    )
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.InstallPreviewDialog", FakeDialog)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.MessageDialog.information",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("blocking static information dialog should not be used")
        ),
    )
    monkeypatch.setattr("src.core.mms.ui.module_list_widget.MessageDialog.show_async", fake_message_show_async)

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    await widget._register_dev_link_async(str(module.path))

    assert register_calls == [str(module.path)]
    assert refresh_calls == [1]
    assert len(shown_messages) == 1
    assert shown_messages[0][1] == (
        "已添加开发模块: demo_module\n当前模块来源会切换为“开发链接”，可在 ATM 中发起任务调试。"
    )
