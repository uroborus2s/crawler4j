from __future__ import annotations

import zipfile
from contextlib import ExitStack
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

from crawler4j_contracts import TaskContext
from src.core.mms.models import DevModuleLink, ModuleInstallError, ModuleSource
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


def _module_yaml(module_name: str, version: str) -> str:
    return dedent(
        f"""
        name: {module_name}
        runtime_api: core-native-v1
        version: {version}
        upgrade_source:
          type: github_release
          repo: example/{module_name}
        default_workflow: default
        workflows:
          - name: default
            display_name: Default
            description: Default workflow
        data:
          resources: []
          views: []
          queries: []
          seeds: []
        """
    ).strip() + "\n"


def _task_file(module_name: str) -> str:
    return dedent(
        f"""
        from crawler4j_contracts import TaskResult, TaskSpec

        TASK = TaskSpec(name="external_task", display_name="External Task")


        async def execute(context):
            return TaskResult.ok(module="{module_name}", source="external")
        """
    ).strip() + "\n"


WORKFLOW_FILE = dedent(
    """
    from crawler4j_contracts import WorkflowSpec

    WORKFLOW = WorkflowSpec(name="default", tasks=("external_task",))


    async def run(context):
        return await context.run_subtask("external_task")
    """
).strip() + "\n"


def _build_module_dir(
    root: Path,
    *,
    package_dir_name: str,
    module_name: str,
    version: str = "1.0.0",
    extra_files: dict[str, str] | None = None,
) -> Path:
    package_root = root / package_dir_name
    tasks_dir = package_root / "tasks"
    workflows_dir = package_root / "workflows"
    for package_dir in (package_root, tasks_dir, workflows_dir):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    extras = dict(extra_files or {})
    init_source = extras.pop("__init__.py", None)
    if init_source is None:
        init_source = ""
    (package_root / "__init__.py").write_text(init_source, encoding="utf-8")
    (package_root / "module.yaml").write_text(_module_yaml(module_name, version), encoding="utf-8")
    (tasks_dir / "external_task.py").write_text(_task_file(module_name), encoding="utf-8")
    (workflows_dir / "default.py").write_text(WORKFLOW_FILE, encoding="utf-8")

    for relative_path, content in extras.items():
        file_path = package_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    return package_root


def _build_module_archive(
    root: Path,
    *,
    package_dir_name: str,
    module_name: str,
    version: str = "1.0.0",
    extra_files: dict[str, str] | None = None,
) -> Path:
    package_root = _build_module_dir(
        root,
        package_dir_name=package_dir_name,
        module_name=module_name,
        version=version,
        extra_files=dict(extra_files or {}),
    )

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
    assert module.path == temp_data_dir / "modules" / "demo_module"

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
    dev_source = _build_module_dir(
        temp_data_dir,
        package_dir_name="demo_module_dev",
        module_name="demo_module",
        version="9.9.9",
    )
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
    descriptor = service.get_runtime_descriptor(
        "demo_module",
        TaskContext(env_id=1, task_name="demo_module", config={}),
    )

    task_file = Path(descriptor.tasks["external_task"].execute.__globals__["__file__"]).resolve()
    assert task_file == (temp_data_dir / "modules" / "demo_module" / "tasks" / "external_task.py").resolve()


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
    assert module.path == temp_data_dir / "modules" / "demo_module"
    assert not (module.path / "obsolete.py").exists()


