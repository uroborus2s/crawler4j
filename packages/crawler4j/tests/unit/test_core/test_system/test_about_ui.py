from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton


def test_config_center_contains_update_controls(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.about_dialog as about_dialog_module
    import src.core.system.ui.config_center_page as config_center_page_module

    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    monkeypatch.setattr(
        about_dialog_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash=None)),
    )
    monkeypatch.setattr(
        config_center_page_module,
        "get_current_version",
        lambda: "0.2.0",
    )
    monkeypatch.setattr(
        config_center_page_module,
        "get_update_service",
        lambda: SimpleNamespace(check_for_updates=lambda: True, availability_reason=""),
    )
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_dialog_module, "load_app_icon_pixmap", lambda _size: pixmap)

    page = config_center_page_module.ConfigCenterPage()
    qtbot.addWidget(page)
    page.show()
    page._domain_buttons["update"].click()

    label_texts = {label.text() for label in page.findChildren(QLabel)}
    button_texts = {button.text() for button in page.findChildren(QPushButton)}

    assert "自动检查更新" in label_texts
    assert "当前版本：v0.2.0" in label_texts
    assert "检查更新" in button_texts


def test_about_dialog_provides_version_and_project_link_only(qtbot, monkeypatch):
    import src.core.system.ui.about_dialog as about_dialog_module

    monkeypatch.setattr(
        about_dialog_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash=None)),
    )
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_dialog_module, "load_app_icon_pixmap", lambda _size: pixmap)

    dialog = about_dialog_module.AboutDialog()
    qtbot.addWidget(dialog)

    label_texts = {label.text() for label in dialog.findChildren(QLabel)}
    button_texts = {button.text() for button in dialog.findChildren(QPushButton)}

    assert dialog.windowTitle() == "关于 蛛行演略"
    assert "蛛行演略 · crawler4j" in label_texts
    assert "v0.2.0" in label_texts
    assert "Development Build" in label_texts
    assert any(about_dialog_module.DOCS_URL in text for text in label_texts)
    assert "检查更新" not in button_texts
