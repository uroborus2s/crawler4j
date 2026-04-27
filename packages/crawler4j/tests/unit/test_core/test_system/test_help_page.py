from pathlib import Path

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QImage

from src.ui.components.button import StyledButton

def _write_doc(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_help_page_loads_default_markdown_and_resolves_relative_links(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.help_page as help_page_module

    docs_root = tmp_path / "docs"
    _write_doc(docs_root / "01-getting-started" / "index.md", "# 开始前\n\n进入 [开始使用](../02-user-guide/user-guide.md)\n")
    _write_doc(
        docs_root / "02-user-guide" / "user-guide.md",
        "# 开始使用\n\n点击这里看 [日常使用](usage.md)。\n",
    )
    _write_doc(docs_root / "02-user-guide" / "usage.md", "# 日常使用\n\n已切换到 usage。\n")
    _write_doc(docs_root / "03-developer-guide" / "index.md", "# 开发指南概览\n")

    monkeypatch.setattr(help_page_module, "get_docs_root", lambda: docs_root)

    page = help_page_module.HelpPage()
    qtbot.addWidget(page)

    assert page.browser.searchPaths() == [str(docs_root)]
    assert Path(page.browser.source().toLocalFile()) == docs_root / "01-getting-started" / "index.md"
    assert page.nav_tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "docs-index"
    assert page.nav_tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole) == "docs-index"

    page._open_link(QUrl("../02-user-guide/user-guide.md"))

    qtbot.waitUntil(
        lambda: Path(page.browser.source().toLocalFile()) == docs_root / "02-user-guide" / "user-guide.md"
    )
    assert page.nav_tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "user-guide"
    html = page.browser.document().toHtml()
    assert "#0000ff" not in html
    assert "#8bd3ff" in html

    page._open_link(QUrl("usage.md"))

    qtbot.waitUntil(
        lambda: Path(page.browser.source().toLocalFile()) == docs_root / "02-user-guide" / "usage.md"
    )
    assert page.nav_tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "usage"


def test_help_page_hides_scrollbars_and_applies_doc_styles(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.help_page as help_page_module

    docs_root = tmp_path / "docs"
    _write_doc(docs_root / "01-getting-started" / "index.md", "# 开始前\n")
    _write_doc(docs_root / "02-user-guide" / "user-guide.md", "# 开始使用\n\n![截图](guide.png)\n")
    _write_doc(docs_root / "03-developer-guide" / "index.md", "# 开发指南概览\n")

    monkeypatch.setattr(help_page_module, "get_docs_root", lambda: docs_root)

    page = help_page_module.HelpPage()
    qtbot.addWidget(page)

    assert page.nav_tree.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.nav_tree.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.browser.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.browser.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    doc_css = page.browser.document().defaultStyleSheet()
    assert "img {" in doc_css
    assert "max-width: 100%" in doc_css
    assert "#8bd3ff" in doc_css
    assert page.current_doc_label is None
    assert isinstance(page.back_btn, StyledButton)
    assert isinstance(page.forward_btn, StyledButton)
    assert isinstance(page.home_btn, StyledButton)


def test_help_page_scales_large_images_to_viewport_width(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.help_page as help_page_module

    docs_root = tmp_path / "docs"
    image_path = docs_root / "assets" / "large.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(2400, 1200, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFFFF)
    assert image.save(str(image_path))

    _write_doc(docs_root / "01-getting-started" / "index.md", "# 开始前\n\n![大图](../assets/large.png)\n")
    _write_doc(docs_root / "03-developer-guide" / "index.md", "# 开发指南概览\n")

    monkeypatch.setattr(help_page_module, "get_docs_root", lambda: docs_root)

    page = help_page_module.HelpPage()
    page.resize(1280, 720)
    qtbot.addWidget(page)
    page.show()
    qtbot.wait(50)

    assert page.browser.viewport().width() > 0
    assert page.browser.document().size().width() <= page.browser.viewport().width() + 4


def test_help_page_includes_developer_guide_entries(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.help_page as help_page_module

    docs_root = tmp_path / "docs"
    _write_doc(docs_root / "01-getting-started" / "index.md", "# 开始前\n")
    _write_doc(docs_root / "03-developer-guide" / "index.md", "# 开发指南概览\n")
    _write_doc(docs_root / "03-developer-guide" / "quickstart.md", "# 快速开始\n")

    monkeypatch.setattr(help_page_module, "get_docs_root", lambda: docs_root)

    page = help_page_module.HelpPage()
    qtbot.addWidget(page)

    assert page.nav_tree.topLevelItem(0).text(0) == "开始前"
    developer_group = page.nav_tree.topLevelItem(2)
    assert developer_group.text(0) == "▸  开发指南"
    assert developer_group.childCount() >= 2
    assert developer_group.child(0).data(0, Qt.ItemDataRole.UserRole) == "developer-index"
    assert developer_group.child(1).data(0, Qt.ItemDataRole.UserRole) == "developer-quickstart"

    page._on_nav_clicked(developer_group, 0)

    assert developer_group.isExpanded() is True
    assert developer_group.text(0) == "▾  开发指南"
