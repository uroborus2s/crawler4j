from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QDialog

from src.core.mms.dev_links import get_dev_module_link_store
from src.core.mms.registry import get_module_registry
from src.core.mms.ui import module_data_table_page as page_module
from src.core.mms.ui.module_data_table_page import ModuleDataTablePage
from src.core.mms.ui.module_detail_page import ModuleDetailPage
from src.core.persistence import get_kv_store


CTRIP_MODULE_ROOT = Path(__file__).resolve().parents[5] / "ctrip_crawler"


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        monkeypatch.setattr("src.core.mms.registry._registry", None, raising=False)
        monkeypatch.setattr("src.core.mms.service._service", None, raising=False)
        monkeypatch.setattr("src.core.mms.dev_links._store", None, raising=False)
        monkeypatch.setattr("src.core.persistence.kv_store._kv_store", None, raising=False)
        yield tmp_path


def test_ctrip_account_ui_smoke_end_to_end(qtbot, monkeypatch):
    if not CTRIP_MODULE_ROOT.exists():
        pytest.skip(f"ctrip module repo not found: {CTRIP_MODULE_ROOT}")

    get_dev_module_link_store().upsert_link("ctrip", CTRIP_MODULE_ROOT)
    registry = get_module_registry()
    registry.refresh()
    module = registry.get_module("ctrip")

    assert module is not None

    detail_page = ModuleDetailPage()
    qtbot.addWidget(detail_page)
    detail_page.set_module(module)

    menu_texts = [detail_page.menu_list.item(index).text() for index in range(detail_page.menu_list.count())]
    assert any("账号管理" in text for text in menu_texts)

    account_page = detail_page._menu_pages["accounts"]
    assert isinstance(account_page, ModuleDataTablePage)

    kv = get_kv_store()
    meta = kv.get("module:ctrip:ui:data_table:accounts")
    assert meta["primary_key"] == "phone"
    assert meta["lock_key"] == "phone"
    assert meta["create_handler"] == "create_account_from_ui"
    assert meta["update_handler"] == "update_account_from_ui"
    assert account_page.table.rowCount() == 0

    warning_messages: list[str] = []
    monkeypatch.setattr(
        page_module.QMessageBox,
        "warning",
        lambda *args: warning_messages.append(str(args[2] if len(args) > 2 else "")),
    )

    class FakeDialog:
        next_payload: dict[str, object] = {}

        def __init__(self, columns, record=None, parent=None):
            self.columns = columns
            self.record = record or {}
            self.parent = parent

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_value(self):
            return dict(self.next_payload)

    monkeypatch.setattr(page_module, "_RecordEditDialog", FakeDialog)

    FakeDialog.next_payload = {
        "phone": "13800138000",
        "account_status": "active",
        "account_level": "vip",
        "register_source": "smoke",
        "registered_at": "2026-04-07T10:00:00+08:00",
        "status_reason": "created in smoke",
    }
    account_page._on_add()

    rows = kv.get("module:ctrip:dataset:accounts")
    assert len(rows) == 1
    assert rows[0]["phone"] == "13800138000"
    assert rows[0]["phone_masked"] == "138****8000"
    assert rows[0]["account_status"] == "active"

    account_page.refresh()
    account_page.table.selectRow(0)
    FakeDialog.next_payload = {
        "account_status": "blocked",
        "account_level": "gold",
        "register_source": "ops",
        "registered_at": "2026-04-07T11:00:00+08:00",
        "status_reason": "edited in smoke",
    }
    account_page._on_edit()

    rows = kv.get("module:ctrip:dataset:accounts")
    assert rows[0]["account_status"] == "blocked"
    assert rows[0]["account_level"] == "gold"
    assert rows[0]["register_source"] == "ops"

    account_page.refresh()
    account_page.table.selectRow(0)
    FakeDialog.next_payload = {
        "account_status": "blocked",
        "completed_count": 9,
    }
    account_page._on_edit()

    rows = kv.get("module:ctrip:dataset:accounts")
    assert rows[0]["completed_count"] == 0
    assert any("completed_count" in message for message in warning_messages)
