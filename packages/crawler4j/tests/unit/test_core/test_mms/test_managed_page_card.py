from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from src.ui.components.card import Card
from src.core.mms.ui.managed_page_renderer import ManagedPageRenderer

from ._core_native_v1 import make_manifest, make_page_info, register_module, restore_module, write_module_tree


def test_managed_page_renderer_supports_hosted_card(qtbot, tmp_path):
    module_name = "hosted_page_card_module"
    module_dir = write_module_tree(
        tmp_path,
        module_name,
        files={
            "pages/dashboard.py": """
            from crawler4j_contracts import PageSpec, TaskContext

            PAGE = PageSpec(
                id="dashboard",
                label="Dashboard",
                icon="📊",
                schema={
                    "type": "Page",
                    "load_handler": "load_dashboard_page",
                    "layout": {"direction": "column", "gap": 16},
                    "children": [
                        {
                            "type": "Card",
                            "title": "活跃账号",
                            "title_align": "center",
                            "content_align": "center",
                            "content_vertical_align": "center",
                            "min_height": 180,
                            "padding": 24,
                            "layout": {"direction": "column", "gap": 6},
                            "children": [
                                {"type": "Text", "style": "subtitle", "binding": "active.value"},
                                {"type": "Text", "style": "meta", "binding": "active.subtitle"},
                            ],
                        },
                        {
                            "type": "Section",
                            "variant": "card",
                            "title": "转化率",
                            "layout": {"direction": "column", "gap": 6},
                            "children": [
                                {"type": "Text", "style": "subtitle", "binding": "conversion.value"},
                                {"type": "Text", "style": "meta", "text": "近 24 小时"},
                            ],
                        }
                    ],
                },
            )


            def load_dashboard_page(context: TaskContext, page_id: str, params=None):
                del context, page_id, params
                return {
                    "active": {
                        "value": 18,
                        "subtitle": "较昨日",
                    },
                    "conversion": {
                        "value": "3.2%",
                    },
                }
            """,
        },
    )
    manifest = make_manifest(module_name, pages=[make_page_info("dashboard", label="看板", icon="📊")])
    service, original_registry, module_info = register_module(module_name, module_dir, manifest=manifest)

    try:
        page = ManagedPageRenderer(module_name, "dashboard", module_info=module_info)
        qtbot.addWidget(page)

        cards = page.findChildren(Card)
        assert len(cards) == 2

        assert cards[0].title_label is not None
        assert cards[0].title_label.text() == "活跃账号"
        assert cards[0].title_align == "center"
        assert cards[0].content_align == "center"
        assert cards[0].content_vertical_align == "center"
        assert cards[0].minimumHeight() == 180
        assert cards[0].title_label.alignment() == Qt.AlignmentFlag.AlignHCenter
        assert any(label.text() == "18" for label in cards[0].findChildren(QLabel))
        assert any(label.text() == "较昨日" for label in cards[0].findChildren(QLabel))

        assert cards[1].title_label is not None
        assert cards[1].title_label.text() == "转化率"
        assert cards[1].title_align == "left"
        assert any(label.text() == "3.2%" for label in cards[1].findChildren(QLabel))
        assert any(label.text() == "近 24 小时" for label in cards[1].findChildren(QLabel))
    finally:
        restore_module(service, original_registry, module_name)
