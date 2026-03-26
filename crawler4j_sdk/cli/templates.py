"""CLI scaffolding templates."""

SCRIPT_TEMPLATE = '''"""任务脚本: {display_name}

{description}
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class {class_name}(TaskScript):
    """{display_name}"""

    name = "{name}"
    display_name = "{display_name}"
    description = "{description}"

    default_config = {{
        "start_url": "https://example.com",
    }}

    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行任务。"""
        start_url = ctx.get_config("start_url", "https://example.com")
        ctx.logger.info(f"开始执行任务，目标地址: {{start_url}}")

        if not ctx.page:
            return TaskResult.fail(
                message="当前运行环境没有可用的浏览器 Page",
                error="page_not_available",
            )

        await ctx.page.goto(start_url, wait_until="domcontentloaded")
        title = await ctx.page.title()
        result = {{
            "url": ctx.page.url,
            "title": title,
        }}
        ctx.captured_data.append(result)

        return TaskResult.ok(
            tasks_completed=1,
            message="任务完成",
            data=result,
        )

    async def on_error(self, ctx: TaskContext, error: Exception) -> None:
        """错误处理。"""
        ctx.logger.error(f"任务出错: {{error}}")
        if ctx.page:
            await ctx.screenshot("error_{name}")
'''

MODEL_PROJECT_PYPROJECT = '''[project]
name = "{project_name}"
version = "0.1.0"
description = "{display_name} 模块项目"
requires-python = ">=3.12"
dependencies = [
    "crawler4j-sdk>=1.0.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
'''

MODEL_PROJECT_README = '''# {display_name}

这是一个完整的 Crawler4j 模块项目，包含：

- `module.yaml` 模块清单
- `tasks/` 任务脚本
- `workflows/` 工作流
- `config_schema.json` 配置 UI

## 安装

```bash
uv sync
```

## 常用命令

```bash
# 创建任务脚本
uv run crawler4j add

# 创建工作流
uv run crawler4j add-workflow sync_orders

# 创建/补齐配置 UI
uv run crawler4j add-ui
```

## 调试

CLI 不再生成 `debug_runner.py`。当前调试主路径是由 Core 发起真实调试会话，再让 IDE 附加。

当模块已经被应用扫描，或已经注册为开发链接模块后，可以在 ATM 中对关联作业发起任务调试：

1. 在 `任务监控` 里找到对应作业，点击 `🐞 调试`
2. 确认调试参数
3. 点击 `生成 VS Code 配置`
4. 点击 `开始调试` 后，再从 VS Code 执行 `Attach to Crawler4j`
'''

