import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton, QSplitter

from src.core.mms.models import (
    ConfigDefaultsInfo,
    DetailMenuItem,
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    UIExtensionInfo,
    WorkflowInfo,
)
from src.core.mms.github_credentials import get_github_credential_store
from src.core.mms.ui.module_detail_page import ModuleDetailPage
from src.ui.components.combo_box import StyledComboBox


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
    detail_menu: list[DetailMenuItem] | None = None,
    config_defaults: ConfigDefaultsInfo | None = None,
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
                entry=entry if entry.startswith("ui:") else "",
                detail_menu=list(detail_menu or []),
            ),
            config_defaults=config_defaults or ConfigDefaultsInfo(),
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

    custom_page = page._menu_pages[ModuleDetailPage.MICRO_APP_MENU_ID]
    assert custom_page.__class__.__name__ == "LoadedPage"
    assert isinstance(custom_page, QLabel)
    assert custom_page.text() == "Loaded from module UI"


def test_module_detail_page_blocks_external_micro_app_without_allowlist(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.EXTERNAL))

    custom_page = page._menu_pages[ModuleDetailPage.MICRO_APP_MENU_ID]
    texts = [label.text() for label in custom_page.findChildren(QLabel)]
    assert any("trust gate" in text or "allowlist" in text for text in texts)


def test_module_detail_page_allows_external_micro_app_when_allowlisted(qtbot, tmp_path):
    from src.core.persistence import get_config_store

    get_config_store().set_setting("mms.ui.allowlist", json.dumps(["demo_module"], ensure_ascii=False))

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.EXTERNAL))

    custom_page = page._menu_pages[ModuleDetailPage.MICRO_APP_MENU_ID]
    assert custom_page.__class__.__name__ == "LoadedPage"
    assert isinstance(custom_page, QLabel)
    assert custom_page.text() == "Loaded from module UI"


def test_module_detail_page_gracefully_degrades_when_custom_page_load_fails(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK, entry="ui:MissingPage"))

    custom_page = page._menu_pages[ModuleDetailPage.MICRO_APP_MENU_ID]
    texts = [label.text() for label in custom_page.findChildren(QLabel)]
    assert any("加载失败" in text or "MissingPage" in text for text in texts)


def test_module_detail_page_renders_core_managed_data_table_entry(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(
        _make_module(
            tmp_path,
            detail_menu=[
                DetailMenuItem(
                    id="accounts",
                    icon="📋",
                    label="账号管理",
                    entry="core:data_table:accounts",
                )
            ],
        )
    )

    custom_page = page._menu_pages["accounts"]
    assert custom_page.__class__.__name__ == "ModuleDataTablePage"


def test_module_detail_page_exposes_config_page_and_persists_module_and_workflow_settings(qtbot, tmp_path):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"base_url": "https://example.com"})
    store.write_workflow_settings("demo_module", "default", {"headless": False})

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch("PyQt6.QtWidgets.QMessageBox.warning"):
        page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

        menu_texts = [page.menu_list.item(i).text() for i in range(page.menu_list.count())]
        assert any("配置" in text for text in menu_texts)

        config_page = page._menu_pages["config"]
        assert isinstance(config_page.workflow_selector, StyledComboBox)
        assert "base_url: https://example.com" in config_page.module_config_editor.toPlainText()
        assert "headless: false" in config_page.workflow_config_editor.toPlainText()

        config_page.module_config_editor.setPlainText(
            "base_url: https://new.example.com\nretry: 3\n"
        )
        config_page._save_module_config()

        config_page.workflow_selector.setCurrentIndex(0)
        config_page.workflow_config_editor.setPlainText(
            "headless: true\nregion: cn\n"
        )
        config_page._save_workflow_config()

    assert store.read_module_settings("demo_module") == {
        "base_url": "https://new.example.com",
        "retry": 3,
    }
    assert store.read_workflow_settings("demo_module", "default") == {
        "headless": True,
        "region": "cn",
    }


