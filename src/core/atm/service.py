"""任务服务（统一门面）。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md (5.4.5)

提供统一的任务操作接口：
    - submit_task: 提交任务
    - stop_task: 停止任务
    - get_task: 获取任务
    - list_tasks: 列出任务
"""

import asyncio
from typing import Any, Callable

from src.core.atm.models import (
    TaskInstance,
    TaskNotFoundError,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.atm.runner import TaskRunner, get_task_runner
from src.core.tsm import TaskSubmission, get_admission_controller
from src.utils.logger import logger


class TaskService:
    """任务服务。
    
    规格 5.4.5 ITaskService:
        - submit_task, stop_task, get_task, list_tasks
    """
    
    def __init__(
        self,
        repository: TaskRepository | None = None,
        runner: TaskRunner | None = None,
    ):
        """初始化任务服务。"""
        self._repository = repository or get_task_repository()
        self._runner = runner or get_task_runner()
        self._admission = get_admission_controller()
        self._pending_queue: asyncio.Queue[TaskInstance] = asyncio.Queue()
        self._script_loader: Callable[[str, str], Any] | None = None
        self._context_factory: Callable[[TaskInstance], Any] | None = None
    
    def configure(
        self,
        script_loader: Callable[[str, str], Any],
        context_factory: Callable[[TaskInstance], Any],
    ) -> None:
        """配置脚本加载器和上下文工厂。
        
        Args:
            script_loader: (module, name) -> TaskScript
            context_factory: (task) -> TaskContext
        """
        self._script_loader = script_loader
        self._context_factory = context_factory
    
    async def submit(self, request: TaskRequest) -> TaskInstance:
        """提交任务。
        
        规格 5.4.3 FR-ATM-001:
            1. 生成唯一 task_id
            2. 加载对应模块配置
            3. 绑定初始状态 PENDING
        
        Args:
            request: 任务请求
        
        Returns:
            任务实例
        """
        # 创建任务实例
        task = TaskInstance.from_request(request)
        
        # 保存到仓库
        self._repository.save(task)
        
        logger.info(f"[ATM] 任务已提交: {task.id[:8]}... ({task.module}/{task.name})")
        
        # 入队
        task.enqueue()
        self._repository.save(task)
        
        # 加入待处理队列
        await self._pending_queue.put(task)
        
        return task
    
    async def stop(self, task_id: str, force: bool = False) -> bool:
        """停止任务。
        
        Args:
            task_id: 任务ID
            force: 是否强制停止
        
        Returns:
            是否停止成功
        """
        task = self._repository.get(task_id)
        if not task:
            raise TaskNotFoundError(f"任务不存在: {task_id}")
        
        if task.status == TaskStatus.RUNNING:
            success = await self._runner.stop(task_id, force)
            if success:
                task.cancel()
                self._repository.save(task)
            return success
        
        if task.status in {TaskStatus.PENDING, TaskStatus.QUEUED}:
            task.cancel()
            self._repository.save(task)
            return True
        
        return False
    
    def get(self, task_id: str) -> TaskInstance | None:
        """获取任务。"""
        return self._repository.get(task_id)
    
    def list_by_status(self, status: TaskStatus) -> list[TaskInstance]:
        """按状态列出任务。"""
        return self._repository.list_by_status(status)
    
    def list_recent(self, limit: int = 50) -> list[TaskInstance]:
        """列出最近的任务。"""
        return self._repository.list_recent(limit)
    
    async def execute(self, task: TaskInstance) -> TaskResult:
        """执行单个任务。
        
        通常由调度器调用。
        """
        if not self._script_loader or not self._context_factory:
            raise RuntimeError("TaskService 未配置 script_loader 和 context_factory")
        
        # 更新状态为运行中
        task.start()
        self._repository.save(task)
        
        logger.info(f"[ATM] 任务开始执行: {task.id[:8]}...")
        
        try:
            # 执行任务
            result = await self._runner.run(
                task,
                self._script_loader,
                self._context_factory,
            )
            
            # 更新状态
            if result.success:
                task.succeed(result)
            else:
                task.fail(result.message)
            
            self._repository.save(task)
            
            logger.info(f"[ATM] 任务完成: {task.id[:8]}... success={result.success}")
            
            return result
            
        except Exception as e:
            task.fail(str(e))
            self._repository.save(task)
            logger.error(f"[ATM] 任务异常: {task.id[:8]}... {e}")
            return TaskResult(success=False, message=str(e))
    
    async def recover(self) -> list[TaskInstance]:
        """恢复中断的任务。"""
        return self._repository.recover_interrupted()
    
    def get_stats(self) -> dict[str, int]:
        """获取任务统计。"""
        return {
            "pending": self._repository.count_by_status(TaskStatus.PENDING),
            "queued": self._repository.count_by_status(TaskStatus.QUEUED),
            "running": self._runner.get_running_count(),
            "succeeded": self._repository.count_by_status(TaskStatus.SUCCEEDED),
            "failed": self._repository.count_by_status(TaskStatus.FAILED),
        }


# 全局单例
_service: TaskService | None = None


def get_task_service() -> TaskService:
    """获取全局 TaskService 实例。"""
    global _service
    if _service is None:
        _service = TaskService()
    return _service
