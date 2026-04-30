from __future__ import annotations

import hashlib
import json
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
    return (
        dedent(
            f"""
        name: {module_name}
        runtime_api: core-native-v2
        version: {version}
        upgrade_source:
          type: github_release
          repo: example/{module_name}
        """
        ).strip()
        + "\n"
    )


def _task_file(module_name: str) -> str:
    return (
        dedent(
            f"""
        from crawler4j_contracts import TaskContext, TaskResult, page_action


        @page_action(name="external_task", label="External Task")
        async def external_task(context: TaskContext):
            return TaskResult.ok(module="{module_name}", source="external")
        """
        ).strip()
        + "\n"
    )


WORKFLOW_FILE = (
    dedent(
        """
    from crawler4j_contracts import TaskContext, TaskResult, workflow


    @workflow(name="default")
    class DefaultWorkflow:
        async def run(self, context: TaskContext):
            return TaskResult.ok(
                module=context.runtime.get("module_name", "demo_module"),
                source="external",
            )
    """
    ).strip()
    + "\n"
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_lock_files(package_root: Path) -> list[Path]:
    ignored_dirs = {
        ".git",
        ".idea",
        ".venv",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
    }
    files: list[Path] = []
    for path in package_root.rglob("*"):
        relative = path.relative_to(package_root)
        relative_posix = relative.as_posix()
        if any(part in ignored_dirs or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_dir() or path.suffix in {".pyc", ".pyo"}:
            continue
        if relative_posix == ".crawler4j/manifest.lock.json" or path.name == ".DS_Store":
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(package_root).as_posix())


def _write_manifest_lock(package_root: Path, *, module_name: str, version: str) -> None:
    lock_dir = package_root / ".crawler4j"
    lock_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "runtime_api": "core-native-v2",
        "module": module_name,
        "version": version,
        "declarations": [
            {
                "kind": "workflow",
                "name": "default",
                "symbol": "workflows.default.DefaultWorkflow",
                "source_path": "workflows/default.py",
                "metadata": {"name": "default"},
            }
        ],
        "files": [
            {
                "path": path.relative_to(package_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _hash_file(path),
            }
            for path in _iter_lock_files(package_root)
        ],
    }
    (lock_dir / "manifest.lock.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _archive_package(root: Path, package_root: Path, archive_name: str) -> Path:
    archive_path = root / archive_name
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w") as zf:
        archive_files = {file_path for file_path in package_root.rglob("*") if file_path.is_file()}
        for file_path in sorted(archive_files, key=lambda item: item.relative_to(package_root).as_posix()):
            zf.write(file_path, arcname=str(file_path.relative_to(root)))
    return archive_path


def _build_module_dir(
    root: Path,
    *,
    package_dir_name: str,
    module_name: str,
    version: str = "1.0.0",
    extra_files: dict[str, str] | None = None,
    write_lock: bool = True,
) -> Path:
    package_root = root / package_dir_name
    data_dir = package_root / "data"
    interfaces_dir = package_root / "interfaces"
    objects_dir = package_root / "objects"
    pages_dir = package_root / "pages"
    tasks_dir = package_root / "tasks"
    workflows_dir = package_root / "workflows"
    for package_dir in (package_root, data_dir, interfaces_dir, objects_dir, pages_dir, tasks_dir, workflows_dir):
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
    if write_lock:
        _write_manifest_lock(package_root, module_name=module_name, version=version)
    return package_root


def _build_module_archive(
    root: Path,
    *,
    package_dir_name: str,
    module_name: str,
    version: str = "1.0.0",
    extra_files: dict[str, str] | None = None,
    write_lock: bool = True,
) -> Path:
    package_root = _build_module_dir(
        root,
        package_dir_name=package_dir_name,
        module_name=module_name,
        version=version,
        extra_files=dict(extra_files or {}),
        write_lock=write_lock,
    )

    return _archive_package(root, package_root, f"{package_dir_name}-{version}.zip")


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
    result = await service.run_module(
        "demo_module",
        TaskContext(env_id=1, task_name="demo_module", config={}, runtime={"module_name": "demo_module"}),
    )

    assert result.success is True
    assert result.data["module"] == "demo_module"
    assert result.data["source"] == "external"

    assert registry.uninstall("demo_module") is True
    assert registry.get_module("demo_module") is None


def test_install_rejects_missing_manifest_lock(temp_data_dir):
    archive = _build_module_archive(
        temp_data_dir,
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        write_lock=False,
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())

    with pytest.raises(ModuleInstallError, match="缺少 manifest lock"):
        registry.install(archive)


def test_install_rejects_stale_manifest_lock_file_hashes(temp_data_dir):
    package_root = _build_module_dir(
        temp_data_dir,
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
    )
    (package_root / "tasks" / "tampered.py").write_text("# unlocked file\n", encoding="utf-8")
    archive = _archive_package(temp_data_dir, package_root, "demo_module_pkg-1.0.0.zip")

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())

    with pytest.raises(ModuleInstallError, match="文件完整性校验失败"):
        registry.install(archive)


def test_install_rejects_zip_path_traversal(temp_data_dir):
    archive = temp_data_dir / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "escape")

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())

    with pytest.raises(ModuleInstallError, match="非法路径"):
        registry.install(archive)


def test_registry_syncs_v2_data_decorators_to_manifest_data(temp_data_dir):
    archive = _build_module_archive(
        temp_data_dir,
        package_dir_name="demo_module_pkg",
        module_name="demo_module",
        extra_files={
            "data/accounts.py": """
from crawler4j_contracts import data_query, data_table


@data_table(
    name="accounts",
    schema=[{"name": "account_id", "type": "string", "required": True}],
    indexes=[{"fields": ["account_id"], "unique": True}],
)
class Accounts:
    pass


@data_query(
    name="ready_accounts",
    source="accounts",
    sql="SELECT account_id FROM {{resource:accounts}}",
    output_schema=[{"name": "account_id", "type": "string"}],
)
def ready_accounts():
    pass
""",
        },
    )

    registry = ModuleRegistry(dev_link_store=_FakeDevLinkStore())
    module = registry.install(archive)

    assert module.manifest.data["resources"][0]["resource_id"] == "accounts"
    assert module.manifest.data["resources"][0]["record_key_field"] == "account_id"
    assert module.manifest.data["queries"][0]["query_id"] == "ready_accounts"
    assert module.manifest.data["queries"][0]["sql"] == "SELECT account_id FROM {{resource:accounts}}"


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
    descriptor = service.get_runtime_descriptor_v2(
        "demo_module",
        TaskContext(env_id=1, task_name="demo_module", config={}),
    )

    task_file = Path(descriptor.page_actions["external_task"].target.__globals__["__file__"]).resolve()
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

    with pytest.raises(ModuleInstallError, match="broken module"):
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

    with pytest.raises(ModuleInstallError, match="broken copied module"):
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

    with pytest.raises(ModuleInstallError, match="broken migrated module"):
        registry.install(bad_archive)

    current = registry.get_module("demo_module")
    assert current is not None
    assert current.manifest.version == "1.0.0"
    assert current.path == legacy_dir
    assert legacy_dir.exists()
    assert not (temp_data_dir / "modules" / "demo_module").exists()
    assert (current.path / "stable.py").exists()
