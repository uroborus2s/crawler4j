"""Task scheduler module.

Manages the background execution of automation tasks across multiple environments.
Implements concurrent task scheduling with configurable limits and intervals.
"""

import asyncio
from typing import Dict

from src.config import config
from src.core.account_manager import AccountManager
from src.core.events import EventType, get_event_bus
from src.core.models.environment import Environment
from src.core.task_runner import TaskResult, TaskResultType, TaskRunner
from src.utils.logger import logger
from src.utils.storage import LaborAccountRepository


class TaskScheduler:
    """Main scheduler for managing concurrent automation tasks.

    Features:
    - Dynamic concurrency limit from settings
    - Configurable task interval
    - Automatic environment creation
    - Graceful shutdown support
    - Blacklist detection and handling
    - Labor account locking and stale lock cleanup
    """

    def __init__(self):
        self.account_manager = AccountManager()
        self.labor_repo = LaborAccountRepository()
        self.bus = get_event_bus()

        self._running = False
        self._active_tasks: Dict[int, asyncio.Task] = {}  # env_id -> Task
        self._task_runners: Dict[int, TaskRunner] = {}  # env_id -> Runner
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    @property
    def active_count(self) -> int:
        """Get count of currently active tasks."""
        return len(self._active_tasks)

    async def start(self):
        """Start the scheduler main loop.

        实现真正的并行执行：
        1. 启动时快速填满并发槽位
        2. 任务完成时立即触发补充检查
        3. 保持 concurrency_limit 个环境同时运行
        """
        if self._running:
            logger.warning("调度器已在运行中")
            return

        # 启动时清理旧锁
        self._cleanup_stale_locks()

        self._running = True
        self._stop_event.clear()
        self._slot_available = asyncio.Event()  # 用于通知有槽位可用

        logger.info("🚀 任务调度器已启动")
        self.bus.emit(EventType.SCHEDULER_STARTED)

        try:
            # 先快速填满并发槽位
            await self._fill_slots()

            while self._running:
                # 等待：停止信号 或 槽位释放信号 或 定期检查（兜底）
                self._slot_available.clear()
                try:
                    await asyncio.wait_for(
                        asyncio.gather(
                            self._stop_event.wait(),
                            self._slot_available.wait(),
                            return_exceptions=True,
                        ),
                        timeout=self._get_task_interval(),
                    )
                except asyncio.TimeoutError:
                    pass  # 定期检查，继续

                if not self._running:
                    break

                # 有槽位释放，尝试补充
                await self._fill_slots()

        except Exception as e:
            logger.error(f"调度器主循环异常: {e}")
        finally:
            await self._shutdown()

    async def _fill_slots(self):
        """Fill available slots up to concurrency limit.

        快速填满所有可用槽位，串行打开环境避免冲突，但任务并行执行。
        """
        async with self._lock:
            limit = self._get_concurrency_limit()

            while len(self._active_tasks) < limit and self._running:
                env = await self._acquire_environment()
                if not env:
                    break  # 没有更多可用环境

                await self._start_task(env)
                # 短暂延迟避免同时打开多个浏览器造成冲突
                await asyncio.sleep(1)

    async def _schedule_cycle(self):
        """Execute one scheduling cycle - fill up to concurrency limit.

        循环启动环境直到达到并发上限，而不是每轮只启动一个。
        """
        async with self._lock:
            limit = self._get_concurrency_limit()
            started_count = 0

            # 循环启动直到达到并发上限
            while len(self._active_tasks) < limit:
                # Try to acquire an environment
                env = await self._acquire_environment()

                if not env:
                    if len(self._active_tasks) == 0 and started_count == 0:
                        logger.debug("当前无可用环境，等待中...")
                    break  # 没有更多可用环境

                # Start task for this environment
                await self._start_task(env)
                started_count += 1

                # 短暂延迟避免过快启动
                await asyncio.sleep(0.5)

    async def _acquire_environment(self) -> Environment | None:
        """Acquire an available environment.

        Priority:
        1. Find an idle environment with valid accounts
        2. Create a new environment if possible

        Returns:
            Environment if available, None otherwise.
        """
        # First try to get an idle environment
        env = self.account_manager.get_idle_environment()
        if env:
            logger.info(f"复用空闲环境: ENV-{env.id}")
            return env

        # Try to create a new environment
        env = await self.account_manager.create_environment_auto_async()
        if env:
            self.bus.emit(EventType.ENVIRONMENT_CREATED, {"env_id": env.id})
            return env

        return None

    async def _start_task(self, env: Environment):
        """Start a task for the given environment.

        Args:
            env: The environment to run task in.
        """
        env_id = env.id
        if not env_id:
            logger.error("环境 ID 无效")
            return

        # Mark environment as running
        self.account_manager.start_environment(env_id)
        self.bus.emit(
            EventType.ENVIRONMENT_STATUS_CHANGED,
            {"env_id": env_id, "status": "running"},
        )

        # Create runner and task
        runner = TaskRunner(env)
        self._task_runners[env_id] = runner

        task = asyncio.create_task(self._run_task(env_id, runner))
        self._active_tasks[env_id] = task

        logger.info(f"启动任务: ENV-{env_id} (当前运行: {len(self._active_tasks)})")

    async def _run_task(self, env_id: int, runner: TaskRunner):
        """Execute a task and handle its completion.

        Args:
            env_id: Environment ID.
            runner: TaskRunner instance.
        """
        try:
            result = await runner.run()
            await self._handle_task_result(env_id, result)

        except asyncio.CancelledError:
            logger.info(f"ENV-{env_id} 任务被取消")
        except Exception as e:
            logger.error(f"ENV-{env_id} 任务执行异常: {e}")
        finally:
            await self._cleanup_task(env_id)

    async def _handle_task_result(self, env_id: int, result: TaskResult):
        """Handle the result of a completed task.

        Args:
            env_id: Environment ID.
            result: TaskResult from the runner.
        """
        if result.ctrip_blacklisted:
            # Handle blacklisted account
            logger.warning(f"ENV-{env_id} 携程账号被封，正在清理...")

            env = self.account_manager.env_repo.get_by_id(env_id)
            if env and env.get("ctrip_account_id"):
                self.account_manager.handle_blacklisted_account(env["ctrip_account_id"])
                self.bus.emit(
                    EventType.CTRIP_ACCOUNT_BLACKLISTED,
                    {"ctrip_id": env["ctrip_account_id"]},
                )
        else:
            # Normal completion - just update stats
            if result.result_type == TaskResultType.SUCCESS:
                logger.info(f"ENV-{env_id} 任务完成: {result.message}")
                self.bus.emit(
                    EventType.TASK_COMPLETED,
                    {"env_id": env_id, "completed": result.tasks_completed},
                )
            elif result.result_type == TaskResultType.NO_TASK:
                logger.info(f"ENV-{env_id} 无可用任务")
            else:
                logger.warning(f"ENV-{env_id} 任务失败: {result.message}")
                self.bus.emit(
                    EventType.TASK_FAILED, {"env_id": env_id, "message": result.message}
                )

    async def _cleanup_task(self, env_id: int):
        """Cleanup after task completion.

        Args:
            env_id: Environment ID.
        """
        # Remove from active tasks
        if env_id in self._active_tasks:
            del self._active_tasks[env_id]
        if env_id in self._task_runners:
            del self._task_runners[env_id]

        # Reset environment status
        self.account_manager.cleanup_environment(env_id)
        self.bus.emit(
            EventType.ENVIRONMENT_STATUS_CHANGED, {"env_id": env_id, "status": "idle"}
        )

        logger.info(f"任务清理完成: ENV-{env_id} (剩余运行: {len(self._active_tasks)})")

        # 通知主循环有槽位释放，可以立即补充新环境
        if hasattr(self, "_slot_available"):
            self._slot_available.set()

    def stop(self):
        """Request graceful shutdown of the scheduler.

        This will:
        1. Stop scheduling new tasks
        2. Cancel all running tasks
        3. Wait for cleanup
        """
        if not self._running:
            return

        logger.info("正在停止调度器...")
        self._running = False
        self._stop_event.set()

        # Cancel all running tasks
        for runner in self._task_runners.values():
            runner.cancel()

        for task in self._active_tasks.values():
            task.cancel()

    async def _shutdown(self):
        """Perform graceful shutdown."""
        logger.info("调度器正在关闭...")

        # Wait for all tasks to complete
        if self._active_tasks:
            logger.info(f"等待 {len(self._active_tasks)} 个任务完成...")
            try:
                await asyncio.wait(
                    self._active_tasks.values(),
                    timeout=30,
                    return_when=asyncio.ALL_COMPLETED,
                )
            except Exception as e:
                logger.warning(f"等待任务完成超时: {e}")

        self._active_tasks.clear()
        self._task_runners.clear()

        self.bus.emit(EventType.SCHEDULER_STOPPED)
        logger.info("🛑 任务调度器已停止")

    def _get_concurrency_limit(self) -> int:
        """Get current concurrency limit from settings."""
        # Reload to get fresh value
        config.reload()
        return config.concurrency_limit

    def _get_task_interval(self) -> int:
        """Get current task interval from settings."""
        config.reload()
        return config.task_interval

    def _cleanup_stale_locks(self) -> None:
        """清理超时的劳保账号锁定。

        在调度器启动时调用，释放可能因异常退出导致的残留锁。
        """
        try:
            # 从设置读取超时时间，默认 5 分钟
            from src.utils.storage import SettingsRepository

            settings = SettingsRepository()
            timeout = settings.get("lock_timeout_minutes", 5)

            released = self.labor_repo.cleanup_stale_locks(timeout)
            if released > 0:
                logger.info(f"🔓 清理了 {released} 个超时的劳保账号锁定")
        except Exception as e:
            logger.warning(f"清理旧锁失败: {e}")


# Backwards compatibility alias
Scheduler = TaskScheduler
