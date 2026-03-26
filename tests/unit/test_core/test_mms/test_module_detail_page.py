from pathlib import Path

from PyQt6.QtWidgets import QPushButton

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, WorkflowInfo
from src.core.mms.ui.module_detail_page import ModuleDetailPage


def _make_module(tmp_path: Path, *, source: ModuleSource = ModuleSource.DEV_LINK) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(
            name="demo_module",
            display_name="Demo Module",
            workflows=[
                WorkflowInfo(name="default", display_name="默认流程"),
            ],
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
