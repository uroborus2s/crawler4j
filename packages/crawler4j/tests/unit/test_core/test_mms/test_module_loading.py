import json
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from crawler4j_sdk import EnvSelectorInfo
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, UIExtensionInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import ModuleService
from src.core.mms.ui_loader import ModuleCustomPageLoader, ModuleUILoadError


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _write_module_files(module_dir: Path, *, init_body: str, ui_body: str) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(init_body, encoding="utf-8")
    (module_dir / "ui.py").write_text(ui_body, encoding="utf-8")


def _make_ui_module(
    tmp_path: Path,
    *,
    source: ModuleSource,
    entry: str = "ui:LoadedPage",
    ui_body: str | None = None,
) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    _write_module_files(
        module_dir,
        init_body="VALUE = 'demo'\n",
        ui_body=ui_body
        or (
            "from PyQt6.QtWidgets import QLabel\n\n"
            "class LoadedPage(QLabel):\n"
            "    def __init__(self):\n"
            "        super().__init__('Loaded from module UI')\n"
        ),
    )
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(
            name="demo_module",
            display_name="Demo Module",
            ui_extension=UIExtensionInfo(type="micro_app", entry=entry),
        ),
        source=source,
        path=module_dir,
    )


def test_module_custom_page_loader_reloads_external_ui_after_file_change(temp_data_dir, qtbot):
    from src.core.persistence import get_config_store

    module = _make_ui_module(temp_data_dir, source=ModuleSource.EXTERNAL)
    get_config_store().set_setting("mms.ui.allowlist", json.dumps([module.name], ensure_ascii=False))
    loader = ModuleCustomPageLoader()

    try:
        first = loader.load_widget(module, "ui:LoadedPage")
        qtbot.addWidget(first)
        assert first.text() == "Loaded from module UI"

        (Path(module.path) / "ui.py").write_text(
            "from PyQt6.QtWidgets import QLabel\n\n"
            "class LoadedPage(QLabel):\n"
            "    def __init__(self):\n"
            "        super().__init__('Reloaded external UI')\n",
            encoding="utf-8",
        )

        second = loader.load_widget(module, "ui:LoadedPage")
        qtbot.addWidget(second)
        assert second.text() == "Reloaded external UI"
    finally:
        purge_module_namespace(module.name)


def test_module_custom_page_loader_surfaces_constructor_typeerror(temp_data_dir, qtbot):
    module = _make_ui_module(
        temp_data_dir,
        source=ModuleSource.DEV_LINK,
        entry="ui:BrokenPage",
        ui_body=(
            "from PyQt6.QtWidgets import QLabel\n\n"
            "class BrokenPage(QLabel):\n"
            "    def __init__(self, module=None):\n"
            "        if module is not None:\n"
            "            raise TypeError('bug inside constructor')\n"
            "        super().__init__('fallback')\n"
        ),
    )
    loader = ModuleCustomPageLoader()

    try:
        with pytest.raises(ModuleUILoadError, match="bug inside constructor"):
            loader.load_widget(module, "ui:BrokenPage")
    finally:
        purge_module_namespace(module.name)


def test_module_service_list_env_selectors_reloads_dev_link_source_without_context(temp_data_dir):
    module_dir = temp_data_dir / ModuleSource.DEV_LINK.value / "selector_module"
    _write_module_files(
        module_dir,
        init_body=(
            "from crawler4j_sdk import EnvSelectorInfo\n\n"
            "class _Assembler:\n"
            "    def list_env_selectors(self):\n"
            "        return [EnvSelectorInfo(name='pick_ready', display_name='Ready')]\n\n"
            "assembler = _Assembler()\n"
        ),
        ui_body="from PyQt6.QtWidgets import QLabel\n",
    )
    module = ModuleInfo(
        name="selector_module",
        manifest=ModuleManifest(name="selector_module"),
        source=ModuleSource.DEV_LINK,
        path=module_dir,
    )
    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: module if name in {module.name, module.name.split('.')[0]} else None
    )

    try:
        first = service.list_env_selectors(module.name)
        assert [selector.name for selector in first] == ["pick_ready"]
        assert first[0] == EnvSelectorInfo(name="pick_ready", display_name="Ready")

        (module_dir / "__init__.py").write_text(
            "from crawler4j_sdk import EnvSelectorInfo\n\n"
            "class _Assembler:\n"
            "    def list_env_selectors(self):\n"
            "        return [EnvSelectorInfo(name='pick_fresh', display_name='Fresh')]\n\n"
            "assembler = _Assembler()\n",
            encoding="utf-8",
        )

        second = service.list_env_selectors(module.name)
        assert [selector.name for selector in second] == ["pick_fresh"]
        assert second[0] == EnvSelectorInfo(name="pick_fresh", display_name="Fresh")
    finally:
        purge_module_namespace(module.name)