def test_module_detail_page_saves_and_clears_repo_token(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)
    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    module.manifest.upgrade_source.repo = "example/private-repo"

    infos: list[str] = []
    with patch("PyQt6.QtWidgets.QMessageBox.information", lambda *args: infos.append(args[2])):
        page.set_module(module)

        assert page.repo_token_status_label is not None
        assert page.repo_token_status_label.text() == "未配置"

        page.repo_token_edit.setText("ghp_secret_token_1234")
        page._save_repo_token()

        assert page.repo_token_status_label.text() == "已配置"
        assert get_github_credential_store().get_token("example/private-repo") == "ghp_secret_token_1234"

    with patch(
        "PyQt6.QtWidgets.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    ), patch("PyQt6.QtWidgets.QMessageBox.information", lambda *args: infos.append(args[2])):
        page._clear_repo_token()

    assert page.repo_token_status_label.text() == "未配置"
    assert get_github_credential_store().get_token("example/private-repo") is None
    assert any("已保存仓库 example/private-repo 的 GitHub Token" in message for message in infos)
    assert any("已清除仓库 example/private-repo 的 GitHub Token" in message for message in infos)


def test_module_detail_page_config_page_uses_resizable_70_30_splitter(qtbot, tmp_path):
    page = ModuleDetailPage()
    page.resize(1280, 900)
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    page._select_menu("config")
    page.show()

    config_page = page._menu_pages["config"]
    qtbot.waitUntil(lambda: sum(config_page.config_splitter.sizes()) > 0)

    sizes = config_page.config_splitter.sizes()
    total = sum(sizes)

    assert isinstance(config_page.config_splitter, QSplitter)
    assert config_page.config_splitter.handleWidth() == 8
    assert total > 0
    assert 0.62 <= sizes[0] / total <= 0.78
    assert sizes[0] > sizes[1]


def test_module_detail_page_config_editors_hide_vertical_scrollbars(qtbot, tmp_path):
    page = ModuleDetailPage()
    qtbot.addWidget(page)

    page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    config_page = page._menu_pages["config"]

    assert (
        config_page.module_config_editor.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert (
        config_page.workflow_config_editor.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )


def test_module_detail_page_rejects_json_literal_in_config_editors(qtbot, tmp_path):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"base_url": "https://example.com"})
    store.write_workflow_settings("demo_module", "default", {"headless": False})

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch("PyQt6.QtWidgets.QMessageBox.warning") as warning:
        page.set_module(_make_module(tmp_path, source=ModuleSource.DEV_LINK))

        config_page = page._menu_pages["config"]
        config_page.module_config_editor.setPlainText('{"base_url": "https://bad.example.com"}')
        config_page._save_module_config()
        config_page.workflow_config_editor.setPlainText('{"headless": true}')
        config_page._save_workflow_config()

    assert warning.call_count == 2
    assert store.read_module_settings("demo_module") == {
        "base_url": "https://example.com",
    }
    assert store.read_workflow_settings("demo_module", "default") == {
        "headless": False,
    }


def test_module_detail_page_restores_default_settings_after_warning_confirmation(qtbot, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    page = ModuleDetailPage()
    qtbot.addWidget(page)

    module = _make_module(
        tmp_path,
        source=ModuleSource.DEV_LINK,
        config_defaults=ConfigDefaultsInfo(
            module={"base_url": "https://example.com", "retry": 3},
            workflows={"default": {"headless": False, "region": "cn"}},
        ),
    )

    with patch("PyQt6.QtWidgets.QMessageBox.information"), patch(
        "PyQt6.QtWidgets.QMessageBox.warning",
        side_effect=[
            QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Yes,
        ],
    ):
        page.set_module(module)
        config_page = page._menu_pages["config"]

        store.write_module_settings("demo_module", {"base_url": "https://custom.example.com", "retry": 9})
        store.write_workflow_settings("demo_module", "default", {"headless": True, "region": "us"})
        config_page._reload_editors()

        config_page._restore_module_defaults()
        assert store.read_module_settings("demo_module") == {
            "base_url": "https://custom.example.com",
            "retry": 9,
        }

        config_page._restore_module_defaults()
        assert store.read_module_settings("demo_module") == {
            "base_url": "https://example.com",
            "retry": 3,
        }

        config_page._restore_workflow_defaults()
        assert store.read_workflow_settings("demo_module", "default") == {
            "headless": False,
            "region": "cn",
        }
