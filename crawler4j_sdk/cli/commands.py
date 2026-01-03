"""CLI命令实现

提供脚本开发相关的命令行工具。
支持全局执行（uvx）和项目内执行（uv run）。
"""

import argparse
import subprocess
import sys
from pathlib import Path

from crawler4j_sdk.cli.templates import (
    DEBUG_RUNNER,
    PROJECT_PYPROJECT,
    PROJECT_README,
    SCRIPT_TEMPLATE,
)


def to_class_name(name: str) -> str:
    """将脚本名转换为类名"""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts) + "Task"


def to_display_name(name: str) -> str:
    """将脚本名转换为显示名"""
    return name.replace("_", " ").replace("-", " ").title()


def find_tasks_dir() -> Path:
    """查找tasks目录"""
    cwd = Path.cwd()
    
    # 优先查找 tasks/
    if (cwd / "tasks").is_dir():
        return cwd / "tasks"
    
    # 查找 scripts/tasks/
    if (cwd / "scripts" / "tasks").is_dir():
        return cwd / "scripts" / "tasks"
    
    # 默认创建 tasks/
    return cwd / "tasks"


def cmd_init(args):
    """初始化脚本项目"""
    project_name = args.name
    output_dir = Path(args.output) if args.output else Path.cwd() / project_name

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

    # 创建 debug_runner.py
    debug_runner = output_dir / "debug_runner.py"
    debug_runner.write_text(DEBUG_RUNNER, encoding="utf-8")

    # 创建示例脚本
    example_script = tasks_dir / "example_task.py"
    example_script.write_text(
        SCRIPT_TEMPLATE.format(
            name="example_task",
            class_name="ExampleTask",
            display_name="示例任务",
            description="这是一个示例任务脚本",
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

    # 询问是否安装依赖
    if not args.no_install:
        print("📦 安装依赖...")
        try:
            subprocess.run(["uv", "sync"], cwd=str(output_dir), check=True)
            print("✅ 依赖安装完成")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ 自动安装失败，请手动运行: cd {} && uv sync".format(output_dir))

    print()
    print("下一步:")
    print(f"   cd {project_name}")
    print("   uv run crawler4j add  # 创建新脚本")
    return 0


def cmd_add(args):
    """交互式创建脚本"""
    tasks_dir = find_tasks_dir()

    # 交互式获取信息
    if args.name:
        name = args.name
    else:
        name = input("脚本名称 (如 my_task): ").strip()
        if not name:
            print("❌ 脚本名称不能为空")
            return 1

    # 验证名称格式
    if not name.replace("_", "").replace("-", "").isalnum():
        print("❌ 脚本名称只能包含字母、数字、下划线和连字符")
        return 1

    display_name = input(f"显示名称 [{to_display_name(name)}]: ").strip()
    if not display_name:
        display_name = to_display_name(name)

    description = input("描述 [TODO: 添加描述]: ").strip()
    if not description:
        description = "TODO: 添加描述"

    # 创建目录和文件
    tasks_dir.mkdir(parents=True, exist_ok=True)
    filepath = tasks_dir / f"{name}.py"

    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1

    content = SCRIPT_TEMPLATE.format(
        name=name,
        class_name=to_class_name(name),
        display_name=display_name,
        description=description,
    )

    filepath.write_text(content, encoding="utf-8")
    print()
    print(f"✅ 创建脚本: {filepath}")
    print(f"   类名: {to_class_name(name)}")
    print(f"   显示名: {display_name}")
    return 0


def cmd_list(args):
    """列出脚本"""
    tasks_dir = find_tasks_dir()

    if not tasks_dir.exists():
        print("暂无脚本目录")
        return 0

    scripts = list(tasks_dir.glob("*.py"))
    scripts = [s for s in scripts if not s.name.startswith("_")]

    if not scripts:
        print("暂无脚本")
        return 0

    print(f"📦 脚本目录: {tasks_dir}")
    print(f"共 {len(scripts)} 个脚本:")
    for script in sorted(scripts):
        print(f"   - {script.stem}")

    return 0


def cmd_new(args):
    """创建脚本（非交互式）"""
    tasks_dir = find_tasks_dir()
    name = args.name

    filepath = tasks_dir / f"{name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1

    tasks_dir.mkdir(parents=True, exist_ok=True)

    content = SCRIPT_TEMPLATE.format(
        name=name,
        class_name=to_class_name(name),
        display_name=to_display_name(name),
        description="TODO: 添加描述",
    )

    filepath.write_text(content, encoding="utf-8")
    print(f"✅ 创建脚本: {filepath}")
    return 0


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        prog="crawler4j",
        description="Crawler4j 任务脚本开发工具",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # init 命令
    init_parser = subparsers.add_parser(
        "init",
        help="初始化脚本项目",
    )
    init_parser.add_argument("name", help="项目名称")
    init_parser.add_argument("-o", "--output", help="输出目录")
    init_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    init_parser.add_argument("--no-install", action="store_true", help="不自动安装依赖")
    init_parser.set_defaults(func=cmd_init)

    # add 命令（交互式）
    add_parser = subparsers.add_parser(
        "add",
        help="交互式创建脚本",
    )
    add_parser.add_argument("name", nargs="?", help="脚本名称（可选，不填则交互式输入）")
    add_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    add_parser.set_defaults(func=cmd_add)

    # new 命令（非交互式，兼容旧命令）
    new_parser = subparsers.add_parser(
        "new",
        help="快速创建脚本（非交互式）",
    )
    new_parser.add_argument("name", help="脚本名称")
    new_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    new_parser.set_defaults(func=cmd_new)

    # list 命令
    list_parser = subparsers.add_parser(
        "list",
        help="列出脚本",
    )
    list_parser.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
