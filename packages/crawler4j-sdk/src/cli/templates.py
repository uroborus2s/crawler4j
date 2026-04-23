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

'''

MODEL_GITIGNORE_TEMPLATE = '''.DS_Store
.idea/
.vscode/
.venv/
__pycache__/
.mypy_cache/
.pytest_cache/
.ruff_cache/
build/
dist/
*.egg-info/
'''

MODEL_PROJECT_PYPROJECT = '''[project]
name = "{project_name}"
version = "{version}"
description = "{display_name} 模块项目"
requires-python = ">={python_version}"
dependencies = [
    "{sdk_dependency_spec}",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
'''

MODEL_PROJECT_README = '''# {display_name}

这是一个规范化的 Crawler4j 模块项目，核心文件如下：

- `module.yaml`: 模块清单与能力声明。
- `tasks/`: 原子任务脚本。
- `workflows/`: 工作流编排。
- `module_runtime.py`: 环境选择器、生命周期 Hook、宿主页 / 受控数据表声明。

## 常用命令

```bash
# 查看模块概况
uv run crawler4j module show

# 创建任务脚本
uv run crawler4j task create <name>

# 创建工作流
uv run crawler4j workflow create <name>

# 创建宿主页
uv run crawler4j page create dashboard

# 在宿主页里接入纯 UI DataTable 组件
# 通过 `crawler4j page create` 生成页面骨架后，在 build_<page>_page_schema 中补 DataTable

# 创建环境选择器
uv run crawler4j env-selector create pick_ready

# 完整校验并打包
uv run crawler4j check full
uv run crawler4j package build
```

## 调试

在应用中把该目录注册为“开发链接”模块后，可在 ATM 中对关联作业发起任务调试。

## 生命周期约定

- `module_runtime.py` 里的 `on_cleanup` 会在 ATM 执行计划中的环境动作前调用。
- 如果需要根据即将执行的 `recycle / keep_alive / destroy` 做收尾，可读取 `context.runtime["env_action"]`。
'''

MODEL_TEST_TASK_TEMPLATE = '''"""测试任务脚本。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from crawler4j_sdk import TaskContext
from tasks.example_task import ExampleTask


@pytest.mark.asyncio
async def test_example_task_logic():
    # 1. 准备 Mock 环境
    ctx = MagicMock(spec=TaskContext)
    ctx.get_config.return_value = "https://mock.url"
    ctx.logger = MagicMock()
    ctx.page = MagicMock()
    ctx.page.goto = AsyncMock()
    ctx.page.title = AsyncMock(return_value="Mock Title")
    ctx.captured_data = []

    # 2. 执行任务
    task = ExampleTask()
    result = await task.execute(ctx)

    # 3. 验证结果
    assert result.success is True
    assert len(ctx.captured_data) == 1
    assert result.data["title"] == "Mock Title"
    ctx.page.goto.assert_awaited_once_with("https://mock.url", wait_until="domcontentloaded")
    ctx.page.title.assert_awaited_once()
'''
MODEL_MODULE_INIT = '''"""{display_name} 模块入口。

本文件由 SDK 自动托管，不建议手动修改。
模块运行时扩展统一放在同级目录的 `module_runtime.py`。
"""

import importlib
from pathlib import Path
from crawler4j_sdk import EnvCandidate, ModuleAssembler, TaskContext, TaskResult

# 初始化模块组装器
assembler = ModuleAssembler(
    package_root=Path(__file__).parent,
    module_name=__name__,
)


async def run(context: TaskContext) -> TaskResult:
    """模块执行入口，由 Core 调用。"""
    return await assembler.run(context)


# --- 自动导出的生命周期 Hooks (由 Core 调用) ---

async def prepare_env(context, *args):
    hook = assembler.get_hook("prepare_env")
    return await hook(context, *args) if hook else None


async def init_env(context, *args):
    hook = assembler.get_hook("init_env")
    return await hook(context, *args) if hook else None


async def before_run(context, *args):
    hook = assembler.get_hook("before_run")
    return await hook(context, *args) if hook else None


async def select_env(context: TaskContext, candidates: list[EnvCandidate], selector_name: str):
    return await assembler.run_env_selector(selector_name, context, candidates)


async def on_success(context, *args):
    hook = assembler.get_hook("on_success")
    return await hook(context, *args) if hook else None


async def on_failure(context, *args):
    hook = assembler.get_hook("on_failure")
    return await hook(context, *args) if hook else None


async def on_timeout(context, *args):
    hook = assembler.get_hook("on_timeout")
    return await hook(context, *args) if hook else None


async def on_cleanup(context, *args):
    hook = assembler.get_hook("on_cleanup")
    return await hook(context, *args) if hook else None


_runtime_module = None


def _load_runtime_module():
    global _runtime_module
    if _runtime_module is None:
        _runtime_module = importlib.import_module(f"{{__name__}}.module_runtime")
    return _runtime_module


def __getattr__(name: str):
    runtime_module = _load_runtime_module()
    if hasattr(runtime_module, name):
        return getattr(runtime_module, name)
    raise AttributeError(f"module {{__name__!r}} has no attribute {{name!r}}")
'''

MODEL_RUNTIME_TEMPLATE = '''"""{display_name} 模块自定义运行时扩展。

本文件现在是模块标准组成部分，用于声明环境选择器、生命周期 Hooks、
宿主页 schema、托管数据表 schema，以及少量同步加载 / CRUD hook。
"""

import random

from crawler4j_sdk import EnvCandidate, TaskContext, TaskResult, env_selector

# 默认工作流覆盖 (可选)
# DEFAULT_WORKFLOW = "my_custom_workflow"

# 手动注册/覆盖组件 (可选)
# TASK_SCRIPTS = {{}}
# WORKFLOWS = {{}}


@env_selector(
    name="return_none",
    display_name="返回 None",
    description="占位选择器，默认直接返回 None。",
    returns_none=True,
)
def return_none_selector(context: TaskContext, candidates: list[EnvCandidate]):
    """占位环境选择器。"""
    return None


@env_selector(
    name="random_ready",
    display_name="随机选择就绪环境",
    description="从当前 ready 候选里随机挑选一个环境。",
)
def random_ready_selector(context: TaskContext, candidates: list[EnvCandidate]):
    """示例环境选择器。"""
    ready_candidates = [candidate for candidate in candidates if candidate.status == "ready"]
    if not ready_candidates:
        return None
    return random.choice(ready_candidates).env_id


async def prepare_env(context: TaskContext):
    """环境准备 Hook (在执行任何任务前调用)。"""
    pass


async def init_env(context: TaskContext):
    """环境初始化 Hook (在环境准备后、任务执行前调用)。"""
    pass


async def before_run(context: TaskContext):
    """主执行前 Hook (在模块 run 之前调用)。"""
    pass


async def on_success(context: TaskContext, result: TaskResult):
    """成功 Hook。"""
    pass


async def on_failure(context: TaskContext, error: Exception):
    """失败 Hook。"""
    pass


async def on_timeout(context: TaskContext):
    """超时 Hook。"""
    pass


async def on_cleanup(context: TaskContext):
    """最终清理 Hook。

    注意：该 Hook 会在 ATM 执行环境动作前触发。
    如需根据计划中的 recycle / keep_alive / destroy 做收尾，可读取
    `context.runtime["env_action"]`。
    """
    pass


def declare_ui(context: TaskContext):
    """声明 Hosted UI 元数据。

    `crawler4j page create <page_id>` 会把宿主页声明插到这个函数里。
    """
    # SDK-DATA-TABLES
    return None
'''

MODEL_MANIFEST_TEMPLATE = '''name: {module_name}
version: {version}
display_name: {display_name}
description: {description}
author: crawler4j
upgrade_source:
  type: github_release
  repo: {repo}
  allow_prerelease: false
config_defaults:
  module: {{}}
  workflows: {{}}
workflows:
  - name: {workflow_name}
    display_name: {workflow_display_name}
    description: {workflow_description}
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

ENV_SELECTOR_TEMPLATE = '''

@env_selector(
    name="{name}",
    display_name="{display_name}",
    description="{description}",
)
def {function_name}(context: TaskContext, candidates: list[EnvCandidate]):
    """{display_name}。"""
    ready_candidates = [candidate for candidate in candidates if candidate.status == "ready"]
    if not ready_candidates:
        return None
    return ready_candidates[0].env_id
'''

PAGE_HELPER_TEMPLATE = '''

def _declare_{page_id}_page(context: TaskContext):
    """声明 `{page_id}` 宿主页。"""
    if not context.tools or not context.tools.has_tool("ui.declare_page"):
        return None

    return context.tools.call(
        "ui.declare_page",
        page_id="{page_id}",
        schema=build_{page_id}_page_schema(),
    )


def build_{page_id}_page_schema() -> dict:
    """构造 `{page_id}` 宿主页 schema。"""
    return {{
        "type": "Page",
        "title": "{display_name}",
        "load_handler": "load_{page_id}_page",
        "layout": {{"direction": "column", "gap": 16}},
        "children": [
            {{
                "type": "Section",
                "variant": "plain",
                "children": [
                    {{"type": "Text", "style": "title", "text": "{display_name}"}},
                    {{"type": "Text", "style": "subtitle", "text": "{description}"}},
                    {{"type": "Button", "label": "刷新", "action": {{"type": "reload"}}}},
                ],
            }},
            {{
                "type": "Section",
                "title": "页面状态",
                "variant": "card",
                "children": [
                    {{"type": "Text", "style": "body", "binding": "summary"}},
                    {{"type": "Text", "style": "meta", "binding": "updated_at"}},
                ],
            }},
        ],
    }}


def load_{page_id}_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    """同步加载 `{page_id}` 页面数据。"""
    del page_id, params
    return {{
        "summary": "{display_name} 页面已由 hosted page V1 加载。",
        "updated_at": "待接入真实数据",
    }}
'''
