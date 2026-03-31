"""CLI commands for module scaffolding."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from crawler4j_sdk.cli.templates import (
    CONFIG_SCHEMA_TEMPLATE,
    MODEL_DATA_MODELS_TEMPLATE,
    MODEL_GITIGNORE_TEMPLATE,
    MODEL_MANIFEST_TEMPLATE,
    MODEL_MODULE_INIT,
    MODEL_RUNTIME_TEMPLATE,
    MODEL_PROJECT_PYPROJECT,
    MODEL_PROJECT_README,
    MODEL_TEST_TASK_TEMPLATE,
    MODEL_UI_PAGES_TEMPLATE,
    MODEL_UI_SECTION,
    MODEL_UTILS_HELPER_TEMPLATE,
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
    """Convert a identifier to a class name."""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts)


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


def require_module_root(start: Path | None = None) -> Path:
    """Require the current working tree to be a module project."""
    module_root = find_module_root(start)
    if module_root:
        return module_root

    print("❌ 当前目录不在 model 项目中，找不到 module.yaml")
    print("   请先执行 `crawler4j init-model <module_name>` 创建完整模块项目")
    sys.exit(1)


def load_manifest(module_root: Path) -> dict[str, Any]:
    """Load module.yaml as a mutable dictionary."""
    manifest_path = module_root / "module.yaml"
    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def save_manifest(module_root: Path, manifest: dict[str, Any]) -> None:
    """Persist module.yaml."""
    manifest_path = module_root / "module.yaml"
    with manifest_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)


def _run_git_init(output_dir: Path) -> bool:
    try:
        subprocess.run(["git", "init"], cwd=str(output_dir), check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _run_uv_sync(output_dir: Path) -> bool:
    try:
        subprocess.run(["uv", "sync"], cwd=str(output_dir), check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def cmd_init_model(args) -> int:
    """Initialize a complete model/module project with standardized layers."""
    module_name = args.name.strip()
    if not is_valid_module_name(module_name):
        print("❌ model 名称不符合规范")
        return 1

    # 简单配置构建
    output_dir = Path(args.output).expanduser() if args.output else Path.cwd() / module_name
    if output_dir.exists() and not args.force:
        print(f"❌ 目录已存在: {output_dir}")
        return 1

    display_name = args.display_name or to_display_name(module_name)
    wf_name = args.workflow_name or "main_workflow"

    # 1. 创建核心目录
    output_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["tasks", "workflows", "data", "ui", "utils", "tests"]:
        _ensure_package_dir(output_dir / sub)

    # 2. 写入工程文件
    _write_text(output_dir / "pyproject.toml", MODEL_PROJECT_PYPROJECT.format(
        project_name=module_name, display_name=display_name, python_version=args.python_version
    ))
    _write_text(output_dir / "README.md", MODEL_PROJECT_README.format(display_name=display_name))
    _write_text(output_dir / "__init__.py", MODEL_MODULE_INIT.format(
        display_name=display_name
    ))
    # module_runtime.py is optional and skipped by default to keep the root clean
    
    _write_text(output_dir / "module.yaml", MODEL_MANIFEST_TEMPLATE.format(
        module_name=module_name, display_name=display_name, description=f"{display_name} 模块",
        workflow_name=wf_name, workflow_display_name=to_display_name(wf_name),
        workflow_description="默认工作流",
        ui_section=MODEL_UI_SECTION.format(display_name=display_name),
    ))
    
    # 3. 写入初始代码模板
    _write_text(output_dir / "tasks" / "example_task.py", SCRIPT_TEMPLATE.format(
        name="example_task", class_name="ExampleTask", display_name="示例任务", description="任务描述"
    ))
    _write_text(output_dir / "workflows" / f"{wf_name}.py", WORKFLOW_TEMPLATE.format(
        name=wf_name, class_name=f"{to_class_name(wf_name)}Workflow",
        display_name=to_display_name(wf_name), description="工作流描述",
    ))
    _write_text(output_dir / "data" / "models.py", MODEL_DATA_MODELS_TEMPLATE.format(
        display_name="Example", description="示例数据模型", class_name="ExampleModel"
    ))
    _write_text(output_dir / "utils" / "helpers.py", MODEL_UTILS_HELPER_TEMPLATE)
    _write_text(output_dir / "tests" / "test_tasks.py", MODEL_TEST_TASK_TEMPLATE)
    _write_text(output_dir / "ui" / "config_schema.json", CONFIG_SCHEMA_TEMPLATE.format(
        title=f"{display_name} 配置", description="参数配置", workflow_name=wf_name
    ))
    
    _write_text(output_dir / ".gitignore", MODEL_GITIGNORE_TEMPLATE)
    _write_text(output_dir / ".python-version", f"{args.python_version}\n")

    if not args.no_git:
        _run_git_init(output_dir)
    if not args.no_install:
        _run_uv_sync(output_dir)

    print(f"✅ 初始化规范化 model 项目: {output_dir}")
    print(f"   已包含分层结构: Tasks, Workflows, Data, UI, Utils, Tests")
    return 0


def cmd_add(args) -> int:
    module_root = require_module_root()
    name = args.name
    _write_text(module_root / "tasks" / f"{name}.py", SCRIPT_TEMPLATE.format(
        name=name, class_name=f"{to_class_name(name)}Task", display_name=to_display_name(name), description="任务描述"
    ))
    print(f"✅ 创建任务: tasks/{name}.py")
    return 0


def cmd_new(args) -> int:
    """Alias for cmd_add."""
    return cmd_add(args)


def cmd_list(args) -> int:
    """List all task scripts in the module."""
    module_root = require_module_root()
    tasks_dir = module_root / "tasks"
    print(f"📋 模块 {module_root.name} 中的任务脚本：")
    found = False
    for item in tasks_dir.glob("*.py"):
        if item.name.startswith("_"):
            continue
        print(f"  - {item.stem}")
        found = True
    if not found:
        print("  (无)")
    return 0


def cmd_add_workflow(args) -> int:
    module_root = require_module_root()
    name = args.name
    _write_text(module_root / "workflows" / f"{name}.py", WORKFLOW_TEMPLATE.format(
        name=name, class_name=f"{to_class_name(name)}Workflow", display_name=to_display_name(name), description="描述"
    ))
    
    manifest = load_manifest(module_root)
    workflows = manifest.get("workflows", [])
    if not any(w["name"] == name for w in workflows):
        workflows.append({"name": name, "display_name": to_display_name(name), "description": "描述"})
        manifest["workflows"] = workflows
        save_manifest(module_root, manifest)
    print(f"✅ 创建工作流: workflows/{name}.py 并更新清单")
    return 0


def cmd_add_data(args) -> int:
    module_root = require_module_root()
    name = args.name
    _write_text(module_root / "data" / f"{name}.py", MODEL_DATA_MODELS_TEMPLATE.format(
        display_name=to_display_name(name), description="数据模型", class_name=to_class_name(name)
    ))
    print(f"✅ 创建数据模型: data/{name}.py")
    return 0


def cmd_add_ui(args) -> int:
    module_root = require_module_root()
    ui_type = getattr(args, "type", "declarative")
    if ui_type == "code":
        name = getattr(args, "name", "dashboard") or "dashboard"
        _write_text(module_root / "ui" / f"{name}.py", MODEL_UI_PAGES_TEMPLATE.format(
            display_name=to_display_name(name), description="UI 页面", class_name=f"{to_class_name(name)}Page"
        ))
        manifest = load_manifest(module_root)
        ui_ext = manifest.get("ui_extension", {})
        ui_ext["type"] = "micro_app"
        ui_ext["entry"] = f"ui.{name}:{to_class_name(name)}Page"
        manifest["ui_extension"] = ui_ext
        save_manifest(module_root, manifest)
        print(f"✅ 创建代码 UI: ui/{name}.py 并更新清单为 micro_app")
    else:
        print("ℹ️ 声明式配置 ui/config_schema.json 已默认存在。")
    return 0


def cmd_check(args) -> int:
    """Check module consistency."""
    module_root = find_module_root()
    if not module_root:
        print("❌ 未在模块根目录")
        return 1
    
    print(f"🔍 正在自检模块: {module_root.name}")
    manifest = load_manifest(module_root)
    errors = []
    
    # 1. 验证元数据
    if not manifest.get("name"): errors.append("缺失 name 字段")
    if not manifest.get("workflows"): errors.append("未定义 workflows")
    
    # 2. 验证物理目录
    for sub in ["tasks", "workflows", "data", "ui"]:
        if not (module_root / sub).exists():
            errors.append(f"缺少关键目录: {sub}/")
            
    # 3. 验证入口
    if not (module_root / "__init__.py").exists():
        errors.append("缺少根 __init__.py")
        
    if errors:
        for err in errors: print(f"  - ❌ {err}")
        return 1
    
    print("✅ 模块结构验证通过！")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="crawler4j", description="Crawler4j 开发工具")
    subparsers = parser.add_subparsers(dest="command")

    init_p = subparsers.add_parser("init-model", help="初始化规范化 model 项目")
    init_p.add_argument("name")
    init_p.add_argument("-o", "--output")
    init_p.add_argument("-f", "--force", action="store_true")
    init_p.add_argument("--no-install", action="store_true")
    init_p.add_argument("--no-git", action="store_true")
    init_p.add_argument("--workflow-name")
    init_p.add_argument("--display-name")
    init_p.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION)
    init_p.add_argument("--defaults", action="store_true", help="使用默认值，不进行交互")
    init_p.set_defaults(func=cmd_init_model)

    add_p = subparsers.add_parser("add", help="创建任务脚本")
    add_p.add_argument("name")
    add_p.set_defaults(func=cmd_add)

    new_p = subparsers.add_parser("new", help="创建任务脚本 (add 的别名)")
    new_p.add_argument("name")
    new_p.set_defaults(func=cmd_new)

    list_p = subparsers.add_parser("list", help="列出模块中的任务脚本")
    list_p.set_defaults(func=cmd_list)

    wf_p = subparsers.add_parser("add-workflow", help="创建工作流")
    wf_p.add_argument("name")
    wf_p.set_defaults(func=cmd_add_workflow)

    data_p = subparsers.add_parser("add-data", help="创建数据模型")
    data_p.add_argument("name")
    data_p.set_defaults(func=cmd_add_data)

    ui_p = subparsers.add_parser("add-ui", help="创建 UI 组件")
    ui_p.add_argument("name", nargs="?")
    ui_p.add_argument("--type", choices=["declarative", "code"], default="declarative")
    ui_p.set_defaults(func=cmd_add_ui)

    check_p = subparsers.add_parser("check", help="自检模块规范性")
    check_p.set_defaults(func=cmd_check)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
