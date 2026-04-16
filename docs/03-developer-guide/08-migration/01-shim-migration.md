# 8.1 模块根入口收敛迁移指南 (SDK 2.1.0+)

从 SDK 2.1.0 起，模块的根 `__init__.py` 已被收敛为**自动托管的薄壳 (Shim)**。这意味着你不再需要（也不建议）手动修改 `__init__.py`。

## 为什么要迁移？

- **标准化:** 避免每个模块都重复实现复杂的发现逻辑。
- **解耦:** 模块开发者只需关注业务代码（Tasks/Workflows），无需维护框架样板代码。
- **平滑升级:** 框架逻辑的改进将直接在 SDK `ModuleAssembler` 中更新，无需修改模块代码。

## 迁移步骤（旧模块升级）

旧模块（SDK < 2.1.0）必须按照以下步骤迁移到最新结构：

### 1. 重新生成根 `__init__.py`
将你的根 `__init__.py` 内容替换为最新模板（推荐直接使用 `crawler4j init-model` 重新生成，而不是手抄旧片段）。当前正式模板除了 `run` 以外，还会导出 `select_env` 与标准 lifecycle hooks：

```python
"""模块入口。

本文件由 SDK 自动托管，不建议手动修改。
模块级运行时逻辑统一放在同级目录的标准文件 `module_runtime.py` 中。
"""

from pathlib import Path
from crawler4j_sdk import ModuleAssembler, TaskContext, TaskResult

# 初始化模块组装器
assembler = ModuleAssembler(
    package_root=Path(__file__).parent,
    module_name=__name__,
    default_workflow="main_workflow"  # 替换为你的默认工作流名称
)

async def run(context: TaskContext) -> TaskResult:
    """模块执行入口，由 Core 调用。"""
    return await assembler.run(context)
```

### 2. 迁移生命周期 Hooks (如有)
如果你之前在 `__init__.py` 中定义了 `prepare_env`, `init_env` 或 `on_cleanup` 等 Hooks，请将它们移动到同级目录的新文件 `module_runtime.py` 中。

**旧版 `__init__.py`:**
```python
async def prepare_env(context):
    # 一些初始化逻辑
    pass
```

**新版 `module_runtime.py`:**
```python
async def prepare_env(context):
    # 原封不动搬过来即可
    pass
```

### 3. 迁移自定义组件注册 (可选)
如果你有特殊的任务发现逻辑或需要手动注册组件，同样放在 `module_runtime.py` 中：

```python
# module_runtime.py
from my_custom_place import SpecialTask

TASK_SCRIPTS = {
    "special_task": SpecialTask
}
```

## 常见问题 (FAQ)

### Q: `__init__.py` 里的 `run` 函数还能改吗？
A: 不建议修改。现在的 `run` 函数只是调用 `assembler.run(context)`。如果你需要改变分发逻辑，请考虑是否可以改用 `module_runtime.py` 或反馈给 SDK 维护者。

### Q: 必须按最新模板重新初始化吗？
A: 是的。SDK 2.1.0 不再承诺兼容旧版手工维护的 `__init__.py` 逻辑。为了长期的维护性，请务必完成迁移。

### Q: `module_runtime.py` 是必须的吗？
A: 是。现在它是标准模块文件，脚手架默认会生成。即使你暂时不写自定义 hooks，也需要保留该文件，因为 ATM 的“选择环境”模式依赖它声明 `@env_selector(...)` 回调。
