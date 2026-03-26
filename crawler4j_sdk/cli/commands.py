"""CLI commands for module scaffolding."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from crawler4j_sdk.cli.templates import (
    CONFIG_SCHEMA_TEMPLATE,
    MODEL_GITIGNORE_TEMPLATE,
    MODEL_MANIFEST_TEMPLATE,
    MODEL_MODULE_INIT,
    MODEL_PROJECT_PYPROJECT,
    MODEL_PROJECT_README,
    MODEL_UI_SECTION,
    SCRIPT_TEMPLATE,
    WORKFLOW_TEMPLATE,
)

DEFAULT_PYTHON_VERSION = "3.12"


@dataclass(slots=True)
class InitModelConfig:
    module_name: str
    output_dir: Path
    display_name: str
    description: str
    workflow_name: str
    workflow_display_name: str
    workflow_description: str
    python_version: str
    include_ui: bool
    init_git: bool
    auto_install: bool


def to_class_name(name: str) -> str:
    """Convert a task name to a TaskScript class name."""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts) + "Task"


def to_workflow_class_name(name: str) -> str:
    """Convert a workflow name to a TaskFlow class name."""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts) + "Workflow"


def to_display_name(name: str) -> str:
    """Convert an identifier to a human-readable display name."""
    return name.replace("_", " ").replace("-", " ").title()


def is_valid_module_name(name: str) -> bool:
    """Validate a model/module package name."""
    return bool(name) and name.isidentifier() and name == name.lower()


def is_valid_python_file_stem(name: str) -> bool:
    """Validate names that must map to importable Python modules."""
    return is_valid_module_name(name)


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _ensure_package_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    init_file = path / "__init__.py"
    if not init_file.exists():
        _write_text(init_file, "")


def find_module_root(start: Path | None = None) -> Path | None:
    """Find the nearest module root containing module.yaml."""
    current = (start or Path.cwd()).resolve()
    search_roots = [current, *current.parents]

    for candidate in search_roots:
        if (candidate / "module.yaml").is_file():
            return candidate
    return None


def require_module_root(start: Path | None = None) -> Path | None:
    """Require the current working tree to be a module project."""
    module_root = find_module_root(start)
    if module_root:
        return module_root

    print("❌ 当前目录不在 model 项目中，找不到 module.yaml")
    print("   请先执行 `crawler4j init-model <module_name>` 创建完整模块项目")
    return None


def find_tasks_dir(start: Path | None = None) -> Path:
    """Find the tasks directory for the nearest module project."""
    module_root = find_module_root(start)
    if module_root:
        return module_root / "tasks"
    return (start or Path.cwd()).resolve() / "tasks"


def find_workflows_dir(start: Path | None = None) -> Path:
    """Find the most suitable workflows directory."""
    module_root = find_module_root(start)
    if module_root:
        return module_root / "workflows"
    return (start or Path.cwd()).resolve() / "workflows"


def load_manifest(module_root: Path) -> dict[str, Any]:
    """Load module.yaml as a mutable dictionary."""
    manifest_path = module_root / "module.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"找不到 module.yaml: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("module.yaml 顶层必须是对象")
    return data


def save_manifest(module_root: Path, manifest: dict[str, Any]) -> None:
    """Persist module.yaml while keeping key order stable."""
    manifest_path = module_root / "module.yaml"
    with manifest_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            manifest,
            f,
            allow_unicode=True,
            sort_keys=False,
        )


def ensure_ui_extension(
    manifest: dict[str, Any],
    *,
    display_name: str,
    entry: str = "config_schema.json",
) -> None:
    """Ensure manifest includes a declarative UI extension."""
    ui_extension = dict(manifest.get("ui_extension") or {})
    ui_extension["type"] = "declarative"
    ui_extension["entry"] = entry

    nav_item = dict(ui_extension.get("nav_item") or {})
    nav_item.setdefault("icon", "🧩")
    nav_item.setdefault("label", f"{display_name}配置")
    ui_extension["nav_item"] = nav_item
    manifest["ui_extension"] = ui_extension


def upsert_workflow_manifest_entry(
    manifest: dict[str, Any],
    *,
    name: str,
    display_name: str,
    description: str,
    force: bool = False,
) -> None:
    """Append or replace a workflow declaration in module.yaml."""
    workflows = list(manifest.get("workflows") or [])

    new_entry = {
        "name": name,
        "display_name": display_name,
        "description": description,
    }

    for index, workflow in enumerate(workflows):
        if workflow.get("name") != name:
            continue
        if not force:
            raise ValueError(f"module.yaml 中已存在工作流声明: {name}")
        workflows[index] = new_entry
        manifest["workflows"] = workflows
        return

    workflows.append(new_entry)
    manifest["workflows"] = workflows


def _prompt_text(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _prompt_bool(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        answer = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("⚠️ 请输入 y 或 n，或直接回车接受默认值。")


def _build_init_model_config(args, module_name: str) -> InitModelConfig:
    default_output_dir = Path(args.output).expanduser() if args.output else Path.cwd() / module_name
    default_display_name = (args.display_name or to_display_name(module_name)).strip()
    default_workflow_name = (args.workflow_name or "main_workflow").strip()
    default_workflow_display_name = (
        (args.workflow_display_name or to_display_name(default_workflow_name)).strip()
    )
    default_description = (args.description or f"{default_display_name} 模块").strip()
    default_workflow_description = (
        (args.workflow_description or f"{default_display_name} 的默认工作流").strip()
    )
    default_python_version = (args.python_version or DEFAULT_PYTHON_VERSION).strip()
    default_include_ui = not args.no_ui
    default_init_git = not args.no_git
    default_auto_install = not args.no_install

    if getattr(args, "defaults", False):
        return InitModelConfig(
            module_name=module_name,
            output_dir=default_output_dir,
            display_name=default_display_name,
            description=default_description,
            workflow_name=default_workflow_name,
            workflow_display_name=default_workflow_display_name,
            workflow_description=default_workflow_description,
            python_version=default_python_version,
            include_ui=default_include_ui,
            init_git=default_init_git,
            auto_install=default_auto_install,
        )

    print("🧭 进入 model 初始化向导，直接回车即可接受默认值。")
    output_dir = Path(_prompt_text("输出目录", str(default_output_dir))).expanduser()
    display_name = _prompt_text("模块显示名称", default_display_name)
    description = _prompt_text("模块描述", default_description)
    workflow_name = _prompt_text("默认工作流名称", default_workflow_name)
    workflow_display_name = _prompt_text(
        "工作流显示名称",
        args.workflow_display_name or to_display_name(workflow_name),
    )
    workflow_description = _prompt_text(
        "工作流描述",
        args.workflow_description or f"{display_name} 的默认工作流",
    )
    python_version = _prompt_text("Python 版本", default_python_version)
    include_ui = _prompt_bool("生成配置 UI", default_include_ui)
    init_git = _prompt_bool("初始化 Git 仓库", default_init_git)
    auto_install = _prompt_bool("自动执行 uv sync", default_auto_install)

    return InitModelConfig(
        module_name=module_name,
        output_dir=output_dir,
        display_name=display_name,
        description=description,
        workflow_name=workflow_name,
        workflow_display_name=workflow_display_name,
        workflow_description=workflow_description,
        python_version=python_version,
        include_ui=include_ui,
        init_git=init_git,
        auto_install=auto_install,
    )


def _run_git_init(output_dir: Path) -> bool:
    git_dir = output_dir / ".git"
    if git_dir.exists():
        print("ℹ️ Git 仓库已存在，跳过 git init")
        return True

    print("🧱 初始化 Git 仓库...")
    try:
        subprocess.run(["git", "init"], cwd=str(output_dir), check=True)
        print("✅ Git 仓库初始化完成")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ Git 初始化失败，请手动运行: cd {output_dir} && git init")
        return False


def _run_uv_sync(output_dir: Path) -> bool:
    print("📦 安装依赖...")
    try:
        subprocess.run(["uv", "sync"], cwd=str(output_dir), check=True)
        print("✅ 依赖安装完成")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ 自动安装失败，请手动运行: cd {output_dir} && uv sync")
        return False


def cmd_init_model(args) -> int:
    """Initialize a complete model/module project."""
    module_name = args.name.strip()
    if not is_valid_module_name(module_name):
        print("❌ model 名称必须是小写 Python 包名，只能包含字母、数字和下划线")
        print("   例如: demo_model")
        return 1

    config = _build_init_model_config(args, module_name)

    if not is_valid_python_file_stem(config.workflow_name):
        print("❌ 工作流名称必须是小写 Python 标识符，只能包含字母、数字和下划线")
        print("   例如: main_workflow")
        return 1

    if config.output_dir.exists() and not args.force:
        print(f"❌ 目录已存在: {config.output_dir}")
        print("   使用 --force 覆盖")
        return 1

    config.output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_package_dir(config.output_dir / "tasks")
    _ensure_package_dir(config.output_dir / "workflows")

    _write_text(
        config.output_dir / "pyproject.toml",
        MODEL_PROJECT_PYPROJECT.format(
            project_name=module_name,
            display_name=config.display_name,
            python_version=config.python_version,
        ),
    )
    _write_text(
        config.output_dir / "README.md",
        MODEL_PROJECT_README.format(display_name=config.display_name),
    )
    _write_text(
        config.output_dir / "__init__.py",
        MODEL_MODULE_INIT.format(
            display_name=config.display_name,
            default_workflow=config.workflow_name,
            module_name=module_name,
        ),
    )
    _write_text(
        config.output_dir / "module.yaml",
        MODEL_MANIFEST_TEMPLATE.format(
            module_name=module_name,
            display_name=config.display_name,
            description=config.description,
            workflow_name=config.workflow_name,
            workflow_display_name=config.workflow_display_name,
            workflow_description=config.workflow_description,
            ui_section="" if not config.include_ui else MODEL_UI_SECTION.format(display_name=config.display_name),
        ),
    )
    _write_text(
        config.output_dir / "tasks" / "example_task.py",
        SCRIPT_TEMPLATE.format(
            name="example_task",
            class_name="ExampleTask",
            display_name="示例任务",
            description="打开一个页面并采集标题。",
        ),
    )
    _write_text(
        config.output_dir / "workflows" / f"{config.workflow_name}.py",
        WORKFLOW_TEMPLATE.format(
            name=config.workflow_name,
            class_name=to_workflow_class_name(config.workflow_name),
            display_name=config.workflow_display_name,
            description=config.workflow_description,
        ),
    )
    _write_text(config.output_dir / ".gitignore", MODEL_GITIGNORE_TEMPLATE)
    _write_text(config.output_dir / ".python-version", f"{config.python_version}\n")

    if config.include_ui:
        _write_text(
            config.output_dir / "config_schema.json",
            CONFIG_SCHEMA_TEMPLATE.format(
                title=f"{config.display_name} 配置",
                description=f"{config.display_name} 的运行参数配置",
                workflow_name=config.workflow_name,
            ),
        )

    print(f"✅ 初始化 model 项目: {config.output_dir}")
    print(f"   {config.output_dir}/")
    print("   ├── __init__.py")
    print("   ├── .gitignore")
    print("   ├── .python-version")
    print("   ├── module.yaml")
    if config.include_ui:
        print("   ├── config_schema.json")
    print("   ├── tasks/")
    print("   │   └── example_task.py")
    print("   └── workflows/")
    print(f"       └── {config.workflow_name}.py")
    print()

    if config.init_git and not _run_git_init(config.output_dir):
        return 1

    if config.auto_install and not _run_uv_sync(config.output_dir):
        return 1

    print()
    print("下一步:")
    print(f"   cd {config.output_dir.name}")
    if not config.init_git:
        print("   git init                 # 初始化 Git 仓库")
    if not config.auto_install:
        print("   uv sync                  # 安装项目依赖（含 crawler4j-sdk）")
    print("   uv run crawler4j add            # 创建新任务")
    print("   uv run crawler4j add-workflow   # 创建新工作流")
    if config.include_ui:
        print("   uv run crawler4j add-ui         # 生成/补齐配置 UI")
    print("   在应用中把该目录注册/扫描为模块后，可在 ATM 中对相关作业发起“任务调试”")
    return 0


def cmd_add(args) -> int:
    """Interactively create a task script."""
    module_root = require_module_root()
    if not module_root:
        return 1
    tasks_dir = find_tasks_dir(module_root)

    if args.name:
        name = args.name
    else:
        name = input("脚本名称 (如 my_task): ").strip()
        if not name:
            print("❌ 脚本名称不能为空")
            return 1

    if not is_valid_python_file_stem(name):
        print("❌ 任务名称必须是小写 Python 标识符")
        print("   例如: fetch_homepage")
        return 1

    display_name = input(f"显示名称 [{to_display_name(name)}]: ").strip()
    if not display_name:
        display_name = to_display_name(name)

    description = input("描述 [TODO: 添加描述]: ").strip()
    if not description:
        description = "TODO: 添加描述"

    tasks_dir.mkdir(parents=True, exist_ok=True)
    init_file = tasks_dir / "__init__.py"
    if not init_file.exists():
        _write_text(init_file, "")

    filepath = tasks_dir / f"{name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1

    _write_text(
        filepath,
        SCRIPT_TEMPLATE.format(
            name=name,
            class_name=to_class_name(name),
            display_name=display_name,
            description=description,
        ),
    )

    print()
    print(f"✅ 创建脚本: {filepath}")
    print(f"   类名: {to_class_name(name)}")
    print(f"   显示名: {display_name}")
    return 0


def cmd_list(args) -> int:
    """List task scripts in the current project."""
    module_root = require_module_root()
    if not module_root:
        return 1
    tasks_dir = find_tasks_dir(module_root)

    if not tasks_dir.exists():
        print("暂无脚本目录")
        return 0

    scripts = [s for s in tasks_dir.glob("*.py") if not s.name.startswith("_")]
    if not scripts:
        print("暂无脚本")
        return 0

    print(f"📦 脚本目录: {tasks_dir}")
    print(f"共 {len(scripts)} 个脚本:")
    for script in sorted(scripts):
        print(f"   - {script.stem}")

    return 0


def cmd_new(args) -> int:
    """Create a task script non-interactively."""
    module_root = require_module_root()
    if not module_root:
        return 1
    tasks_dir = find_tasks_dir(module_root)
    name = args.name

    if not is_valid_python_file_stem(name):
        print("❌ 任务名称必须是小写 Python 标识符")
        print("   例如: fetch_homepage")
        return 1

    filepath = tasks_dir / f"{name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1

    tasks_dir.mkdir(parents=True, exist_ok=True)
    init_file = tasks_dir / "__init__.py"
    if not init_file.exists():
        _write_text(init_file, "")

    _write_text(
        filepath,
        SCRIPT_TEMPLATE.format(
            name=name,
            class_name=to_class_name(name),
            display_name=to_display_name(name),
            description="TODO: 添加描述",
        ),
    )
    print(f"✅ 创建脚本: {filepath}")
    return 0


def cmd_add_workflow(args) -> int:
    """Create a workflow file and register it in module.yaml."""
    module_root = find_module_root()
    if not module_root:
        print("❌ 当前目录不在 model 项目中，找不到 module.yaml")
        return 1

    name = args.name.strip()
    if not is_valid_python_file_stem(name):
        print("❌ 工作流名称必须是小写 Python 标识符")
        print("   例如: sync_orders")
        return 1

    display_name = (args.display_name or to_display_name(name)).strip()
    description = (args.description or f"{display_name} 工作流").strip()

    workflows_dir = find_workflows_dir(module_root)
    _ensure_package_dir(workflows_dir)
    filepath = workflows_dir / f"{name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        print("   使用 --force 覆盖")
        return 1

    _write_text(
        filepath,
        WORKFLOW_TEMPLATE.format(
            name=name,
            class_name=to_workflow_class_name(name),
            display_name=display_name,
            description=description,
        ),
    )

    manifest = load_manifest(module_root)
    try:
        upsert_workflow_manifest_entry(
            manifest,
            name=name,
            display_name=display_name,
            description=description,
            force=args.force,
        )
    except ValueError as error:
        print(f"❌ {error}")
        return 1

    save_manifest(module_root, manifest)
    print(f"✅ 创建工作流: {filepath}")
    print("✅ 已更新 module.yaml")
    return 0


def cmd_add_ui(args) -> int:
    """Create or repair a declarative UI config for a module project."""
    module_root = find_module_root()
    if not module_root:
        print("❌ 当前目录不在 model 项目中，找不到 module.yaml")
        return 1

    manifest = load_manifest(module_root)
    module_name = manifest.get("name") or module_root.name
    display_name = manifest.get("display_name") or to_display_name(module_name)
    workflow_name = "main_workflow"
    workflows = manifest.get("workflows") or []
    if workflows:
        workflow_name = workflows[0].get("name") or workflow_name

    title = (args.title or f"{display_name} 配置").strip()
    description = (args.description or f"{display_name} 的运行参数配置").strip()

    config_path = module_root / "config_schema.json"
    if config_path.exists() and not args.force:
        print(f"ℹ️ 已存在配置 Schema，保留现有文件: {config_path}")
    else:
        _write_text(
            config_path,
            CONFIG_SCHEMA_TEMPLATE.format(
                title=title,
                description=description,
                workflow_name=workflow_name,
            ),
        )
        print(f"✅ 创建配置 UI: {config_path}")

    ensure_ui_extension(manifest, display_name=display_name, entry="config_schema.json")
    save_manifest(module_root, manifest)
    print("✅ 已更新 module.yaml")
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="crawler4j",
        description="Crawler4j model 开发工具",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    init_model_parser = subparsers.add_parser("init-model", help="初始化完整 model 项目")
    init_model_parser.add_argument("name", help="model / 模块名称（小写包名）")
    init_model_parser.add_argument("-o", "--output", help="输出目录")
    init_model_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    init_model_parser.add_argument("--defaults", action="store_true", help="使用命令行参数与默认值，不进入交互向导")
    init_model_parser.add_argument("--no-install", action="store_true", help="不自动安装依赖")
    init_model_parser.add_argument("--no-git", action="store_true", help="不自动初始化 Git 仓库")
    init_model_parser.add_argument(
        "--workflow-name",
        default="main_workflow",
        help="默认工作流名称",
    )
    init_model_parser.add_argument("--display-name", help="模块显示名称")
    init_model_parser.add_argument("--description", help="模块描述")
    init_model_parser.add_argument("--workflow-display-name", help="工作流显示名称")
    init_model_parser.add_argument("--workflow-description", help="工作流描述")
    init_model_parser.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION, help="写入 .python-version 的 Python 版本")
    init_model_parser.add_argument("--no-ui", action="store_true", help="不生成配置 UI")
    init_model_parser.set_defaults(func=cmd_init_model)

    add_parser = subparsers.add_parser("add", help="在当前 model 项目中交互式创建任务脚本")
    add_parser.add_argument("name", nargs="?", help="任务脚本名称（可选，不填则交互式输入）")
    add_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    add_parser.set_defaults(func=cmd_add)

    new_parser = subparsers.add_parser("new", help="在当前 model 项目中快速创建任务脚本")
    new_parser.add_argument("name", help="任务脚本名称")
    new_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    new_parser.set_defaults(func=cmd_new)

    list_parser = subparsers.add_parser("list", help="列出当前 model 项目中的任务脚本")
    list_parser.set_defaults(func=cmd_list)

    workflow_parser = subparsers.add_parser("add-workflow", help="创建工作流模板并更新 module.yaml")
    workflow_parser.add_argument("name", help="工作流名称")
    workflow_parser.add_argument("--display-name", help="工作流显示名称")
    workflow_parser.add_argument("--description", help="工作流描述")
    workflow_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖")
    workflow_parser.set_defaults(func=cmd_add_workflow)

    ui_parser = subparsers.add_parser("add-ui", help="创建或补齐 declarative UI 配置")
    ui_parser.add_argument("--title", help="UI 标题")
    ui_parser.add_argument("--description", help="UI 描述")
    ui_parser.add_argument("-f", "--force", action="store_true", help="强制覆盖配置文件")
    ui_parser.set_defaults(func=cmd_add_ui)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
