"""Crawler4j SDK - 任务脚本开发工具包。

本包提供 Crawler4j 任务脚本开发工具。
稳定契约类型由 crawler4j-contracts 提供，SDK 对其进行聚合导出。

稳定导出 (Stable API - 同 MAJOR 版本内冻结):
    - TaskScript: 原子任务基类
    - TaskFlow: 工作流编排基类
    - TaskContext: 任务执行上下文
    - TaskResult: 任务结果模型
    - DatabaseCapability: Core 注入的数据能力接口

2.0.0 起的破坏性变更:
    - 删除 DataService 兼容命名
    - 删除旧的 `ctx.db.storage / accounts / tasks` 文档口径
    - 模块必须直接使用 `TaskContext.db` 和 `DatabaseCapability`

非稳定扩展 (Non-stable):
    - extensions 模块: 业务特定扩展类型

安装:
    uv tool install crawler4j-sdk
    # 或一次性运行
    uvx --from crawler4j-sdk crawler4j --help

快速开始:
    >>> from crawler4j_sdk import TaskScript, TaskContext, TaskResult
    >>> 
    >>> class MyTask(TaskScript):
    ...     name = "my_task"
    ...     display_name = "我的任务"
    ...     
    ...     async def execute(self, ctx: TaskContext) -> TaskResult:
    ...         await ctx.page.goto("https://example.com")
    ...         return TaskResult.ok(message="完成")

CLI 命令:
    crawler4j init-model <module_name>  # 初始化完整模块项目
    crawler4j add [name]                # 在模块目录中创建脚本
    crawler4j list                      # 在模块目录中列出脚本

参考文档: docs/02-requirements/reference-srs/06-sdk/
"""

from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.workflow import TaskFlow
from crawler4j_contracts import (
    DatabaseCapability,
    EnvOpsCapability,
    IPPoolCapability,
    TaskContext,
    TaskResult,
    UICapability,
)

__version__ = "2.0.0"

# 稳定导出列表（同 MAJOR 版本内冻结）
__all__ = [
    # 核心契约类型
    "TaskScript",
    "TaskFlow",
    "TaskContext",
    "TaskResult",
    "DatabaseCapability",
    "IPPoolCapability",
    "EnvOpsCapability",
    "UICapability",
]
