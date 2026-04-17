from __future__ import annotations

import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from crawler4j_sdk import TaskContext
from src.core.mms.models import DevModuleLink, ModuleSource
from src.core.mms.registry import ModuleRegistry
from src.core.mms.service import ModuleService


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        stack.enter_context(patch("src.core.mms.registry.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


class _FakeDevLinkStore:
    def __init__(self, links: list[DevModuleLink] | None = None):
        self._links = {link.module_name: link for link in links or []}
        self.deleted_names: list[str] = []

    def list_links(self) -> list[DevModuleLink]:
        return list(self._links.values())

    def delete_link(self, module_name: str) -> bool:
        existed = module_name in self._links
        if existed:
            self.deleted_names.append(module_name)
            self._links.pop(module_name, None)
        return existed


def _build_module_archive(
    root: Path,
    *,
    package_dir_name: str,
    module_name: str,
    version: str = "1.0.0",
    extra_files: dict[str, str] | None = None,
) -> Path:
    package_root = root / package_dir_name
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "module.yaml").write_text(
        "name: {module_name}\n"
        "version: {version}\n"
        "upgrade_source:\n"
        "  type: github_release\n"
        "  repo: example/{module_name}\n".format(
            module_name=module_name,
            version=version,
        ),
        encoding="utf-8",
    )
    (package_root / "__init__.py").write_text(
        "from crawler4j_contracts import TaskResult\n\n"
        "def run(context):\n"
        f"    return TaskResult.ok(module='{module_name}', source='external')\n",
        encoding="utf-8",
    )
    for relative_path, content in (extra_files or {}).items():
        file_path = package_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    archive_path = root / f"{package_dir_name}-{version}.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for file_path in package_root.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, arcname=str(file_path.relative_to(root)))
    return archive_path


@pytest.mark.asyncio
async def test_registry_installs_packaged_module_and_module_service_runs_it(temp_data_dir):
    archive = _build_module_archive(
        temp_data_dir,
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    module = registry.install(archive)

    assert module.name == "demo_module"
    assert module.source == ModuleSource.EXTERNAL
    assert module.path == temp_data_dir / "modules" / "demo_module_pkg"

    service = ModuleService()
    service.registry = registry
    result = await service.run_module("demo_module", TaskContext(env_id=1, task_name="demo_module", config={}))

    assert result.success is True
    assert result.data["module"] == "demo_module"
    assert result.data["source"] == "external"

    assert registry.uninstall("demo_module") is True
    assert registry.get_module("demo_module") is None


@pytest.mark.asyncio
async def test_installing_packaged_module_removes_same_name_dev_link_and_uses_installed_path(temp_data_dir):
    archive = _build_module_archive(
        temp_data_dir,
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
    )
    dev_source = temp_data_dir / "demo_module_dev"
    dev_source.mkdir(parents=True, exist_ok=True)
    (dev_source / "module.yaml").write_text(
        "name: demo_module\n"
        "version: 9.9.9\n"
        "upgrade_source:\n"
        "  type: github_release\n"
        "  repo: example/demo_module\n",
        encoding="utf-8",
    )
    (dev_source / "__init__.py").write_text("VALUE = 'dev'\n", encoding="utf-8")
    dev_store = _FakeDevLinkStore(
        [
            DevModuleLink(
                module_name="demo_module",
                source_path=str(dev_source),
            )
        ]
    )

    registry = ModuleRegistry(dev_link_store=dev_store)
    module = registry.install(archive)

    assert module.source == ModuleSource.EXTERNAL
    assert dev_store.deleted_names == ["demo_module"]

    service = ModuleService()
    service.registry = registry
    module_obj = service._load_module(
        "demo_module",
        TaskContext(env_id=1, task_name="demo_module", config={}),
    )

    assert Path(module_obj.__file__).resolve() == (temp_data_dir / "modules" / "demo_module_pkg" / "__init__.py").resolve()


def test_zip_upgrade_replaces_existing_module_without_leaving_stale_files(temp_data_dir):
    first_archive = _build_module_archive(
        temp_data_dir / "v1",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"obsolete.py": "OLD = True\n"},
    )
    second_archive = _build_module_archive(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.1.0",
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    registry.install(first_archive)
    module = registry.install(second_archive)

    assert module.manifest.version == "1.1.0"
    assert module.path == temp_data_dir / "modules" / "demo_module_pkg"
    assert not (module.path / "obsolete.py").exists()
