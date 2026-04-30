"""CLI scaffolding templates."""

from __future__ import annotations


SCRIPT_TEMPLATE = '''"""页面操作: {display_name}

{description}
"""

from crawler4j_contracts import TaskContext, TaskResult, page_action


@page_action(
    name="{name}",
    label="{display_name}",
    description="{description}",
    parameters=[
        {{"name": "start_url", "type": "string", "required": True, "default": "https://example.com"}},
    ],
)
async def {name}(ctx: TaskContext, start_url: str = "https://example.com") -> TaskResult:
    """执行页面操作。"""
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

    return TaskResult.ok(
        tasks_completed=1,
        message="页面操作完成",
        data=result,
    )
'''

INTERFACE_TEMPLATE = '''"""接口声明: {display_name}

{description}
"""

from crawler4j_contracts import interface


@interface(name="{name}", label="{display_name}", description="{description}")
class {class_name}:
    """{display_name} 接口。"""
'''

COMPONENT_TEMPLATE = '''"""组件声明: {display_name}

{description}
"""

from crawler4j_contracts import component


@component(name="{name}", implements="{implements}", label="{display_name}", description="{description}")
class {class_name}:
    """{display_name} 组件。"""
'''

MODEL_GITIGNORE_TEMPLATE = """.DS_Store
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
"""

MODEL_PROJECT_PYPROJECT = """[project]
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
"""

MODEL_PROJECT_README = """# {display_name}

这是一个 `core-native-v2` 协议模块项目，核心文件如下：

- `module.yaml`: 模块清单与 `runtime_api` 声明。
- `interfaces/`: 可注入接口声明，使用 `@interface`。
- `objects/`: 组件实现，使用 `@component`。
- `workflows/`: 工作流对象，使用 `@workflow`。
- `tasks/`: 页面操作函数，使用 `@page_action`。
- `data/`: 数据表与命名查询声明，使用 `@data_table` / `@data_query`。
- `pages/`: Hosted UI 页面；可以平铺在 `pages/*.py`，也可以按单层业务分组放到 `pages/<group>/*.py`。
- `.crawler4j/manifest.lock.json`: SDK 扫描生成的 v2 manifest lock。

## 常用命令

```bash
# 查看模块概况
uv run crawler4j module show

# 创建接口与组件
uv run crawler4j interface create labor
uv run crawler4j component create api_labor --implements labor

# 创建工作流
uv run crawler4j workflow create <name>

# 创建页面操作
uv run crawler4j page-action create <name>

# 创建宿主页
uv run crawler4j page create dashboard
uv run crawler4j page create account_detail --group account --no-menu

# 创建数据表 / 查询
uv run crawler4j data table create accounts
uv run crawler4j data query create get_account_by_id --source accounts

# 生成 manifest lock
uv run crawler4j manifest lock

# 完整校验并打包
uv run crawler4j check full
uv run crawler4j package build
```

## 运行边界

- 模块运行时只依赖 `crawler4j-contracts`。
- `crawler4j-sdk` 只作为 CLI / 校验 / 开发辅助存在。
- Core 会自行扫描 v2 装饰器生成运行时 descriptor，不会调用模块根 `run()` 或 `declare_ui()`。
- 对象依赖和 component 参数可以写在装饰器参数里，也可以写成 `Annotated[..., object_inject(...)]` / `Annotated[..., object_param(...)]`。
- 表与命名查询统一由装饰器声明；旧 `module.yaml.data` 已不再是 0.4.x 运行契约。
"""

MODEL_TEST_TASK_TEMPLATE = '''"""测试页面操作。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from crawler4j_contracts import TaskContext
from tasks.example_action import example_action


@pytest.mark.asyncio
async def test_example_action_logic():
    ctx = MagicMock(spec=TaskContext)
    ctx.logger = MagicMock()
    ctx.page = MagicMock()
    ctx.page.goto = AsyncMock()
    ctx.page.title = AsyncMock(return_value="Mock Title")

    result = await example_action(ctx, "https://mock.url")

    assert result.success is True
    assert result.data["title"] == "Mock Title"
    ctx.page.goto.assert_awaited_once_with("https://mock.url", wait_until="domcontentloaded")
    ctx.page.title.assert_awaited_once()
'''

MODEL_MODULE_INIT = '''"""{display_name} 模块包。

Core 会直接扫描 `interfaces/`、`objects/`、`workflows/`、`tasks/`、`data/`、`pages/`。
宿主页源码既可以平铺，也可以按单层分组放到 `pages/<group>/`。
模块根包不再承载运行时装配逻辑。
"""
'''

MODEL_MANIFEST_TEMPLATE = """name: {module_name}
runtime_api: core-native-v2
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
ui_extension:
  pages: []
"""

MODEL_INTERFACES_INIT_TEMPLATE = '"""v2 接口声明集合。"""\n'
MODEL_OBJECTS_INIT_TEMPLATE = '"""v2 组件声明集合。"""\n'
MODEL_WORKFLOWS_INIT_TEMPLATE = '"""v2 工作流声明集合。"""\n'
MODEL_TASKS_INIT_TEMPLATE = '"""v2 页面操作集合。"""\n'
MODEL_DATA_INIT_TEMPLATE = '"""v2 数据契约声明集合。"""\n'
MODEL_PAGES_INIT_TEMPLATE = '"""Hosted UI 页面集合。"""\n'

WORKFLOW_TEMPLATE = '''"""工作流: {display_name}

{description}
"""

from crawler4j_contracts import TaskContext, workflow


@workflow(name="{name}", label="{display_name}", description="{description}")
class {class_name}:
    """{display_name} 工作流。"""

    async def run(self, ctx: TaskContext):
        """执行工作流。"""
        ctx.state["phase"] = "{name}"
        return {{"phase": "{name}"}}
'''

DATA_TABLE_TEMPLATE = '''"""数据表声明: {display_name}

{description}
"""

from crawler4j_contracts import data_table


@data_table(
    name="{name}",
    label="{display_name}",
    description="{description}",
    schema=[
        {{"name": "account_id", "type": "string", "required": True}},
    ],
)
class {class_name}:
    """{display_name} 表。"""
'''

DATA_QUERY_TEMPLATE = '''"""数据查询声明: {display_name}

{description}
"""

from crawler4j_contracts import data_query


@data_query(
    name="{name}",
    source="{source}",
    sql="SELECT account_id FROM {{{{resource:{source}}}}} WHERE account_id = :account_id LIMIT 1",
    output_schema=[
        {{"name": "account_id", "type": "string"}},
    ],
)
def {name}():
    """{display_name} 查询声明。"""
'''


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
        "summary": "{display_name} 页面已由 core-native-v2 加载。",
        "updated_at": "待接入真实数据",
    }}
'''.format(
        page_id=page_id,
        display_name=display_name,
        description=description,
    )
