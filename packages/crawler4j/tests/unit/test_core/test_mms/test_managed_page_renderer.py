from __future__ import annotations

import asyncio
import builtins
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from PyQt6.QtCore import QItemSelectionModel, QPoint, QRect, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
)

from src.core.mms.ui.managed_page_renderer import (
    CRUD_ROW_ACTION_DELETE,
    CRUD_ROW_ACTION_EDIT,
    ManagedPageRenderer,
)
from src.core.mms.ui.hosted_form import FORM_EVENT_STALE, FORM_HANDLE_REJECTED, FORM_SCOPE_UNAVAILABLE
from src.core.persistence import get_module_data_store
from src.ui.components.button import StyledButton
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


@pytest.fixture
def bulk_update_page(qtbot, tmp_path):
    module_name = "hosted_page_bulk_update_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/accounts.py": """
            from crawler4j_contracts import page, ui_action

            ROWS = [
                {"account_id": 7, "name": "alpha", "note": "first"},
                {"account_id": "7", "name": "beta", "note": "second"},
                {"account_id": 7, "name": "duplicate", "note": "third"},
                {"name": "missing", "note": "fourth"},
            ]
            COLUMNS = [
                {"key": "account_id", "label": "ID"},
                {"key": "name", "label": "名称"},
                {"key": "note", "label": "备注"},
            ]
            CRUD = {
                "mode": "handlers",
                "primary_key": "account_id",
                "form": {"update_columns": ["name", "note"]},
                "update_handler": "update_account_from_ui",
                "delete_handler": "delete_account_from_ui",
                "bulk_update_handler": "bulk_update_accounts_from_ui",
            }

            @page(
                name="accounts",
                label="账号管理",
                schema={
                    "type": "Page",
                    "children": [
                        {
                            "type": "DataTable",
                            "table_id": "accounts",
                            "selection_mode": "multi",
                            "data_source": {"type": "rows", "rows": ROWS},
                            "crud": CRUD,
                            "columns": COLUMNS,
                        },
                        {
                            "type": "DataTable",
                            "table_id": "row_accounts",
                            "selection_mode": "multi",
                            "data_source": {"type": "rows", "rows": ROWS},
                            "crud": {**CRUD, "render": "row_actions"},
                            "columns": COLUMNS,
                        },
                        {
                            "type": "DataTable",
                            "table_id": "hidden_bulk_accounts",
                            "selection_mode": "multi",
                            "data_source": {"type": "rows", "rows": ROWS},
                            "crud": {**CRUD, "toolbar": {"bulk_update": False}},
                            "columns": COLUMNS,
                        },
                        {
                            "type": "DataTable",
                            "table_id": "default_selection",
                            "data_source": {"type": "rows", "rows": ROWS[:1]},
                            "columns": COLUMNS,
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="bulk_update_accounts_from_ui")
            def bulk_update_accounts_from_ui(context, primary_keys, payload):
                del context, primary_keys, payload
                return {"ok": True}


            @ui_action(name="update_account_from_ui")
            def update_account_from_ui(context, account_id, payload):
                del context, account_id, payload
                return {"ok": True}


            @ui_action(name="delete_account_from_ui")
            def delete_account_from_ui(context, account_id):
                del context, account_id
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)
        for table in page._data_table_widgets.values():
            qtbot.waitUntil(lambda current=table: current.rowCount() > 0)

        yield page
    finally:
        restore_module(service, original_registry, module_name)


def _select_rows(table, *row_indexes: int) -> None:
    selection_model = table.table.selectionModel()
    selection_model.clearSelection()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for row_index in row_indexes:
        selection_model.select(table.table.model().index(row_index, 0), flags)


def _toolbar_buttons(table) -> dict[str, QPushButton]:
    buttons: dict[str, QPushButton] = {}
    for index in range(table._toolbar.count()):
        item = table._toolbar.itemAt(index)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QPushButton):
            buttons[widget.text()] = widget
    return buttons


def _field_change_component() -> dict:
    return {
        "type": "DataTable",
        "table_id": "accounts",
        "title": "账号",
        "columns": [
            {
                "key": "preset",
                "label": "模板",
                "type": "select",
                "required": True,
                "options": ["basic", "advanced", "final"],
                "on_change": {"type": "ui_action", "name": "handle_field_change"},
            },
            {"key": "priority", "label": "优先级", "type": "int"},
            {"key": "enabled", "label": "启用", "type": "bool"},
            {"key": "note", "label": "备注", "type": "text"},
            {"key": "marker", "label": "标记", "type": "text"},
            {
                "key": "untouched",
                "label": "无事件字段",
                "type": "select",
                "options": ["one", "two"],
            },
        ],
        "crud": {
            "primary_key": "id",
            "form": {
                "create_columns": ["preset", "priority", "enabled", "note", "marker", "untouched"],
                "update_columns": ["preset", "priority", "enabled", "note", "marker", "untouched"],
                "layout": {"columns": 3, "gap": 12},
            },
            "create_handler": "create_account",
            "update_handler": "update_account",
        },
    }


def _field_change_row() -> dict:
    return {
        "id": "a1",
        "preset": "basic",
        "priority": 1,
        "enabled": True,
        "note": "old",
        "marker": "value",
        "untouched": "one",
    }


def test_managed_page_renderer_bulk_toolbar_and_selection_rules(bulk_update_page):
    page = bulk_update_page
    table = page._data_table_widgets["accounts"]
    row_table = page._data_table_widgets["row_accounts"]
    hidden_table = page._data_table_widgets["hidden_bulk_accounts"]
    default_table = page._data_table_widgets["default_selection"]

    assert table.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert row_table.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert default_table.table.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection

    buttons = _toolbar_buttons(table)
    assert set(buttons) == {"编辑", "删除", "批量编辑"}
    assert set(_toolbar_buttons(row_table)) == {"批量编辑"}
    assert "批量编辑" not in _toolbar_buttons(hidden_table)

    assert buttons["编辑"].isEnabled() is False
    assert buttons["删除"].isEnabled() is False
    assert buttons["批量编辑"].isEnabled() is False

    _select_rows(table, 0)
    assert buttons["编辑"].isEnabled() is True
    assert buttons["删除"].isEnabled() is True
    assert buttons["批量编辑"].isEnabled() is True

    _select_rows(table, 0, 1)
    assert buttons["编辑"].isEnabled() is False
    assert buttons["删除"].isEnabled() is False
    assert buttons["批量编辑"].isEnabled() is True

    _select_rows(table)
    assert all(button.isEnabled() is False for button in buttons.values())


def test_managed_page_renderer_single_crud_guards_multi_select_and_row_actions_use_clicked_row(
    bulk_update_page,
    monkeypatch,
):
    page = bulk_update_page
    table = page._data_table_widgets["accounts"]
    row_table = page._data_table_widgets["row_accounts"]
    components = {component["table_id"]: component for component in page._schema["children"]}
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        page._bridge,
        "call_ui_action",
        lambda action_name, params, **_kwargs: calls.append((action_name, dict(params))) or {"ok": True},
    )
    monkeypatch.setattr(
        page,
        "_prompt_crud_form_payload",
        lambda component, *, mode, row=None: {"name": "changed", "note": None},
    )
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.ConfirmDialog.delete_confirm",
        lambda parent, item_name: True,
    )

    _select_rows(table, 0, 1)
    page._handle_update_action(components["accounts"], table)
    page._handle_delete_action(components["accounts"], table)
    assert calls == []

    _select_rows(row_table, 0, 1)
    clicked_row = row_table.displayed_rows()[1]
    page._handle_table_row_action(
        components["row_accounts"],
        row_table,
        CRUD_ROW_ACTION_EDIT,
        clicked_row,
    )
    page._handle_table_row_action(
        components["row_accounts"],
        row_table,
        CRUD_ROW_ACTION_DELETE,
        clicked_row,
    )

    assert calls == [
        (
            "update_account_from_ui",
            {"account_id": "7", "payload": {"name": "changed", "note": None}},
        ),
        ("delete_account_from_ui", {"account_id": "7"}),
    ]


def test_managed_page_renderer_bulk_update_sync_payload_refresh_and_failures(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    page = bulk_update_page
    table = page._data_table_widgets["accounts"]
    component = next(component for component in page._schema["children"] if component["table_id"] == "accounts")

    dialog, widgets = page._build_crud_form_dialog(component, mode="update", row=None)
    qtbot.addWidget(dialog)
    assert [widget.text() for widget, _column in widgets.values() if isinstance(widget, StyledLineEdit)] == ["", ""]
    blank_payload, error = page._collect_crud_form_payload(widgets)
    assert error is None
    assert blank_payload == {"name": None, "note": None}

    prompts = [blank_payload, {"name": "explode", "note": None}]
    monkeypatch.setattr(
        page,
        "_prompt_crud_form_payload",
        lambda component, *, mode, row=None: dict(prompts.pop(0)),
    )
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(page, "_show_warning", lambda title, message: warnings.append((title, message)))
    calls: list[tuple[str, dict]] = []

    def call_ui_action(action_name, params, **_kwargs):
        calls.append((action_name, dict(params)))
        if params["payload"].get("name") == "explode":
            raise RuntimeError("bulk exploded")
        return {"ok": True}

    monkeypatch.setattr(page._bridge, "call_ui_action", call_ui_action)
    refreshes: list[dict] = []
    table.query_requested.connect(lambda _request_id, query: refreshes.append(dict(query)))

    _select_rows(table, 0, 1, 2)
    page._handle_bulk_update_action(component, table)

    assert warnings == []
    assert calls == [
        (
            "bulk_update_accounts_from_ui",
            {"primary_keys": [7, "7"], "payload": {"name": None, "note": None}},
        )
    ]
    assert table.selected_rows() == []
    assert len(refreshes) == 1

    _select_rows(table, 0, 3)
    page._handle_bulk_update_action(component, table)
    assert len(calls) == 1
    assert len(refreshes) == 1
    assert table.selected_rows() == [table.displayed_rows()[0], table.displayed_rows()[3]]
    assert warnings == [("批量编辑失败", "当前记录缺少主键字段: account_id")]

    _select_rows(table, 0)
    page._handle_bulk_update_action(component, table)
    assert calls[-1] == (
        "bulk_update_accounts_from_ui",
        {"primary_keys": [7], "payload": {"name": "explode", "note": None}},
    )
    assert table.selected_rows() == [table.displayed_rows()[0]]
    assert len(refreshes) == 1
    assert warnings[-1] == ("批量编辑失败", "bulk exploded")


@pytest.mark.asyncio
async def test_managed_page_renderer_bulk_update_async_uses_non_blocking_dialog_and_matches_failures(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    page = bulk_update_page
    table = page._data_table_widgets["accounts"]
    component = next(component for component in page._schema["children"] if component["table_id"] == "accounts")
    values = iter(["async value", "explode"])

    def fail_exec(self):
        raise AssertionError("blocking exec should not be used in async bulk update flow")

    def fake_show(dialog: QDialog):
        qtbot.addWidget(dialog)
        edits = dialog.findChildren(StyledLineEdit)
        assert len(edits) == 2
        edits[0].setText(next(values))
        edits[1].clear()
        asyncio.get_running_loop().call_soon(lambda: dialog.done(int(QDialog.DialogCode.Accepted)))

    monkeypatch.setattr(QDialog, "exec", fail_exec)
    monkeypatch.setattr(QDialog, "show", fake_show)
    warning = AsyncMock()
    monkeypatch.setattr(page, "_show_warning_async", warning)
    calls: list[tuple[str, dict]] = []

    async def call_ui_action_async(action_name, params, **_kwargs):
        calls.append((action_name, dict(params)))
        if params["payload"].get("name") == "explode":
            raise RuntimeError("bulk exploded")
        return {"ok": True}

    monkeypatch.setattr(page._bridge, "call_ui_action_async", call_ui_action_async)
    refreshes: list[dict] = []
    table.query_requested.connect(lambda _request_id, query: refreshes.append(dict(query)))

    _select_rows(table, 0, 1)
    page._handle_bulk_update_action(component, table)
    for _ in range(50):
        if calls and refreshes:
            break
        await asyncio.sleep(0.01)
    assert calls == [
        (
            "bulk_update_accounts_from_ui",
            {"primary_keys": [7, "7"], "payload": {"name": "async value", "note": None}},
        )
    ]
    assert table.selected_rows() == []
    assert len(refreshes) == 1

    _select_rows(table, 0)
    await page._handle_bulk_update_action_async(component, table)
    assert calls[-1] == (
        "bulk_update_accounts_from_ui",
        {"primary_keys": [7], "payload": {"name": "explode", "note": None}},
    )
    assert table.selected_rows() == [table.displayed_rows()[0]]
    assert len(refreshes) == 1
    warning.assert_awaited_once_with("批量编辑失败", "bulk exploded")


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


def test_managed_page_renderer_dispatches_table_toolbar_import_to_ui_action(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_table_toolbar_import_module"
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
                            "columns": [
                                {"key": "phone", "label": "手机号"},
                                {"key": "name", "label": "姓名"},
                            ],
                            "toolbar": {
                                "actions": [
                                    {
                                        "id": "import_accounts",
                                        "label": "导入账号",
                                        "icon": "upload",
                                        "action": {
                                            "type": "open_import_dialog",
                                            "target_type": "ctrip_account",
                                            "business_key_field": "phone",
                                            "submit": {"type": "ui_action", "name": "import_accounts"},
                                        },
                                    }
                                ]
                            },
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="import_accounts")
            async def import_accounts(context, import_payload: dict):
                del context
                CALLS.append(import_payload)
                return {
                    "batch_id": "imp-001",
                    "total_rows": len(import_payload["rows"]),
                    "staged_rows": 1,
                    "failed_rows": 0,
                    "target_type": "ctrip_account",
                    "records_page_id": "import_data_records",
                }
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []
    import_payload = {
        "source_type": "clipboard",
        "source_name": "clipboard",
        "target_type": "ctrip_account",
        "rows": [
            {
                "source_row_no": 2,
                "business_key": "13800000000",
                "payload": {"phone": "13800000000", "name": "Alice"},
                "raw_payload": {"phone": "13800000000", "name": "Alice"},
            }
        ],
    }

    monkeypatch.setattr(
        ManagedPageRenderer,
        "_prompt_import_payload",
        lambda self, action: import_payload,
    )
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.ChoiceDialog.choose",
        lambda *_args, **_kwargs: "records",
    )

    try:
        page = ManagedPageRenderer(
            module_name,
            "accounts",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
        )
        qtbot.addWidget(page)

        import_button = next(button for button in page.findChildren(QPushButton) if "导入账号" in button.text())
        import_button.click()

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert actions_module.CALLS == [import_payload]
        assert opened_pages == [
            (
                "import_data_records",
                {"batch_id": "imp-001", "target_type": "ctrip_account"},
            )
        ]
    finally:
        restore_module(service, original_registry, module_name)


@pytest.mark.asyncio
async def test_managed_page_renderer_dispatches_import_payload_to_workflow_job(qtbot, tmp_path, monkeypatch):
    module_name = "hosted_toolbar_workflow_import_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "workflows/import_accounts.py": """
            from crawler4j_contracts import workflow

            @workflow(name="import_accounts")
            class ImportAccounts:
                pass
            """,
            "pages/accounts.py": """
            from crawler4j_contracts import page

            @page(
                name="accounts",
                label="账号管理",
                schema={
                    "type": "Page",
                    "toolbar": {
                        "actions": [
                            {
                                "id": "import_accounts",
                                "label": "后台导入",
                                "action": {
                                    "type": "open_import_dialog",
                                    "target_type": "ctrip_account",
                                    "submit": {"type": "workflow", "name": "import_accounts"},
                                },
                            }
                        ]
                    },
                    "children": [],
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
    import_payload = {
        "source_type": "clipboard",
        "source_name": "clipboard",
        "target_type": "ctrip_account",
        "rows": [],
    }
    task_service = type(
        "FakeTaskService",
        (),
        {
            "create_job": AsyncMock(return_value="job-import"),
            "start_job": AsyncMock(return_value=True),
        },
    )()
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        ManagedPageRenderer,
        "_prompt_import_payload_async",
        AsyncMock(return_value=import_payload),
    )
    monkeypatch.setattr("src.core.mms.ui.managed_page_renderer.get_task_service", lambda: task_service)
    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.MessageDialog.information_async",
        AsyncMock(side_effect=lambda _parent, title, message, **_kwargs: messages.append((title, message)) or 0),
    )

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)
        toolbar_action = page._schema["toolbar"]["actions"][0]

        await page._handle_toolbar_action_async(toolbar_action)

        task_service.create_job.assert_awaited_once()
        kwargs = task_service.create_job.await_args.kwargs
        assert kwargs["name"] == "Hosted UI 导入/hosted_toolbar_workflow_import_module/import_accounts"
        run_profile = kwargs["run_profile"]
        assert run_profile.execution.module == module_name
        assert run_profile.execution.workflow == "import_accounts"
        assert run_profile.resource.acquisition.creation.params["import_payload"] == import_payload
        task_service.start_job.assert_awaited_once_with("job-import")
        assert messages == [("后台导入已启动", "已创建并启动导入任务: job-import")]
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


