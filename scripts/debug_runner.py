"""Legacy VSCode task-script debug helper.

This helper is kept at the workspace root because it is only for local
development. The recommended debug path for crawler4j modules is still
DevLink -> ATM 调试。Use this script only when you need a direct local
Playwright session against a standard module project's ``tasks/`` directory.

Usage:
1. Set ``SCRIPT_NAME`` below.
2. If needed, export ``CRAWLER4J_DEBUG_MODULE_ROOT=/path/to/module``.
3. Start the script from VSCode or ``uv run python scripts/debug_runner.py``.

Example ``.vscode/launch.json`` entry:
{
    "name": "调试任务脚本",
    "type": "debugpy",
    "request": "launch",
    "program": "${workspaceFolder}/scripts/debug_runner.py",
    "console": "integratedTerminal"
}
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from crawler4j_sdk import TaskContext, TaskScript
from crawler4j_sdk.context import DefaultHttpClient

# ==================== 配置区 ====================
SCRIPT_NAME = "example_task"  # 修改为要调试的脚本名
TEST_CONFIG = {
    "max_items": 5,
    "debug": True,
}
# ================================================

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = Path(os.environ.get("CRAWLER4J_DEBUG_MODULE_ROOT", WORKSPACE_ROOT)).resolve()
TASKS_DIR = MODULE_ROOT / "tasks"

sys.path.insert(0, str(MODULE_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")


async def main() -> None:
    """Run a TaskScript inside a disposable Playwright session."""
    print(f"调试脚本: {SCRIPT_NAME}")
    print(f"模块目录: {MODULE_ROOT}")
    print(f"测试配置: {TEST_CONFIG}")
    print("-" * 50)

    if not TASKS_DIR.exists():
        print(f"未找到 tasks/ 目录: {TASKS_DIR}")
        print("当前仓库默认调试链路是 DevLink -> ATM；若要使用该脚本，请指定标准模块项目根目录。")
        return

    script_path = TASKS_DIR / f"{SCRIPT_NAME}.py"

    if not script_path.exists():
        print(f"脚本不存在: {script_path}")
        return

    spec = importlib.util.spec_from_file_location(SCRIPT_NAME, str(script_path))
    if not spec or not spec.loader:
        print(f"无法加载脚本: {script_path}")
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    script_class: type[TaskScript] | None = None
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, TaskScript) and obj is not TaskScript:
            script_class = obj
            break

    if not script_class:
        print("未找到 TaskScript 子类")
        return

    print(f"加载脚本: {script_class.display_name or SCRIPT_NAME}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        ctx = TaskContext(
            env_id=9999,
            task_name=SCRIPT_NAME,
            config=TEST_CONFIG,
            page=page,
            context=context,
            logger=logger,
            http=DefaultHttpClient(),
        )

        print("\n开始执行...")
        try:
            instance = script_class()
            await instance.on_init(ctx)
            result = await instance.execute(ctx)
            await instance.on_cleanup(ctx)

            print("\n" + "=" * 50)
            print("执行完成")
            print(f"成功: {result.success}")
            print(f"消息: {result.message}")
            if hasattr(result, "tasks_completed"):
                print(f"任务数: {result.tasks_completed}")
            if result.data:
                print(f"数据: {result.data}")
        except Exception as exc:
            print(f"\n执行失败: {exc}")
            import traceback

            traceback.print_exc()

        print("\n按 Enter 关闭浏览器...")
        input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
