from __future__ import annotations

import importlib
import sys
from types import ModuleType

from PyQt6.QtCore import Qt


def _import_managed_page_renderer_with_fake_bridge(monkeypatch, *, declared_page: dict, payload: dict | None = None):
    fake_runtime_module = ModuleType("src.core.mms.ui.module_ui_runtime")

    class FakeBridge:
        def __init__(self, module_name: str, module_info=None):
            del module_name, module_info

        def declare_ui(self, *, page_id: str | None = None, params: dict | None = None):
            del page_id, params
            return None

        def get_declared_page(self, page_id: str) -> dict:
            del page_id
            return dict(declared_page)

        def call_page_handler(self, handler_name: str, page_id: str, params: dict | None = None) -> dict:
            del handler_name, page_id, params
            return dict(payload or {})

    fake_runtime_module.ModuleUIRuntimeBridge = FakeBridge
    monkeypatch.setitem(sys.modules, "src.core.mms.ui.module_ui_runtime", fake_runtime_module)
    sys.modules.pop("src.core.mms.ui.managed_page_renderer", None)

    managed_page_renderer = importlib.import_module("src.core.mms.ui.managed_page_renderer")
    return managed_page_renderer.ManagedPageRenderer


def test_managed_page_renderer_hides_vertical_scrollbar_when_page_scroll_is_hidden(qtbot, monkeypatch):
    ManagedPageRenderer = _import_managed_page_renderer_with_fake_bridge(
        monkeypatch,
        declared_page={
            "type": "Page",
            "title": "今日运营看板",
            "load_handler": "load_dashboard_page",
            "scroll": {"vertical": "hidden"},
            "children": [{"type": "Text", "style": "title", "text": "今日运营看板"}],
        },
    )

    page = ManagedPageRenderer("demo_module", "dashboard")
    qtbot.addWidget(page)

    assert page._scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_managed_page_renderer_uses_vertical_auto_scroll_by_default(qtbot, monkeypatch):
    ManagedPageRenderer = _import_managed_page_renderer_with_fake_bridge(
        monkeypatch,
        declared_page={
            "type": "Page",
            "title": "今日运营看板",
            "load_handler": "load_dashboard_page",
            "children": [{"type": "Text", "style": "title", "text": "今日运营看板"}],
        },
    )

    page = ManagedPageRenderer("demo_module", "dashboard")
    qtbot.addWidget(page)

    assert page._scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert page._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_managed_page_renderer_uses_vertical_auto_scroll_when_declared(qtbot, monkeypatch):
    ManagedPageRenderer = _import_managed_page_renderer_with_fake_bridge(
        monkeypatch,
        declared_page={
            "type": "Page",
            "title": "今日运营看板",
            "load_handler": "load_dashboard_page",
            "scroll": {"vertical": "auto"},
            "children": [{"type": "Text", "style": "title", "text": "今日运营看板"}],
        },
    )

    page = ManagedPageRenderer("demo_module", "dashboard")
    qtbot.addWidget(page)

    assert page._scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert page._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
