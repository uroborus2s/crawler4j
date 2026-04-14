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
        "    creation_params = context.get_config('creation_params')\n"
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
        config={"creation_params": {"name_prefix": "hooked"}},
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
