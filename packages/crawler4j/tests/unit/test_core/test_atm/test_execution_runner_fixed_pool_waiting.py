from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.atm.models import Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus, EnvUnavailableError


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


def _build_env() -> tuple[Environment, EnvLease]:
    env = Environment(
        id=21,
        name="env-21",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="ext-21",
    )
    lease = EnvLease(id="lease-21", env_id=env.id, task_run_id="task-21", token="token-21")
    return env, lease


def _build_request() -> ExecutionRequest:
    return ExecutionRequest(
        task=Task(id="task-21", job_id="job-21"),
        module_name="demo.module",
        hooks_module="demo.module",
        workflow_name="default",
        execution_params={},
        job_params={},
        runtime_params={},
        state={"job_id": "job-21", "task_id": "task-21"},
        selector_name="fixed_pool_selector",
        resource_pool_name="bound_account_ready",
        acquisition_mode=AcquisitionMode.SELECT,
        selector_wait_timeout=60,
        wait_for_resource=True,
    )


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


def _build_runner(
    *,
    env: Environment | None,
    lease: EnvLease | None,
    module_service,
    env_lookup: Environment | None = None,
    pool_card=None,
):
    rem = SimpleNamespace(
        list_envs=AsyncMock(return_value=[env] if env else []),
        list_allocatable_envs=AsyncMock(return_value=[env] if env else []),
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(return_value=lease),
        ),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env_lookup if env_lookup is not None else env),
        get_metadata=AsyncMock(
            return_value={"eligible": True} if pool_card is None else pool_card,
        ),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        recycle_env=AsyncMock(return_value=None),
        destroy_env=AsyncMock(return_value=True),
    )
    return ExecutionRunner(rem=rem, mms=module_service), rem


@pytest.mark.asyncio
async def test_execution_runner_waits_when_fixed_pool_has_no_candidates():
    request = _build_request()
    module_service = _build_module_service()
    runner, rem = _build_runner(env=None, lease=None, module_service=module_service)

    await runner.run(request)

    rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert "等待环境池工位" in (request.task.message or "")


@pytest.mark.asyncio
async def test_execution_runner_records_waiting_since_when_fixed_pool_enters_queue(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.created_at = 1_710_000_000
    waiting_since = request.task.created_at + 90
    module_service = _build_module_service()
    runner, _rem = _build_runner(env=None, lease=None, module_service=module_service)
    monkeypatch.setattr(execution_runner.time, "time", lambda: waiting_since)

    await runner.run(request)

    assert request.task.created_at == 1_710_000_000
    assert getattr(request.task, "waiting_since", None) == waiting_since
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境池工位: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_preserves_existing_waiting_since_on_requeue(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.waiting_since = 1_710_000_090
    module_service = _build_module_service()
    runner, _rem = _build_runner(env=None, lease=None, module_service=module_service)
    monkeypatch.setattr(execution_runner.time, "time", lambda: 1_710_000_190)

    await runner.run(request)

    assert request.task.waiting_since == 1_710_000_090
    assert request.task.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_execution_runner_fixed_pool_requeues_when_selected_candidate_disappears():
    request = _build_request()
    env, lease = _build_env()

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service, env_lookup=None)
    rem.get_env = AsyncMock(return_value=None)

    await runner.run(request)

    rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境池工位: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_fixed_pool_fails_when_lease_acquire_raises():
    request = _build_request()
    request.task.message = "等待环境池工位: bound_account_ready"
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.lease_manager.acquire = AsyncMock(side_effect=RuntimeError("lease failed"))

    await runner.run(request)

    rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.FAILED
    assert request.task.error == "Resource Error: lease failed"
    assert request.task.message == ""
    assert request.task.waiting_since is None


@pytest.mark.asyncio
async def test_execution_runner_fixed_pool_requeues_when_selected_env_is_taken(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.lease_manager.acquire = AsyncMock(
        side_effect=EnvUnavailableError("环境 21 已被占用", stage="LEASE")
    )
    monkeypatch.setattr(execution_runner.time, "time", lambda: 1_710_000_190)

    await runner.run(request)

    rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境池工位: bound_account_ready"
    assert request.task.waiting_since == 1_710_000_090


@pytest.mark.asyncio
async def test_execution_runner_fixed_pool_requeues_when_pool_card_turns_ineligible_after_lease(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "select_env":
            return env.id
        return None

    module_service = _build_module_service(hook)
    runner, rem = _build_runner(
        env=env,
        lease=lease,
        module_service=module_service,
        pool_card={"eligible": False},
    )
    monkeypatch.setattr(execution_runner.time, "time", lambda: 1_710_000_190)

    await runner.run(request)

    rem.list_allocatable_envs.assert_awaited_once_with("demo", "bound_account_ready")
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    rem.get_metadata.assert_awaited_once()
    rem.release.assert_awaited_once_with(lease)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境池工位: bound_account_ready"
    assert request.task.waiting_since == 1_710_000_090
