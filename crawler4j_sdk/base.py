"""TaskScript基类定义。

所有任务脚本必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawler4j_sdk.context import TaskContext
    from crawler4j_sdk.result import TaskResult


class TaskScript(ABC):
    """任务脚本基类
    
    所有任务脚本必须继承此类并实现 execute 方法。
    
    类属性:
        name: 脚本唯一标识符
        display_name: 显示名称
        description: 脚本描述
        default_config: 默认配置字典
    
    示例:
        ```python
        from crawler4j_sdk import TaskScript, TaskContext, TaskResult
        
        class MyTask(TaskScript):
            name = "my_task"
            display_name = "我的任务"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                await ctx.page.goto("https://example.com")
                return TaskResult(success=True)
        ```
    """
    
    # 必须在子类中定义
    name: str = ""
    display_name: str = ""
    description: str = ""
    
    # 可选：默认配置
    default_config: dict = {}
    
    @abstractmethod
    async def execute(self, ctx: "TaskContext") -> "TaskResult":
        """执行任务的主方法
        
        Args:
            ctx: 任务执行上下文，包含page、config、logger等
            
        Returns:
            TaskResult: 执行结果
        """
        raise NotImplementedError
    
    async def on_error(self, ctx: "TaskContext", error: Exception) -> None:
        """错误处理钩子（可选覆盖）
        
        当execute抛出异常时调用。
        
        Args:
            ctx: 任务执行上下文
            error: 捕获的异常
        """
        ctx.logger.error(f"任务执行异常: {error}")
    
    async def on_init(self, ctx: "TaskContext") -> None:
        """初始化钩子（可选覆盖）
        
        在execute之前调用，可用于初始化资源。
        """
        pass
    
    async def on_cleanup(self, ctx: "TaskContext") -> None:
        """清理钩子（可选覆盖）
        
        无论成功或失败都会在最后调用，用于清理资源。
        """
        pass
