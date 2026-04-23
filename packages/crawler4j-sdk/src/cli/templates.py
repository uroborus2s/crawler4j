"""CLI scaffolding templates."""

from __future__ import annotations


SCRIPT_TEMPLATE = '''"""任务脚本: {display_name}

{description}
"""

from crawler4j_contracts import TaskContext, TaskResult, TaskSpec

TASK = TaskSpec(
    name="{name}",
    display_name="{display_name}",
    description="{description}",
    default_config={{
        "start_url": "https://example.com",
    }},
)


async def execute(ctx: TaskContext) -> TaskResult:
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
    "{contracts_dependency_spec}",
]

[dependency-groups]
dev = [
    "{sdk_dependency_spec}",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
'''

MODEL_PROJECT_README = '''# {display_name}

这是一个 `core-native-v1` 协议模块项目，核心文件如下：

- `module.yaml`: 模块清单与 `runtime_api` 声明。
- `tasks/`: 原子任务，一个文件导出一个 `TASK` 与 `execute(ctx)`。
- `workflows/`: 工作流，一个文件导出一个 `WORKFLOW` 与 `run(ctx)`。
- `hooks/`: 生命周期 Hook，一个文件导出一个 `handle(...)`。
- `env_selectors/`: 环境选择器，一个文件导出一个 `SELECTOR` 与 `select(ctx, candidates)`。
- `pages/`: Hosted UI 页面，一个文件导出一个 `PAGE` 与页面处理函数。

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

# 创建环境选择器
uv run crawler4j env-selector create pick_ready

# 重建某个 Hook 骨架
uv run crawler4j hook create on_cleanup --force

# 完整校验并打包
uv run crawler4j check full
uv run crawler4j package build
```

## 运行边界

- 模块运行时只依赖 `crawler4j-contracts`。
- `crawler4j-sdk` 只作为 CLI / 校验 / 开发辅助存在。
- Core 会自行扫描目录生成运行时 descriptor，不会调用模块根 `run()` 或 `declare_ui()`。
'''

MODEL_TEST_TASK_TEMPLATE = '''"""测试任务脚本。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from crawler4j_contracts import TaskContext
from tasks.example_task import execute


@pytest.mark.asyncio
async def test_example_task_logic():
    ctx = MagicMock(spec=TaskContext)
    ctx.get_config.return_value = "https://mock.url"
    ctx.logger = MagicMock()
    ctx.page = MagicMock()
    ctx.page.goto = AsyncMock()
    ctx.page.title = AsyncMock(return_value="Mock Title")
    ctx.captured_data = []

    result = await execute(ctx)

    assert result.success is True
    assert len(ctx.captured_data) == 1
    assert result.data["title"] == "Mock Title"
    ctx.page.goto.assert_awaited_once_with("https://mock.url", wait_until="domcontentloaded")
    ctx.page.title.assert_awaited_once()
'''

MODEL_MODULE_INIT = '''"""{display_name} 模块包。

Core 会直接扫描 `tasks/`、`workflows/`、`hooks/`、`env_selectors/`、`pages/`。
模块根包不再承载运行时装配逻辑。
"""
'''

MODEL_MANIFEST_TEMPLATE = '''name: {module_name}
runtime_api: core-native-v1
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
default_workflow: {workflow_name}
workflows:
  - name: {workflow_name}
    display_name: {workflow_display_name}
    description: {workflow_description}
ui_extension:
  pages: []
'''

MODEL_HOOKS_INIT_TEMPLATE = '"""模块生命周期 Hook 集合。"""\n'
MODEL_SELECTORS_INIT_TEMPLATE = '"""环境选择器集合。"""\n'
MODEL_PAGES_INIT_TEMPLATE = '"""Hosted UI 页面集合。"""\n'

