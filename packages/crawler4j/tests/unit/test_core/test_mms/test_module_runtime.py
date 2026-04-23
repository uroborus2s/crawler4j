import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler4j_contracts import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, WorkflowInfo
from src.core.mms.service import ModuleService


def _manifest(name: str, *, default_workflow: str = "main_workflow") -> ModuleManifest:
    return ModuleManifest(
        name=name,
        runtime_api="core-native-v1",
        workflows=[WorkflowInfo(name=default_workflow)],
        default_workflow=default_workflow,
    )


def _write_module_package(module_dir: Path, name: str) -> None:
    (module_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (module_dir / "workflows").mkdir(parents=True, exist_ok=True)
    (module_dir / "hooks").mkdir(parents=True, exist_ok=True)
    for package_dir in (module_dir, module_dir / "tasks", module_dir / "workflows", module_dir / "hooks"):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (module_dir / "tasks" / "example_task.py").write_text(
        "from crawler4j_contracts import TaskResult, TaskSpec\n\n"
        "TASK = TaskSpec(name='example_task', display_name='Example Task')\n\n"
        "async def execute(context):\n"
        f"    return TaskResult.ok(message='ok', module='{name}')\n",
        encoding="utf-8",
    )
    (module_dir / "workflows" / "main_workflow.py").write_text(
        "from crawler4j_contracts import WorkflowSpec\n\n"
        "WORKFLOW = WorkflowSpec(name='main_workflow', tasks=('example_task',))\n\n"
        "async def run(context):\n"
        "    return await context.run_subtask('example_task')\n",
        encoding="utf-8",
    )
    (module_dir / "hooks" / "prepare_env.py").write_text(
        "async def handle(context):\n"
        "    creation_params = context.runtime.get('creation_params')\n"
        "    if not creation_params:\n"
        "        return None\n"
        "    return {'creation_params': creation_params}\n",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_module_service_runs_example_module(tmp_path):
    module_dir = tmp_path / "example_module"
    _write_module_package(module_dir, "example_module")

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="example_module",
            manifest=_manifest("example_module"),
            path=module_dir,
        )
    )

    ctx = TaskContext(env_id=1, task_name="example_module", config={})
    result = await service.run_module("example_module", ctx)

    assert result.success is True
    assert result.data["module"] == "example_module"


@pytest.mark.asyncio
async def test_module_service_calls_optional_hook(tmp_path):
    module_dir = tmp_path / "example_module"
    _write_module_package(module_dir, "example_module")

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="example_module",
            manifest=_manifest("example_module"),
            path=module_dir,
        )
    )

    ctx = TaskContext(
        env_id=0,
        task_name="example_module",
        runtime={"creation_params": {"name_prefix": "hooked"}},
    )

    result = await service.call_hook("example_module", "prepare_env", ctx)

    assert result == {"creation_params": {"name_prefix": "hooked"}}


@pytest.mark.asyncio
async def test_module_service_loads_package_from_path_when_manifest_name_differs(tmp_path):
    module_dir = tmp_path / "demo_module_pkg"
    _write_module_package(module_dir, "demo_module")

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="demo_module",
            manifest=_manifest("demo_module"),
            path=module_dir,
        )
    )

    ctx = TaskContext(env_id=1, task_name="demo_module", config={})
    result = await service.run_module("demo_module", ctx)

    assert result.success is True
    assert result.data["module"] == "demo_module"


def test_module_service_reloads_dev_module_once_per_context(tmp_path):
    module_name = "reloadable_module"
    module_dir = tmp_path / module_name
    (module_dir / "tasks").mkdir(parents=True)
    (module_dir / "workflows").mkdir(parents=True)
    for package_dir in (module_dir, module_dir / "tasks", module_dir / "workflows"):
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    def write_module(version: int) -> None:
        (module_dir / "tasks" / "versioned.py").write_text(
            "from crawler4j_contracts import TaskResult, TaskSpec\n\n"
            "TASK = TaskSpec(name='versioned')\n"
            f"VERSION = {version}\n\n"
            "async def execute(context):\n"
            "    return TaskResult.ok(version=VERSION)\n",
            encoding="utf-8",
        )
        (module_dir / "workflows" / "main_workflow.py").write_text(
            "from crawler4j_contracts import WorkflowSpec\n\n"
            "WORKFLOW = WorkflowSpec(name='main_workflow', tasks=('versioned',))\n\n"
            "async def run(context):\n"
            "    return await context.run_subtask('versioned')\n",
            encoding="utf-8",
        )

    write_module(1)

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=_manifest(module_name),
            path=module_dir,
            source=ModuleSource.DEV_LINK,
        )
    )

    try:
        context_a = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        descriptor_v1 = service.get_runtime_descriptor(module_name, context_a)
        assert descriptor_v1.tasks["versioned"].execute.__globals__["VERSION"] == 1

        time.sleep(1.1)
        write_module(2)

        descriptor_same_context = service.get_runtime_descriptor(module_name, context_a)
        assert descriptor_same_context is descriptor_v1
        assert descriptor_same_context.tasks["versioned"].execute.__globals__["VERSION"] == 1

        context_b = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        descriptor_v2 = service.get_runtime_descriptor(module_name, context_b)
        assert descriptor_v2.tasks["versioned"].execute.__globals__["VERSION"] == 2
    finally:
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                sys.modules.pop(loaded_name, None)
