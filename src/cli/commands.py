"""CLI命令实现

提供脚本开发相关的命令行工具。
"""

import argparse
import sys
from pathlib import Path
from textwrap import dedent

SCRIPT_TEMPLATE = dedent('''
    """任务脚本: {display_name}

    描述: TODO
    """

    from crawler4j_sdk import TaskScript, TaskContext, TaskResult


    class {class_name}(TaskScript):
        """{display_name}"""
        
        name = "{name}"
        display_name = "{display_name}"
        description = "TODO: 添加任务描述"
        
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
''').strip()

PROJECT_PYPROJECT = dedent('''
    [project]
    name = "{project_name}"
    version = "0.1.0"
    description = "Crawler4j 任务脚本项目"
    requires-python = ">=3.12"
    dependencies = [
        "crawler4j-sdk>=1.0.0",
        "playwright>=1.40.0",
    ]

    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"
''').strip()

PROJECT_README = dedent('''
    # {project_name}

    Crawler4j 任务脚本项目。

    ## 安装

    ```bash
    uv sync
    ```

    ## 开发

    1. 在 `tasks/` 目录下创建脚本
    2. 使用 `debug_runner.py` 进行本地调试
    3. 将 `tasks/` 目录配置到框架中使用

    ## 脚本列表

    - `example_task.py` - 示例任务
''').strip()


def to_class_name(name: str) -> str:
    """将脚本名转换为类名"""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts) + "Task"


def to_display_name(name: str) -> str:
    """将脚本名转换为显示名"""
    return name.replace("_", " ").replace("-", " ").title()


def cmd_new_script(args):
    """创建新脚本"""
    name = args.name
    output_dir = Path(args.output) if args.output else Path("scripts/tasks")
    
    # 确保目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件
    filename = f"{name}.py"
    filepath = output_dir / filename
    
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1
    
    # 渲染模板
    content = SCRIPT_TEMPLATE.format(
        name=name,
        class_name=to_class_name(name),
        display_name=to_display_name(name),
    )
    
    filepath.write_text(content, encoding="utf-8")
    print(f"✅ 创建脚本: {filepath}")
    print(f"   类名: {to_class_name(name)}")
    print(f"   显示名: {to_display_name(name)}")
    return 0


def cmd_init_project(args):
    """初始化脚本项目"""
    project_name = args.name
    output_dir = Path(args.output) if args.output else Path(project_name)
    
    if output_dir.exists() and not args.force:
        print(f"❌ 目录已存在: {output_dir}")
        print("   使用 --force 覆盖")
        return 1
    
    # 创建目录结构
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    
    # 创建 pyproject.toml
    pyproject = output_dir / "pyproject.toml"
    pyproject.write_text(
        PROJECT_PYPROJECT.format(project_name=project_name),
        encoding="utf-8"
    )
    
    # 创建 README.md
    readme = output_dir / "README.md"
    readme.write_text(
        PROJECT_README.format(project_name=project_name),
        encoding="utf-8"
    )
    
    # 复制 debug_runner.py
    debug_runner_src = Path(__file__).parent.parent.parent / "scripts" / "debug_runner.py"
    if debug_runner_src.exists():
        debug_runner_dst = output_dir / "debug_runner.py"
        debug_runner_dst.write_text(debug_runner_src.read_text(), encoding="utf-8")
    
    # 创建示例脚本
    example_script = tasks_dir / "example_task.py"
    example_script.write_text(
        SCRIPT_TEMPLATE.format(
            name="example_task",
            class_name="ExampleTask",
            display_name="示例任务",
        ),
        encoding="utf-8"
    )
    
    print(f"✅ 初始化项目: {output_dir}")
    print(f"   {output_dir}/")
    print(f"   ├── pyproject.toml")
    print(f"   ├── README.md")
    print(f"   ├── debug_runner.py")
    print(f"   └── tasks/")
    print(f"       └── example_task.py")
    print()
    print("下一步:")
    print(f"   cd {output_dir}")
    print("   uv sync")
    print("   uv add crawler4j-sdk")
    return 0


def cmd_reload_scripts(args):
    """重载脚本"""
    from src.plugins.script_manager import get_script_manager
    
    manager = get_script_manager()
    
    # 添加默认目录
    default_dir = Path("scripts/tasks")
    if default_dir.exists():
        manager.add_directory(default_dir)
    
    count = manager.reload_all()
    print(f"✅ 已重载 {count} 个脚本")
    
    for script in manager.list_scripts():
        print(f"   - {script['display_name']}: {script['description'][:40]}...")
    
    return 0


def cmd_list_scripts(args):
    """列出已加载脚本"""
    from src.plugins.script_manager import get_script_manager
    
    manager = get_script_manager()
    
    # 添加默认目录
    default_dir = Path("scripts/tasks")
    if default_dir.exists():
        manager.add_directory(default_dir)
        manager.load_all()
    
    scripts = manager.list_scripts()
    
    if not scripts:
        print("暂无已加载脚本")
        return 0
    
    print(f"已加载 {len(scripts)} 个脚本:")
    for script in scripts:
        print(f"   - {script['name']}")
        print(f"     显示名: {script['display_name']}")
        print(f"     路径: {script['path']}")
    
    return 0


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        prog="crawler4j",
        description="Crawler4j 命令行工具",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # new-script 命令
    new_script_parser = subparsers.add_parser(
        "new-script",
        help="创建新的任务脚本",
    )
    new_script_parser.add_argument("name", help="脚本名称（如 my_task）")
    new_script_parser.add_argument("-o", "--output", help="输出目录")
    new_script_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    new_script_parser.set_defaults(func=cmd_new_script)
    
    # init-project 命令
    init_project_parser = subparsers.add_parser(
        "init-project",
        help="初始化独立脚本项目",
    )
    init_project_parser.add_argument("name", help="项目名称")
    init_project_parser.add_argument("-o", "--output", help="输出目录")
    init_project_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    init_project_parser.set_defaults(func=cmd_init_project)
    
    # scripts reload 命令
    reload_parser = subparsers.add_parser(
        "reload-scripts",
        help="重载所有脚本",
    )
    reload_parser.set_defaults(func=cmd_reload_scripts)
    
    # scripts list 命令
    list_parser = subparsers.add_parser(
        "list-scripts",
        help="列出已加载脚本",
    )
    list_parser.set_defaults(func=cmd_list_scripts)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
