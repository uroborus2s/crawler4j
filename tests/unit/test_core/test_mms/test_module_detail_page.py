import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.core.mms.models import (
    DetailMenuItem,
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    UIExtensionInfo,
    WorkflowInfo,
)
from src.core.mms.ui.module_detail_page import ModuleDetailPage


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
    entry: str = "ui:LoadedPage",
    ui_type: str = "micro_app",
) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text("VALUE = 'demo'\n", encoding="utf-8")
    (module_dir / "ui.py").write_text(
        "from PyQt6.QtWidgets import QLabel\n\n"
        "class LoadedPage(QLabel):\n"
        "    def __init__(self):\n"
        "        super().__init__('Loaded from module UI')\n",
        encoding="utf-8",
    )
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(
            name="demo_module",
            display_name="Demo Module",
            workflows=[
                WorkflowInfo(name="default", display_name="默认流程"),
            ],
            ui_extension=UIExtensionInfo(
                type=ui_type,
                detail_menu=[
                    DetailMenuItem(
                        id="custom",
                        icon="🧩",
                        label="自定义页",
                        entry=entry,
                    )
                ],
            ),
        ),
        source=source,
        path=module_dir,
    )


def test_module_detail_page_no_longer_exposes_debug_ui(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

    menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
    assert all("调试" not in text for text in menu_texts)

    button_texts = [button.text() for button in page.findChildren(QPushButton)]
    assert all("调试" not in text for text in button_texts)


def test_module_detail_page_loads_micro_app_for_dev_link_modules(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

    custom_page = page._menu_pages["custom"]
    assert custom_page.__class__.__name__ == "LoadedPage"
    assert isinstance(custom_page, QLabel)
    assert custom_page.text() == "Loaded from module UI"


def test_module_detail_page_blocks_external_micro_app_without_allowlist(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.EXTERNAL))

    custom_page = page._menu_pages["custom"]
    texts = [label.text() for label in custom_page.findChildren(QLabel)]
    assert any("trust gate" in text or "allowlist" in text for text in texts)


def test_module_detail_page_allows_external_micro_app_when_allowlisted(qtbot, tmp_path):
    from src.core.persistence import get_config_store

    get_config_store().set_setting("mms.ui.allowlist", json.dumps(["demo_module"], ensure_ascii=False))

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.EXTERNAL))

    custom_page = page._menu_pages["custom"]
    assert custom_page.__class__.__name__ == "LoadedPage"
    assert isinstance(custom_page, QLabel)
    assert custom_page.text() == "Loaded from module UI"


def test_module_detail_page_gracefully_degrades_when_custom_page_load_fails(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK, entry="ui:MissingPage"))

    custom_page = page._menu_pages["custom"]
    texts = [label.text() for label in custom_page.findChildren(QLabel)]
    assert any("加载失败" in text or "MissingPage" in text for text in texts)
