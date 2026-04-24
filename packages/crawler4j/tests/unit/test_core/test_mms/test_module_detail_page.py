from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton

from src.core.mms.github_credentials import get_github_credential_store
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.mms.ui.module_detail_page import ModuleDetailPage

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


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
    pages: list | None = None,
    files: dict[str, str] | None = None,
    display_name: str = "Demo Module",
    description: str = "",
) -> ModuleInfo:
    module_dir = write_module_tree(tmp_path / source.value, "demo_module", files=files or {})
    return ModuleInfo(
        name="demo_module",
        manifest=make_manifest(
            "demo_module",
            display_name=display_name,
            description=description,
            pages=list(pages or []),
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
            make_page_info("dashboard", label="今日运营看板", icon="📊"),
            make_page_info("accounts", label="账号管理", icon="📋"),
        ],
        files={
            "pages/dashboard.py": f"""
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="dashboard",
                label="今日运营看板",
                icon="📊",
                schema={{
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {{"type": "Text", "style": "title", "binding": "title"}},
                        {{"type": "Text", "style": "body", "binding": "summary"}},
                        {{
                            "type": "Button",
                            "label": "打开账号管理",
                            "action": {{"type": "open_page", "page_id": "accounts"}},
                        }},
                        {{
                            "type": "DataTable",
                            "table_id": "dashboard_metrics",
                            "title": "统计明细",
                            "data_source": {{"type": "binding", "binding": "rows"}},
                            "columns": [
                                {{"key": "metric", "label": "指标"}},
                                {{"key": "value", "label": "值"}},
                            ],
                        }},
                    ],
                }},
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {{
                    "title": "{dashboard_title}",
                    "summary": "展示宿主页渲染内容",
                    "rows": [{{"metric": "活跃账号", "value": "12"}}],
                }}
            """,
            "pages/accounts.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="accounts",
                label="账号管理",
                icon="📋",
                schema={
                    "type": "Page",
                    "load_handler": "load_accounts_page",
                    "children": [
                        {"type": "Text", "style": "title", "binding": "title"},
                        {
                            "type": "DataTable",
                            "table_id": "accounts_table",
                            "title": "账号管理",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [{"key": "phone", "label": "手机号"}],
                        },
                    ],
                },
            )


            def load_accounts_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {
                    "title": "账号管理",
                    "rows": [{"phone": "13800138000"}],
                }
            """,
        },
    )


def _activate_runtime(module: ModuleInfo) -> tuple[object, object]:
    service, original_registry, _ = register_module(
        module.name,
        Path(module.path),
        manifest=module.manifest,
        source=module.source,
    )
    return service, original_registry


def test_module_detail_page_no_longer_exposes_debug_ui(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

    menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
    assert all("调试" not in text for text in menu_texts)

    button_texts = [button.text() for button in page.findChildren(QPushButton)]
    assert all("调试" not in text for text in button_texts)


def test_module_detail_page_loads_hosted_pages_from_manifest(qtbot, tmp_path):
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK)
    service, original_registry = _activate_runtime(module)
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    try:
        page.set_module(module)

        menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
        assert "📊 今日运营看板" in menu_texts
        assert "📋 账号管理" in menu_texts
        assert "dashboard" not in page._menu_pages
        assert "accounts" not in page._menu_pages
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_defers_hosted_page_loading_until_selected(qtbot, tmp_path):
    events_path = tmp_path / "hosted-page-events.log"
    module = _make_module(
        tmp_path,
        source=ModuleSource.DEV_LINK,
        pages=[make_page_info("dashboard", label="懒加载看板", icon="📊")],
        files={
            "pages/dashboard.py": f"""
            from pathlib import Path

            from crawler4j_contracts import PageSpec, TaskContext

            EVENTS_PATH = Path({str(events_path)!r})


            def _record(event: str) -> None:
                previous = EVENTS_PATH.read_text(encoding="utf-8") if EVENTS_PATH.exists() else ""
                EVENTS_PATH.write_text(previous + event + "\\n", encoding="utf-8")


            PAGE = PageSpec(
                id="dashboard",
                label="懒加载看板",
                icon="📊",
                schema={{
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [{{"type": "Text", "binding": "title"}}],
                }},
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                _record("load_handler")
                return {{"title": "懒加载看板"}}
            """,
        },
    )
    service, original_registry = _activate_runtime(module)
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    try:
        page.set_module(module)

        assert "dashboard" not in page._menu_pages
        assert not events_path.exists()

        page._select_menu("dashboard")
        qtbot.waitUntil(lambda: events_path.exists())

        hosted_page = page._menu_pages["dashboard"]
        assert events_path.read_text(encoding="utf-8").splitlines() == ["load_handler"]
        assert any(label.text() == "懒加载看板" for label in hosted_page.findChildren(QLabel))
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_loads_selected_hosted_page(qtbot, tmp_path):
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.EXTERNAL)
    service, original_registry = _activate_runtime(module)
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    try:
        page.set_module(module)
        page._select_menu("dashboard")
        hosted_page = page._menu_pages["dashboard"]
        texts = [label.text() for label in hosted_page.findChildren(QLabel)]

        assert "今日运营看板" in texts
        assert "展示宿主页渲染内容" in texts
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_reloads_dev_link_hosted_page_after_source_change(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK)
    service, original_registry = _activate_runtime(module)

    try:
        page.set_module(module)
        page._select_menu("dashboard")
        hosted_page = page._menu_pages["dashboard"]
        assert any(label.text() == "今日运营看板" for label in hosted_page.findChildren(QLabel))

        module_dir = Path(module.path)
        time.sleep(1.1)
        (module_dir / "pages" / "dashboard.py").write_text(
            dedent(
                """
                from crawler4j_contracts import PageSpec

                PAGE = PageSpec(
                    id="dashboard",
                    label="今日运营看板",
                    icon="📊",
                    schema={
                        "type": "Page",
                        "load_handler": "load_dashboard_page",
                        "children": [{"type": "Text", "style": "title", "binding": "title"}],
                    },
                )


                def load_dashboard_page(context, page_id, params=None):
                    del context, page_id, params
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
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_refreshes_existing_hosted_page_when_reselected(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_hosted_ui_module(tmp_path, source=ModuleSource.DEV_LINK)
    service, original_registry = _activate_runtime(module)

    try:
        page.set_module(module)
        page._select_menu("accounts")
        accounts_page = page._menu_pages["accounts"]
        table = accounts_page._data_table_widgets["accounts_table"]
        assert any(label.text() == "账号管理" for label in accounts_page.findChildren(QLabel))
        assert table.item(0, 0).text() == "13800138000"

        module_dir = Path(module.path)
        time.sleep(1.1)
        (module_dir / "pages" / "accounts.py").write_text(
            dedent(
                """
                from crawler4j_contracts import PageSpec

                PAGE = PageSpec(
                    id="accounts",
                    label="账号管理",
                    icon="📋",
                    schema={
                        "type": "Page",
                        "load_handler": "load_accounts_page",
                        "children": [
                            {"type": "Text", "style": "title", "binding": "title"},
                            {
                                "type": "DataTable",
                                "table_id": "accounts_table",
                                "title": "账号管理",
                                "data_source": {"type": "binding", "binding": "rows"},
                                "columns": [{"key": "phone", "label": "手机号"}],
                            },
                        ],
                    },
                )


                def load_accounts_page(context, page_id, params=None):
                    del context, page_id, params
                    return {
                        "title": "已重新加载账号页",
                        "rows": [{"phone": "13900139000"}],
                    }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        page._select_menu("info")
        page._select_menu("accounts")

        assert page._menu_pages["accounts"] is accounts_page
        assert any(label.text() == "已重新加载账号页" for label in accounts_page.findChildren(QLabel))
        table = accounts_page._data_table_widgets["accounts_table"]
        assert table.item(0, 0).text() == "13900139000"
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_open_page_button_switches_to_target_page(qtbot, tmp_path):
    module = _make_hosted_ui_module(tmp_path)
    service, original_registry = _activate_runtime(module)
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    try:
        page.set_module(module)
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
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_row_action_refreshes_cached_target_with_new_params(qtbot, tmp_path):
    module = _make_module(
        tmp_path,
        pages=[
            make_page_info("dashboard", label="主表", icon="📊"),
        ],
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec

            PAGE = PageSpec(
                id="dashboard",
                label="主表",
                icon="📊",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "master",
                            "title": "主表",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [{"key": "account_id", "label": "账号"}],
                            "row_action": {
                                "type": "open_page",
                                "page_id": "details",
                                "params": {
                                    "account_id": {"binding": "account_id"},
                                },
                            },
                        },
                    ],
                },
            )


            def load_dashboard_page(context, page_id, params=None):
                del context, page_id, params
                return {"rows": [{"account_id": "acct-001"}, {"account_id": "acct-002"}]}
            """,
            "pages/details.py": """
            from crawler4j_contracts import PageSpec

            DETAIL_ROWS = {
                "acct-001": [{"account_id": "acct-001", "detail_id": "detail-1"}],
                "acct-002": [
                    {"account_id": "acct-002", "detail_id": "detail-2"},
                    {"account_id": "acct-002", "detail_id": "detail-3"},
                ],
            }

            PAGE = PageSpec(
                id="details",
                label="详情页",
                icon="📋",
                schema={
                    "type": "Page",
                    "load_handler": "load_details_page",
                    "children": [
                        {"type": "Text", "binding": "title"},
                        {
                            "type": "DataTable",
                            "table_id": "details_table",
                            "title": "详情表",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "detail_id", "label": "明细"},
                            ],
                        },
                    ],
                },
            )


            def load_details_page(context, page_id, params=None):
                del context, page_id
                account_id = ""
                if isinstance(params, dict):
                    account_id = str(params.get("account_id") or "")
                rows = DETAIL_ROWS.get(account_id, [])
                return {
                    "title": f"详情页: {account_id or 'none'}",
                    "rows": rows,
                }
            """,
        },
    )
    service, original_registry = _activate_runtime(module)
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    try:
        page.set_module(module)

        menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
        assert "📊 主表" in menu_texts
        assert "📋 详情页" not in menu_texts

        page._select_menu("dashboard")
        dashboard = page._menu_pages["dashboard"]
        master_table = dashboard._data_table_widgets["master"]

        master_table.cellClicked.emit(0, 0)
        qtbot.waitUntil(
            lambda: "details" in page._menu_pages
            and page.content_stack.currentWidget() is page._menu_pages["details"]
        )
        details_page = page._menu_pages["details"]
        details_table = details_page._data_table_widgets["details_table"]
        assert details_table.item(0, 1).text() == "detail-1"

        page._select_menu("dashboard")
        master_table = dashboard._data_table_widgets["master"]
        master_table.cellClicked.emit(1, 0)

        qtbot.waitUntil(
            lambda: page._menu_pages["details"] is details_page
            and details_page._data_table_widgets["details_table"].rowCount() == 2
        )
        details_table = details_page._data_table_widgets["details_table"]
        assert details_table.item(0, 0).text() == "acct-002"
        assert details_table.item(0, 1).text() == "detail-2"
        assert details_table.item(1, 1).text() == "detail-3"
    finally:
        restore_module(service, original_registry, module.name)


def test_module_detail_page_save_repo_token_updates_status_label(qtbot, monkeypatch, tmp_path):
    store = get_github_credential_store()
    monkeypatch.setattr(store, "set_token", lambda repo, token: None)
    monkeypatch.setattr(store, "has_token", lambda repo: True)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    module = _make_hosted_ui_module(tmp_path)
    module.manifest.upgrade_source.repo = "demo/repo"
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    page.set_module(module)
    page._select_menu("info")

    assert page.repo_token_edit is not None
    assert page.repo_token_status_label is not None

    page.repo_token_edit.setText("ghp_saved")
    page._save_repo_token()

    assert "已配置" in page.repo_token_status_label.text()


def test_module_detail_page_clear_repo_token_updates_status_label(qtbot, monkeypatch, tmp_path):
    store = get_github_credential_store()
    monkeypatch.setattr(store, "clear_token", lambda repo: None)
    monkeypatch.setattr(store, "has_token", lambda repo: False)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    module = _make_hosted_ui_module(tmp_path)
    module.manifest.upgrade_source.repo = "demo/repo"
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    page.set_module(module)
    page._select_menu("info")

    assert page.repo_token_edit is not None
    assert page.repo_token_status_label is not None

    page.repo_token_edit.setText("ghp_to_clear")
    page._clear_repo_token()

    assert page.repo_token_edit.text() == ""
    assert "未配置" in page.repo_token_status_label.text()
