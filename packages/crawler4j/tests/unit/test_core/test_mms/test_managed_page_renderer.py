from __future__ import annotations

import asyncio
import builtins
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QSizePolicy

from src.core.mms.ui.managed_page_renderer import ManagedPageRenderer
from src.core.persistence import get_module_data_store
from src.ui.components.button import StyledButton
from src.ui.components.line_edit import StyledLineEdit

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def test_managed_page_renderer_requires_fixed_query_result_contract():
    with pytest.raises(ValueError, match="HostedDataTableQueryResult"):
        ManagedPageRenderer._normalize_inline_query_result(None, {"rows": []})  # type: ignore[arg-type]


def test_managed_page_renderer_loads_page_data_refreshes_and_handles_open_page(qtbot, tmp_path):
    module_name = "hosted_page_module"
    load_key = "_hosted_page_module_load_count"
    setattr(builtins, load_key, 0)
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": f"""
            import builtins

            from crawler4j_contracts import TaskContext, page

            LOAD_COUNT_KEY = "{load_key}"

            @page(
                name="dashboard",
                label="Dashboard",
                icon="📊",
                schema={{
                    "type": "Page",
                    "children": [
                        {{"type": "Text", "style": "title", "binding": "title"}},
                        {{"type": "Text", "style": "body", "binding": "load_count_text"}},
                        {{"type": "Button", "label": "刷新", "action": {{"type": "reload"}}}},
                        {{"type": "Button", "label": "打开账号页", "action": {{"type": "open_page", "page_id": "accounts"}}}},
                        {{
                            "type": "DataTable",
                            "table_id": "metrics",
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
                count = int(getattr(builtins, LOAD_COUNT_KEY, 0)) + 1
                setattr(builtins, LOAD_COUNT_KEY, count)
                return {{
                    "title": "今日运营看板",
                    "load_count_text": f"第 {{count}} 次加载",
                    "rows": [{{"metric": "活跃账号", "value": str(10 + count)}}],
                }}
            """,
            "pages/accounts.py": """
            from crawler4j_contracts import TaskContext, page

            @page(
                name="accounts",
                label="Accounts",
                icon="📋",
                schema={
                    "type": "Page",
                    "children": [{"type": "Text", "style": "title", "binding": "title"}],
                },
            )
            def load_accounts_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {"title": "账号页"}
            """,
        },
    )
    manifest = make_manifest(
        module_name,
        pages=[
            make_page_info("dashboard", label="今日运营看板", icon="📊"),
            make_page_info("accounts", label="账号管理", icon="📋"),
        ],
    )
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
        )
        qtbot.addWidget(page)

        assert any(label.text() == "今日运营看板" for label in page.findChildren(QLabel))
        assert any(label.text() == "第 1 次加载" for label in page.findChildren(QLabel))
        first_table = page._data_table_widgets["metrics"]
        assert first_table.item(0, 0).text() == "活跃账号"
        assert first_table.item(0, 1).text() == "11"

        reload_button = next(button for button in page.findChildren(QPushButton) if button.text() == "刷新")
        reload_button.click()
        qtbot.waitUntil(lambda: any(label.text() == "第 2 次加载" for label in page.findChildren(QLabel)))

        open_button = next(button for button in page.findChildren(QPushButton) if button.text() == "打开账号页")
        open_button.click()
        assert opened_pages == [("accounts", None)]
    finally:
        restore_module(service, original_registry, module_name)
        delattr(builtins, load_key)


def test_managed_page_renderer_handles_ui_action_button(qtbot, tmp_path):
    module_name = "hosted_ui_action_button_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import TaskContext, page

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "Button",
                            "label": "创建账号",
                            "action": {
                                "type": "ui_action",
                                "name": "create_account_from_ui",
                                "params": {"account_id": {"value": "acct-001"}},
                            },
                        },
                    ],
                },
            )
            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {}
            """,
            "pages/actions.py": """
            from crawler4j_contracts import TaskContext, ui_action

            CALLS = []

            @ui_action(name="create_account_from_ui")
            async def create_account_from_ui(context: TaskContext, account_id: str):
                del context
                CALLS.append({"account_id": account_id})
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "dashboard", module_info=module_info)
        qtbot.addWidget(page)

        action_button = next(button for button in page.findChildren(QPushButton) if button.text() == "创建账号")
        action_button.click()

        import importlib

        action_module = importlib.import_module(f"{module_name}.pages.actions")
        assert action_module.CALLS == [{"account_id": "acct-001"}]
    finally:
        restore_module(service, original_registry, module_name)


@pytest.mark.asyncio
async def test_managed_page_renderer_async_ui_action_failure_uses_async_warning(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_ui_action_failure_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import TaskContext, page, ui_action

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "Button",
                            "label": "失败操作",
                            "action": {"type": "ui_action", "name": "fail_from_ui"},
                        },
                    ],
                },
            )
            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="fail_from_ui")
            async def fail_from_ui(context: TaskContext):
                del context
                raise RuntimeError("action failed")
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    warnings: list[tuple[str, str]] = []

    def fail_sync_warning(*_args, **_kwargs):
        raise AssertionError("blocking warning should not be used in async Hosted UI action flow")

    async def fake_warning_async(_parent, title, message, **_kwargs):
        warnings.append((title, message))
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr("src.core.mms.ui.managed_page_renderer.MessageDialog.warning", fail_sync_warning)
    monkeypatch.setattr("src.core.mms.ui.managed_page_renderer.MessageDialog.warning_async", fake_warning_async)

    try:
        page = ManagedPageRenderer(module_name, "dashboard", module_info=module_info)
        qtbot.addWidget(page)

        action_button = next(button for button in page.findChildren(QPushButton) if button.text() == "失败操作")
        action_button.click()

        for _ in range(50):
            if warnings:
                break
            await asyncio.sleep(0.01)

        assert warnings == [("操作失败", "action failed")]
    finally:
        restore_module(service, original_registry, module_name)


@pytest.mark.asyncio
async def test_managed_page_renderer_crud_create_uses_async_dialog_without_exec(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_page_async_crud_create_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page, ui_action

            CALLS = []

            @page(
                name="accounts",
                label="账号管理",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {"type": "rows", "rows": []},
                            "crud": {
                                "mode": "handlers",
                                "primary_key": "account_id",
                                "form": {"create_columns": ["name", "secret"]},
                                "create_handler": "create_account_from_ui",
                            },
                            "columns": [
                                {"key": "account_id", "label": "ID", "visible": False},
                                {"key": "name", "label": "账号名", "required": True},
                                {"key": "secret", "label": "密码", "required": True},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="create_account_from_ui")
            async def create_account_from_ui(context, payload):
                del context
                CALLS.append(dict(payload))
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    def fail_exec(self):
        raise AssertionError("blocking exec should not be used in async Hosted UI CRUD flow")

    def fake_show(dialog: QDialog):
        qtbot.addWidget(dialog)
        if dialog.windowTitle() == "新增账号管理":
            edits = dialog.findChildren(StyledLineEdit)
            assert len(edits) == 2
            edits[0].setText("alpha")
            edits[1].setText("secret-alpha")
        asyncio.get_running_loop().call_soon(lambda: dialog.done(int(QDialog.DialogCode.Accepted)))

    monkeypatch.setattr(QDialog, "exec", fail_exec)
    monkeypatch.setattr(QDialog, "show", fake_show)

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        component = page._schema["children"][0]
        table = page._data_table_widgets["accounts"]
        await page._handle_create_action_async(component, table)

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert actions_module.CALLS == [{"name": "alpha", "secret": "secret-alpha"}]
    finally:
        restore_module(service, original_registry, module_name)


@pytest.mark.asyncio
async def test_managed_page_renderer_crud_delete_uses_async_confirm(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_page_async_crud_delete_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page, ui_action

            CALLS = []

            @page(
                name="accounts",
                label="账号管理",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {
                                "type": "rows",
                                "rows": [{"account_id": "acct-001", "name": "alpha"}],
                            },
                            "crud": {
                                "mode": "handlers",
                                "primary_key": "account_id",
                                "delete_handler": "delete_account_from_ui",
                            },
                            "columns": [
                                {"key": "account_id", "label": "ID"},
                                {"key": "name", "label": "账号名"},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="delete_account_from_ui")
            async def delete_account_from_ui(context, account_id):
                del context
                CALLS.append(str(account_id))
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    def fail_sync_confirm(*_args, **_kwargs):
        raise AssertionError("blocking delete confirm should not be used in async Hosted UI CRUD flow")

    async def fake_delete_confirm_async(_parent, item_name):
        assert item_name == "alpha"
        return True

    monkeypatch.setattr("src.core.mms.ui.managed_page_renderer.ConfirmDialog.delete_confirm", fail_sync_confirm)
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.ConfirmDialog.delete_confirm_async",
        fake_delete_confirm_async,
    )

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 1)
        table.selectRow(0)
        component = page._schema["children"][0]
        await page._handle_delete_action_async(component, table)

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert actions_module.CALLS == ["acct-001"]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_keeps_header_icon_button_compact(qtbot, tmp_path):
    module_name = "hosted_page_header_button_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/detail.py": """
            from crawler4j_contracts import TaskContext, page

            @page(
                name="detail",
                label="明细",
                icon="📄",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "Section",
                            "variant": "plain",
                            "layout": {"direction": "row", "gap": 8},
                            "children": [
                                {
                                    "type": "Button",
                                    "icon": "←",
                                    "aria_label": "返回",
                                    "size": "icon",
                                    "variant": "ghost",
                                    "action": {"type": "open_page", "page_id": "accounts"},
                                },
                                {"type": "Text", "style": "title", "text": "劳保计费明细"},
                            ],
                        },
                    ],
                },
            )
            def load_detail_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("detail", label="明细", icon="📄")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "detail", module_info=module_info)
        qtbot.addWidget(page)

        back_button = next(button for button in page.findChildren(QPushButton) if button.text() == "←")
        assert back_button.toolTip() == "返回"
        assert back_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
        assert back_button.minimumWidth() <= 40
        assert back_button.maximumWidth() <= 40
        assert back_button.width() <= 40
    finally:
        restore_module(service, original_registry, module_name)


def _sync_managed_dataset(module_root, *, module_name: str, resource_id: str) -> None:
    from src.core.mms.data_contract import normalize_manifest_data

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "managed_dataset",
                    "schema": {
                        "version": 1,
                        "columns": [
                            {"name": "id", "type": "text", "required": True},
                            {"name": "account_id", "type": "text"},
                            {"name": "name", "type": "text"},
                            {"name": "secret", "type": "text"},
                            {"name": "status", "type": "text"},
                        ],
                    },
                }
            ],
            "views": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def test_managed_page_renderer_managed_resource_query_is_not_limited_to_first_1000_rows(qtbot, tmp_path):
    module_name = "hosted_page_large_managed_resource_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page

            @page(
                name="accounts",
                label="账号管理",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {"type": "managed_resource", "resource_id": "accounts"},
                            "features": {"pagination": {"page_size": 20}},
                            "columns": [
                                {
                                    "key": "account_id",
                                    "label": "ID",
                                    "searchable": True,
                                    "sortable": True,
                                },
                                {
                                    "key": "name",
                                    "label": "账号名",
                                    "searchable": True,
                                    "sortable": True,
                                },
                                {"key": "status", "label": "状态"},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    store = get_module_data_store()

    try:
        _sync_managed_dataset(module_dir, module_name=module_name, resource_id="accounts")
        rows = [
            {
                "id": str(index),
                "account_id": f"acct-{index:04d}",
                "name": f"account {index}",
                "status": "active",
            }
            for index in range(1, 1006)
        ]
        assert store.replace_resource_records(module_name, "accounts", rows) is True

        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.info_label.text() == "共 1005 条")
        assert table.rowCount() == 20

        table.search_input.setText("account 1005")
        qtbot.waitUntil(lambda: table.info_label.text() == "共 1 条")
        assert table.rowCount() == 1
        assert table.item(0, 0).text() == "acct-1005"
        assert table.item(0, 1).text() == "account 1005"
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_supports_managed_resource_crud_tables(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_page_crud_table_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page, ui_action

            @page(
                name="accounts",
                label="账号管理",
                icon="📋",
                schema={
                    "type": "Page",
                    "title": "账号管理",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {"type": "managed_resource", "resource_id": "accounts"},
                            "crud": {
                                "mode": "handlers",
                                "primary_key": "account_id",
                                "form": {
                                    "create_columns": ["name", "secret"],
                                    "update_columns": ["name", "secret"],
                                },
                                "create_handler": "create_account_from_ui",
                                "update_handler": "update_account_from_ui",
                                "delete_handler": "delete_account_from_ui",
                            },
                            "columns": [
                                {"key": "account_id", "label": "ID", "visible": False},
                                {"key": "name", "label": "账号名", "required": True},
                                {"key": "secret", "label": "密码", "visible": False, "required": True},
                                {"key": "status", "label": "状态", "readonly": True},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="create_account_from_ui")
            def create_account_from_ui(context, payload):
                rows = context.db.from_("accounts").execute()
                next_id = len(rows) + 1
                row = {
                    "account_id": str(next_id),
                    "name": str(payload.get("name") or ""),
                    "secret": str(payload.get("secret") or ""),
                    "status": "active",
                }
                context.db.into("accounts").replace(rows + [row])
                return {"record": row, "created": True}


            @ui_action(name="update_account_from_ui")
            def update_account_from_ui(context, account_id, payload):
                rows = context.db.from_("accounts").execute()
                updated_rows = []
                updated = None
                for row in rows:
                    current = dict(row)
                    if str(current.get("account_id")) == str(account_id):
                        current.update(
                            {
                                "name": str(payload.get("name") or current.get("name") or ""),
                                "secret": str(payload.get("secret") or current.get("secret") or ""),
                            }
                        )
                        updated = dict(current)
                    updated_rows.append(current)
                context.db.into("accounts").replace(updated_rows)
                return {"record": updated, "created": False}


            @ui_action(name="delete_account_from_ui")
            def delete_account_from_ui(context, account_id):
                rows = context.db.from_("accounts").execute()
                remaining = [row for row in rows if str(row.get("account_id")) != str(account_id)]
                deleted = next((row for row in rows if str(row.get("account_id")) == str(account_id)), None)
                context.db.into("accounts").replace(remaining)
                return {"deleted": True, "record": deleted, "account_id": str(account_id)}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理", icon="📋")])
    manifest.data = {
        "resources": [
            {
                "resource_id": "accounts",
                "storage_mode": "managed_dataset",
                "record_key_field": "account_id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "account_id", "type": "text", "required": True},
                    ],
                },
                "indexes": {},
                "cleanup_policy": "delete_rows",
            }
        ],
        "views": [],
        "seeds": [],
    }
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    store = get_module_data_store()
    payloads = iter(
        [
            {"name": "beta", "secret": "secret-beta"},
            {"name": "alpha-updated", "secret": "secret-alpha-2"},
        ]
    )

    monkeypatch.setattr(
        ManagedPageRenderer,
        "_prompt_crud_form_payload",
        lambda self, component, *, mode, row=None: dict(next(payloads)),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.ConfirmDialog.delete_confirm",
        lambda parent, item_name: True,
    )

    try:
        _sync_managed_dataset(module_dir, module_name=module_name, resource_id="accounts")
        assert (
            store.replace_resource_records(
                module_name,
                "accounts",
                [
                    {
                        "account_id": "1",
                        "name": "alpha",
                        "secret": "secret-alpha",
                        "status": "active",
                    }
                ],
            )
            is True
        )

        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 1)

        button_texts = [button.text() for button in page.findChildren(QPushButton)]
        assert "新增" in button_texts
        assert "编辑" in button_texts
        assert "删除" in button_texts
        assert table.columnCount() == 2
        assert table.horizontalHeaderItem(0).text() == "账号名"
        assert table.horizontalHeaderItem(1).text() == "状态"
        assert table.item(0, 0).text() == "alpha"

        add_button = next(button for button in page.findChildren(QPushButton) if button.text() == "新增")
        edit_button = next(button for button in page.findChildren(QPushButton) if button.text() == "编辑")
        delete_button = next(button for button in page.findChildren(QPushButton) if button.text() == "删除")
        assert isinstance(add_button, StyledButton)
        assert isinstance(edit_button, StyledButton)
        assert isinstance(delete_button, StyledButton)
        assert "font-family" in add_button.styleSheet()
        assert "font-family" in edit_button.styleSheet()
        assert "font-family" in delete_button.styleSheet()

        add_button.click()
        qtbot.waitUntil(lambda: table.rowCount() == 2)
        names = {table.item(row, 0).text() for row in range(table.rowCount())}
        assert names == {"alpha", "beta"}

        alpha_row_index = next(
            index for index, row in enumerate(table.displayed_rows()) if str(row.get("name") or "") == "alpha"
        )
        table.selectRow(alpha_row_index)
        edit_button.click()
        qtbot.waitUntil(lambda: any(table.item(row, 0).text() == "alpha-updated" for row in range(table.rowCount())))
        stored_rows = sorted(
            store.query_resource_records(module_name, "accounts", select=["*"]),
            key=lambda row: str(row.get("account_id") or ""),
        )
        assert [
            {
                "account_id": str(row.get("account_id") or ""),
                "name": str(row.get("name") or ""),
                "secret": str(row.get("secret") or ""),
                "status": str(row.get("status") or ""),
            }
            for row in stored_rows
        ] == [
            {
                "account_id": "1",
                "name": "alpha-updated",
                "secret": "secret-alpha-2",
                "status": "active",
            },
            {
                "account_id": "2",
                "name": "beta",
                "secret": "secret-beta",
                "status": "active",
            },
        ]

        beta_row_index = next(
            index for index, row in enumerate(table.displayed_rows()) if str(row.get("name") or "") == "beta"
        )
        table.selectRow(beta_row_index)
        delete_button.click()
        qtbot.waitUntil(lambda: table.rowCount() == 1)
        assert [
            {
                "account_id": str(row.get("account_id") or ""),
                "name": str(row.get("name") or ""),
                "secret": str(row.get("secret") or ""),
                "status": str(row.get("status") or ""),
            }
            for row in store.query_resource_records(module_name, "accounts", select=["*"])
        ] == [
            {
                "account_id": "1",
                "name": "alpha-updated",
                "secret": "secret-alpha-2",
                "status": "active",
            }
        ]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_supports_row_action_crud_tables(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_page_row_action_crud_table_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page, ui_action

            @page(
                name="accounts",
                label="账号管理",
                icon="📋",
                schema={
                    "type": "Page",
                    "title": "账号管理",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {"type": "managed_resource", "resource_id": "accounts"},
                            "crud": {
                                "mode": "handlers",
                                "render": "row_actions",
                                "toolbar": {"create": True},
                                "primary_key": "account_id",
                                "form": {
                                    "create_columns": ["name", "secret"],
                                    "update_columns": ["name", "secret"],
                                },
                                "create_handler": "create_account_from_ui",
                                "update_handler": "update_account_from_ui",
                                "delete_handler": "delete_account_from_ui",
                            },
                            "columns": [
                                {"key": "account_id", "label": "ID", "visible": False},
                                {"key": "name", "label": "账号名", "required": True},
                                {"key": "secret", "label": "密码", "visible": False, "required": True},
                                {"key": "status", "label": "状态", "readonly": True},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="create_account_from_ui")
            def create_account_from_ui(context, payload):
                rows = context.db.from_("accounts").execute()
                next_id = len(rows) + 1
                row = {
                    "account_id": str(next_id),
                    "name": str(payload.get("name") or ""),
                    "secret": str(payload.get("secret") or ""),
                    "status": "active",
                }
                context.db.into("accounts").replace(rows + [row])
                return {"record": row, "created": True}


            @ui_action(name="update_account_from_ui")
            def update_account_from_ui(context, account_id, payload):
                rows = context.db.from_("accounts").execute()
                updated_rows = []
                updated = None
                for row in rows:
                    current = dict(row)
                    if str(current.get("account_id")) == str(account_id):
                        current.update(
                            {
                                "name": str(payload.get("name") or current.get("name") or ""),
                                "secret": str(payload.get("secret") or current.get("secret") or ""),
                            }
                        )
                        updated = dict(current)
                    updated_rows.append(current)
                context.db.into("accounts").replace(updated_rows)
                return {"record": updated, "created": False}


            @ui_action(name="delete_account_from_ui")
            def delete_account_from_ui(context, account_id):
                rows = context.db.from_("accounts").execute()
                remaining = [row for row in rows if str(row.get("account_id")) != str(account_id)]
                deleted = next((row for row in rows if str(row.get("account_id")) == str(account_id)), None)
                context.db.into("accounts").replace(remaining)
                return {"deleted": True, "record": deleted, "account_id": str(account_id)}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理", icon="📋")])
    manifest.data = {
        "resources": [
            {
                "resource_id": "accounts",
                "storage_mode": "managed_dataset",
                "record_key_field": "account_id",
                "schema": {
                    "version": 1,
                    "columns": [
                        {"name": "account_id", "type": "text", "required": True},
                    ],
                },
                "indexes": {},
                "cleanup_policy": "delete_rows",
            }
        ],
        "views": [],
        "seeds": [],
    }
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    store = get_module_data_store()
    payloads = iter(
        [
            {"name": "beta", "secret": "secret-beta"},
            {"name": "alpha-updated", "secret": "secret-alpha-2"},
        ]
    )

    monkeypatch.setattr(
        ManagedPageRenderer,
        "_prompt_crud_form_payload",
        lambda self, component, *, mode, row=None: dict(next(payloads)),
    )
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.ConfirmDialog.delete_confirm",
        lambda parent, item_name: True,
    )

    try:
        _sync_managed_dataset(module_dir, module_name=module_name, resource_id="accounts")
        assert (
            store.replace_resource_records(
                module_name,
                "accounts",
                [
                    {
                        "account_id": "1",
                        "name": "alpha",
                        "secret": "secret-alpha",
                        "status": "active",
                    }
                ],
            )
            is True
        )

        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 1)

        assert table.columnCount() == 3
        assert table.horizontalHeaderItem(0).text() == "账号名"
        assert table.horizontalHeaderItem(1).text() == "状态"
        assert table.horizontalHeaderItem(2).text() == "操作"
        assert table.item(0, 0).text() == "alpha"
        toolbar_button_texts = []
        for index in range(table._toolbar.count()):
            item = table._toolbar.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                toolbar_button_texts.append(widget.text())
        assert toolbar_button_texts == ["新增"]

        add_button = next(button for button in page.findChildren(QPushButton) if button.text() == "新增")
        add_button.click()
        qtbot.waitUntil(lambda: table.rowCount() == 2)

        action_cell = table.cellWidget(0, 2)
        assert action_cell is not None
        action_texts = [button.text() for button in action_cell.findChildren(QPushButton)]
        assert action_texts == ["编辑", "删除"]

        edit_button = next(button for button in action_cell.findChildren(QPushButton) if button.text() == "编辑")
        edit_button.click()
        qtbot.waitUntil(lambda: any(table.item(row, 0).text() == "alpha-updated" for row in range(table.rowCount())))

        beta_row_index = next(
            index for index, row in enumerate(table.displayed_rows()) if str(row.get("name") or "") == "beta"
        )
        delete_button = next(
            button
            for button in table.cellWidget(beta_row_index, 2).findChildren(QPushButton)
            if button.text() == "删除"
        )
        delete_button.click()
        qtbot.waitUntil(lambda: table.rowCount() == 1)

        assert [
            {
                "account_id": str(row.get("account_id") or ""),
                "name": str(row.get("name") or ""),
                "secret": str(row.get("secret") or ""),
                "status": str(row.get("status") or ""),
            }
            for row in store.query_resource_records(module_name, "accounts", select=["*"])
        ] == [
            {
                "account_id": "1",
                "name": "alpha-updated",
                "secret": "secret-alpha-2",
                "status": "active",
            }
        ]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_localizes_and_styles_crud_dialog(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_page_crud_dialog_style_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page

            @page(
                name="accounts",
                label="账号管理",
                icon="📋",
                schema={
                    "type": "Page",
                    "title": "账号管理",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号管理",
                            "data_source": {"type": "rows", "rows": []},
                            "crud": {
                                "mode": "handlers",
                                "primary_key": "account_id",
                                "form": {
                                    "create_columns": ["name", "secret"],
                                },
                                "create_handler": "create_account_from_ui",
                            },
                            "columns": [
                                {"key": "account_id", "label": "ID", "visible": False},
                                {"key": "name", "label": "账号名", "required": True},
                                {"key": "secret", "label": "密码", "required": True},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理", icon="📋")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    observed: dict[str, object] = {}

    def _fake_exec(dialog: QDialog) -> int:
        observed["title"] = dialog.windowTitle()
        observed["button_texts"] = [button.text() for button in dialog.findChildren(QPushButton)]
        observed["stylesheet"] = dialog.styleSheet()
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(QDialog, "exec", _fake_exec)

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        component = page._schema["children"][0]
        payload = page._prompt_crud_form_payload(component, mode="create")

        assert payload is None
        assert observed["title"] == "新增账号管理"
        assert "取消" in observed["button_texts"]
        assert "确认" in observed["button_texts"]
        assert "#1e1e2e" in observed["stylesheet"]
        assert "QLabel" in observed["stylesheet"]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_scopes_load_and_query_handlers_to_readonly_tools(qtbot, tmp_path):
    module_name = "hosted_page_readonly_tools_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import HostedDataTableQuery, HostedDataTableQueryResult, TaskContext, page

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {"type": "Text", "style": "body", "binding": "load_tools"},
                        {"type": "Text", "style": "body", "binding": "load_write_error"},
                        {
                            "type": "DataTable",
                            "table_id": "stats",
                            "title": "统计明细",
                            "data_source": {"type": "query_handler", "handler": "query_stats_table"},
                            "columns": [
                                {"key": "metric", "label": "指标", "searchable": True},
                                {"key": "value", "label": "值"},
                            ],
                        },
                    ],
                },
            )
            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del page_id, params
                load_tools = ",".join(spec.name for spec in context.tools.list_tools())
                try:
                    context.db.into("hosted_ui_load").replace([])
                except Exception as exc:
                    load_write_error = type(exc).__name__
                return {
                    "load_tools": load_tools,
                    "load_write_error": load_write_error,
                }


            def query_stats_table(context: TaskContext, query: HostedDataTableQuery):
                query_tools = ",".join(spec.name for spec in context.tools.list_tools())
                try:
                    context.db.into("hosted_ui_query").replace([])
                except Exception as exc:
                    query_write_error = type(exc).__name__
                return HostedDataTableQueryResult(
                    rows=[
                        {"metric": "query_tools", "value": query_tools},
                        {"metric": "query_write_error", "value": query_write_error},
                        {"metric": "query_type", "value": type(query).__name__},
                        {"metric": "query_search_fields", "value": ",".join(query.search_fields)},
                        {"metric": "query_sort", "value": ",".join(item.field for item in query.sort)},
                    ],
                    total=5,
                    page=query.page,
                    page_size=query.page_size,
                )
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "dashboard", module_info=module_info)
        qtbot.addWidget(page)

        readonly_tools = "ui.get_page"
        assert any(label.text() == readonly_tools for label in page.findChildren(QLabel))
        assert any(label.text() == "RuntimeError" for label in page.findChildren(QLabel))

        table = page._data_table_widgets["stats"]
        qtbot.waitUntil(lambda: table.item(1, 1) is not None)

        assert table.item(0, 0).text() == "query_tools"
        assert table.item(0, 1).text() == readonly_tools
        assert table.item(1, 0).text() == "query_write_error"
        assert table.item(1, 1).text() == "RuntimeError"
        assert table.item(2, 0).text() == "query_type"
        assert table.item(2, 1).text() == "HostedDataTableQuery"
        assert table.item(3, 0).text() == "query_search_fields"
        assert table.item(3, 1).text() == "metric"
        assert table.item(4, 0).text() == "query_sort"
        assert table.item(4, 1).text() == ""

        component = page._schema["children"][2]
        assert (
            page._normalize_table_query_for_handler(
                component,
                {"sort": [{"field": "metric", "direction": "asc"}]},
            )["sort"]
            == []
        )

        sortable_component = dict(component)
        sortable_component["columns"] = [
            {**dict(component["columns"][0]), "sortable": True},
            dict(component["columns"][1]),
        ]
        assert page._normalize_table_query_for_handler(
            sortable_component,
            {"sort": [{"field": "metric", "direction": "asc"}]},
        )["sort"] == [{"field": "metric", "direction": "asc"}]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_row_action_opens_page_with_row_params(qtbot, tmp_path):
    module_name = "hosted_page_row_action_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import page

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号总览",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "status", "label": "状态"},
                            ],
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
                return {
                    "rows": [
                        {"account_id": "acct-001", "status": "active"},
                        {"account_id": "acct-002", "status": "blocked"},
                    ],
                }
            """,
            "pages/details.py": """
            from crawler4j_contracts import page

            @page(
                name="details",
                label="Details",
                schema={
                    "type": "Page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )
            def load_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", {"account_id": "acct-002"})]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_row_action_without_params_does_not_forward_row_payload(qtbot, tmp_path):
    module_name = "hosted_page_no_row_params_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import page

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "title": "账号总览",
                            "data_source": {"type": "binding", "binding": "rows"},
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "status", "label": "状态"},
                            ],
                            "row_action": {
                                "type": "open_page",
                                "page_id": "details",
                            },
                        },
                    ],
                },
            )
            def load_dashboard_page(context, page_id, params=None):
                del context, page_id, params
                return {
                    "rows": [
                        {"account_id": "acct-001", "status": "active"},
                        {"account_id": "acct-002", "status": "blocked"},
                    ],
                }
            """,
            "pages/details.py": """
            from crawler4j_contracts import page

            @page(
                name="details",
                label="Details",
                schema={
                    "type": "Page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )
            def load_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    calls: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: calls.append((page_id, params)),
        )
        qtbot.addWidget(page)

        page._data_table_widgets["accounts"].cellClicked.emit(1, 0)
        assert calls == [("details", None)]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_supports_navigation_params_and_button_actions(qtbot, tmp_path):
    module_name = "hosted_page_navigation_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import page

            @page(
                name="dashboard",
                label="Dashboard",
                schema={
                    "type": "Page",
                    "children": [
                        {"type": "Text", "style": "body", "binding": "selected_phone"},
                        {
                            "type": "Button",
                            "label": "打开详情页",
                            "action": {
                                "type": "open_page",
                                "page_id": "account_details",
                                "params": {
                                    "phone": {"binding": "selected.phone"},
                                    "source": {"value": "dashboard"},
                                },
                            },
                        },
                    ],
                },
            )
            def load_dashboard_page(context, page_id, params=None):
                del context, page_id
                selected_phone = "none"
                params_state = "none" if params is None else "dict"
                if isinstance(params, dict):
                    selected_phone = str(params.get("phone") or "none")
                return {
                    "selected_phone": f"params:{params_state}|selected:{selected_phone}",
                    "selected": {"phone": selected_phone},
                }
            """,
            "pages/account_details.py": """
            from crawler4j_contracts import page

            @page(
                name="account_details",
                label="Account Details",
                schema={
                    "type": "Page",
                    "children": [{"type": "Text", "binding": "title"}],
                },
            )
            def load_account_details_page(context, page_id, params=None):
                del context, page_id, params
                return {"title": "详情页"}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard"), make_page_info("account_details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "dashboard",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
            initial_params={"phone": "13800138000"},
        )
        qtbot.addWidget(page)

        assert any(label.text() == "params:dict|selected:13800138000" for label in page.findChildren(QLabel))

        open_button = next(button for button in page.findChildren(QPushButton) if button.text() == "打开详情页")
        open_button.click()

        assert opened_pages == [("account_details", {"phone": "13800138000", "source": "dashboard"})]
    finally:
        restore_module(service, original_registry, module_name)
