"""Module Assembler for Crawler4j modules.

This module provides the ModuleAssembler class which handles automatic discovery
of tasks and workflows within a module, and provides a standardized entry point.
"""

import importlib
import inspect
import logging
from pathlib import Path
from pkgutil import iter_modules
from typing import Callable, Dict, Optional, Type

import yaml

from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.context import TaskContext
from crawler4j_sdk.result import TaskResult
from crawler4j_sdk.workflow import TaskFlow

logger = logging.getLogger(__name__)


class ModuleAssembler:
    """Handles discovery and execution of module components."""

    def __init__(self, package_root: Path, module_name: str, default_workflow: str = ""):
        self.package_root = package_root
        self.module_name = module_name
        self.default_workflow = default_workflow
        self.task_scripts: Dict[str, Type[TaskScript]] = {}
        self.workflows: Dict[str, Type[TaskFlow]] = {}

        # Hooks that can be overridden by module_runtime.py
        self.hooks: Dict[str, Callable] = {}

        self._load_manifest()
        self._discover()
        self._load_runtime_extensions()

    def _load_manifest(self):
        """Load default_workflow from module.yaml if not set."""
        manifest_path = self.package_root / "module.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = yaml.safe_load(f)
                    if manifest and not self.default_workflow:
                        workflows = manifest.get("workflows", [])
                        if workflows and isinstance(workflows, list):
                            self.default_workflow = workflows[0].get("name", "")
            except Exception as e:
                logger.warning(f"Failed to load manifest at {manifest_path}: {e}")

    def _load_registry(self, subpackage: str, base_cls: type) -> Dict[str, type]:
        registry: Dict[str, type] = {}
        package_dir = self.package_root / subpackage
        if not package_dir.exists():
            return registry

        full_package_name = f"{self.module_name}.{subpackage}"
        for module_info in iter_modules([str(package_dir)]):
            if module_info.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"{full_package_name}.{module_info.name}")
                for attr_name in dir(module):
                    candidate = getattr(module, attr_name)
                    if (
                        inspect.isclass(candidate)
                        and issubclass(candidate, base_cls)
                        and candidate is not base_cls
                    ):
                        key = getattr(candidate, "name", "") or module_info.name
                        registry[key] = candidate
            except Exception:
                continue
        return registry

    def _discover(self):
        """Automatically discover tasks and workflows."""
        self.task_scripts = self._load_registry("tasks", TaskScript)
        self.workflows = self._load_registry("workflows", TaskFlow)

    def _load_runtime_extensions(self):
        """Load optional module_runtime.py extensions."""
        runtime_path = self.package_root / "module_runtime.py"
        if runtime_path.exists():
            try:
                runtime_module = importlib.import_module(f"{self.module_name}.module_runtime")

                # Load hooks if present
                hook_names = [
                    "prepare_env",
                    "init_env",
                    "before_run",
                    "on_success",
                    "on_failure",
                    "on_timeout",
                    "on_cleanup",
                ]
                for name in hook_names:
                    if hasattr(runtime_module, name):
                        self.hooks[name] = getattr(runtime_module, name)

                # Allow overriding default_workflow
                if hasattr(runtime_module, "DEFAULT_WORKFLOW"):
                    self.default_workflow = getattr(runtime_module, "DEFAULT_WORKFLOW")

                # Allow manual registration/override of tasks/workflows
                if hasattr(runtime_module, "TASK_SCRIPTS"):
                    self.task_scripts.update(getattr(runtime_module, "TASK_SCRIPTS"))
                if hasattr(runtime_module, "WORKFLOWS"):
                    self.workflows.update(getattr(runtime_module, "WORKFLOWS"))

            except Exception as e:
                logger.warning(f"Failed to load runtime extensions: {e}")

    async def _run_task_script(self, script_cls: Type[TaskScript], ctx: TaskContext) -> TaskResult:
        script = script_cls()
        await script.on_init(ctx)
        try:
            result = await script.execute(ctx)
        except Exception as error:
            await script.on_error(ctx, error)
            raise
        finally:
            await script.on_cleanup(ctx)

        if isinstance(result, TaskResult):
            return result
        return TaskResult.ok(data=result)

    async def _run_task_flow(self, flow_cls: Type[TaskFlow], ctx: TaskContext) -> TaskResult:
        flow = flow_cls()
        try:
            await flow.run(ctx)
            await flow.on_complete(ctx)
        except Exception as error:
            await flow.on_error(ctx, error)
            raise
        return TaskResult.ok(data=dict(ctx.state))

    async def _subtask_executor(self, task_name: str, ctx: TaskContext) -> TaskResult:
        if task_name not in self.task_scripts:
            raise ValueError(f"Unknown subtask: {task_name}")
        return await self._run_task_script(self.task_scripts[task_name], ctx)

    async def run(self, context: TaskContext) -> TaskResult:
        """Module execution entry point."""
        workflow_name = context.get_config("workflow", self.default_workflow) or self.default_workflow

        if workflow_name in self.workflows:
            context._subtask_executor = self._subtask_executor
            return await self._run_task_flow(self.workflows[workflow_name], context)

        if workflow_name in self.task_scripts:
            return await self._run_task_script(self.task_scripts[workflow_name], context)

        raise ValueError(f"Workflow or task not found: {workflow_name}")

    def get_hook(self, name: str) -> Optional[Callable]:
        """Get a registered hook by name."""
        return self.hooks.get(name)