def test_managed_page_renderer_dispatches_custom_row_action_to_ui_action(qtbot, tmp_path):
    module_name = "hosted_page_custom_row_action_module"
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
                                "rows": [
                                    {
                                        "phone": "13800138000",
                                        "name": "alpha",
                                        "actions": [
                                            {"id": "verify_phone", "label": "验证"},
                                        ],
                                    },
                                ],
                            },
                            "crud": {
                                "mode": "handlers",
                                "render": "row_actions",
                                "primary_key": "phone",
                                "form": {"update_columns": ["name"]},
                                "update_handler": "update_account_from_ui",
                                "delete_handler": "delete_account_from_ui",
                            },
                            "columns": [
                                {"key": "phone", "label": "手机号"},
                                {"key": "name", "label": "账号名"},
                                {"key": "actions", "label": "操作", "type": "actions"},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="verify_phone")
            def verify_phone(context, phone):
                del context
                CALLS.append({"phone": phone})
                return {"ok": True}


            @ui_action(name="update_account_from_ui")
            def update_account_from_ui(context, phone, payload):
                del context, phone, payload
                return {"ok": True}


            @ui_action(name="delete_account_from_ui")
            def delete_account_from_ui(context, phone):
                del context, phone
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 1)
        action_cell = table.cellWidget(0, 2)
        assert action_cell is not None
        action_texts = [button.text() for button in action_cell.findChildren(QPushButton)]
        assert action_texts == ["验证", "编辑", "删除"]

        verify_button = next(button for button in action_cell.findChildren(QPushButton) if button.text() == "验证")
        verify_button.click()

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert actions_module.CALLS == [{"phone": "13800138000"}]
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_row_button_opens_page_with_clicked_row_params(qtbot, tmp_path):
    module_name = "hosted_page_row_button_navigation_module"
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
                            "data_source": {
                                "type": "rows",
                                "rows": [
                                    {
                                        "account_id": "acct-001",
                                        "actions": [
                                            {
                                                "id": "open_details",
                                                "label": "详情",
                                                "type": "open_page",
                                                "page_id": "details",
                                                "params": {
                                                    "account_id": {"binding": "account_id"},
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "account_id": "acct-002",
                                        "actions": [
                                            {
                                                "id": "open_details",
                                                "label": "详情",
                                                "type": "open_page",
                                                "page_id": "details",
                                                "params": {
                                                    "account_id": {"binding": "account_id"},
                                                },
                                            },
                                        ],
                                    },
                                ],
                            },
                            "columns": [
                                {"key": "account_id", "label": "账号"},
                                {"key": "actions", "label": "操作", "type": "actions"},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="open_details")
            def open_details(context, account_id):
                del context
                CALLS.append({"account_id": account_id})
                return {"ok": True}
            """,
            "pages/details.py": """
            from crawler4j_contracts import page

            @page(
                name="details",
                label="详情",
                schema={"type": "Page", "children": []},
            )
            def load_details_page(context, page_id, params=None):
                del context, page_id, params
                return {}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts"), make_page_info("details")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)
    opened_pages: list[tuple[str, dict[str, object] | None]] = []

    try:
        page = ManagedPageRenderer(
            module_name,
            "accounts",
            module_info=module_info,
            open_page_callback=lambda page_id, params=None: opened_pages.append((page_id, params)),
        )
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 2)
        refresh_requests: list[dict[str, object]] = []
        table.query_requested.connect(lambda _request_id, query: refresh_requests.append(dict(query)))

        action_cell = table.cellWidget(1, 1)
        assert action_cell is not None
        details_button = next(button for button in action_cell.findChildren(QPushButton) if button.text() == "详情")
        details_button.click()

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert opened_pages == [("details", {"account_id": "acct-002"})]
        assert actions_module.CALLS == []
        assert refresh_requests == []
    finally:
        restore_module(service, original_registry, module_name)


def test_managed_page_renderer_dispatches_non_crud_row_action_params_to_ui_action(qtbot, tmp_path):
    module_name = "hosted_page_non_crud_release_action_module"
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
                                "rows": [
                                    {
                                        "phone": "13800138000",
                                        "run_status": "占用中",
                                        "actions": [
                                            {
                                                "id": "release_account",
                                                "label": "释放",
                                                "params": {"phone": {"binding": "phone"}},
                                            },
                                        ],
                                    },
                                ],
                            },
                            "columns": [
                                {"key": "phone", "label": "手机号"},
                                {"key": "run_status", "label": "占用状态"},
                                {"key": "actions", "label": "操作", "type": "actions"},
                            ],
                        },
                    ],
                },
            )
            def load_accounts_page(context, page_id, params=None):
                del context, page_id, params
                return {}


            @ui_action(name="release_account")
            def release_account(context, phone):
                del context
                CALLS.append({"phone": phone})
                return {"ok": True}
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("accounts", label="账号管理")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "accounts", module_info=module_info)
        qtbot.addWidget(page)

        table = page._data_table_widgets["accounts"]
        qtbot.waitUntil(lambda: table.rowCount() == 1)
        action_cell = table.cellWidget(0, 2)
        assert action_cell is not None
        release_button = next(button for button in action_cell.findChildren(QPushButton) if button.text() == "释放")
        release_button.click()

        import importlib

        actions_module = importlib.import_module(f"{module_name}.pages.accounts")
        assert actions_module.CALLS == [{"phone": "13800138000"}]
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

        page.set_navigation_params(
            {
                "account_id": "acct-001",
                "record_status": "from_navigation",
            },
            auto_refresh=False,
        )
        normalized_query = page._normalize_table_query_for_handler(
            sortable_component,
            {
                "params": {"record_status": "黑号"},
                "sort": [{"field": "metric", "direction": "asc"}],
            },
        )
        assert normalized_query["params"] == {
            "account_id": "acct-001",
            "record_status": "黑号",
        }
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


