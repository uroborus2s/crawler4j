from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, JobType, Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, ExecutionContext, RunProfile
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


def _build_module_service(selector_hook=None):
    async def default_hook(module_name, hook_name, context, *args):
        return None

    service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        call_hook=AsyncMock(side_effect=selector_hook or default_hook),
    )

    async def run_env_selector(module_name, selector_name, context, candidates):
        return await service.call_hook(module_name, "select_env", context, candidates, selector_name)

    service.run_env_selector = AsyncMock(side_effect=run_env_selector)
    return service


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

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(return_value=lease),
            claim_created_env=AsyncMock(return_value=lease),
        ),
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

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock(), claim_created_env=AsyncMock()),
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


@pytest.mark.asyncio
async def test_dispatcher_service_fixed_pool_waits_instead_of_failing_on_selector_none(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "return_none",
                "resource_pool": "bound_account_ready",
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
            return None
        return None

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        list_allocatable_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock(), claim_created_env=AsyncMock()),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-pool-18", job_id="job-pool-18")
    job = Job(id="job-pool-18", name="job-18", type=JobType.SERVICE, run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.PENDING
    assert task.error == ""
    assert "等待环境" in (task.message or "")


@pytest.mark.asyncio
async def test_dispatcher_service_fixed_pool_requeues_when_selected_candidate_disappears(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "pick_missing",
                "resource_pool": "bound_account_ready",
                "wait_timeout": 45,
            },
        },
        execution=ExecutionContext(module="demo.module"),
    )

    env = Environment(
        id=19,
        name="bit-env-19",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        external_id="19",
    )

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        list_allocatable_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock(), claim_created_env=AsyncMock()),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=None),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-pool-19", job_id="job-pool-19")
    job = Job(id="job-pool-19", name="job-19", type=JobType.SERVICE, run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.PENDING
    assert task.error == ""
    assert task.message == "等待环境池工位: bound_account_ready"


@pytest.mark.asyncio
async def test_dispatcher_service_fixed_pool_fails_when_selector_returns_non_candidate_env(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "pick_missing",
                "resource_pool": "bound_account_ready",
                "wait_timeout": 45,
            },
        },
        execution=ExecutionContext(module="demo.module"),
    )

    candidate_env = Environment(
        id=19,
        name="bit-env-19",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        external_id="19",
    )

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return 999
        return None

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=candidate_env),
        list_envs=AsyncMock(return_value=[candidate_env]),
        list_allocatable_envs=AsyncMock(return_value=[candidate_env]),
        lease_manager=SimpleNamespace(acquire=AsyncMock(), claim_created_env=AsyncMock()),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=None),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-pool-19b", job_id="job-pool-19b")
    job = Job(id="job-pool-19b", name="job-19b", type=JobType.SERVICE, run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.FAILED
    assert "返回了不存在的环境" in (task.error or "")
    assert task.message == ""


@pytest.mark.asyncio
async def test_dispatcher_service_fixed_pool_fails_when_lease_acquire_raises(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "selector_name": "pick_ready",
                "resource_pool": "bound_account_ready",
                "wait_timeout": 45,
            },
        },
        execution=ExecutionContext(module="demo.module"),
    )

    env = Environment(
        id=20,
        name="bit-env-20",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        external_id="20",
    )

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        list_allocatable_envs=AsyncMock(return_value=[env]),
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(side_effect=RuntimeError("lease failed")),
            claim_created_env=AsyncMock(),
        ),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )

    task = Task(id="task-pool-20", job_id="job-pool-20")
    job = Job(id="job-pool-20", name="job-20", type=JobType.SERVICE, run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    dispatcher.rem.lease_manager.acquire.assert_awaited_once_with(env, task.id, timeout=45)
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.FAILED
    assert task.error == "Resource Error: lease failed"
    assert task.message == ""
