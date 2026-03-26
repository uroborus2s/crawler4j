"""TaskFlow 工作流编排基类。

本模块定义了 Crawler4j SDK 的核心契约之一：TaskFlow（工作流编排基类）。
TaskFlow 用于把多个 TaskScript 组合成一个可取消、可重试、可观测的复合流程。

稳定契约 (Stable API - 同 MAJOR 版本内冻结):
    - 类属性: name, display_name, description
    - 方法: run, on_error, on_complete

参考规格: docs/02-requirements/reference-srs/06-sdk/06-2-taskflow.md
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crawler4j_sdk.context import TaskContext


class TaskFlow(ABC):
    """工作流编排基类。
    
    TaskFlow 用于把多个 TaskScript 组合成一个"可取消、可重试、可观测"的复合流程。
    通过 Python 代码方式编排子任务的执行顺序：顺序、循环、分支、条件判断。
    
    类属性 (Stable):
        name: 工作流唯一标识符 (MUST)，用于调度、引用和追溯。
        display_name: 面向 UI/日志的可读名称 (SHOULD)。
        description: 简要说明 (SHOULD)。
    
    生命周期方法调用顺序:
        1. run(ctx)          - 主执行方法
        2. on_error(ctx, e)  - 异常处理钩子 (仅当 run 抛出异常时)
        3. on_complete(ctx)  - 完成回调 (仅当 run 正常完成时)
    
    子任务调用:
        - 通过 ctx.run_subtask("task_name", **kwargs) 调用子任务
        - kwargs 会合并到 ctx.state，子任务共享同一个 state
        - 返回值为子任务 TaskResult.data
    
    停止/取消语义:
        - ctx.request_stop(): 请求停止工作流
        - ctx.should_stop(): 检查停止标志，长循环必须周期性检查
    
    断点恢复建议:
        - 将可恢复点写入 ctx.state，例如 cursor/phase/last_task_id
        - 运行时在需要时将 ctx.state 持久化并在重试/恢复时回灌
    
    示例:
        >>> from crawler4j_sdk import TaskFlow, TaskContext
        >>> 
        >>> class CtripCrawlWorkflow(TaskFlow):
        ...     name = "ctrip_crawl"
        ...     display_name = "携程数据采集"
        ...     description = "完整的携程任务领取和数据提交流程"
        ...     
        ...     async def run(self, ctx: TaskContext) -> None:
        ...         # 登录
        ...         await ctx.run_subtask("ctrip_login")
        ...         
        ...         # 循环处理任务
        ...         while not ctx.should_stop():
        ...             # 记录阶段便于诊断
        ...             ctx.state["phase"] = "claim"
        ...             task = await ctx.run_subtask("claim_task")
        ...             if not task:
        ...                 break
        ...             
        ...             ctx.state["phase"] = "search"
        ...             data = await ctx.run_subtask("ctrip_search", task=task)
        ...             
        ...             ctx.state["phase"] = "submit"
        ...             await ctx.run_subtask("labor_submit", data=data)
        ...     
        ...     async def on_error(self, ctx: TaskContext, error: Exception) -> None:
        ...         await ctx.screenshot("workflow_error")
        ...         ctx.logger.error(f"工作流异常: {error}")
    """
    
    # === 类属性 (Stable) ===
    
    name: str = ""
    """工作流唯一标识符 (MUST)。用于调度、引用和追溯，应保持稳定。"""
    
    display_name: str = ""
    """面向 UI/日志的可读名称 (SHOULD)。"""
    
    description: str = ""
    """工作流简要说明 (SHOULD)。"""
    
    # === 主执行方法 (Stable) ===
    
    @abstractmethod
    async def run(self, ctx: "TaskContext") -> None:
        """执行工作流的主方法 (MUST 实现)。
        
        这是 TaskFlow 的核心方法，子类必须实现。
        方法应编排子任务的执行顺序，使用 Python 控制流实现顺序、循环、分支逻辑。
        
        Args:
            ctx: 任务执行上下文。使用 ctx.run_subtask() 调用子任务，
                 使用 ctx.should_stop() 检查停止标志。
        
        Note:
            - 工作流本身不返回 TaskResult，由运行时归一整体成功/失败
            - 长循环必须周期性检查 ctx.should_stop()
            - 关键阶段建议写入 ctx.state["phase"] 便于诊断
            - 可恢复游标建议写入 ctx.state["cursor"]
        """
        pass
    
    # === 生命周期钩子 (Stable, 可选覆盖) ===
    
    async def on_error(self, ctx: "TaskContext", error: Exception) -> None:
        """工作流级别的错误处理钩子 (MAY 覆盖)。
        
        当 run 抛出异常时调用，用于错误补救、截图取证等。
        
        Args:
            ctx: 任务执行上下文。
            error: 捕获的异常对象。
        
        Note:
            - 默认实现记录错误日志
            - 建议在此处调用 ctx.screenshot() 保存现场
        """
        ctx.logger.error(f"工作流 {self.name} 执行失败: {error}")
    
    async def on_complete(self, ctx: "TaskContext") -> None:
        """工作流完成回调 (MAY 覆盖)。
        
        当 run 正常完成（未抛出异常）时调用，用于清理逻辑或统计。
        
        Args:
            ctx: 任务执行上下文。
        
        Note:
            - 默认实现记录完成日志
            - 可在此处进行资源释放或统计汇总
        """
        ctx.logger.info(f"工作流 {self.name} 执行完成")
