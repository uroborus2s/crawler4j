"""任务执行器。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md (5.4.3)

负责：
    - 执行驱动：调用 SDK 接口执行 TaskScript
    - 超时控制
    - 异常捕获
"""

import asyncio
from typing import Any, Callable

from src.core.atm.models import TaskExecutionError, TaskInstance, TaskResult, TaskStatus
from src.core.atm.repository import TaskRepository, get_task_repository
from src.utils.logger import logger


class TaskRunner:
    """任务执行器。
    
    规格 5.4.3 FR-ATM-002:
        在指定驱动器中运行任务逻辑。
        1. 准备 TaskContext
        2. 调用 TaskScript.on_init()
        3. 调用 TaskScript.execute()
        4. 调用 TaskScript.on_cleanup()
    """
    
    def __init__(self, repository: TaskRepository | None = None):
        """初始化执行器。"""
        self._repository = repository or get_task_repository()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._cancel_signals: dict[str, asyncio.Event] = {}
    
    async def run(
        self,
        task: TaskInstance,
        script_loader: Callable[[str, str], Any],
        context_factory: Callable[[TaskInstance], Any],
    ) -> TaskResult:
        """执行任务。
        
        Args:
            task: 任务实例
            script_loader: 脚本加载器 (module, name) -> TaskScript
            context_factory: 上下文工厂 (task) -> TaskContext
        
        Returns:
            任务结果
        """
        # 初始化取消信号
        cancel_event = asyncio.Event()
        self._cancel_signals[task.id] = cancel_event
        
        try:
            # 加载脚本
            script = script_loader(task.module, task.name)
            if not script:
                raise TaskExecutionError(f"脚本加载失败: {task.module}/{task.name}")
            
            # 创建上下文
            ctx = context_factory(task)
            
            # 注入取消检查
            ctx._should_exit = False
            
            # 包装执行
            async def execute_with_lifecycle():
                try:
                    # on_init
                    if hasattr(script, "on_init"):
                        await script.on_init(ctx)
                    
                    # 检查取消
                    if cancel_event.is_set():
                        return TaskResult(success=False, message="任务已取消")
                    
                    # execute
                    result = await script.execute(ctx)
                    
                    return result
                    
                finally:
                    # on_cleanup
                    if hasattr(script, "on_cleanup"):
                        try:
                            await script.on_cleanup(ctx)
                        except Exception as e:
                            logger.warning(f"[ATM] cleanup 异常: {e}")
            
            # 超时控制
            async_task = asyncio.create_task(execute_with_lifecycle())
            self._running_tasks[task.id] = async_task
            
            try:
                result = await asyncio.wait_for(async_task, timeout=task.timeout)
                return result if result else TaskResult(success=True)
                
            except asyncio.TimeoutError:
                logger.error(f"[ATM] 任务超时: {task.id[:8]}...")
                return TaskResult(success=False, message=f"任务超时 ({task.timeout}s)")
                
            except asyncio.CancelledError:
                return TaskResult(success=False, message="任务已取消")
            
        except Exception as e:
            logger.error(f"[ATM] 任务执行异常: {e}")
            return TaskResult(success=False, message=str(e))
            
        finally:
            self._running_tasks.pop(task.id, None)
            self._cancel_signals.pop(task.id, None)
    
    async def stop(self, task_id: str, force: bool = False) -> bool:
        """停止任务。
        
        规格 5.4.3 FR-ATM-003:
            - Graceful Stop: 设置 should_exit 标志
            - Force Stop: 直接取消 asyncio Task
        
        Args:
            task_id: 任务ID
            force: 是否强制停止
        
        Returns:
            是否停止成功
        """
        # 设置取消信号
        cancel_event = self._cancel_signals.get(task_id)
        if cancel_event:
            cancel_event.set()
        
        if force:
            # 强制取消
            async_task = self._running_tasks.get(task_id)
            if async_task:
                async_task.cancel()
                logger.info(f"[ATM] 强制停止任务: {task_id[:8]}...")
                return True
        
        return cancel_event is not None
    
    def is_running(self, task_id: str) -> bool:
        """检查任务是否正在运行。"""
        return task_id in self._running_tasks
    
    def get_running_count(self) -> int:
        """获取正在运行的任务数量。"""
        return len(self._running_tasks)


# 全局单例
_runner: TaskRunner | None = None


def get_task_runner() -> TaskRunner:
    """获取全局 TaskRunner 实例。"""
    global _runner
    if _runner is None:
        _runner = TaskRunner()
    return _runner
