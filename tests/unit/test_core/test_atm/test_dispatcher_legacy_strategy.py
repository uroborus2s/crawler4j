from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, Task, TaskStatus
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus
from src.core.tsm.models import AcquisitionMode, ExecutionContext, TaskStrategy, EnvType


@pytest.mark.asyncio
async def test_dispatcher_matches_existing_env_for_match_strategy(monkeypatch):
    strategy = TaskStrategy(
        id="match-vb",
        name="match-vb",
        resource={
            "provider": "virtualbrowser",
            "acquisition": {
                "mode": AcquisitionMode.MATCH,
                "selector": {"env_type": EnvType.VIRTUAL_BROWSER, "wait_timeout": 60},
                "creation": {"params": {"fingerprint": {"randomize_all": True}}},
            },
        },
        execution=ExecutionContext(module="demo.module"),
    )

    env = Environment(
        id=12,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="12",
    )
    lease = EnvLease(id="lease-1", env_id=env.id, task_run_id="task-1", token="token-1")

    loader = SimpleNamespace(get=lambda strategy_id: strategy)
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.tsm.get_strategy_loader", lambda: loader)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        acquire_atomic=AsyncMock(return_value=lease),
        create_env=AsyncMock(return_value=env),
        lease_manager=SimpleNamespace(acquire=AsyncMock(return_value=lease)),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-1", job_id="job-1")
    job = Job(id="job-1", name="job", strategy_id=strategy.id)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.acquire_atomic.assert_awaited_once()
    dispatcher.rem.create_env.assert_not_awaited()
    dispatcher.rem.start_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_awaited_once()
    assert task.status == TaskStatus.SUCCEEDED
