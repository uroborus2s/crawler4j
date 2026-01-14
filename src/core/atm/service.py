"""任务服务（统一门面）。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md (5.4.5)

提供统一的任务操作接口：
    - create_task: 创建任务配置
    - run_task: 触发任务执行 (Delegate to TSM)
    - list_tasks: 列出任务配置
    - get_task_run: 获取执行记录
"""

import asyncio
import copy
from typing import Any

from src.core.atm.models import (
    AutomationTask,
    TaskNotFoundError,
    TaskRun,
    TaskStatus,
)
from src.core.atm.repository import TaskRepository, get_task_repository

# from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.tsm import get_orchestrator, get_strategy_loader


class TaskService:
    """任务服务。
    
    ATM 的核心控制器。负责：
    1. 管理任务配置 (AutomationTask)
    2. 触发任务执行 (调用 TSM Orchestrator)
    3. 记录任务运行历史 (TaskRun)
    """
    
    def __init__(self, repository: TaskRepository | None = None):
        self._repository = repository or get_task_repository()
        self._orchestrator = get_orchestrator()
        self._loader = get_strategy_loader()
        
        # 订阅模块禁用事件 (To be implemented properly with new model)
        # get_event_bus().subscribe(EventType.MODULE_DISABLED, self._on_module_disabled)

    # === Task Configuration Management ===

    def create_task(self, name: str, strategy_id: str, cron: str | None = None, default_params: dict | None = None) -> str:
        """创建新任务配置。"""
        # 验证策略是否存在
        strategy = self._loader.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        task = AutomationTask(
            name=name,
            strategy_id=strategy_id,
            cron_expression=cron,
            default_params=default_params or {},
        )
        self._repository.save_task(task)
        logger.info(f"[ATM] Created task: {task.name} ({task.id})")
        return task.id

    def list_tasks(self) -> list[AutomationTask]:
        """列出所有任务配置。"""
        return self._repository.list_tasks()

    def get_task(self, task_id: str) -> AutomationTask | None:
        """获取任务配置。"""
        return self._repository.get_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        """删除任务配置。"""
        # TODO: 是否级联删除运行历史？目前暂不需要。
        return self._repository.delete_task(task_id)

    # === Task Execution Management ===

    async def run_task(self, task_id: str, params_override: dict | None = None) -> str:
        """触发任务执行 (立即运行)。
        
        Flow:
        1. 获取任务配置
        2. 获取关联策略
        3. 创建 TaskRun 记录 (Starting)
        4. 调用 TSM 编排执行
        5. 更新 TaskRun 结果
        """
        # 1. 获取配置
        task_config = self.get_task(task_id)
        if not task_config:
            raise TaskNotFoundError(f"Task not found: {task_id}")

        # 2. 获取策略
        strategy = self._loader.get(task_config.strategy_id)
        if not strategy:
            raise RuntimeError(f"Strategy {task_config.strategy_id} missing for task {task_id}")

        # 准备执行参数 (Default + Override)
        final_params = task_config.default_params.copy()
        if params_override:
            final_params.update(params_override)

        # 3. 创建运行记录
        run = TaskRun(
            task_id=task_id,
            status=TaskStatus.STARTING,
            trigger_type="manual",  # TODO: 区分 cron/manual
        )
        self._repository.save_run(run)

        # 4. 准备策略副本 (避免修改原始策略)
        # 覆盖策略中的 execution params
        strategy_copy = copy.deepcopy(strategy)
        if strategy_copy.execution:
            strategy_copy.execution.params.update(final_params)
        
        # 异步执行 (Fire and Forget or Wait? ATM usually fires)
        # 但为了简单，这里可能是 await，或者 spawn task. 
        # TSM Orchestrator 目前是 async execute.
        # 我们应该 wrap process 避免阻塞 API 调用者? 
        # 也可以直接 await 并返回结果 (如果调用者期望同步等待)
        # 设计文档 implied 异步触发。这里我们使用 asyncio.create_task 后台运行。
        
        asyncio.create_task(self._execute_process(run, strategy_copy))
        
        return run.id

    async def _execute_process(self, run: TaskRun, strategy: Any):
        """后台执行过程。"""
        try:
            run.start()
            self._repository.save_run(run)
            logger.info(f"[ATM] TaskRun started: {run.id} (Task: {run.task_id})")

            # 调用编排器
            # TSM Execute returns OrchestratorResult
            result = await self._orchestrator.execute(strategy)
            
            # 更新状态
            run.env_id = result.results[0].env_id if result.results else None
            
            # 聚合结果
            msg = f"Completed ({result.succeeded_instances}/{result.total_instances})"
            run.finish(success=result.success, message=msg)
            
        except Exception as e:
            logger.error(f"[ATM] Execution failed for run {run.id}: {e}")
            run.finish(success=False, message=str(e))
        finally:
            self._repository.save_run(run)

    async def stop_run(self, run_id: str) -> bool:
        """停止指定的运行实例。"""
        run = self._repository.get_run(run_id)
        if not run:
            return False
            
        if run.status == TaskStatus.RUNNING:
            # TSM Orchestrator Cancel currently cancels GLOBAL execution?
            # Orchestrator needs to support cancelling specific strategy/run?
            # 现在的 Orchestrator 是简单的单例模式，execute 是实例方法。
            # 如果并发执行，我们需要 Orchestrator 返回 control handle 或者它内部管理。
            # 暂时调用全局 cancel (Limit of current TSM impl)
            await self._orchestrator.cancel()
            
            run.cancel()
            self._repository.save_run(run)
            return True
        return False
    
    async def stop_task(self, task_id: str) -> bool:
        """停止任务的当前运行实例（如果有）。"""
        last_run = self.get_last_run(task_id)
        if last_run and last_run.status == TaskStatus.RUNNING:
            return await self.stop_run(last_run.id)
        return False

    # === Query Methods ===

    def get_run(self, run_id: str) -> TaskRun | None:
        return self._repository.get_run(run_id)

    def list_runs(self, limit: int = 50) -> list[TaskRun]:
        return self._repository.list_recent_runs(limit)

    def get_last_run(self, task_id: str) -> TaskRun | None:
        return self._repository.get_last_run(task_id)


# 全局单例
_service: TaskService | None = None


def get_task_service() -> TaskService:
    """获取全局 TaskService 实例。"""
    global _service
    if _service is None:
        _service = TaskService()
    return _service
