import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from crawler4j_sdk import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest
from src.core.mms.service import ModuleService


def _write_module_package(module_dir: Path, name: str) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(
        "from crawler4j_contracts import TaskResult\n\n"
        "def run(context):\n"
        f"    return TaskResult.ok(message='ok', module='{name}')\n\n"
        "def prepare_env(context):\n"
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
            manifest=ModuleManifest(name="example_module"),
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
            manifest=ModuleManifest(name="example_module"),
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
    module_dir.mkdir()
    (module_dir / "helpers.py").write_text(
        "from crawler4j_contracts import TaskResult\n\n"
        "def build_result(name: str) -> TaskResult:\n"
        "    return TaskResult.ok(module=name)\n",
        encoding="utf-8",
    )
    (module_dir / "__init__.py").write_text(
        "from .helpers import build_result\n\n"
        "def run(context):\n"
        "    return build_result('demo_module')\n",
        encoding="utf-8",
    )

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="demo_module",
            manifest=ModuleManifest(name="demo_module"),
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
    module_dir.mkdir()

    def write_module(version: int) -> None:
        (module_dir / "__init__.py").write_text(
            f"VERSION = {version}\n",
            encoding="utf-8",
        )

    write_module(1)

    service = ModuleService()
    service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=ModuleManifest(name=module_name),
            path=module_dir,
        )
    )

    try:
        context_a = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        module_v1 = service._load_module(module_name, context_a)
        assert module_v1.VERSION == 1

        time.sleep(1.1)
        write_module(2)

        module_same_context = service._load_module(module_name, context_a)
        assert module_same_context is module_v1
        assert module_same_context.VERSION == 1

        context_b = TaskContext(env_id=0, task_name=module_name, runtime={"devel_mode": True})
        module_v2 = service._load_module(module_name, context_b)
        assert module_v2.VERSION == 2
    finally:
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
                sys.modules.pop(loaded_name, None)