WORKFLOW_TEMPLATE = '''"""工作流: {display_name}

{description}
"""

from crawler4j_contracts import TaskContext, WorkflowSpec

WORKFLOW = WorkflowSpec(
    name="{name}",
    display_name="{display_name}",
    description="{description}",
    tasks=("example_task",),
)


async def run(ctx: TaskContext):
    """执行工作流。"""
    ctx.state["phase"] = "{name}"
    return await ctx.run_subtask("example_task")
'''

HOOK_NAMES = (
    "prepare_env",
    "init_env",
    "before_run",
    "on_success",
    "on_failure",
    "on_timeout",
    "on_cleanup",
)

_HOOK_TEMPLATE_SPECS = {
    "prepare_env": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext):",
        "body": "    return None",
    },
    "init_env": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext):",
        "body": "    return None",
    },
    "before_run": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext):",
        "body": "    return None",
    },
    "on_success": {
        "imports": "TaskContext, TaskResult",
        "signature": "async def handle(context: TaskContext, result: TaskResult):",
        "body": "    return None",
    },
    "on_failure": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext, error: Exception):",
        "body": "    return None",
    },
    "on_timeout": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext):",
        "body": "    return None",
    },
    "on_cleanup": {
        "imports": "TaskContext",
        "signature": "async def handle(context: TaskContext):",
        "body": '    _ = context.runtime.get("env_action")\n    return None',
    },
}

RETURN_NONE_SELECTOR_TEMPLATE = '''"""环境选择器: 返回 None。"""

from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(
    name="return_none",
    display_name="返回 None",
    description="占位选择器，默认直接返回 None。",
    returns_none=True,
)


def select(context: TaskContext, candidates: list[EnvCandidate]):
    """占位环境选择器。"""
    del context, candidates
    return None
'''

RANDOM_READY_SELECTOR_TEMPLATE = '''"""环境选择器: 随机选择就绪环境。"""

import random

from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(
    name="random_ready",
    display_name="随机选择就绪环境",
    description="从当前 ready 候选里随机挑选一个环境。",
)


def select(context: TaskContext, candidates: list[EnvCandidate]):
    """示例环境选择器。"""
    del context
    ready_candidates = [candidate for candidate in candidates if candidate.status == "ready"]
    if not ready_candidates:
        return None
    return random.choice(ready_candidates).env_id
'''


def render_hook_template(hook_name: str) -> str:
    spec = _HOOK_TEMPLATE_SPECS[hook_name]
    return '''"""生命周期 Hook: {hook_name}。"""

from crawler4j_contracts import {imports}


{signature}
{body}
'''.format(
        hook_name=hook_name,
        imports=spec["imports"],
        signature=spec["signature"],
        body=spec["body"],
    )


def render_selector_template(
    *,
    name: str,
    display_name: str,
    description: str,
) -> str:
    return '''"""环境选择器: {display_name}

{description}
"""

from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(
    name="{name}",
    display_name="{display_name}",
    description="{description}",
)


def select(context: TaskContext, candidates: list[EnvCandidate]):
    """{display_name}。"""
    del context
    ready_candidates = [candidate for candidate in candidates if candidate.status == "ready"]
    if not ready_candidates:
        return None
    return ready_candidates[0].env_id
'''.format(
        name=name,
        display_name=display_name,
        description=description,
    )


def render_page_template(
    *,
    page_id: str,
    display_name: str,
    description: str,
) -> str:
    return '''"""Hosted UI 页面: {display_name}

{description}
"""

from __future__ import annotations

from crawler4j_contracts import PageSpec, TaskContext

PAGE = PageSpec(
    id="{page_id}",
    label="{display_name}",
    icon="📄",
    schema={{
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
    }},
)


def load_{page_id}_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    """同步加载 `{page_id}` 页面数据。"""
    del context, page_id, params
    return {{
        "summary": "{display_name} 页面已由 core-native-v1 加载。",
        "updated_at": "待接入真实数据",
    }}
'''.format(
        page_id=page_id,
        display_name=display_name,
        description=description,
    )