def test_zip_upgrade_reuses_existing_install_dir_when_zip_root_changes(temp_data_dir):
    first_archive = _build_module_archive(
        temp_data_dir / "v1",
        package_dir_name="demo_module_pkg_v1",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"obsolete.py": "OLD = True\n"},
    )
    second_archive = _build_module_archive(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg_v2",
        module_name="demo_module",
        version="1.1.0",
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    first_module = registry.install(first_archive)
    upgraded = registry.install(second_archive)

    assert upgraded.manifest.version == "1.1.0"
    assert upgraded.path == first_module.path
    assert upgraded.path == temp_data_dir / "modules" / "demo_module"
    assert upgraded.path.exists()
    assert not (upgraded.path / "obsolete.py").exists()
    assert not (temp_data_dir / "modules" / "demo_module_pkg_v1").exists()
    assert not (temp_data_dir / "modules" / "demo_module_pkg_v2").exists()


def test_zip_upgrade_migrates_legacy_non_canonical_install_dir(temp_data_dir):
    legacy_dir = _build_module_dir(
        temp_data_dir / "modules",
        package_dir_name="demo_module_pkg_v1",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"obsolete.py": "OLD = True\n"},
    )
    second_archive = _build_module_archive(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg_v2",
        module_name="demo_module",
        version="1.1.0",
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    registry.load(force=True)
    upgraded = registry.install(second_archive)

    assert upgraded.manifest.version == "1.1.0"
    assert upgraded.path == temp_data_dir / "modules" / "demo_module"
    assert upgraded.path.exists()
    assert not legacy_dir.exists()
    assert not (upgraded.path / "obsolete.py").exists()
    assert not (temp_data_dir / "modules" / "demo_module_pkg_v2").exists()


def test_zip_upgrade_rolls_back_when_new_package_fails_import(temp_data_dir):
    first_archive = _build_module_archive(
        temp_data_dir / "v1",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"stable.py": "STABLE = True\n"},
    )
    bad_archive = _build_module_archive(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.1.0",
        extra_files={"__init__.py": "raise RuntimeError('broken module')\n"},
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    registry.install(first_archive)

    with pytest.raises(ModuleInstallError, match="模块导入预检失败"):
        registry.install(bad_archive)

    current = registry.get_module("demo_module")
    assert current is not None
    assert current.manifest.version == "1.0.0"
    assert current.path == temp_data_dir / "modules" / "demo_module"
    assert (current.path / "stable.py").exists()
    assert "broken module" not in (current.path / "__init__.py").read_text(encoding="utf-8")


def test_dir_install_rolls_back_when_copied_module_fails_import(temp_data_dir):
    first_dir = _build_module_dir(
        temp_data_dir / "v1",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"stable.py": "STABLE = True\n"},
    )
    bad_dir = _build_module_dir(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        version="1.1.0",
        extra_files={"__init__.py": "raise RuntimeError('broken copied module')\n"},
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    registry.install(first_dir)

    with pytest.raises(ModuleInstallError, match="模块导入预检失败"):
        registry.install(bad_dir)

    current = registry.get_module("demo_module")
    assert current is not None
    assert current.manifest.version == "1.0.0"
    assert current.path == temp_data_dir / "modules" / "demo_module"
    assert (current.path / "stable.py").exists()


def test_zip_upgrade_rolls_back_to_legacy_dir_when_canonical_migration_fails(temp_data_dir):
    legacy_dir = _build_module_dir(
        temp_data_dir / "modules",
        package_dir_name="demo_module_pkg_v1",
        module_name="demo_module",
        version="1.0.0",
        extra_files={"stable.py": "STABLE = True\n"},
    )
    bad_archive = _build_module_archive(
        temp_data_dir / "v2",
        package_dir_name="demo_module_pkg_v2",
        module_name="demo_module",
        version="1.1.0",
        extra_files={"__init__.py": "raise RuntimeError('broken migrated module')\n"},
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    registry.load(force=True)

    with pytest.raises(ModuleInstallError, match="模块导入预检失败"):
        registry.install(bad_archive)

    current = registry.get_module("demo_module")
    assert current is not None
    assert current.manifest.version == "1.0.0"
    assert current.path == legacy_dir
    assert legacy_dir.exists()
    assert not (temp_data_dir / "modules" / "demo_module").exists()
    assert (current.path / "stable.py").exists()
