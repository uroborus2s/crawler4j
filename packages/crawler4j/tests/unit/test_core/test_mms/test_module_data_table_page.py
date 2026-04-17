from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QDialog

from src.core.mms.models import ModuleSource
from src.core.mms.ui import module_data_table_page as page_module
from src.core.mms.ui.module_data_table_page import ModuleDataTablePage
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path

def test_module_data_table_page_declares_schema_and_renders_display_fields(qtbot, monkeypatch):
    def fake_handler(self, handler_name, *args):
        assert handler_name == "declare_ui"
        self._data_store.write_data_table_schema(
            "demo_module",
            "accounts",
            {
                "title": "账号管理",
                "dataset": "accounts",
                "primary_key": "phone",
                "lock_key": "phone",
                "display_fields": ["phone_masked", "account_status", "updated_at"],
                "columns": [
                    {"key": "phone", "label": "手机号原文", "visible": False},
                    {"key": "phone_masked", "label": "手机号"},
                    {"key": "account_status", "label": "账号状态"},
                    {"key": "updated_at", "label": "更新时间"},
                ],
            },
        )
        self._data_store.write_dataset(
            "demo_module",
            "accounts",
            [
                {
                    "phone": "13800138000",
                    "phone_masked": "138****8000",
                    "account_status": "active",
                    "updated_at": "2026-04-07T10:00:00+08:00",
                }
            ],
        )
        return None

    monkeypatch.setattr(ModuleDataTablePage, "_call_module_handler", fake_handler)

    page = ModuleDataTablePage("demo_module", "accounts")
    qtbot.addWidget(page)

    assert page.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.table.horizontalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel

    headers = [page.table.horizontalHeaderItem(index).text() for index in range(page.table.columnCount())]
    assert headers == ["手机号", "账号状态", "更新时间", "占用中"]
    assert page.table.item(0, 0).text() == "138****8000"
    assert page.table.item(0, 1).text() == "active"


def test_module_data_table_page_routes_add_and_edit_to_module_handlers(qtbot, monkeypatch):
    calls: list[tuple[str, tuple[object, ...]]] = []

    def fake_handler(self, handler_name, *args):
        calls.append((handler_name, args))
        self._data_store.write_data_table_schema(
            "demo_module",
            "accounts",
            {
                "title": "账号管理",
                "dataset": "accounts",
                "primary_key": "phone",
                "lock_key": "phone",
                "create_handler": "create_account_from_ui",
                "update_handler": "update_account_from_ui",
                "display_fields": ["phone_masked", "account_status"],
                "create_fields": ["phone", "account_status"],
                "update_fields": ["account_status"],
                "columns": [
                    {"key": "phone", "label": "手机号", "required": True, "visible": False},
                    {"key": "phone_masked", "label": "手机号"},
                    {"key": "account_status", "label": "账号状态", "required": True},
                ],
            },
        )
        rows = self._data_store.read_dataset("demo_module", "accounts")
        if handler_name == "create_account_from_ui":
            rows = list(rows)
            rows.append(
                {
                    "phone": "13800138001",
                    "phone_masked": "138****8001",
                    "account_status": "new",
                }
            )
            self._data_store.write_dataset("demo_module", "accounts", rows)
        elif handler_name == "update_account_from_ui":
            rows = [
                {
                    **row,
                    "account_status": "blocked" if row.get("phone") == args[0] else row.get("account_status"),
                }
                for row in rows
            ]
            self._data_store.write_dataset("demo_module", "accounts", rows)
        return None

    monkeypatch.setattr(ModuleDataTablePage, "_call_module_handler", fake_handler)
    page_data_store = page_module.get_module_data_store()
    page_data_store.write_dataset(
        "demo_module",
        "accounts",
        [
            {
                "phone": "13800138000",
                "phone_masked": "138****8000",
                "account_status": "active",
            }
        ],
    )

    page = ModuleDataTablePage("demo_module", "accounts")
    qtbot.addWidget(page)

    class FakeDialog:
        next_payload = {}

        def __init__(self, columns, record=None, parent=None):
            self.columns = columns
            self.record = record or {}
            self.parent = parent

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_value(self):
            return dict(self.next_payload)

    monkeypatch.setattr(page_module, "_RecordEditDialog", FakeDialog)

    FakeDialog.next_payload = {"phone": "13800138001", "account_status": "new"}
    page._on_add()

    page.refresh()
    page.table.selectRow(0)
    FakeDialog.next_payload = {"account_status": "blocked"}
    page._on_edit()

    assert ("create_account_from_ui", ({"phone": "13800138001", "account_status": "new"},)) in calls
    assert ("update_account_from_ui", ("13800138000", {"account_status": "blocked"})) in calls
    assert page._data_store.read_dataset("demo_module", "accounts")[0]["account_status"] == "blocked"


