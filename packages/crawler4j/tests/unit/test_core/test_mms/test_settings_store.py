from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.mms.models import ModuleStatus
from src.core.mms.registry import ModuleRegistry
from src.core.mms.scanner import ModuleScanner


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        stack.enter_context(patch("src.core.mms.registry.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


class _FakeDevLinkStore:
    def list_links(self) -> list[object]:
        return []

    def delete_link(self, module_name: str) -> bool:  # noqa: ARG002
        return False


def _write_module(root: Path, name: str = "demo_module") -> Path:
    module_dir = root / name
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "module.yaml").write_text(
        f"name: {name}\nversion: 1.0.0\nsdk_version_range: \">=1.0.2\"\n",
        encoding="utf-8",
    )
    (module_dir / "__init__.py").write_text("VALUE = 'demo'\n", encoding="utf-8")
    return module_dir


def test_settings_store_reads_writes_and_exports_module_and_workflow_settings(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    store.write_module_settings("demo_module", {"api_key": "secret", "enabled": True})
    store.write_workflow_settings("demo_module", "login", {"headless": False})
    store.write_workflow_settings("demo_module", "search", {"limit": 10})

    assert store.read_module_settings("demo_module") == {"api_key": "secret", "enabled": True}
    assert store.read_workflow_settings("demo_module", "login") == {"headless": False}
    assert store.read_workflow_settings("demo_module", "search") == {"limit": 10}
    assert store.export_module_settings("demo_module") == {
        "module": {"api_key": "secret", "enabled": True},
        "workflows": {
            "login": {"headless": False},
            "search": {"limit": 10},
        },
    }


def test_settings_store_returns_empty_module_settings_without_persisted_record(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    assert store.read_module_settings("demo_module") == {}


def test_registry_persists_module_status_across_reload(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    scan_root = temp_data_dir / "scan_root"
    _write_module(scan_root)
    store = ModuleSettingsStore()

    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )

    assert registry.get_module("demo_module").status == ModuleStatus.ENABLED
    assert registry.disable_module("demo_module") is True

    reloaded = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert reloaded.get_module("demo_module").status == ModuleStatus.DISABLED

    assert reloaded.enable_module("demo_module") is True
    enabled_again = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert enabled_again.get_module("demo_module").status == ModuleStatus.ENABLED


def test_uninstall_clears_settings_by_default_and_can_keep_them(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    scan_root = temp_data_dir / "scan_root"
    _write_module(scan_root)
    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"api_key": "secret"})
    store.write_workflow_settings("demo_module", "login", {"headless": False})

    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert registry.uninstall("demo_module") is True
    assert store.export_module_settings("demo_module") == {"module": {}, "workflows": {}}

    _write_module(scan_root)
    store.write_module_settings("demo_module", {"api_key": "secret"})
    store.write_workflow_settings("demo_module", "login", {"headless": False})
    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )

    assert registry.uninstall("demo_module", keep_settings=True) is True
    assert store.export_module_settings("demo_module") == {
        "module": {"api_key": "secret"},
        "workflows": {"login": {"headless": False}},
    }