def test_crud_form_create_uses_exact_defaults_and_update_prefers_row(bulk_update_page, qtbot):
    page = bulk_update_page
    component = _field_change_component()
    defaults = {
        "preset": "final",
        "priority": 0,
        "enabled": False,
        "note": "",
        "marker": "undefined",
        "untouched": "two",
    }
    for column in component["columns"]:
        column["default"] = defaults[column["key"]]

    create_dialog, create_widgets = page._build_crud_form_dialog(component, mode="create")
    qtbot.addWidget(create_dialog)
    create_controller = create_dialog._hosted_form_controller
    assert create_controller.values == defaults
    assert create_widgets["preset"][0].currentData() == "final"
    assert create_widgets["priority"][0].text() == "0"
    assert create_widgets["enabled"][0].currentData() is False
    assert create_widgets["note"][0].text() == ""
    assert create_widgets["marker"][0].text() == "undefined"
    create_payload, create_error = page._collect_crud_form_payload(create_widgets)
    assert create_error is None
    assert create_payload == defaults

    update_row = {
        "id": "a1",
        "preset": "basic",
        "priority": 9,
        "enabled": True,
        "note": "row",
        "marker": "row-marker",
        "untouched": "one",
    }
    update_dialog, update_widgets = page._build_crud_form_dialog(component, mode="update", row=update_row)
    qtbot.addWidget(update_dialog)
    assert update_dialog._hosted_form_controller.values == {
        field: update_row[field] for field in defaults
    }
    assert update_widgets["preset"][0].currentData() == "basic"
    assert update_widgets["priority"][0].text() == "9"
    assert update_widgets["enabled"][0].currentData() is True
    assert update_widgets["note"][0].text() == "row"
    assert update_widgets["marker"][0].text() == "row-marker"


