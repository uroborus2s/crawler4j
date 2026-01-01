
import asyncio
import logging
import sys
import unittest.mock
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append("/Users/uroborus/PythonProject/crawler4j")

# Mock BrowserAPI before importing core modules that might use it
sys.modules["src.core.browser_api"] = MagicMock()

# Mock PyQt6 completely
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()

# Mock Playwright
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()

# Mock requests
sys.modules["requests"] = MagicMock()

# Mock cv2 and numpy
sys.modules["cv2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["ddddocr"] = MagicMock()

# Mock logger to avoid PyQt dependency
mock_logger_module = MagicMock()
mock_logger_module.logger = logging.getLogger("mock_logger")
sys.modules["src.utils.logger"] = mock_logger_module

from src.core.environment_manager import EnvironmentManager
from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment, EnvironmentStatus
from src.core.models.labor_account import LaborAccount
from src.core.scheduler import TaskScheduler

# from src.utils.logger import logger # Removed import, use local logger

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verifier")

async def verification_test():
    """Verify that tasks run concurrently and don't block the loop."""
    logger.info("Starting Concurrency Verification...")
    
    # Mock dependencies
    scheduler = TaskScheduler()
    
    # Mock AccountManager to return environments without hitting DB
    scheduler.account_manager = MagicMock()
    
    # Create some mock environments
    mock_envs = []
    for i in range(5):
        env = Environment(
            id=i+1,
            ctrip_account_id=i+100,
            labor_account_id=i+200,
            browser_profile_id=f"mock_profile_{i}",
            status=EnvironmentStatus.IDLE
        )
        mock_envs.append(env)
    
    # Mock _acquire_environment to return these environments sequentially
    # We override the actual method for testing
    scheduler._acquire_environment = AsyncMock(side_effect=mock_envs + [None])
    
    # Mock _start_task to simulate a long running async task
    async def mock_run_task(env_id, runner):
        logger.info(f"Task {env_id} starting (sleeping 2s)...")
        await asyncio.sleep(2)
        logger.info(f"Task {env_id} finished.")
        return MagicMock(result_type="SUCCESS", tasks_completed=1, ctrip_blacklisted=False)
        
    scheduler._run_task = mock_run_task
    
    # Set concurrency limit
    scheduler._get_concurrency_limit = MagicMock(return_value=3)
    scheduler._get_task_interval = MagicMock(return_value=1)
    
    # Start scheduler in background
    logger.info("Starting Scheduler...")
    scheduler_task = asyncio.create_task(scheduler.start())
    
    # Monitor active tasks
    for _ in range(5):
        await asyncio.sleep(0.6)
        logger.info(f"Active tasks: {len(scheduler._active_tasks)}")
        
    # Stop scheduler
    logger.info("Stopping Scheduler...")
    scheduler.stop()
    await scheduler_task
    logger.info("Scheduler stopped.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(verification_test())
        print("VERIFICATION SUCCESS: Scheduler ran without crashing.")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
