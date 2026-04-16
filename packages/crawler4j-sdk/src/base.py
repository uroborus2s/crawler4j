"""TaskScript 基类定义。

本模块定义了 Crawler4j SDK 的核心契约之一：TaskScript（原子任务基类）。
所有任务脚本必须继承此类并实现 execute 方法。

稳定契约 (Stable API - 同 MAJOR 版本内冻结):
    - 类属性: name, display_name, description, default_config
    - 方法: execute

参考规格: docs/02-requirements/reference-srs/06-sdk/06-1-taskscript.md
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crawler4j_sdk.context import TaskContext
    from crawler4j_sdk.result import TaskResult


class TaskScript(ABC):
    """原子任务基类。
    
    TaskScript 是最小可执行单元：给定上下文与配置，执行一次业务动作并返回结构化结果。
    
    类属性 (Stable):
        name: 任务唯一标识符 (MUST)，用于调度、引用和追溯。
        display_name: 面向 UI/日志的可读名称 (SHOULD)。
        description: 简要说明 (SHOULD)。
        default_config: 默认配置字典 (MAY)，运行时会与外部配置深合并。
    
    并发语义:
        - 单个 TaskScript 实例不要求线程安全
        - 框架不得并发调用同一实例的 execute
        - 每次执行应使用新实例，避免隐式共享状态
    
    示例:
        >>> from crawler4j_sdk import TaskScript, TaskContext, TaskResult
        >>>
        >>> class LoginTask(TaskScript):
        ...     name = "login"
        ...     display_name = "用户登录"
        ...     description = "执行网站登录流程"
        ...     default_config = {"timeout": 30}
        ...
        ...     async def execute(self, ctx: TaskContext) -> TaskResult:
        ...         await ctx.page.goto("https://example.com/login")
        ...         # ... 登录逻辑
        ...         return TaskResult.ok(message="登录成功")
    """
    
    # === 类属性 (Stable) ===
    
    name: str = ""
    """任务唯一标识符 (MUST)。用于调度、引用和追溯，应保持稳定。"""
    
    display_name: str = ""
    """面向 UI/日志的可读名称 (SHOULD)。"""
    
    description: str = ""
    """任务简要说明 (SHOULD)。"""
    
    default_config: dict[str, Any] = {}
    """默认配置字典 (MAY)。运行时会与外部配置深合并，外部配置优先。"""
    
    # === 主执行方法 (Stable) ===
    
    @abstractmethod
    async def execute(self, ctx: "TaskContext") -> "TaskResult":
        """执行任务的主方法 (MUST 实现)。
        
        这是 TaskScript 的核心方法，子类必须实现。
        方法应完成一次完整的业务动作并返回结构化结果。
        
        Args:
            ctx: 任务执行上下文，提供 page、config、runtime、logger、tools 等能力。
                 脚本应只通过 ctx 获取框架能力，不得直接耦合 Core 内部对象。
        
        Returns:
            TaskResult: 执行结果。成功使用 TaskResult.ok()，失败使用 TaskResult.fail()。

        Raises:
            Exception: 允许抛出异常，由宿主 ATM 统一处理并映射到失败生命周期。

        Note:
            - 业务失败（可预期）建议返回 TaskResult.fail()
            - 不可预期异常可直接抛出，由运行时处理
            - 应避免长时间阻塞调用，使用 async I/O
        """
        raise NotImplementedError
