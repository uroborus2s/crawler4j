import pytest
import logging
import sys
import yaml
import importlib
from textwrap import dedent
from unittest.mock import MagicMock, AsyncMock

from crawler4j_sdk.assembler import ModuleAssembler
from crawler4j_sdk.cli.templates import MODEL_MODULE_INIT
from crawler4j_sdk.context import TaskContext

@pytest.fixture
def temp_module(tmp_path):
    module_dir = tmp_path / "test_module"
    module_dir.mkdir()
    (module_dir / "tasks").mkdir()
    (module_dir / "workflows").mkdir()
    (module_dir / "__init__.py").touch()
    
    # Add to sys.path
    sys.path.append(str(tmp_path))
    yield module_dir
    sys.path.remove(str(tmp_path))
    # Cleanup sys.modules to avoid side effects between tests
    for mod in list(sys.modules.keys()):
        if mod.startswith("test_module"):
            del sys.modules[mod]

def create_mock_context():
    ctx = MagicMock(spec=TaskContext)
    ctx.runtime = {}
    ctx.config = {}
    ctx.get_config.return_value = None
    ctx.state = {}
    ctx.logger = logging.getLogger("test")
    ctx.run_subtask = AsyncMock(return_value={"data": "mocked"})
    return ctx


def write_managed_root_module(module_dir):
    (module_dir / "__init__.py").write_text(
        MODEL_MODULE_INIT.format(display_name="Test Module"),
        encoding="utf-8",
    )

@pytest.mark.asyncio
async def test_assembler_discovery(temp_module):
    # 1. Create a task
    task_code = """
from crawler4j_sdk import TaskScript, TaskResult

class MyTask(TaskScript):
    name = "my_task"
    async def execute(self, ctx):
        return TaskResult.ok(data={"status": "task_done"})
"""
    (temp_module / "tasks" / "my_task.py").write_text(task_code)
    (temp_module / "tasks" / "__init__.py").touch()

    # 2. Create a workflow
    flow_code = """
from crawler4j_sdk import TaskFlow

class MyFlow(TaskFlow):
    name = "my_flow"
    async def run(self, ctx):
        await ctx.run_subtask("my_task")
"""
    (temp_module / "workflows" / "my_flow.py").write_text(flow_code)
    (temp_module / "workflows" / "__init__.py").touch()

    # 3. Assemble
    assembler = ModuleAssembler(temp_module, "test_module", default_workflow="my_flow")
    
    assert "my_task" in assembler.task_scripts
    assert "my_flow" in assembler.workflows

    # 4. Run
    ctx = create_mock_context()
    ctx.runtime["workflow"] = "my_flow"
    
    result = await assembler.run(ctx)
    assert result.success is True
    assert ctx._subtask_executor is not None
    
    # Verify subtask executor works
    sub_result = await ctx._subtask_executor("my_task", ctx)
    assert sub_result.success is True
    assert sub_result.data == {"status": "task_done"}

@pytest.mark.asyncio
async def test_assembler_runtime_hooks(temp_module):
    # Create module_runtime.py
    runtime_code = """
from crawler4j_sdk import TaskContext

async def prepare_env(ctx):
    ctx.state["prepared"] = True

async def on_cleanup(ctx):
    ctx.state["cleaned"] = True
"""
    (temp_module / "module_runtime.py").write_text(runtime_code)
    
    # Create a simple task to run
    task_code = """
from crawler4j_sdk import TaskScript, TaskResult
class SimpleTask(TaskScript):
    name = "simple"
    async def execute(self, ctx):
        return TaskResult.ok()
"""
    (temp_module / "tasks" / "simple.py").write_text(task_code)
    (temp_module / "tasks" / "__init__.py").touch()

    assembler = ModuleAssembler(temp_module, "test_module", default_workflow="simple")
    
    ctx = create_mock_context()
    ctx.runtime["workflow"] = "simple"
    
    # Test internal calling (though it's not strictly what run() does anymore, 
    # we can check get_hook)
    prepare_hook = assembler.get_hook("prepare_env")
    assert prepare_hook is not None
    await prepare_hook(ctx)
    assert ctx.state.get("prepared") is True

@pytest.mark.asyncio
async def test_assembler_runtime_overrides(temp_module):
    # Create module_runtime.py that overrides DEFAULT_WORKFLOW
    runtime_code = """
DEFAULT_WORKFLOW = "overridden_task"

from crawler4j_sdk import TaskScript, TaskResult
class OverriddenTask(TaskScript):
    name = "overridden_task"
    async def execute(self, ctx):
        return TaskResult.ok(data={"status": "overridden"})

TASK_SCRIPTS = {"overridden_task": OverriddenTask}
"""
    (temp_module / "module_runtime.py").write_text(runtime_code)
    
    assembler = ModuleAssembler(temp_module, "test_module", default_workflow="should_be_overridden")
    
    assert assembler.default_workflow == "overridden_task"
    assert "overridden_task" in assembler.task_scripts

    ctx = create_mock_context()
    # No explicit workflow in config, should use default
    ctx.get_config.return_value = None
    
    result = await assembler.run(ctx)
    assert result.success is True
    assert result.data == {"status": "overridden"}


