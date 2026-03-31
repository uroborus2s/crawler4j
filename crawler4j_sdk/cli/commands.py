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
    MODEL_PROJECT_PYPROJECT,
    MODEL_PROJECT_README,
    MODEL_UI_PAGES_TEMPLATE,
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


def to_data_class_name(name: str) -> str:
    """Convert a identifier to a class name (Model/Page)."""
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


def find_tasks_dir(module_root: Path) -> Path:
    return module_root / "tasks"


def find_workflows_dir(module_root: Path) -> Path:
    return module_root / "workflows"


def find_data_dir(module_root: Path) -> Path:
    return module_root / "data"


def find_ui_dir(module_root: Path) -> Path:
    return module_root / "ui"


def load_manifest(module_root: Path) -> dict[str, Any]:
    """Load module.yaml as a mutable dictionary."""
    manifest_path = module_root / "module.yaml"
    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def save_manifest(module_root: Path, manifest: dict[str, Any]) -> None:
    """Persist module.yaml while keeping key order stable."""
    manifest_path = module_root / "module.yaml"
    with manifest_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)


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
        return True
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
    """Initialize a complete model/module project."""
    module_name = args.name.strip()
    if not is_valid_module_name(module_name):
        print("❌ model 名称不符合规范")
        return 1

    config = _build_init_model_config(args, module_name)

    if config.output_dir.exists() and not args.force:
        print(f"❌ 目录已存在: {config.output_dir}")
        return 1

    config.output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_package_dir(config.output_dir / "tasks")
    _ensure_package_dir(config.output_dir / "workflows")
    _ensure_package_dir(config.output_dir / "data")
    _ensure_package_dir(config.output_dir / "ui")

    _write_text(config.output_dir / "pyproject.toml", MODEL_PROJECT_PYPROJECT.format(
        project_name=module_name, display_name=config.display_name, python_version=config.python_version
    ))
    _write_text(config.output_dir / "README.md", MODEL_PROJECT_README.format(display_name=config.display_name))
    _write_text(config.output_dir / "__init__.py", MODEL_MODULE_INIT.format(
        display_name=config.display_name, default_workflow=config.workflow_name
    ))
    _write_text(config.output_dir / "module.yaml", MODEL_MANIFEST_TEMPLATE.format(
        module_name=module_name, display_name=config.display_name, description=config.description,
        workflow_name=config.workflow_name, workflow_display_name=config.workflow_display_name,
        workflow_description=config.workflow_description,
        ui_section="" if not config.include_ui else MODEL_UI_SECTION.format(display_name=config.display_name),
    ))
    _write_text(config.output_dir / "tasks" / "example_task.py", SCRIPT_TEMPLATE.format(
        name="example_task", class_name="ExampleTask", display_name="示例任务", description="任务描述"
    ))
    _write_text(config.output_dir / "workflows" / f"{config.workflow_name}.py", WORKFLOW_TEMPLATE.format(
        name=config.workflow_name, class_name=to_workflow_class_name(config.workflow_name),
        display_name=config.workflow_display_name, description=config.workflow_description,
    ))
    _write_text(config.output_dir / ".gitignore", MODEL_GITIGNORE_TEMPLATE)
    _write_text(config.output_dir / ".python-version", f"{config.python_version}\n")

    if config.include_ui:
        _write_text(config.output_dir / "ui" / "config_schema.json", CONFIG_SCHEMA_TEMPLATE.format(
            title=f"{config.display_name} 配置", description="配置描述", workflow_name=config.workflow_name
        ))

    if config.init_git:
        _run_git_init(config.output_dir)
    if config.auto_install:
        _run_uv_sync(config.output_dir)

    print(f"✅ 初始化规范化 model 项目: {config.output_dir}")
    return 0


def cmd_add(args) -> int:
    module_root = require_module_root()
    name = args.name
    tasks_dir = find_tasks_dir(module_root)
    _ensure_package_dir(tasks_dir)
    _write_text(tasks_dir / f"{name}.py", SCRIPT_TEMPLATE.format(
        name=name, class_name=to_class_name(name), display_name=to_display_name(name), description="任务描述"
    ))
    print(f"✅ 创建任务: {tasks_dir}/{name}.py")
    return 0


