from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler4j_contracts import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, UpgradeSourceInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import ModuleService


def _manifest(name: str, *, runtime_api: str = "core-native-v2") -> ModuleManifest:
    return ModuleManifest(
        name=name,
        runtime_api=runtime_api,
        upgrade_source=UpgradeSourceInfo(repo=f"example/{name}"),
    )


def _write_v2_module_package(module_dir: Path, workflow_source: str) -> None:
    for package_dir in (
        module_dir,
        module_dir / "interfaces",
        module_dir / "objects",
        module_dir / "workflows",
        module_dir / "tasks",
        module_dir / "data",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (module_dir / "workflows" / "main_workflow.py").write_text(workflow_source, encoding="utf-8")


def _write_v2_module_package_with_files(module_dir: Path, files: dict[str, str]) -> None:
    for package_dir in (
        module_dir,
        module_dir / "interfaces",
        module_dir / "objects",
        module_dir / "workflows",
        module_dir / "tasks",
        module_dir / "data",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for relative_path, content in files.items():
        file_path = module_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")


def _workflow_source(module_name: str, version: int = 1) -> str:
    return (
        "from crawler4j_contracts import TaskContext, TaskResult, workflow\n\n"
        "@workflow(name='main_workflow')\n"
        "class MainWorkflow:\n"
        "    async def run(self, context: TaskContext):\n"
        f"        return TaskResult.ok(module='{module_name}', version={version})\n"
    )


def _service_for_module(module_name: str, module_dir: Path, *, source: ModuleSource = ModuleSource.BUILTIN):
    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=_manifest(module_name),
            path=module_dir,
            source=source,
        )
    )
    return service


@pytest.mark.asyncio
async def test_module_service_runs_core_native_v2_workflow(tmp_path):
    module_name = "example_module"
    module_dir = tmp_path / module_name
    _write_v2_module_package(module_dir, _workflow_source(module_name))

    service = _service_for_module(module_name, module_dir)
    ctx = TaskContext(env_id=1, task_name=module_name, config={})
    result = await service.run_module(module_name, ctx)

    assert result.success is True
    assert result.data == {"module": module_name, "version": 1}


@pytest.mark.asyncio
async def test_module_service_injects_run_page_action_for_v2_workflows(tmp_path):
    module_name = "workflow_page_action_module"
    module_dir = tmp_path / module_name
    _write_v2_module_package_with_files(
        module_dir,
        {
            "tasks/open_login.py": (
                "from crawler4j_contracts import TaskContext, page_action\n\n"
                "@page_action(name='open_login_page')\n"
                "async def open_login_page(ctx: TaskContext, url: str):\n"
                "    ctx.state['opened_url'] = url\n"
                "    return {'opened': url}\n"
            ),
            "workflows/main_workflow.py": (
                "from crawler4j_contracts import TaskContext, TaskResult, workflow\n\n"
                "@workflow(name='main_workflow')\n"
                "class MainWorkflow:\n"
                "    async def run(self, ctx: TaskContext):\n"
                "        payload = await ctx.run_page_action('open_login_page', url='https://example.com/login')\n"
                "        return TaskResult.ok(action_payload=payload, opened_url=ctx.state.get('opened_url'))\n"
            ),
        },
    )

    service = _service_for_module(module_name, module_dir)
    ctx = TaskContext(env_id=1, task_name=module_name, config={})
    result = await service.run_module(module_name, ctx)

    assert result.success is True
    assert result.data == {
        "action_payload": {"opened": "https://example.com/login"},
        "opened_url": "https://example.com/login",
    }


@pytest.mark.asyncio
async def test_module_service_rejects_legacy_runtime_api(tmp_path):
    module_name = "legacy_module"
    module_dir = tmp_path / module_name
    _write_v2_module_package(module_dir, _workflow_source(module_name))

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=_manifest(module_name, runtime_api="core-native-v1"),
            path=module_dir,
        )
    )

    with pytest.raises(ValueError, match="Only core-native-v2 modules are executable"):
        await service.run_module(module_name, TaskContext(env_id=1, task_name=module_name, config={}))


@pytest.mark.asyncio
async def test_module_service_reloads_dev_module_once_per_context(tmp_path):
    module_name = "reloadable_module"
    module_dir = tmp_path / module_name
    _write_v2_module_package(module_dir, _workflow_source(module_name, version=1))

    service = _service_for_module(module_name, module_dir, source=ModuleSource.DEV_LINK)

    try:
        context_a = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        first = await service.run_module(module_name, context_a)
        assert first.data["version"] == 1

        time.sleep(1.1)
        _write_v2_module_package(module_dir, _workflow_source(module_name, version=2))

        same_context = await service.run_module(module_name, context_a)
        assert same_context.data["version"] == 1

        context_b = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        refreshed = await service.run_module(module_name, context_b)
        assert refreshed.data["version"] == 2
    finally:
        purge_module_namespace(module_name)
