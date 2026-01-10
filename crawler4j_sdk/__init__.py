"""Crawler4j SDK - 任务脚本开发工具包。

本包提供 Crawler4j 任务脚本的开发契约和工具。
SDK 是 Modules 与 Core/Runtime 之间的唯一契约边界。

稳定导出 (Stable API - 同 MAJOR 版本内冻结):
    - TaskScript: 原子任务基类
    - TaskFlow: 工作流编排基类
    - TaskContext: 任务执行上下文
    - TaskResult: 任务结果模型
    - DataService: 数据服务聚合类

非稳定扩展 (Non-stable):
    - extensions 模块: 业务特定扩展类型

安装:
    pip install crawler4j-sdk

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
    crawler4j init <project_name>  # 初始化项目
    crawler4j add [name]           # 创建脚本
    crawler4j list                 # 列出脚本

参考文档: docs/srs/06-sdk/
"""

from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.context import TaskContext
from crawler4j_sdk.db import DataService
from crawler4j_sdk.result import TaskResult
from crawler4j_sdk.workflow import TaskFlow

__version__ = "1.0.0"

# 稳定导出列表（同 MAJOR 版本内冻结）
__all__ = [
    # 核心契约类型
    "TaskScript",
    "TaskFlow",
    "TaskContext",
    "TaskResult",
    "DataService",
]