def test_crud_form_without_layout_stays_single_column(bulk_update_page, qtbot):
    page = bulk_update_page
    component = _field_change_component()
    component["crud"]["form"].pop("layout")

    dialog, widgets = page._build_crud_form_dialog(component, mode="create")
    qtbot.addWidget(dialog)
    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    grid = scroll.widget().layout()

    assert isinstance(grid, QGridLayout)
    assert dialog._hosted_form_layout_columns == 1
    assert len(widgets) == 6
    assert grid.count() == 12
    assert [grid.getItemPosition(index)[1] for index in range(grid.count())] == [0, 1] * 6


def test_crud_form_grid_uses_shared_label_and_input_physical_columns(bulk_update_page, qtbot):
    page = bulk_update_page
    component = _field_change_component()

    dialog, widgets = page._build_crud_form_dialog(component, mode="create")
    qtbot.addWidget(dialog)
    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    grid = scroll.widget().layout()

    assert isinstance(grid, QGridLayout)
    assert grid.count() == len(widgets) * 2
    assert not any(
        isinstance(grid.itemAt(index).widget().layout(), QFormLayout)
        for index in range(grid.count())
    )

    field_names = list(component["crud"]["form"]["create_columns"])
    for field_index, field_name in enumerate(field_names):
        row = field_index // 3
        label_column = (field_index % 3) * 2
        input_column = label_column + 1
        label_widget = grid.itemAtPosition(row, label_column).widget()
        input_widget = grid.itemAtPosition(row, input_column).widget()

        assert isinstance(label_widget, QLabel)
        assert label_widget.text().endswith("：")
        assert label_widget.alignment() & Qt.AlignmentFlag.AlignRight
        assert label_widget.alignment() & Qt.AlignmentFlag.AlignVCenter
        assert input_widget is widgets[field_name][0]
        assert input_widget.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    assert [grid.columnStretch(index) for index in range(6)] == [0, 1, 0, 1, 0, 1]


