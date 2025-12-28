"""Scheduler module.

Manages the background execution of tasks across multiple environments.
"""

import asyncio
from typing import Dict

from src.automation.driver import AutomationDriver
from src.config import config
from src.core.account_manager import AccountManager
from src.core.events import EventType, get_event_bus
from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment
from src.core.models.labor_account import LaborAccount
from src.core.task_orchestrator import TaskOrchestrator
from src.utils.logger import logger
from src.utils.storage import CtripAccountRepository, LaborAccountRepository


class Scheduler:
    """Main scheduler for managing concurrent automation tasks."""
    
    def __init__(self):
        self.account_manager = AccountManager()
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        
        self._running = False
        self._active_tasks: Dict[int, asyncio.Task] = {} # env_id -> Task
        self._stop_event = asyncio.Event()

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
            
        self._running = True
        self._stop_event.clear()
        logger.info("🚀 任务调度器已启动")
        
        while self._running:
            # 1. check concurrency limit
            current_running = len(self._active_tasks)
            limit = config.concurrency_limit
            
            if current_running < limit:
                # 2. get next environment to run
                env = self.account_manager.get_next_environment()
                
                if env:
                    # 3. start task for this environment
                    task = asyncio.create_task(self._run_environment(env))
                    self._active_tasks[env.id] = task
                    logger.info(f"启动新任务环境: ENV-{env.id} (当前运行: {len(self._active_tasks) + 1})")
                else:
                    if not self._active_tasks:
                        logger.info("当前无可用账号或环境，等待中...")
            
            # Sleep before next check
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=config.task_interval)
                break
            except asyncio.TimeoutError:
                pass
                
        logger.info("🛑 任务调度器已停止")

    def stop(self):
        """Request the scheduler to stop."""
        self._running = False
        self._stop_event.set()
        
        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()

    async def _run_environment(self, env: Environment):
        """Run the automation loop for a specific environment."""
        env_id = env.id
        bus = get_event_bus()
        
        try:
            # Mark running in DB
            self.account_manager.start_environment(env_id)
            bus.emit(EventType.ENVIRONMENT_STATUS_CHANGED, {"env_id": env_id, "status": "running"})
            
            # Get full account models
            ctrip_data = self.ctrip_repo.get_by_id(env.ctrip_account_id)
            labor_data = self.labor_repo.get_by_id(env.labor_account_id)
            
            if not ctrip_data or not labor_data:
                logger.error(f"环境 ENV-{env_id} 找不到账号数据")
                return
                
            ctrip = CtripAccount.from_dict(ctrip_data)
            labor = LaborAccount.from_dict(labor_data)
            
            # Start driver and run loop
            async with AutomationDriver.connect(env.browser_profile_id) as page:
                orchestrator = TaskOrchestrator(page)
                
                while self._running:
                    success = await orchestrator.run_loop_once(ctrip, labor)
                    
                    if success:
                        # Update stats
                        self.account_manager.update_labor_stats(labor.id, completed=1, approved=1)
                        bus.emit(EventType.LABOR_STATS_UPDATED, {"id": labor.id})
                    else:
                        # Logic for failure
                        logger.warning(f"环境 ENV-{env_id} 任务轮询未完成，重试中...")
                        
                        # T056: Exception handling - if marked blacklisted/banned
                        # This would be detected inside orchestrator/login
                        check_ctrip = self.ctrip_repo.get_by_id(ctrip.id)
                        if check_ctrip and check_ctrip["status"] == "blacklisted":
                            logger.error(f"检测到携程账号 {ctrip.phone} 已被封禁，终止环境")
                            self.account_manager.blacklist_ctrip_account(ctrip.id)
                            break
                    
                    # Wait for interval
                    await asyncio.sleep(config.task_interval)
                    
        except asyncio.CancelledError:
            logger.info(f"环境 ENV-{env_id} 任务被取消")
        except Exception as e:
            logger.error(f"环境 ENV-{env_id} 运行崩溃: {e}")
            bus.emit(EventType.ENVIRONMENT_STATUS_CHANGED, {"env_id": env_id, "status": "error"})
        finally:
            # Cleanup
            self.account_manager.stop_environment(env_id)
            bus.emit(EventType.ENVIRONMENT_STATUS_CHANGED, {"env_id": env_id, "status": "idle"})
            if env_id in self._active_tasks:
                del self._active_tasks[env_id]
            logger.info(f"结束任务环境: ENV-{env_id}")
