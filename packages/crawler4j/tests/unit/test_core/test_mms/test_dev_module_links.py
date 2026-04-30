from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _write_module(module_dir: Path, name: str, version: str) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "module.yaml").write_text(
        "name: {name}\n"
        "runtime_api: core-native-v2\n"
        "version: {version}\n"
        "upgrade_source:\n"
        "  type: github_release\n"
        "  repo: example/{name}\n".format(name=name, version=version),
        encoding="utf-8",
    )
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    for package_name in ("interfaces", "objects", "workflows", "tasks", "data"):
        package_dir = module_dir / package_name
        package_dir.mkdir(exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "workflows" / "default.py").write_text(
        "from crawler4j_contracts import workflow\n\n"
        "@workflow(name='default')\n"
        "class DefaultWorkflow:\n"
        "    pass\n",
        encoding="utf-8",
    )


def test_registry_prefers_dev_link_over_scanned_module(temp_data_dir):
    from src.core.mms.models import ModuleSource
    from src.core.mms.registry import ModuleRegistry
    from src.core.mms.scanner import ModuleScanner

    builtin_root = temp_data_dir / "builtin"
    builtin_module = builtin_root / "demo_module"
    dev_module = temp_data_dir / "demo_module_dev"
    _write_module(builtin_module, "demo_module", "1.0.0")
    _write_module(dev_module, "demo_module", "9.9.9")

    registry = ModuleRegistry(scanner=ModuleScanner(scan_paths=[builtin_root]))

    module = registry.register_dev_link(dev_module)

    assert module.source == ModuleSource.DEV_LINK
    assert module.path == dev_module
    assert module.manifest.version == "9.9.9"


def test_registry_keeps_invalid_dev_link_when_source_disappears(temp_data_dir):
    from src.core.mms.models import ModuleSource, ModuleStatus
    from src.core.mms.registry import ModuleRegistry
    from src.core.mms.scanner import ModuleScanner

    builtin_root = temp_data_dir / "builtin"
    dev_module = temp_data_dir / "demo_module_dev"
    _write_module(dev_module, "demo_module", "1.0.0")

    registry = ModuleRegistry(scanner=ModuleScanner(scan_paths=[builtin_root]))
    registry.register_dev_link(dev_module)

    (dev_module / "module.yaml").unlink()
    registry.refresh()

    module = registry.get_module("demo_module")
    assert module is not None
    assert module.source == ModuleSource.DEV_LINK
    assert module.status == ModuleStatus.INVALID
    assert "module.yaml" in module.error


def test_registry_updates_existing_dev_link_for_same_module_name(temp_data_dir):
    from src.core.mms.registry import ModuleRegistry
    from src.core.mms.scanner import ModuleScanner

    builtin_root = temp_data_dir / "builtin"
    first_dev = temp_data_dir / "demo_module_dev_1"
    second_dev = temp_data_dir / "demo_module_dev_2"
    _write_module(first_dev, "demo_module", "1.0.0")
    _write_module(second_dev, "demo_module", "2.0.0")

    registry = ModuleRegistry(scanner=ModuleScanner(scan_paths=[builtin_root]))

    registry.register_dev_link(first_dev)
    module = registry.register_dev_link(second_dev)

    assert module.path == second_dev
    assert module.manifest.version == "2.0.0"
    assert len(registry.list_dev_links()) == 1


def test_registry_can_remove_dev_link(temp_data_dir):
    from src.core.mms.registry import ModuleRegistry
    from src.core.mms.scanner import ModuleScanner

    builtin_root = temp_data_dir / "builtin"
    dev_module = temp_data_dir / "demo_module_dev"
    _write_module(dev_module, "demo_module", "1.0.0")

    registry = ModuleRegistry(scanner=ModuleScanner(scan_paths=[builtin_root]))
    registry.register_dev_link(dev_module)

    assert registry.remove_dev_link("demo_module") is True
    assert registry.get_module("demo_module") is None
    assert registry.list_dev_links() == []


def test_registry_falls_back_to_installed_module_after_removing_dev_link(temp_data_dir):
    from src.core.mms.models import ModuleSource
    from src.core.mms.registry import ModuleRegistry
    from src.core.mms.scanner import ModuleScanner

    external_root = temp_data_dir / "external"
    external_module = external_root / "demo_module"
    dev_module = temp_data_dir / "demo_module_dev"
    _write_module(external_module, "demo_module", "1.0.0")
    _write_module(dev_module, "demo_module", "9.9.9")

    registry = ModuleRegistry(scanner=ModuleScanner(scan_paths=[external_root]))
    registry.register_dev_link(dev_module)

    assert registry.get_module("demo_module").source == ModuleSource.DEV_LINK

    assert registry.remove_dev_link("demo_module") is True

    module = registry.get_module("demo_module")
    assert module is not None
    assert module.source == ModuleSource.EXTERNAL
    assert module.path == external_module
    assert module.manifest.version == "1.0.0"
