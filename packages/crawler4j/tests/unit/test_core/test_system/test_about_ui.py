from __future__ import annotations

import threading
from types import SimpleNamespace

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QPushButton


def test_about_page_contains_update_controls(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.about_page as about_page_module

    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    monkeypatch.setattr(
        about_page_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash="a1cd539")),
    )
    monkeypatch.setattr(
        about_page_module,
        "get_update_service",
        lambda: SimpleNamespace(
            check_for_updates=lambda: True,
            configure=lambda **_kwargs: None,
            is_supported=True,
            availability_reason="",
            last_action_message="",
        ),
    )
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_page_module, "load_app_icon_pixmap", lambda _size: pixmap)

    page = about_page_module.AboutPage()
    qtbot.addWidget(page)
    page.show()

    label_texts = {label.text() for label in page.findChildren(QLabel)}
    button_texts = {button.text() for button in page.findChildren(QPushButton)}

    assert "自动检查更新" in label_texts
    assert "更新操作" in label_texts
    assert "v0.2.0" in label_texts
    assert "Build a1cd539" in label_texts
    assert "检查更新" in button_texts
    assert "升级" in button_texts


def test_about_page_runs_update_flow_off_ui_thread(qtbot, monkeypatch, tmp_path):
    import src.core.system.ui.about_page as about_page_module

    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    main_thread_id = threading.get_ident()
    worker_started = threading.Event()
    release_worker = threading.Event()
    observed: dict[str, int] = {}

    class FakeUpdateService:
        is_supported = True
        availability_reason = ""
        last_action_message = ""

        def configure(self, **_kwargs) -> None:
            return None

        def check_for_updates(self) -> bool:
            observed["thread_id"] = threading.get_ident()
            if observed["thread_id"] == main_thread_id:
                raise AssertionError("Update flow must not run on the UI thread")
            worker_started.set()
            release_worker.wait(timeout=2)
            self.last_action_message = "已下载更新，应用将退出并重启。"
            return True

    update_service = FakeUpdateService()
    monkeypatch.setattr(
        about_page_module,
        "get_version_service",
        lambda: SimpleNamespace(get_build_info=lambda: SimpleNamespace(version="0.2.0", commit_hash="a1cd539")),
    )
    monkeypatch.setattr(about_page_module, "get_update_service", lambda: update_service)
    pixmap = QPixmap(16, 16)
    pixmap.fill()
    monkeypatch.setattr(about_page_module, "load_app_icon_pixmap", lambda _size: pixmap)

    page = about_page_module.AboutPage()
    qtbot.addWidget(page)

    try:
        page._trigger_update_flow()
        qtbot.waitUntil(worker_started.is_set)

        assert page.check_update_btn.isEnabled() is False
        assert page.upgrade_btn.isEnabled() is False
        assert page.update_status_label.text() == "正在检查并下载更新，请不要关闭客户端。"

        release_worker.set()
        qtbot.waitUntil(lambda: page.update_status_label.text() == "已下载更新，应用将退出并重启。")
    finally:
        release_worker.set()

    assert observed["thread_id"] != main_thread_id
    assert page.check_update_btn.isEnabled() is True
    assert page.upgrade_btn.isEnabled() is True


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
