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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.core.atm.models import (
    AutomationTask,
    TaskNotFoundError,
    TaskRun,
    TaskStatus,
    TriggerConfig,
    TriggerType,
)
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.foundation.event_bus import Event, EventType, get_event_bus
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
        self._active_runs: dict[str, asyncio.Event] = {}
        self._scheduler = AsyncIOScheduler()
        self._started = False
        
        self._started = False

    async def start(self):
        """启动 ATM 服务 (恢复状态、启动调度器)。"""
        if self._started:
            return
        
        logger.info("[ATM] Starting TaskService...")
        self._started = True
        
        # 1. 恢复异常退出的任务
        await self._recover_running_tasks()
        
        # 2. 启动调度器
        self._scheduler.start()
        
        # 3. 加载所有定时任务
        await self._load_scheduled_tasks()

    async def _recover_running_tasks(self):
        """将上次未正常退出的 RUNNING 任务置为 INTERRUPTED。"""
        # 我们假设 restart 后 memory map 是空的，所有数据库里 RUNNING 的都是残留
        running_runs = await self._repository.list_runs_by_status(TaskStatus.RUNNING)
        count = 0
        for run in running_runs:
            # 双重检查: 只有不在当前内存里的才算残留 (虽然启动时肯定是空的)
            if run.id not in self._active_runs:
                logger.warning(f"[ATM] Recovering orphaned task run: {run.id}")
                run.status = TaskStatus.INTERRUPTED
                run.error = "Service restarted abruptly"
                run.end_time = int(asyncio.get_event_loop().time()) # approx
                await self._repository.save_run(run)
                count += 1
        if count > 0:
            logger.info(f"[ATM] Recovered {count} orphaned runs.")

    async def _load_scheduled_tasks(self):
        """加载已有的 Cron 任务到调度器。"""
        tasks = await self.list_tasks()
        for task in tasks:
            if task.trigger_config:
                self._add_scheduler_job(task)

    def _add_scheduler_job(self, task: AutomationTask):
        """添加或更新调度任务。"""
        try:
            # 移除旧的 (如果存在)
            if self._scheduler.get_job(task.id):
                self._scheduler.remove_job(task.id)
            
            trigger = None
            
            # 1. 优先使用 trigger_config
            if task.trigger_config:
                if task.trigger_config.type == TriggerType.CRON:
                    if task.trigger_config.cron_expr:
                        trigger = CronTrigger.from_crontab(task.trigger_config.cron_expr)
                
                elif task.trigger_config.type == TriggerType.INTERVAL:
                    if task.trigger_config.interval_seconds:
                        trigger = IntervalTrigger(seconds=task.trigger_config.interval_seconds)
                        
                elif task.trigger_config.type == TriggerType.RANDOM:
                    if task.trigger_config.interval_seconds:
                        # random_range treated as jitter
                        jitter = task.trigger_config.random_range or 0
                        trigger = IntervalTrigger(
                            seconds=task.trigger_config.interval_seconds,
                            jitter=jitter
                        )



            if trigger:
                self._scheduler.add_job(
                    self._run_task_job,
                    trigger=trigger,
                    id=task.id,
                    name=task.name,
                    args=[task.id],
                    replace_existing=True
                )
                desc = f"{task.trigger_config.type.value}" if task.trigger_config else "cron"
                logger.info(f"[ATM] Scheduled task {task.name} (Type: {desc})")
                
        except Exception as e:
            logger.error(f"[ATM] Failed to schedule task {task.name}: {e}")

    async def _run_task_job(self, task_id: str):
        """调度器回调 wrapper (因为 run_task 是 async)。"""
        # APScheduler AsyncIOScheduler 支持 async func
        await self.run_task(task_id, params_override={"trigger": "schedule"})

    # === Task Configuration Management ===

    async def create_task(
        self, 
        name: str, 
        strategy_id: str, 
        trigger_config: TriggerConfig | None = None,
        default_params: dict | None = None, 
    ) -> str:
        """创建新任务配置。"""
        # 验证策略是否存在
        strategy = self._loader.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        task = AutomationTask(
            name=name,
            strategy_id=strategy_id,
            trigger_config=trigger_config,
            default_params=default_params or {},
        )
        await self._repository.save_task(task)
        
        # 更新调度
        if task.trigger_config:
            self._add_scheduler_job(task)
            
        logger.info(f"[ATM] Created task: {task.name} ({task.id})")
        get_event_bus().publish(Event(type=EventType.TASK_CONFIG_CREATED, data={"task_id": task.id, "name": task.name}))
        return task.id

    async def list_tasks(self) -> list[AutomationTask]:
        """列出所有任务配置。"""
        return await self._repository.list_tasks()

    async def get_task(self, task_id: str) -> AutomationTask | None:
        """获取任务配置。"""
        return await self._repository.get_task(task_id)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务配置。"""
        # 移除调度
        if self._scheduler.get_job(task_id):
            self._scheduler.remove_job(task_id)

        # TODO: 是否级联删除运行历史？目前暂不需要。
        success = await self._repository.delete_task(task_id)
        if success:
            get_event_bus().publish(Event(type=EventType.TASK_CONFIG_DELETED, data={"task_id": task_id}))
        return success

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
        task_config = await self.get_task(task_id)
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
        await self._repository.save_run(run)

        # 4. 准备策略副本 (避免修改原始策略)
        # 覆盖策略中的 execution params
        strategy_copy = copy.deepcopy(strategy)
        if strategy_copy.execution:
            strategy_copy.execution.params.update(final_params)
        
        # 创建取消事件
        cancel_event = asyncio.Event()
        self._active_runs[run.id] = cancel_event
        
        get_event_bus().publish(Event(
            type=EventType.TASK_STARTED, 
            task_run_id=run.id,
            data={"task_id": task_id}
        ))
        asyncio.create_task(self._execute_process(run, strategy_copy, cancel_event))
        
        return run.id

    async def _execute_process(self, run: TaskRun, strategy: Any, cancel_event: asyncio.Event):
        """后台执行过程。"""
        try:
            run.start()
            await self._repository.save_run(run)
            logger.info(f"[ATM] TaskRun started: {run.id} (Task: {run.task_id})")

            # 调用编排器 (传递 cancel_event)
            result = await self._orchestrator.execute(strategy, cancel_event=cancel_event)
            
            # 更新状态
            run.env_id = result.results[0].env_id if result.results else None
            
            # 聚合结果
            msg = f"Completed ({result.succeeded_instances}/{result.total_instances})"
            run.finish(success=result.success, message=msg)
            
            get_event_bus().publish(Event(
                type=EventType.TASK_FINISHED if result.success else EventType.TASK_FAILED,
                task_run_id=run.id,
                data={"task_id": run.task_id, "result": result.success}
            ))
            
        except Exception as e:
            logger.error(f"[ATM] Execution failed for run {run.id}: {e}")
            run.finish(success=False, message=str(e))
            get_event_bus().publish(Event(
                type=EventType.TASK_FAILED,
                task_run_id=run.id,
                data={"task_id": run.task_id, "error": str(e)}
            ))
        finally:
            self._active_runs.pop(run.id, None)
            await self._repository.save_run(run)

    async def stop_run(self, run_id: str) -> bool:
        """停止指定的运行实例。"""
        run = await self._repository.get_run(run_id)
        if not run:
            return False
            
        if run.id in self._active_runs:
             self._active_runs[run.id].set()
             
             run.cancel()
             await self._repository.save_run(run)
             
             get_event_bus().publish(Event(
                type=EventType.TASK_CANCELLED,
                task_run_id=run.id,
                data={"task_id": run.task_id}
             ))
             return True
        return False
    
    async def stop_task(self, task_id: str) -> bool:
        """停止任务的当前运行实例（如果有）。"""
        last_run = await self.get_last_run(task_id)
        if last_run and last_run.status == TaskStatus.RUNNING:
            return await self.stop_run(last_run.id)
        return False

    # === Query Methods ===

    async def get_run(self, run_id: str) -> TaskRun | None:
        return await self._repository.get_run(run_id)

    async def list_runs(self, limit: int = 50) -> list[TaskRun]:
        return await self._repository.list_recent_runs(limit)

    async def list_task_runs(self, task_id: str, limit: int = 50) -> list[TaskRun]:
        """获取指定任务的运行历史。"""
        return await self._repository.list_runs_by_task(task_id, limit)

    async def get_last_run(self, task_id: str) -> TaskRun | None:
        return await self._repository.get_last_run(task_id)


# 全局单例
_service: TaskService | None = None


def get_task_service() -> TaskService:
    """获取全局 TaskService 实例。"""
    global _service
    if _service is None:
        _service = TaskService()
    return _service
