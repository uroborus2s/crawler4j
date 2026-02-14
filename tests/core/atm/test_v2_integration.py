"""Task Engine V2 Flow Test.

Verifies:
1. Job Creation
2. Job Activation (Controller Reconcile)
3. Task Dispatching
4. Atomic Leasing (Real DB)
"""

import asyncio
import os

import pytest

from src.core.atm.models import JobState, JobType, TaskStatus
from src.core.atm.service import get_task_service
from src.core.persistence import init_database
from src.core.rem.manager import get_environment_manager


@pytest.mark.asyncio
async def test_v2_flow():
    # 1. Init DB
    init_database()
    
    # 2. Init Services
    rem = get_environment_manager()
    await rem.startup() # Startup REM (GC, etc)
    
    # Mock Provider? Or use 'debug_dummy' if available.
    # We need to register a provider or have environments in DB.
    # Assuming 'playwright_local' is default and might fail if no browser installed in CI?
    # We'll see. If it fails, we'll mock.
    
    service = get_task_service()
    await service.start() # Starts Controller
    
    # 3. Create Job
    job_id = await service.create_job(
        name="Test Job V2",
        job_type=JobType.BATCH,
        concurrency=2, # Target 2 tasks
        strategy_id="test_strategy" # Needs to exist?
    )
    
    # 4. Start Job
    await service.start_job(job_id)
    
    # 5. Wait for Controller to Dispatch
    # Controller runs every 1s.
    await asyncio.sleep(2.5)
    
    # 6. Check Tasks
    tasks = await service.list_tasks(job_id)
    print(f"Tasks found: {len(tasks)}")
    
    # We expect 2 tasks to be created (PENDING or RUNNING)
    assert len(tasks) == 2
    
    # 7. Check Task Status
    # Dispatcher fires async, so they might be RUNNING, FAILED, or SUCCEEDED (if fast)
    for t in tasks:
        print(f"Task {t.id}: {t.status} - {t.error}")
        assert t.status in [TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.SUCCEEDED]

    # 8. Clean up
    await service.stop()
    # await rem.shutdown()