def test_module_data_table_page_refresh_overwrites_stale_schema(qtbot, monkeypatch):
    page_module.get_module_data_store().write_data_table_schema(
        "demo_module",
        "accounts",
        {
            "title": "过期账号管理",
            "dataset": "accounts",
            "columns": ["phone_masked", "account_status"],
        },
    )

    def fake_handler(self, handler_name, *args):
        assert handler_name == "declare_ui"
        self._data_store.write_data_table_schema(
            "demo_module",
            "accounts",
            {
                "title": "账号管理",
                "dataset": "accounts",
                "primary_key": "phone",
                "lock_key": "phone",
                "create_handler": "create_account_from_ui",
                "update_handler": "update_account_from_ui",
                "display_fields": ["phone_masked", "account_status"],
                "columns": [
                    {"key": "phone", "label": "手机号", "visible": False},
                    {"key": "phone_masked", "label": "手机号"},
                    {"key": "account_status", "label": "账号状态"},
                ],
            },
        )
        return None

    monkeypatch.setattr(ModuleDataTablePage, "_call_module_handler", fake_handler)

    page = ModuleDataTablePage("demo_module", "accounts")
    qtbot.addWidget(page)

    schema = page._data_store.read_data_table_schema("demo_module", "accounts")

    assert schema["primary_key"] == "phone"
    assert schema["create_handler"] == "create_account_from_ui"
    assert all(isinstance(column, dict) for column in schema["columns"])


def test_module_data_table_page_builds_devlink_context_with_settings(qtbot, monkeypatch):
    monkeypatch.setattr(ModuleDataTablePage, "refresh", lambda self: None)
    monkeypatch.setattr(
        page_module,
        "get_module_settings_store",
        lambda: SimpleNamespace(read_module_settings=lambda module_name: {"module_name": module_name}),
    )

    page = ModuleDataTablePage("demo_module", "accounts")
    qtbot.addWidget(page)
    page._mms.registry = SimpleNamespace(get_module=lambda module_name: SimpleNamespace(source=ModuleSource.DEV_LINK))

    context = page._build_task_context()

    assert context.config["module_name"] == "demo_module"
    assert context.runtime["devel_mode"] is True
    assert context.tools is not None


def test_record_edit_dialog_uses_styled_combo_box(qtbot):
    dialog = page_module._RecordEditDialog(
        columns=[
            {
                "key": "status",
                "label": "状态",
                "type": "select",
                "options": ["active", "blocked"],
            }
        ],
        record={"status": "blocked"},
    )
    qtbot.addWidget(dialog)

    widget = dialog._widgets["status"]

    assert isinstance(widget, StyledComboBox)
    assert widget.currentText() == "blocked"


def test_record_edit_dialog_uses_styled_line_edit(qtbot):
    dialog = page_module._RecordEditDialog(
        columns=[
            {
                "key": "account",
                "label": "账号",
                "type": "text",
            }
        ],
        record={"account": "demo-user"},
    )
    qtbot.addWidget(dialog)

    widget = dialog._widgets["account"]

    assert isinstance(widget, StyledLineEdit)
    assert widget.text() == "demo-user"
