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
version = "0.1.0"
description = "{display_name} 模块项目"
requires-python = ">={python_version}"
dependencies = [
    "crawler4j-sdk>=1.1.0,<2.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
'''

MODEL_PROJECT_README = '''# {display_name}

这是一个规范化的 Crawler4j 模块项目，采用分层架构设计：

- `module.yaml`: 模块清单与能力声明。
- `tasks/`: [任务层] 原子操作脚本，负责具体页面交互或数据采集。
- `workflows/`: [编排层] 业务逻辑流，负责串联多个任务。
- `ui/`: [界面层] 包含 `config_schema.json` (声明式) 和代码型 UI 组件。
- `data/`: [数据层] 包含数据模型定义 (`models.py`) 和 Schema。

## 常用命令

```bash
# 创建任务脚本
uv run crawler4j add <name>

# 创建工作流
uv run crawler4j add-workflow <name>

# 创建数据模型
uv run crawler4j add-data <name>

# 创建代码型 UI 页面
uv run crawler4j add-ui --type code
```

## 调试

在应用中把该目录注册为“开发链接”模块后，可在 ATM 中对关联作业发起任务调试。
'''

MODEL_DATA_MODELS_TEMPLATE = '''"""数据模型: {display_name}

{description}
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class {class_name}(BaseModel):
    """{display_name} 模型"""
    id: str = Field(..., description="唯一标识")
    name: Optional[str] = Field(None, description="显示名称")
    data: dict[str, Any] = Field(default_factory=dict, description="原始数据")
'''

MODEL_UTILS_HELPER_TEMPLATE = '''"""模块通用工具。"""

def format_currency(value: float) -> str:
    """格式化货币。"""
    return f"¥{value:,.2f}"
'''

MODEL_TEST_TASK_TEMPLATE = '''"""测试任务脚本。"""

import pytest
from unittest.mock import MagicMock
from crawler4j_sdk import TaskContext
from tasks.example_task import ExampleTask

@pytest.mark.asyncio
async def test_example_task_logic():
    # 1. 准备 Mock 环境
    ctx = MagicMock(spec=TaskContext)
    ctx.get_config.return_value = "https://mock.url"
    ctx.page = MagicMock()
    ctx.captured_data = []
    
    # 2. 执行任务
    task = ExampleTask()
    result = await task.execute(ctx)
    
    # 3. 验证结果
    assert result.success is True
    assert len(ctx.captured_data) == 1
'''

MODEL_UI_PAGES_TEMPLATE = '''"""界面组件: {display_name}

{description}
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from crawler4j_sdk import TaskContext


class {class_name}(QWidget):
    """{display_name} 页面"""

    def __init__(self, ctx: TaskContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.label = QLabel(f"欢迎使用 {{self.__class__.__name__}}")
        self.btn = QPushButton("刷新数据")
        self.btn.clicked.connect(self.on_refresh)
        
        layout.addWidget(self.label)
        layout.addWidget(self.btn)

    def on_refresh(self):
        self.ctx.logger.info("UI 请求刷新数据")
        # 实现具体逻辑
'''

MODEL_MODULE_INIT = '''"""{display_name} 模块入口。

本文件由 SDK 自动托管，不建议手动修改。
如需扩展运行时逻辑（Hooks、自定义发现等），请在同级目录创建 `module_runtime.py`。
"""

from pathlib import Path
from crawler4j_sdk import ModuleAssembler, TaskContext, TaskResult

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
'''

MODEL_RUNTIME_TEMPLATE = '''"""{display_name} 模块自定义运行时扩展。

本文件为可选文件，用于存放模块级的生命周期 Hooks、手动注册组件或覆盖默认行为。
"""

from crawler4j_sdk import TaskContext

# 默认工作流覆盖 (可选)
# DEFAULT_WORKFLOW = "my_custom_workflow"

# 手动注册/覆盖组件 (可选)
# TASK_SCRIPTS = {{}}
# WORKFLOWS = {{}}


async def prepare_env(context: TaskContext):
    """环境准备 Hook (在执行任何任务前调用)。"""
    pass


async def init_env(context: TaskContext):
    """环境初始化 Hook (在环境准备后、任务执行前调用)。"""
    pass


async def on_cleanup(context: TaskContext):
    """清理 Hook (任务执行完成后总是调用)。"""
    pass
'''

MODEL_MANIFEST_TEMPLATE = '''name: {module_name}
version: 1.0.0
display_name: {display_name}
description: {description}
author: crawler4j
sdk_version_range: ">=1.1.0"
{ui_section}workflows:
  - name: {workflow_name}
    display_name: {workflow_display_name}
    description: {workflow_description}
'''

MODEL_UI_SECTION = '''ui_extension:
  type: declarative
  entry: ui/config_schema.json
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
