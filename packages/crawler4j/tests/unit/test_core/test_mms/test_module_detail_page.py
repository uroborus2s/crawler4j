from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton, QSplitter

from src.core.mms.models import (
    ConfigDefaultsInfo,
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    UIPageInfo,
    UIExtensionInfo,
    WorkflowInfo,
)
from src.core.mms.github_credentials import get_github_credential_store
from src.core.mms.ui.dev_link_actions import DevLinkRemovalResult
from src.core.mms.ui.module_detail_page import ModuleDetailPage
from src.ui.components.combo_box import StyledComboBox


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _make_module(
    tmp_path: Path,
    *,
    source: ModuleSource = ModuleSource.DEV_LINK,
    pages: list[UIPageInfo] | None = None,
    runtime_body: str | None = None,
    config_defaults: ConfigDefaultsInfo | None = None,
) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    if runtime_body:
        (module_dir / "__init__.py").write_text(
            dedent(
                """
                import importlib

                _runtime_module = None


                def _load_runtime_module():
                    global _runtime_module
                    if _runtime_module is None:
                        _runtime_module = importlib.import_module(f"{__name__}.module_runtime")
                    return _runtime_module


                def __getattr__(name: str):
                    runtime_module = _load_runtime_module()
                    if hasattr(runtime_module, name):
                        return getattr(runtime_module, name)
                    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (module_dir / "module_runtime.py").write_text(dedent(runtime_body).strip() + "\n", encoding="utf-8")
    else:
        (module_dir / "__init__.py").write_text("VALUE = 'demo'\n", encoding="utf-8")

    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(
            name="demo_module",
            display_name="Demo Module",
            workflows=[
                WorkflowInfo(name="default", display_name="默认流程"),
            ],
            ui_extension=UIExtensionInfo(
                pages=list(pages or []),
            ),
            config_defaults=config_defaults or ConfigDefaultsInfo(),
        ),
        source=source,
        path=module_dir,
    )


def _make_hosted_ui_module(
    tmp_path: Path,
    *,
    source: ModuleSource = ModuleSource.DEV_LINK,
    dashboard_title: str = "今日运营看板",
) -> ModuleInfo:
    return _make_module(
        tmp_path,
        source=source,
        pages=[
            UIPageInfo(
                id="dashboard",
                icon="📊",
                label="今日运营看板",
                entry="core:page:dashboard",
            ),
            UIPageInfo(
                id="accounts",
                icon="📋",
                label="账号管理",
                entry="core:data_table:accounts",
            ),
        ],
        runtime_body=f"""
        from crawler4j_sdk import TaskContext


        def declare_ui(context: TaskContext):
            context.tools.call(
                "ui.declare_page",
                page_id="dashboard",
                schema={{
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {{"type": "Text", "style": "title", "binding": "title"}},
                        {{"type": "Text", "style": "body", "binding": "summary"}},
                        {{
                            "type": "Button",
                            "label": "打开账号管理",
                            "action": {{"type": "open_page", "entry": "core:data_table:accounts"}},
                        }},
                        {{
                            "type": "DataTable",
                            "title": "统计明细",
                            "binding": "rows",
                            "columns": [
                                {{"key": "metric", "label": "指标"}},
                                {{"key": "value", "label": "值"}},
                            ],
                        }},
                    ],
                }},
            )
            context.tools.call(
                "ui.declare_data_table",
                view_id="accounts",
                schema={{
                    "title": "账号管理",
                    "dataset": "accounts",
                    "columns": [
                        {{"key": "phone", "label": "手机号"}},
                    ],
                }},
            )
            context.tools.call(
                "db.replace_records",
                dataset="accounts",
                records=[{{"phone": "13800138000"}}],
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            return {{
                "title": "{dashboard_title}",
                "summary": "展示宿主页渲染内容",
                "rows": [
                    {{"metric": "活跃账号", "value": "12"}},
                ],
            }}
        """,
    )


def test_module_detail_page_no_longer_exposes_debug_ui(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

    menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
    assert all("调试" not in text for text in menu_texts)

    button_texts = [button.text() for button in page.findChildren(QPushButton)]
    assert all("调试" not in text for text in button_texts)


def test_module_detail_page_loads_hosted_pages_from_manifest(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK))

    menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
    assert "📊 今日运营看板" in menu_texts
    assert "📋 账号管理" in menu_texts
    assert "dashboard" not in page._menu_pages
    assert "accounts" not in page._menu_pages
    assert page._entry_to_menu_id["core:page:dashboard"] == "dashboard"
    assert page._entry_to_menu_id["core:data_table:accounts"] == "accounts"


def test_module_detail_page_defers_hosted_page_hooks_until_selected(qtbot, tmp_path):
    events_path = tmp_path / "hosted-page-events.log"
    module = _make_module(
        tmp_path,
        source=ModuleSource.DEV_LINK,
        pages=[
            UIPageInfo(
                id="dashboard",
                icon="📊",
                label="懒加载看板",
                entry="core:page:dashboard",
            ),
        ],
        runtime_body=f"""
        from pathlib import Path

        from crawler4j_sdk import TaskContext


        EVENTS_PATH = Path({str(events_path)!r})


        def _record(event: str) -> None:
            previous = EVENTS_PATH.read_text(encoding="utf-8") if EVENTS_PATH.exists() else ""
            EVENTS_PATH.write_text(previous + event + "\\n", encoding="utf-8")


        def declare_ui(context: TaskContext):
            _record("declare_ui")
            context.tools.call(
                "ui.declare_page",
                page_id="dashboard",
                schema={{
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {{"type": "Text", "binding": "title"}},
                    ],
                }},
            )


        def load_dashboard_page(context: TaskContext, page_id: str, params=None):
            _record("load_handler")
            return {{
                "title": "懒加载看板",
            }}
        """,
    )
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(module)

    assert "dashboard" not in page._menu_pages
    assert not events_path.exists()

    page._select_menu("dashboard")
    qtbot.waitUntil(lambda: events_path.exists())

    hosted_page = page._menu_pages["dashboard"]
    assert events_path.read_text(encoding="utf-8").splitlines() == [
        "declare_ui",
        "load_handler",
    ]
    assert any(label.text() == "懒加载看板" for label in hosted_page.findChildren(QLabel))


def test_module_detail_page_loads_hosted_page_for_core_page_entry(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_hosted_ui_module(tmp_path, source=ModuleSource.EXTERNAL))
    page._select_menu("dashboard")
    hosted_page = page._menu_pages["dashboard"]
    texts = [label.text() for label in hosted_page.findChildren(QLabel)]

    assert "今日运营看板" in texts
    assert "展示宿主页渲染内容" in texts


def test_module_detail_page_reloads_dev_link_hosted_page_after_source_change(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK)

    page.set_module(module)
    page._select_menu("dashboard")
    hosted_page = page._menu_pages["dashboard"]
    assert any(label.text() == "今日运营看板" for label in hosted_page.findChildren(QLabel))

    module_dir = Path(module.path)
    (module_dir / "module_runtime.py").write_text(
        dedent(
            """
            from crawler4j_sdk import TaskContext


            def declare_ui(context: TaskContext):
                context.tools.call(
                    "ui.declare_page",
                    page_id="dashboard",
                    schema={
                        "type": "Page",
                        "load_handler": "load_dashboard_page",
                        "children": [
                            {"type": "Text", "style": "title", "binding": "title"},
                        ],
                    },
                )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                return {"title": "已重新加载看板"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    page.set_module(module)
    assert "dashboard" not in page._menu_pages
    page._select_menu("dashboard")
    reloaded_page = page._menu_pages["dashboard"]
    assert any(label.text() == "已重新加载看板" for label in reloaded_page.findChildren(QLabel))


def test_module_detail_page_refreshes_existing_data_table_page_when_reselected(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK)

    page.set_module(module)
    page._select_menu("accounts")
    accounts_page = page._menu_pages["accounts"]
    assert accounts_page.title_label.text() == "账号管理"
    assert accounts_page.table.item(0, 0).text() == "13800138000"

    module_dir = Path(module.path)
    (module_dir / "module_runtime.py").write_text(
        dedent(
            """
            from crawler4j_sdk import TaskContext


            def declare_ui(context: TaskContext):
                context.tools.call(
                    "ui.declare_page",
                    page_id="dashboard",
                    schema={
                        "type": "Page",
                        "load_handler": "load_dashboard_page",
                        "children": [
                            {"type": "Text", "style": "title", "binding": "title"},
                        ],
                    },
                )
                context.tools.call(
                    "ui.declare_data_table",
                    view_id="accounts",
                    schema={
                        "title": "已重新加载账号表",
                        "dataset": "accounts",
                        "columns": [
                            {"key": "phone", "label": "手机号"},
                        ],
                    },
                )
                context.tools.call(
                    "db.replace_records",
                    dataset="accounts",
                    records=[{"phone": "13900139000"}],
                )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                return {"title": "已重新加载看板"}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    page._select_menu("info")
    page._select_menu("accounts")

    assert page._menu_pages["accounts"] is accounts_page
    assert accounts_page.title_label.text() == "已重新加载账号表"
    assert accounts_page.table.item(0, 0).text() == "13900139000"


def test_module_detail_page_renders_core_managed_data_table_entry(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_hosted_ui_module(tmp_path))
    assert "accounts" not in page._menu_pages

    page._select_menu("accounts")
    custom_page = page._menu_pages["accounts"]
    assert custom_page.__class__.__name__ == "ModuleDataTablePage"


def test_module_detail_page_open_page_button_switches_to_target_entry(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_hosted_ui_module(tmp_path))
    assert "dashboard" not in page._menu_pages
    assert "accounts" not in page._menu_pages
    page._select_menu("dashboard")

    hosted_page = page._menu_pages["dashboard"]
    open_button = next(
        button
        for button in hosted_page.findChildren(QPushButton)
        if button.text() == "打开账号管理"
    )
    open_button.click()

    qtbot.waitUntil(
        lambda: "accounts" in page._menu_pages
        and page.content_stack.currentWidget() is page._menu_pages["accounts"]
    )

    current_item = page.menu_list.currentItem()
    assert current_item is not None
    assert current_item.data(Qt.ItemDataRole.UserRole) == "accounts"


def test_module_detail_page_remove_dev_link_uses_shared_fallback_message(qtbot, tmp_path, monkeypatch):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    fallback = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    fallback.manifest.display_name = "Fallback Module"

    monkeypatch.setattr(
        "src.core.mms.ui.module_detail_page.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    info_messages: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_detail_page.QMessageBox.information",
        lambda *args: info_messages.append(args[2]),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.module_detail_page.remove_dev_link_and_describe",
        lambda name: DevLinkRemovalResult(
            fallback=fallback if name == module.name else None,
            title="已切换",
            message="已移除开发链接，当前已回退到 正式安装模块: demo_module",
        ),
    )

    page.set_module(module)
    page._remove_dev_link()

    assert page._module is fallback
    assert info_messages == ["已移除开发链接，当前已回退到 正式安装模块: demo_module"]


def test_module_detail_page_exposes_config_page_and_persists_module_and_workflow_settings(qtbot, tmp_path):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"base_url": "https://example.com"})
    store.write_workflow_settings("demo_module", "default", {"headless": False})

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch("PyQt6.QtWidgets.QMessageBox.warning"):
        page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

        menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
        assert any("配置" in text for text in menu_texts)

        config_page = page._menu_pages["config"]
        assert isinstance(config_page.workflow_selector, StyledComboBox)
        assert "base_url: https://example.com" in config_page.module_config_editor.toPlainText()
        assert "headless: false" in config_page.workflow_config_editor.toPlainText()

        config_page.module_config_editor.setPlainText(
            "base_url: https://new.example.com\nretry: 3\n"
        )
        config_page._save_module_config()

        config_page.workflow_selector.setCurrentIndex(0)
        config_page.workflow_config_editor.setPlainText(
            "headless: true\nregion: cn\n"
        )
        config_page._save_workflow_config()

    assert store.read_module_settings("demo_module") == {
        "base_url": "https://new.example.com",
        "retry": 3,
    }
    assert store.read_workflow_settings("demo_module", "default") == {
        "headless": True,
        "region": "cn",
    }


def test_module_detail_page_saves_and_clears_repo_token(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    module.manifest.upgrade_source.repo = "example/private-repo"

    infos: list[str] = []
    with patch("PyQt6.QtWidgets.QMessageBox.information", lambda *args: infos.append(args[2])):
        page.set_module(module)

        assert page.repo_token_status_label is not None
        assert page.repo_token_status_label.text() == "未配置"

        page.repo_token_edit.setText("ghp_secret_token_1234")
        page._save_repo_token()

        assert page.repo_token_status_label.text() == "已配置"
        assert get_github_credential_store().get_token("example/private-repo") == "ghp_secret_token_1234"

    with patch(
        "PyQt6.QtWidgets.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    ), patch("PyQt6.QtWidgets.QMessageBox.information", lambda *args: infos.append(args[2])):
        page._clear_repo_token()

    assert page.repo_token_status_label.text() == "未配置"
    assert get_github_credential_store().get_token("example/private-repo") is None
    assert any("已保存仓库 example/private-repo 的 GitHub Token" in message for message in infos)
    assert any("已清除仓库 example/private-repo 的 GitHub Token" in message for message in infos)


def test_module_detail_page_config_page_uses_resizable_70_30_splitter(qtbot, tmp_path):
    page = ModuleDetailPage()
    page.resize(1280, 900)
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    page._select_menu("config")
    page.show()

    config_page = page._menu_pages["config"]
    qtbot.waitUntil(lambda: sum(config_page.config_splitter.sizes()) > 0)

    sizes = config_page.config_splitter.sizes()
    total = sum(sizes)

    assert isinstance(config_page.config_splitter, QSplitter)
    assert config_page.config_splitter.handleWidth() == 8
    assert total > 0
    assert 0.62 <= sizes[0] / total <= 0.78
    assert sizes[0] > sizes[1]


def test_module_detail_page_config_editors_hide_vertical_scrollbars(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    config_page = page._menu_pages["config"]

    assert (
        config_page.module_config_editor.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert (
        config_page.workflow_config_editor.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )


def test_module_detail_page_rejects_json_literal_in_config_editors(qtbot, tmp_path):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"base_url": "https://example.com"})
    store.write_workflow_settings("demo_module", "default", {"headless": False})

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch("PyQt6.QtWidgets.QMessageBox.warning") as warning:
        page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

        config_page = page._menu_pages["config"]
        config_page.module_config_editor.setPlainText('{"base_url": "https://bad.example.com"}')
        config_page._save_module_config()
        config_page.workflow_config_editor.setPlainText('{"headless": true}')
        config_page._save_workflow_config()

    assert warning.call_count == 2
    assert store.read_module_settings("demo_module") == {
        "base_url": "https://example.com",
    }
    assert store.read_workflow_settings("demo_module", "default") == {
        "headless": False,
    }


def test_module_detail_page_restores_default_settings_after_warning_confirmation(qtbot, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    module = _make_module(
        tmp_path,
        source=ModuleSource.DEV_LINK,
        config_defaults=ConfigDefaultsInfo(
            module={"base_url": "https://example.com", "retry": 3},
            workflows={"default": {"headless": False, "region": "cn"}},
        ),
    )

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch(
        "PyQt6.QtWidgets.QMessageBox.warning",
        side_effect=[
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Yes,
        ],
    ):
        page.set_module(module)
        config_page = page._menu_pages["config"]

        store.write_module_settings("demo_module", {"base_url": "https://custom.example.com", "retry": 9})
        store.write_workflow_settings("demo_module", "default", {"headless": True, "region": "us"})
        config_page._reload_editors()

        config_page._restore_module_defaults()
        assert store.read_module_settings("demo_module") == {
            "base_url": "https://custom.example.com",
            "retry": 9,
        }

        config_page._restore_module_defaults()
        assert store.read_module_settings("demo_module") == {
            "base_url": "https://example.com",
            "retry": 3,
        }

        config_page._restore_workflow_defaults()
        assert store.read_workflow_settings("demo_module", "default") == {
            "headless": False,
            "region": "cn",
        }