def cmd_add_workflow(args) -> int:
    module_root = require_module_root()
    name = args.name
    wf_dir = find_workflows_dir(module_root)
    _ensure_package_dir(wf_dir)
    _write_text(wf_dir / f"{name}.py", WORKFLOW_TEMPLATE.format(
        name=name, class_name=to_workflow_class_name(name), display_name=to_display_name(name), description="描述"
    ))
    
    manifest = load_manifest(module_root)
    workflows = manifest.get("workflows", [])
    if not any(w["name"] == name for w in workflows):
        workflows.append({"name": name, "display_name": to_display_name(name), "description": "描述"})
        manifest["workflows"] = workflows
        save_manifest(module_root, manifest)
    print(f"✅ 创建工作流: {wf_dir}/{name}.py")
    return 0


def cmd_add_data(args) -> int:
    module_root = require_module_root()
    name = args.name
    data_dir = find_data_dir(module_root)
    _ensure_package_dir(data_dir)
    _write_text(data_dir / f"{name}.py", MODEL_DATA_MODELS_TEMPLATE.format(
        display_name=to_display_name(name), description="数据模型", class_name=to_data_class_name(name)
    ))
    print(f"✅ 创建模型: {data_dir}/{name}.py")
    return 0


def cmd_add_ui(args) -> int:
    module_root = require_module_root()
    ui_dir = find_ui_dir(module_root)
    _ensure_package_dir(ui_dir)
    
    if args.type == "code":
        name = args.name or "dashboard"
        _write_text(ui_dir / f"{name}.py", MODEL_UI_PAGES_TEMPLATE.format(
            display_name=to_display_name(name), description="UI 页面", class_name=to_data_class_name(name)
        ))
        manifest = load_manifest(module_root)
        ui_ext = manifest.get("ui_extension", {})
        ui_ext["type"] = "micro_app"
        ui_ext["entry"] = f"ui:{to_data_class_name(name)}"
        manifest["ui_extension"] = ui_ext
        save_manifest(module_root, manifest)
        print(f"✅ 创建代码 UI: {ui_dir}/{name}.py 并更新清单")
    else:
        _write_text(ui_dir / "config_schema.json", CONFIG_SCHEMA_TEMPLATE.format(
            title="配置", description="描述", workflow_name="main_workflow"
        ))
        print(f"✅ 创建声明式配置 UI")
    return 0


def cmd_list(args) -> int:
    module_root = require_module_root()
    tasks_dir = find_tasks_dir(module_root)
    if not tasks_dir.exists():
        print("暂无任务")
        return 0
    scripts = [s.stem for s in tasks_dir.glob("*.py") if not s.name.startswith("_")]
    print(f"📦 共 {len(scripts)} 个任务: {', '.join(scripts)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="crawler4j")
    subparsers = parser.add_subparsers(dest="command")

    init_p = subparsers.add_parser("init-model")
    init_p.add_argument("name")
    init_p.add_argument("-o", "--output")
    init_p.add_argument("-f", "--force", action="store_true")
    init_p.add_argument("--defaults", action="store_true")
    init_p.add_argument("--no-install", action="store_true")
    init_p.add_argument("--no-git", action="store_true")
    init_p.add_argument("--workflow-name", default="main_workflow")
    init_p.add_argument("--display-name")
    init_p.add_argument("--description")
    init_p.add_argument("--workflow-display-name")
    init_p.add_argument("--workflow-description")
    init_p.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION)
    init_p.add_argument("--no-ui", action="store_true")
    init_p.set_defaults(func=cmd_init_model)

    add_p = subparsers.add_parser("add")
    add_p.add_argument("name")
    add_p.set_defaults(func=cmd_add)

    wf_p = subparsers.add_parser("add-workflow")
    wf_p.add_argument("name")
    wf_p.set_defaults(func=cmd_add_workflow)

    data_p = subparsers.add_parser("add-data")
    data_p.add_argument("name")
    data_p.set_defaults(func=cmd_add_data)

    ui_p = subparsers.add_parser("add-ui")
    ui_p.add_argument("name", nargs="?")
    ui_p.add_argument("--type", choices=["declarative", "code"], default="declarative")
    ui_p.set_defaults(func=cmd_add_ui)

    list_p = subparsers.add_parser("list")
    list_p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
