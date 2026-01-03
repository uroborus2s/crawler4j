"""模块CLI命令实现

提供模块开发、打包、安装等命令。
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path
from textwrap import dedent

# 模块骨架模板
MODULE_YAML_TEMPLATE = dedent('''
name: {name}
display_name: {display_name}
description: TODO: 添加模块描述
version: 1.0.0
author: crawler4j

# 模块默认配置
config:
  max_retries: 3

# 任务链列表
workflows: []
''').strip()

WORKFLOW_TEMPLATE = dedent('''
"""任务链: {display_name}"""

from crawler4j_sdk import TaskFlow, TaskContext


class {class_name}(TaskFlow):
    """{display_name}"""
    
    name = "{name}"
    display_name = "{display_name}"
    description = "TODO: 添加描述"
    
    async def run(self, ctx: TaskContext) -> None:
        """执行任务链"""
        ctx.logger.info("开始执行任务链...")
        
        # TODO: 编排子任务
        # await ctx.run_subtask("login")
        # await ctx.run_subtask("search")
        
        ctx.logger.info("任务链执行完成")
''').strip()

TASK_TEMPLATE = dedent('''
"""子任务: {display_name}"""

from crawler4j_sdk import TaskScript, TaskContext, TaskResult


class {class_name}(TaskScript):
    """{display_name}"""
    
    name = "{name}"
    display_name = "{display_name}"
    description = "TODO: 添加描述"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行任务"""
        ctx.logger.info("开始执行任务...")
        
        # TODO: 实现任务逻辑
        
        return TaskResult.ok(
            tasks_completed=1,
            message="任务完成"
        )