@pytest.mark.asyncio
async def test_assembler_ignores_legacy_config_workflow_field(temp_module):
    flow_default_code = """
from crawler4j_sdk import TaskFlow, TaskResult

class DefaultFlow(TaskFlow):
    name = "default_flow"
    async def run(self, ctx):
        return TaskResult.ok(data={"workflow": "default"})
"""
    flow_runtime_code = """
from crawler4j_sdk import TaskFlow, TaskResult

class LegacyConfigFlow(TaskFlow):
    name = "legacy_config_flow"
    async def run(self, ctx):
        return TaskResult.ok(data={"workflow": "legacy_config"})
"""
    (temp_module / "workflows" / "default_flow.py").write_text(flow_default_code)
    (temp_module / "workflows" / "legacy_config_flow.py").write_text(flow_runtime_code)
    (temp_module / "workflows" / "__init__.py").touch()

    assembler = ModuleAssembler(temp_module, "test_module", default_workflow="default_flow")

    ctx = TaskContext(
        env_id=1,
        task_name="test_task",
        config={"workflow": "legacy_config_flow"},
        runtime={},
    )

    result = await assembler.run(ctx)

    assert result.success is True
    assert result.data == {"workflow": "default"}


@pytest.mark.asyncio
async def test_assembler_discovers_env_selectors(temp_module):
    runtime_code = """
from crawler4j_sdk import env_selector

@env_selector("return_none", display_name="返回 None", returns_none=True)
async def return_none_selector(context, candidates):
    return None

@env_selector("random_ready", display_name="随机选择就绪环境")
async def random_ready_selector(context, candidates):
    return candidates[0].env_id if candidates else None
"""
    (temp_module / "module_runtime.py").write_text(runtime_code)

    assembler = ModuleAssembler(temp_module, "test_module", default_workflow="noop")

    selectors = assembler.list_env_selectors()

    assert [selector.name for selector in selectors] == ["random_ready", "return_none"]
    assert selectors[1].returns_none is True

    ctx = create_mock_context()
    chosen = await assembler.run_env_selector(
        "random_ready",
        ctx,
        [MagicMock(env_id=23)],
    )
    assert chosen == 23

@pytest.mark.asyncio
async def test_assembler_manifest_loading(temp_module):
    # Create module.yaml
    manifest = {
        "name": "test_module",
        "upgrade_source": {
            "type": "github_release",
            "repo": "example/test_module",
        },
        "workflows": [
            {"name": "manifest_wf", "display_name": "Manifest Workflow"}
        ]
    }
    (temp_module / "module.yaml").write_text(yaml.dump(manifest))
    
    # Create the workflow
    flow_code = """
from crawler4j_sdk import TaskFlow
class ManifestFlow(TaskFlow):
    name = "manifest_wf"
    async def run(self, ctx): pass
"""
    (temp_module / "workflows" / "manifest_wf.py").write_text(flow_code)
    (temp_module / "workflows" / "__init__.py").touch()

    # Assemble without explicit default_workflow
    assembler = ModuleAssembler(temp_module, "test_module")
    
    assert assembler.default_workflow == "manifest_wf"
    assert "manifest_wf" in assembler.workflows

@pytest.mark.asyncio
async def test_managed_root_module_delegates_hooks_and_runtime_attributes(temp_module):
    write_managed_root_module(temp_module)
    assert (temp_module / "__init__.py").read_text(encoding="utf-8") == MODEL_MODULE_INIT.format(
        display_name="Test Module"
    )
    (temp_module / "module_runtime.py").write_text(
        dedent(
            """
            RUNTIME_FLAG = "runtime-visible"

            async def prepare_env(ctx, *args):
                ctx.state["prepare_env_args"] = list(args)
                return {"hook": "called", "args": list(args)}
            """
        ).strip()
        + "\n"
    )

    module = importlib.import_module("test_module")
    ctx = create_mock_context()

    assert await module.prepare_env(ctx, "demo") == {
        "hook": "called",
        "args": ["demo"],
    }
    assert ctx.state["prepare_env_args"] == ["demo"]
    assert await module.on_cleanup(ctx, "ignored") is None
    assert module.RUNTIME_FLAG == "runtime-visible"


@pytest.mark.asyncio
async def test_assembler_logs_import_failure_and_surfaces_discovery_hint(temp_module, caplog):
    broken_task_code = """
import definitely_missing_dep
from crawler4j_sdk import TaskScript

class BrokenTask(TaskScript):
    name = "broken"
"""
    (temp_module / "tasks" / "broken.py").write_text(broken_task_code)
    (temp_module / "tasks" / "__init__.py").touch()

    with caplog.at_level(logging.ERROR):
        assembler = ModuleAssembler(temp_module, "test_module", default_workflow="broken")

    assert "broken" not in assembler.task_scripts
    assert "test_module.tasks.broken" in caplog.text
    assert "definitely_missing_dep" in caplog.text

    ctx = create_mock_context()
    ctx.get_config.return_value = "broken"

    with pytest.raises(ValueError, match="definitely_missing_dep"):
        await assembler.run(ctx)