def test_crud_form_shared_columns_align_labels_and_inputs_across_rows(bulk_update_page, qtbot):
    page = bulk_update_page
    dialog, _widgets = page._build_crud_form_dialog(
        _field_change_component(),
        mode="create",
    )
    qtbot.addWidget(dialog)
    dialog.resize(dialog.minimumWidth(), min(520, dialog.maximumHeight()))
    dialog.show()
    qtbot.wait(20)

    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    grid = scroll.widget().layout()

    for label_column, input_column in ((0, 1), (2, 3), (4, 5)):
        first_label = grid.itemAtPosition(0, label_column).widget()
        second_label = grid.itemAtPosition(1, label_column).widget()
        first_input = grid.itemAtPosition(0, input_column).widget()
        second_input = grid.itemAtPosition(1, input_column).widget()

        assert first_label.geometry().right() == second_label.geometry().right()
        assert first_input.geometry().left() == second_input.geometry().left()


def test_crud_form_many_fields_are_scrollable_with_hidden_scrollbars_and_visible_action_row(
    bulk_update_page,
    qtbot,
):
    page = bulk_update_page
    columns = [
        {"key": f"field_{index}", "label": f"字段 {index}", "type": "text", "default": f"value-{index}"}
        for index in range(35)
    ]
    component = {
        "type": "DataTable",
        "table_id": "long_form",
        "title": "长表单",
        "columns": columns,
        "crud": {
            "form": {
                "create_columns": [column["key"] for column in columns],
                "layout": {"columns": 3, "gap": 10},
            },
            "create_handler": "create_item",
        },
    }

    dialog, widgets = page._build_crud_form_dialog(component, mode="create")
    qtbot.addWidget(dialog)
    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    confirm = dialog.findChild(StyledButton, "managedCrudConfirmButton")
    cancel = dialog.findChild(StyledButton, "managedCrudCancelButton")

    assert len(widgets) == 35
    assert scroll is not None
    assert scroll.widgetResizable() is True
    assert (
        scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    grid = scroll.widget().layout()
    assert isinstance(grid, QGridLayout)
    assert dialog._hosted_form_layout_columns == 3
    assert dialog._hosted_form_layout_rows == 12
    assert grid.count() == 70
    assert max(grid.getItemPosition(index)[1] for index in range(grid.count())) == 5
    assert dialog.maximumHeight() <= 720
    screen = dialog.screen().availableGeometry()
    assert dialog.maximumWidth() <= screen.width()
    assert dialog.maximumHeight() <= screen.height()
    assert confirm is not None and cancel is not None
    assert not scroll.isAncestorOf(confirm)
    assert not scroll.isAncestorOf(cancel)

    dialog.resize(dialog.maximumWidth(), 420)
    dialog.show()
    vertical_scrollbar = scroll.verticalScrollBar()
    qtbot.waitUntil(lambda: vertical_scrollbar.maximum() > 0)
    scroll.setFocus()
    qtbot.keyClick(scroll, Qt.Key.Key_PageDown)
    assert vertical_scrollbar.value() > 0
    vertical_scrollbar.setValue(0)
    vertical_scrollbar.setValue(1)
    assert vertical_scrollbar.value() == 1


def test_crud_form_layout_downgrades_columns_on_narrow_screen(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    class NarrowGeometry:
        @staticmethod
        def width() -> int:
            return 420

        @staticmethod
        def height() -> int:
            return 640

    class NarrowScreen:
        @staticmethod
        def availableGeometry() -> NarrowGeometry:
            return NarrowGeometry()

    class WideGeometry:
        @staticmethod
        def width() -> int:
            return 1920

        @staticmethod
        def height() -> int:
            return 1080

    class WideScreen:
        @staticmethod
        def availableGeometry() -> WideGeometry:
            return WideGeometry()

    class WidePrimaryApplication:
        @staticmethod
        def primaryScreen() -> WideScreen:
            return WideScreen()

    monkeypatch.setattr(
        "src.core.mms.ui.managed_page_renderer.QApplication",
        WidePrimaryApplication,
    )
    monkeypatch.setattr(bulk_update_page, "screen", lambda: NarrowScreen())

    dialog, _widgets = bulk_update_page._build_crud_form_dialog(
        _field_change_component(),
        mode="create",
    )
    qtbot.addWidget(dialog)

    assert dialog._hosted_form_layout_columns == 1
    assert dialog.maximumWidth() == 340
    assert dialog.maximumHeight() == 560


def test_crud_form_layout_clamps_large_valid_gap_to_screen_geometry(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    class FixedScreen:
        @staticmethod
        def availableGeometry() -> QRect:
            return QRect(0, 0, 800, 800)

    monkeypatch.setattr(bulk_update_page, "screen", lambda: FixedScreen())
    component = _field_change_component()
    component["crud"]["form"]["layout"]["gap"] = 2**31

    dialog, widgets = bulk_update_page._build_crud_form_dialog(
        component,
        mode="create",
    )
    qtbot.addWidget(dialog)
    dialog.resize(dialog.maximumWidth(), min(520, dialog.maximumHeight()))
    dialog.show()
    qtbot.wait(20)
    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    grid = scroll.widget().layout()
    first_input = widgets["preset"][0]
    input_left = first_input.mapTo(scroll.viewport(), QPoint(0, 0)).x()
    input_right = first_input.mapTo(
        scroll.viewport(),
        QPoint(first_input.width() - 1, 0),
    ).x()

    assert isinstance(grid, QGridLayout)
    assert 0 <= grid.horizontalSpacing() <= dialog.maximumWidth()
    assert 0 <= grid.verticalSpacing() <= dialog.maximumHeight()
    assert dialog._hosted_form_layout_columns == 1
    assert 0 <= input_left <= input_right < scroll.viewport().width()


def test_crud_form_preserves_declared_gap_between_logical_columns(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    class WideGeometry:
        @staticmethod
        def width() -> int:
            return 1920

        @staticmethod
        def height() -> int:
            return 1080

    class WideScreen:
        @staticmethod
        def availableGeometry() -> WideGeometry:
            return WideGeometry()

    monkeypatch.setattr(bulk_update_page, "screen", lambda: WideScreen())
    component = _field_change_component()
    component["crud"]["form"]["layout"]["gap"] = 100

    dialog, _widgets = bulk_update_page._build_crud_form_dialog(
        component,
        mode="create",
    )
    qtbot.addWidget(dialog)
    dialog.resize(dialog.minimumWidth(), min(520, dialog.maximumHeight()))
    dialog.show()
    qtbot.wait(20)
    scroll = dialog.findChild(QScrollArea, "managedCrudFormScrollArea")
    form_container = scroll.widget()
    grid = form_container.layout()

    assert isinstance(grid, QGridLayout)
    assert dialog._hosted_form_layout_columns == 3
    assert grid.horizontalSpacing() == 0
    for label_column in (0, 2, 4):
        label_widget = grid.itemAtPosition(0, label_column).widget()
        input_widget = grid.itemAtPosition(0, label_column + 1).widget()
        margins = label_widget.contentsMargins()
        assert margins.left() == (0 if label_column == 0 else 100)
        assert margins.right() == 6
        label_content_right = label_widget.mapTo(
            form_container,
            label_widget.contentsRect().topRight(),
        ).x()
        assert input_widget.geometry().left() - label_content_right - 1 == 6
        if label_column:
            previous_input = grid.itemAtPosition(0, label_column - 1).widget()
            label_content_left = label_widget.mapTo(
                form_container,
                label_widget.contentsRect().topLeft(),
            ).x()
            assert label_content_left - previous_input.geometry().right() - 1 >= 100


def test_form_select_change_event_can_reset_entire_form_and_handle_closes(
    bulk_update_page,
    qtbot,
    monkeypatch,
):
    page = bulk_update_page
    dialog, widgets = page._build_crud_form_dialog(
        _field_change_component(),
        mode="update",
        row=_field_change_row(),
    )
    qtbot.addWidget(dialog)
    controller = dialog._hosted_form_controller
    controller.set_validation_error("note", "invalid")
    captured: list[dict] = []
    bound_tools = []
    reset_values = {
        "preset": "advanced",
        "priority": 0,
        "enabled": False,
        "note": "",
        "marker": "undefined",
        "untouched": "two",
    }

    def call_ui_action(action_name, params, **kwargs):
        assert action_name == "handle_field_change"
        captured.append(params["event"])
        tools = kwargs["hosted_form_tools"]
        bound_tools.append(tools)
        return tools.reset(
            form_id=params["event"]["scope"]["form_id"],
            initial_values=reset_values,
        )

    monkeypatch.setattr(page._bridge, "call_ui_action", call_ui_action)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(page, "_show_warning", lambda title, message: warnings.append((title, message)))

    preset = widgets["preset"][0]
    assert isinstance(preset, StyledComboBox)
    preset.setCurrentIndex(preset.findData("advanced"))

    event_values = {key: value for key, value in _field_change_row().items() if key != "id"}
    event_values["preset"] = "advanced"
    assert captured == [
        {
            "component": {"id": "accounts", "type": "Select"},
            "field": "preset",
            "event": "change",
            "value": "advanced",
            "previous_value": "basic",
            "scope": {
                "kind": "form",
                "form_id": dialog._hosted_form_id,
                "mode": "update",
                "values": event_values,
            },
        }
    ]
    assert controller.values == reset_values
    assert controller.initial_values == reset_values
    assert controller.dirty is False
    assert controller.validation_errors == {}
    assert widgets["priority"][0].text() == "0"
    assert widgets["enabled"][0].currentData() is False
    assert widgets["note"][0].text() == ""
    assert widgets["marker"][0].text() == "undefined"
    payload, error = page._collect_crud_form_payload(widgets)
    assert error is None
    assert payload == reset_values
    assert warnings == []

    untouched = widgets["untouched"][0]
    untouched.setCurrentIndex(untouched.findData("one"))
    assert len(captured) == 1

    dialog.reject()
    with pytest.raises(RuntimeError, match=FORM_HANDLE_REJECTED):
        bound_tools[0].reset(form_id=dialog._hosted_form_id, initial_values=reset_values)


def test_standalone_select_change_has_no_form_handle(bulk_update_page, monkeypatch):
    page = bulk_update_page
    captured: list[dict] = []
    reset_errors: list[str] = []

    def call_ui_action(action_name, params, **kwargs):
        assert action_name == "handle_field_change"
        captured.append(params["event"])
        with pytest.raises(RuntimeError, match=FORM_SCOPE_UNAVAILABLE) as exc_info:
            kwargs["hosted_form_tools"].reset(form_id="forged", initial_values={})
        reset_errors.append(str(exc_info.value))
        return {"ok": True}

    monkeypatch.setattr(page._bridge, "call_ui_action", call_ui_action)
    widget = page._build_component(
        {
            "type": "Select",
            "id": "preset",
            "label": "模板",
            "value": "basic",
            "options": ["basic", "advanced"],
            "on_change": {"type": "ui_action", "name": "handle_field_change"},
        }
    )
    combo = page._standalone_field_widgets["preset"]
    combo.setCurrentIndex(combo.findData("advanced"))

    assert widget is not combo
    assert captured == [
        {
            "component": {"id": "preset", "type": "Select"},
            "field": "preset",
            "event": "change",
            "value": "advanced",
            "previous_value": "basic",
            "scope": {"kind": "standalone"},
        }
    ]
    assert "form_id" not in captured[0]["scope"]
    assert reset_errors == [f"ui.form.reset rejected: {FORM_SCOPE_UNAVAILABLE}"]


def test_form_change_handler_failure_keeps_current_form(bulk_update_page, qtbot, monkeypatch):
    page = bulk_update_page
    dialog, widgets = page._build_crud_form_dialog(
        _field_change_component(),
        mode="update",
        row=_field_change_row(),
    )
    qtbot.addWidget(dialog)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(page._bridge, "call_ui_action", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(page, "_show_warning", lambda title, message: warnings.append((title, message)))

    preset = widgets["preset"][0]
    preset.setCurrentIndex(preset.findData("advanced"))

    assert dialog._hosted_form_controller.values["preset"] == "advanced"
    assert dialog._hosted_form_controller.initial_values["preset"] == "basic"
    assert dialog._hosted_form_controller.dirty is True
    assert warnings == [("字段更新失败", "boom")]


@pytest.mark.asyncio
async def test_rapid_form_changes_reject_stale_reset(bulk_update_page, qtbot, monkeypatch):
    page = bulk_update_page
    dialog, widgets = page._build_crud_form_dialog(
        _field_change_component(),
        mode="update",
        row=_field_change_row(),
    )
    qtbot.addWidget(dialog)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(page, "_show_warning", lambda title, message: warnings.append((title, message)))

    async def call_ui_action_async(_action_name, params, **kwargs):
        value = params["event"]["value"]
        await asyncio.sleep(0.04 if value == "advanced" else 0.01)
        marker = "old-result" if value == "advanced" else "new-result"
        values = {**params["event"]["scope"]["values"], "marker": marker}
        return kwargs["hosted_form_tools"].reset(
            form_id=params["event"]["scope"]["form_id"],
            initial_values=values,
        )

    monkeypatch.setattr(page._bridge, "call_ui_action_async", call_ui_action_async)
    preset = widgets["preset"][0]
    preset.setCurrentIndex(preset.findData("advanced"))
    preset.setCurrentIndex(preset.findData("final"))
    await asyncio.sleep(0.08)

    assert dialog._hosted_form_controller.values["preset"] == "final"
    assert dialog._hosted_form_controller.values["marker"] == "new-result"
    assert warnings == []
    assert FORM_EVENT_STALE == "FORM_EVENT_STALE"
