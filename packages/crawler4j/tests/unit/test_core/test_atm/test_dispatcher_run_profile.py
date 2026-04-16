from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, ExecutionContext, RunProfile
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


@pytest.mark.asyncio
async def test_dispatcher_selects_existing_env_for_run_profile(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "random_ready",
                "wait_timeout": 60,
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

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        call_hook=AsyncMock(side_effect=hook),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock(return_value=lease)),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-1", job_id="job-1")
    job = Job(id="job-1", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_envs.assert_awaited_once()
    dispatcher.rem.lease_manager.acquire.assert_awaited_once_with(env, task.id, timeout=60)
    dispatcher.rem.create_env.assert_not_awaited()
    dispatcher.rem.start_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_awaited_once()
    assert task.status == TaskStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_dispatcher_passes_selector_name_to_module_callback(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "return_none",
                "wait_timeout": 45,
            },
        },
        execution=ExecutionContext(module="demo.module"),
    )

    env = Environment(
        id=18,
        name="bit-env",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        external_id="18",
    )

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            assert args[1] == "return_none"
            assert args[0][0].env_id == env.id
            return None
        return None

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        call_hook=AsyncMock(side_effect=hook),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock()),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-18", job_id="job-18")
    job = Job(id="job-18", name="job-18", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    select_call = next(call for call in module_service.call_hook.await_args_list if call.args[1] == "select_env")
    assert select_call.args[4] == "return_none"
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    assert task.status == TaskStatus.FAILED
    assert "返回了 none" in (task.error or "")


@pytest.mark.asyncio
async def test_dispatcher_requires_run_profile():
    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace()

    task = Task(id="task-inline", job_id="job-inline")
    job = Job(id="job-inline", name="job-inline")

    with pytest.raises(ValueError, match="missing run_profile"):
        await dispatcher._run_logic(task, job)
