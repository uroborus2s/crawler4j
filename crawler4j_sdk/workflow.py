"""SDK 工作流编排模块

支持复合任务的定义和执行。
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawler4j_sdk.context import TaskContext


class TaskFlow(ABC):
    """复合任务基类
    
    用于定义由多个子任务组成的完整工作流程。
    
    Example:
        class CtripCrawlWorkflow(TaskFlow):
            name = "ctrip_crawl"
            
            async def run(self, ctx: TaskContext):
                await ctx.run_subtask("ctrip_login")
                await ctx.run_subtask("check_account")
                
                while not ctx.should_stop():
                    task = await ctx.run_subtask("claim_task")
                    if not task:
                        break
                    data = await ctx.run_subtask("ctrip_search", task=task)
                    await ctx.run_subtask("labor_submit", data=data)
    """
    
    name: str = ""
    display_name: str = ""
    description: str = ""
    
    @abstractmethod
    async def run(self, ctx: "TaskContext") -> None:
        """执行工作流
        
        子类必须实现此方法，在其中编排子任务的执行顺序。
        
        Args:
            ctx: 任务上下文
        """
        pass
    
    async def on_error(self, ctx: "TaskContext", error: Exception) -> None:
        """工作流级别的错误处理
        
        Args:
            ctx: 任务上下文
            error: 发生的异常
        """
        ctx.logger.error(f"工作流 {self.name} 执行失败: {error}")
    
    async def on_complete(self, ctx: "TaskContext") -> None:
        """工作流完成后的清理逻辑"""
        ctx.logger.info(f"工作流 {self.name} 执行完成")