MODEL_MODULE_INIT = '''"""{display_name} 模块入口。"""

from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from crawler4j_sdk import TaskContext, TaskFlow, TaskResult, TaskScript


PACKAGE_ROOT = Path(__file__).parent
DEFAULT_WORKFLOW = "{default_workflow}"


def _load_registry(subpackage: str, base_cls: type) -> dict[str, type]:
    registry: dict[str, type] = {{}}
    package_dir = PACKAGE_ROOT / subpackage
    if not package_dir.exists():
        return registry

    package_name = f"{{__name__}}.{{subpackage}}"
    for module_info in iter_modules([str(package_dir)]):
        if module_info.name.startswith("_"):
            continue
        module = import_module(f"{{package_name}}.{{module_info.name}}")
        for attr_name in dir(module):
            candidate = getattr(module, attr_name)
            if isinstance(candidate, type) and issubclass(candidate, base_cls) and candidate is not base_cls:
                key = getattr(candidate, "name", "") or module_info.name
                registry[key] = candidate
    return registry


TASK_SCRIPTS: dict[str, type[TaskScript]] = _load_registry("tasks", TaskScript)
WORKFLOWS: dict[str, type[TaskFlow]] = _load_registry("workflows", TaskFlow)


async def _run_task_script(script_cls: type[TaskScript], ctx: TaskContext) -> TaskResult:
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


async def _run_task_flow(flow_cls: type[TaskFlow], ctx: TaskContext) -> TaskResult:
    flow = flow_cls()
    try:
        await flow.run(ctx)
        await flow.on_complete(ctx)
    except Exception as error:
        await flow.on_error(ctx, error)
        raise
    return TaskResult.ok(data=dict(ctx.state))


async def _subtask_executor(task_name: str, ctx: TaskContext) -> TaskResult:
    if task_name not in TASK_SCRIPTS:
        raise ValueError(f"Unknown subtask: {{task_name}}")
    return await _run_task_script(TASK_SCRIPTS[task_name], ctx)


async def run(context: TaskContext) -> TaskResult:
    workflow_name = context.get_config("workflow", DEFAULT_WORKFLOW)

    if workflow_name in WORKFLOWS:
        context._subtask_executor = _subtask_executor
        return await _run_task_flow(WORKFLOWS[workflow_name], context)

    if workflow_name in TASK_SCRIPTS:
        return await _run_task_script(TASK_SCRIPTS[workflow_name], context)

    if DEFAULT_WORKFLOW and DEFAULT_WORKFLOW in WORKFLOWS:
        context.logger.warning(
            f"[{module_name}] Unknown workflow '{{workflow_name}}', fallback to '{{DEFAULT_WORKFLOW}}'."
        )
        context._subtask_executor = _subtask_executor
        return await _run_task_flow(WORKFLOWS[DEFAULT_WORKFLOW], context)

    raise ValueError(f"Unknown workflow or task: {{workflow_name}}")


async def prepare_env(context: TaskContext):
    creation_params = dict(context.get_config("creation_params", {{}}) or {{}})
    if not creation_params:
        return None
    return {{"creation_params": creation_params}}


async def init_env(context: TaskContext):
    start_url = context.get_config("start_url")
    if context.page and start_url:
        await context.page.goto(start_url, wait_until="domcontentloaded")
        context.logger.info(f"[{module_name}] init_env opened: {{start_url}}")


async def before_run(context: TaskContext):
    context.logger.info(f"[{module_name}] before_run")


async def on_success(context: TaskContext, result):
    context.logger.info(f"[{module_name}] on_success: {{result}}")


async def on_failure(context: TaskContext, error: Exception):
    context.logger.error(f"[{module_name}] on_failure: {{error}}")
    if context.page:
        try:
            await context.screenshot("{module_name}_failure")
        except Exception:
            pass


async def on_timeout(context: TaskContext):
    context.logger.warning(f"[{module_name}] on_timeout")


async def on_cleanup(context: TaskContext):
    context.logger.info(f"[{module_name}] on_cleanup")
'''

MODEL_MANIFEST_TEMPLATE = '''name: {module_name}
version: 1.0.0
display_name: {display_name}
description: {description}
author: crawler4j
sdk_version_range: ">=1.0.0"
{ui_section}workflows:
  - name: {workflow_name}
    display_name: {workflow_display_name}
    description: {workflow_description}
'''

MODEL_UI_SECTION = '''ui_extension:
  type: declarative
  entry: config_schema.json
  nav_item:
    icon: "🧩"
    label: "{display_name}配置"

'''

CONFIG_SCHEMA_TEMPLATE = '''{{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "title": "{title}",
  "description": "{description}",
  "properties": {{
    "workflow": {{
      "type": "string",
      "title": "工作流名称",
      "default": "{workflow_name}"
    }},
    "start_url": {{
      "type": "string",
      "title": "起始 URL",
      "default": "https://example.com"
    }},
    "headless": {{
      "type": "boolean",
      "title": "无头模式",
      "default": false
    }},
    "max_pages": {{
      "type": "integer",
      "title": "最大页数",
      "default": 1,
      "minimum": 1,
      "maximum": 100
    }}
  }}
}}
'''

WORKFLOW_TEMPLATE = '''"""工作流: {display_name}

{description}
"""

from crawler4j_sdk import TaskContext, TaskFlow


class {class_name}(TaskFlow):
    """{display_name}"""

    name = "{name}"
    display_name = "{display_name}"
    description = "{description}"

    async def run(self, ctx: TaskContext) -> None:
        """执行工作流。"""
        ctx.state["phase"] = "{name}"
        await ctx.run_subtask("example_task")
'''