''').strip()


def to_class_name(name: str) -> str:
    """转换为类名"""
    parts = name.replace("-", "_").split("_")
    return "".join(word.capitalize() for word in parts)


def to_display_name(name: str) -> str:
    """转换为显示名"""
    return name.replace("_", " ").replace("-", " ").title()


def get_modules_dir() -> Path:
    """获取模块目录"""
    return Path("modules")


def cmd_module_init(args):
    """初始化新模块"""
    name = args.name
    modules_dir = get_modules_dir()
    module_path = modules_dir / name
    
    if module_path.exists() and not args.force:
        print(f"❌ 模块已存在: {module_path}")
        print("   使用 --force 覆盖")
        return 1
    
    # 创建目录结构
    module_path.mkdir(parents=True, exist_ok=True)
    (module_path / "workflows").mkdir(exist_ok=True)
    (module_path / "tasks").mkdir(exist_ok=True)
    
    # 创建 module.yaml
    yaml_path = module_path / "module.yaml"
    yaml_path.write_text(
        MODULE_YAML_TEMPLATE.format(
            name=name,
            display_name=to_display_name(name),
        ),
        encoding="utf-8"
    )
    
    print(f"✅ 创建模块: {module_path}")
    print(f"   {module_path}/")
    print(f"   ├── module.yaml")
    print(f"   ├── workflows/")
    print(f"   └── tasks/")
    print()
    print("下一步:")
    print(f"   crawler4j module add-workflow {name} <workflow_name>")
    print(f"   crawler4j module add-task {name} <task_name>")
    return 0


def cmd_module_add_workflow(args):
    """添加任务链"""
    module_name = args.module
    workflow_name = args.name
    
    module_path = get_modules_dir() / module_name
    if not module_path.exists():
        print(f"❌ 模块不存在: {module_name}")
        return 1
    
    workflows_dir = module_path / "workflows"
    workflows_dir.mkdir(exist_ok=True)
    
    filepath = workflows_dir / f"{workflow_name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        return 1
    
    class_name = to_class_name(workflow_name) + "Workflow"
    display_name = to_display_name(workflow_name)
    
    filepath.write_text(
        WORKFLOW_TEMPLATE.format(
            name=workflow_name,
            class_name=class_name,
            display_name=display_name,
        ),
        encoding="utf-8"
    )
    
    print(f"✅ 创建任务链: {filepath}")
    print(f"   类名: {class_name}")
    return 0


def cmd_module_add_task(args):
    """添加子任务"""
    module_name = args.module
    task_name = args.name
    
    module_path = get_modules_dir() / module_name
    if not module_path.exists():
        print(f"❌ 模块不存在: {module_name}")
        return 1
    
    tasks_dir = module_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    
    filepath = tasks_dir / f"{task_name}.py"
    if filepath.exists() and not args.force:
        print(f"❌ 文件已存在: {filepath}")
        return 1
    
    class_name = to_class_name(task_name) + "Task"
    display_name = to_display_name(task_name)
    
    filepath.write_text(
        TASK_TEMPLATE.format(
            name=task_name,
            class_name=class_name,
            display_name=display_name,
        ),
        encoding="utf-8"
    )
    
    print(f"✅ 创建子任务: {filepath}")
    print(f"   类名: {class_name}")
    return 0


def cmd_module_validate(args):
    """验证模块"""
    from src.plugins.module_loader import ModuleLoader
    
    module_path = get_modules_dir() / args.module
    if not module_path.exists():
        print(f"❌ 模块不存在: {args.module}")
        return 1
    
    loader = ModuleLoader()
    valid, errors = loader.validate_module(module_path)
    
    if valid:
        print(f"✅ 模块 {args.module} 结构有效")
        return 0
    else:
        print(f"❌ 模块 {args.module} 验证失败:")
        for err in errors:
            print(f"   - {err}")
        return 1


def cmd_module_pack(args):
    """打包模块"""
    module_name = args.module
    module_path = get_modules_dir() / module_name
    
    if not module_path.exists():
        print(f"❌ 模块不存在: {module_name}")
        return 1
    
    # 读取版本号
    yaml_path = module_path / "module.yaml"
    version = "1.0.0"
    if yaml_path.exists():
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            version = data.get("version", "1.0.0")
    
    # 输出文件名
    output = args.output or f"{module_name}-{version}.zip"
    
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in module_path.rglob("*"):
            # 跳过 __pycache__
            if "__pycache__" in str(file_path):
                continue
            if file_path.is_file():
                arcname = file_path.relative_to(module_path)
                zf.write(file_path, arcname)
    
    print(f"✅ 已打包: {output}")
    return 0


def cmd_module_install(args):
    """安装模块"""
    from src.plugins.module_loader import get_module_loader
    
    loader = get_module_loader()
    loader.set_base_path(get_modules_dir())
    
    source = args.source
    
    if loader.install_module(source):
        print("✅ 安装成功")
        return 0
    else:
        print("❌ 安装失败")
        return 1


def cmd_module_list(args):
    """列出模块"""
    from src.plugins.module_loader import get_module_loader
    
    loader = get_module_loader()
    modules_dir = get_modules_dir()
    
    if not modules_dir.exists():
        print("暂无模块")
        return 0
    
    loader.scan_modules(modules_dir)
    modules = loader.list_modules()
    
    if not modules:
        print("暂无模块")
        return 0
    
    print(f"已加载 {len(modules)} 个模块:\n")
    for info in modules:
        print(f"  📦 {info.display_name or info.name}")
        print(f"     名称: {info.name}")
        print(f"     版本: {info.version}")
        if info.workflows:
            wf_names = [w.name for w in info.workflows]
            print(f"     任务链: {', '.join(wf_names)}")
        if info.tasks:
            print(f"     子任务: {', '.join(info.tasks)}")
        print()
    
    return 0


def setup_module_parser(subparsers):
    """设置模块命令解析器"""
    module_parser = subparsers.add_parser("module", help="模块管理命令")
    module_subparsers = module_parser.add_subparsers(dest="module_cmd")
    
    # init
    init_parser = module_subparsers.add_parser("init", help="创建新模块")
    init_parser.add_argument("name", help="模块名称")
    init_parser.add_argument("-f", "--force", action="store_true")
    init_parser.set_defaults(func=cmd_module_init)
    
    # add-workflow
    add_wf_parser = module_subparsers.add_parser("add-workflow", help="添加任务链")
    add_wf_parser.add_argument("module", help="模块名称")
    add_wf_parser.add_argument("name", help="任务链名称")
    add_wf_parser.add_argument("-f", "--force", action="store_true")
    add_wf_parser.set_defaults(func=cmd_module_add_workflow)
    
    # add-task
    add_task_parser = module_subparsers.add_parser("add-task", help="添加子任务")
    add_task_parser.add_argument("module", help="模块名称")
    add_task_parser.add_argument("name", help="子任务名称")
    add_task_parser.add_argument("-f", "--force", action="store_true")
    add_task_parser.set_defaults(func=cmd_module_add_task)
    
    # validate
    validate_parser = module_subparsers.add_parser("validate", help="验证模块")
    validate_parser.add_argument("module", help="模块名称")
    validate_parser.set_defaults(func=cmd_module_validate)
    
    # pack
    pack_parser = module_subparsers.add_parser("pack", help="打包模块")
    pack_parser.add_argument("module", help="模块名称")
    pack_parser.add_argument("-o", "--output", help="输出文件")
    pack_parser.set_defaults(func=cmd_module_pack)
    
    # install
    install_parser = module_subparsers.add_parser("install", help="安装模块")
    install_parser.add_argument("source", help="模块来源(zip/git)")
    install_parser.set_defaults(func=cmd_module_install)
    
    # list
    list_parser = module_subparsers.add_parser("list", help="列出模块")
    list_parser.set_defaults(func=cmd_module_list)
    
    return module_parser
