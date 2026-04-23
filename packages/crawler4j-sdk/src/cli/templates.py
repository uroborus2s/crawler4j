"""CLI scaffolding templates."""

from __future__ import annotations


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
- `module_runtime.py`: 宿主接缝薄壳，只负责把 `pages/`、`hooks/`、`env_selectors/` 暴露给宿主。
- `pages/`: Hosted UI 页面，一页一个文件。
- `hooks/`: 生命周期 Hook，一类 Hook 一个文件。
- `env_selectors/`: 环境选择器，一个选择器一个文件。
- `tasks/`: 原子任务脚本。
- `workflows/`: 工作流编排。

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

# 在页面 schema 里接入纯 UI DataTable 组件
# 通过 `crawler4j page create` 生成页面骨架后，在 pages/<page>.py 中补 DataTable

# 创建环境选择器
uv run crawler4j env-selector create pick_ready

# 重建某个 Hook 骨架
uv run crawler4j hook create on_cleanup --force

# 完整校验并打包
uv run crawler4j check full
uv run crawler4j package build
```

## 调试

在应用中把该目录注册为“开发链接”模块后，可在 ATM 中对关联作业发起任务调试。

## 生命周期约定

- `module_runtime.py` 只保留宿主接缝薄壳；真正的 Hook 实现在 `hooks/` 下。
- `hooks/on_cleanup.py` 会在 ATM 执行计划中的环境动作前调用。
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
模块运行时扩展统一由同级 `module_runtime.py` 暴露，真正实现拆在
`pages/`、`hooks/`、`env_selectors/` 目录下。
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

MODEL_RUNTIME_TEMPLATE = '''"""{display_name} 模块宿主接缝层。

本文件保持为薄壳。
- 页面实现放在 `pages/`
- 生命周期 Hook 放在 `hooks/`
- 环境选择器放在 `env_selectors/`
"""

from __future__ import annotations

import importlib
from typing import Any

from crawler4j_sdk import TaskContext

_hooks = importlib.import_module(f"{{__package__}}.hooks")
_pages = importlib.import_module(f"{{__package__}}.pages")
_env_selectors = importlib.import_module(f"{{__package__}}.env_selectors")

# 默认工作流覆盖 (可选)
# DEFAULT_WORKFLOW = "my_custom_workflow"

# 手动注册/覆盖组件 (可选)
# TASK_SCRIPTS = {{}}
# WORKFLOWS = {{}}

_DYNAMIC_EXPORTS = tuple(_hooks.__all__) + tuple(_pages.__all__) + tuple(_env_selectors.__all__)


def declare_ui(context: TaskContext):
    """声明 Hosted UI 元数据。"""
    return _pages.declare_pages(context)


def __getattr__(name: str) -> Any:
    for namespace in (_hooks, _pages, _env_selectors):
        if hasattr(namespace, name):
            return getattr(namespace, name)
    raise AttributeError(f"module {{__name__!r}} has no attribute {{name!r}}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_DYNAMIC_EXPORTS) | {{"declare_ui"}})
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

MODEL_HOOKS_INIT_TEMPLATE = '''"""模块生命周期 Hook 集合。"""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []

for _path in sorted(Path(__file__).parent.glob("*.py")):
    if _path.name == "__init__.py" or _path.name.startswith("_"):
        continue
    _module = importlib.import_module(f"{__name__}.{_path.stem}")
    _hook = getattr(_module, _path.stem, None)
    if callable(_hook):
        globals()[_path.stem] = _hook
        if _path.stem not in __all__:
            __all__.append(_path.stem)
'''

MODEL_SELECTORS_INIT_TEMPLATE = '''"""环境选择器集合。"""

from __future__ import annotations

import importlib
from pathlib import Path

__all__: list[str] = []

for _path in sorted(Path(__file__).parent.glob("*.py")):
    if _path.name == "__init__.py" or _path.name.startswith("_"):
        continue
    _module = importlib.import_module(f"{__name__}.{_path.stem}")
    for _name in dir(_module):
        if _name.startswith("_") or not _name.endswith("_selector"):
            continue
        globals()[_name] = getattr(_module, _name)
        if _name not in __all__:
            __all__.append(_name)
'''

MODEL_PAGES_INIT_TEMPLATE = '''"""Hosted UI 页面集合。"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from crawler4j_sdk import TaskContext

_PAGE_MODULES: list[ModuleType] = []
__all__ = ["declare_pages"]

for _path in sorted(Path(__file__).parent.glob("*.py")):
    if _path.name == "__init__.py" or _path.name.startswith("_"):
        continue
    _module = importlib.import_module(f"{__name__}.{_path.stem}")
    _PAGE_MODULES.append(_module)
    for _name in dir(_module):
        if _name.startswith("_"):
            continue
        if not _name.startswith(("build_", "declare_", "load_", "query_")):
            continue
        globals()[_name] = getattr(_module, _name)
        if _name not in __all__:
            __all__.append(_name)


def declare_pages(context: TaskContext):
    """按文件顺序声明所有宿主页。"""
    for module in _PAGE_MODULES:
        declarer_name = str(getattr(module, "PAGE_DECLARER", "") or "").strip()
        if not declarer_name:
            continue
        declarer = getattr(module, declarer_name, None)
        if callable(declarer):
            declarer(context)
    return None
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
        "docstring": "环境准备 Hook (在执行任何任务前调用)。",
        "signature": "async def prepare_env(context: TaskContext):",
    },
    "init_env": {
        "imports": "TaskContext",
        "docstring": "环境初始化 Hook (在环境准备后、任务执行前调用)。",
        "signature": "async def init_env(context: TaskContext):",
    },
    "before_run": {
        "imports": "TaskContext",
        "docstring": "主执行前 Hook (在模块 run 之前调用)。",
        "signature": "async def before_run(context: TaskContext):",
    },
    "on_success": {
        "imports": "TaskContext, TaskResult",
        "docstring": "成功 Hook。",
        "signature": "async def on_success(context: TaskContext, result: TaskResult):",
    },
    "on_failure": {
        "imports": "TaskContext",
        "docstring": "失败 Hook。",
        "signature": "async def on_failure(context: TaskContext, error: Exception):",
    },
    "on_timeout": {
        "imports": "TaskContext",
        "docstring": "超时 Hook。",
        "signature": "async def on_timeout(context: TaskContext):",
    },
    "on_cleanup": {
        "imports": "TaskContext",
        "docstring": """最终清理 Hook。

    注意：该 Hook 会在 ATM 执行环境动作前触发。
    如需根据计划中的 recycle / keep_alive / destroy 做收尾，可读取
    `context.runtime["env_action"]`。
    """,
        "signature": "async def on_cleanup(context: TaskContext):",
    },
}

RETURN_NONE_SELECTOR_TEMPLATE = '''"""环境选择器: 返回 None。

占位选择器，默认直接返回 None。
"""

from crawler4j_sdk import EnvCandidate, TaskContext, env_selector

__all__ = ["return_none_selector"]


@env_selector(
    name="return_none",
    display_name="返回 None",
    description="占位选择器，默认直接返回 None。",
    returns_none=True,
)
def return_none_selector(context: TaskContext, candidates: list[EnvCandidate]):
    """占位环境选择器。"""
    del context, candidates
    return None
'''

RANDOM_READY_SELECTOR_TEMPLATE = '''"""环境选择器: 随机选择就绪环境。

从当前 ready 候选里随机挑选一个环境。
"""

import random

from crawler4j_sdk import EnvCandidate, TaskContext, env_selector

__all__ = ["random_ready_selector"]


@env_selector(
    name="random_ready",
    display_name="随机选择就绪环境",
    description="从当前 ready 候选里随机挑选一个环境。",
)
def random_ready_selector(context: TaskContext, candidates: list[EnvCandidate]):
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

from crawler4j_sdk import {imports}

__all__ = ["{hook_name}"]


{signature}
    """{docstring}"""
    pass
'''.format(
        hook_name=hook_name,
        imports=spec["imports"],
        signature=spec["signature"],
        docstring=spec["docstring"],
    )


def render_selector_template(
    *,
    name: str,
    display_name: str,
    description: str,
    function_name: str,
) -> str:
    return '''"""环境选择器: {display_name}

{description}
"""

from crawler4j_sdk import EnvCandidate, TaskContext, env_selector

__all__ = ["{function_name}"]


@env_selector(
    name="{name}",
    display_name="{display_name}",
    description="{description}",
)
def {function_name}(context: TaskContext, candidates: list[EnvCandidate]):
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
        function_name=function_name,
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

from crawler4j_sdk import TaskContext

PAGE_ID = "{page_id}"
PAGE_DECLARER = "declare_{page_id}_page"

__all__ = [
    "build_{page_id}_page_schema",
    "declare_{page_id}_page",
    "load_{page_id}_page",
]


def declare_{page_id}_page(context: TaskContext):
    """声明 `{page_id}` 宿主页。"""
    if not context.tools or not context.tools.has_tool("ui.declare_page"):
        return None

    return context.tools.call(
        "ui.declare_page",
        page_id=PAGE_ID,
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
    del context, page_id, params
    return {{
        "summary": "{display_name} 页面已由 hosted page V1 加载。",
        "updated_at": "待接入真实数据",
    }}
'''.format(
        page_id=page_id,
        display_name=display_name,
        description=description,
    )
