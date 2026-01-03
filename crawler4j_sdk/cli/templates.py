"""脚本模板"""

SCRIPT_TEMPLATE = '''"""任务脚本: {display_name}

{description}
"""

from crawler4j_sdk import TaskScript, TaskContext, TaskResult


class {class_name}(TaskScript):
    """{display_name}"""

    name = "{name}"
    display_name = "{display_name}"
    description = "{description}"

    default_config = {{
        # TODO: 添加默认配置
    }}

    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行任务

        Args:
            ctx: 任务上下文，提供page、http、logger等能力

        Returns:
            TaskResult: 执行结果
        """
        ctx.logger.info("开始执行任务...")

        # TODO: 实现任务逻辑
        # 示例：
        # await ctx.page.goto("https://example.com")
        # data = await ctx.http.get("https://api.example.com/data")

        return TaskResult.ok(
            tasks_completed=1,
            message="任务完成",
        )

    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"任务出错: {{error}}")
        await ctx.screenshot("error_{name}")
'''

PROJECT_PYPROJECT = '''[project]
name = "{project_name}"
version = "0.1.0"
description = "Crawler4j 任务脚本项目"
requires-python = ">=3.12"
dependencies = [
    "crawler4j-sdk>=1.0.0",
    "playwright>=1.40.0",
]

[project.scripts]
crawler4j = "crawler4j_sdk.cli.commands:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''

PROJECT_README = '''# {project_name}

Crawler4j 任务脚本项目。

## 安装

```bash
uv sync
```

## 开发

```bash
# 交互式创建脚本
uv run crawler4j add

# 列出脚本
uv run crawler4j list
```

## 调试

1. 修改 `debug_runner.py` 中的 `SCRIPT_NAME`
2. VSCode 按 F5 启动调试
'''

DEBUG_RUNNER = '''"""VSCode调试入口脚本

使用方法：
1. 修改下方 SCRIPT_NAME 为要调试的脚本名
2. 在脚本中设置断点
3. 按 F5 启动调试
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright

from crawler4j_sdk import TaskScript, TaskContext, TaskResult
from crawler4j_sdk.context import HttpClient

# ==================== 配置区 ====================
SCRIPT_NAME = "example_task"  # 修改为要调试的脚本名
TEST_CONFIG = {
    "debug": True,
}
# ================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")


async def main():
    """主调试入口"""
    print(f"🔧 调试脚本: {SCRIPT_NAME}")
    print(f"📝 测试配置: {TEST_CONFIG}")
    print("-" * 50)

    # 动态导入脚本
    import importlib.util
    script_path = Path(__file__).parent / "tasks" / f"{SCRIPT_NAME}.py"

    if not script_path.exists():
        print(f"❌ 脚本不存在: {script_path}")
        return

    spec = importlib.util.spec_from_file_location(SCRIPT_NAME, str(script_path))
    if not spec or not spec.loader:
        print(f"❌ 无法加载脚本: {script_path}")
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 查找TaskScript子类
    script_class = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, TaskScript) and obj is not TaskScript:
            script_class = obj
            break

    if not script_class:
        print("❌ 未找到TaskScript子类")
        return

    print(f"✅ 加载脚本: {script_class.display_name or SCRIPT_NAME}")

    # 启动浏览器
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 创建测试Context
        ctx = TaskContext(
            env_id=9999,
            task_name=SCRIPT_NAME,
            config=TEST_CONFIG,
            page=page,
            context=context,
            logger=logger,
            http=HttpClient(),
        )

        # 执行脚本
        print("\\n🚀 开始执行...")
        try:
            instance = script_class()
            await instance.on_init(ctx)
            result = await instance.execute(ctx)
            await instance.on_cleanup(ctx)

            print("\\n" + "=" * 50)
            print(f"✅ 执行完成!")
            print(f"   成功: {result.success}")
            print(f"   任务数: {result.tasks_completed}")
            print(f"   消息: {result.message}")
        except Exception as e:
            print(f"\\n❌ 执行失败: {e}")
            import traceback
            traceback.print_exc()

        # 保持浏览器打开
        print("\\n按Enter关闭浏览器...")
        input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
'''
