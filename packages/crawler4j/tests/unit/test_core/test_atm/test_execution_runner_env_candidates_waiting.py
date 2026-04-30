from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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
        workflow_name="default",
        state={"job_id": "job-21", "task_id": "task-21"},
        candidates_name="bound_account_ready",
        acquisition_mode=AcquisitionMode.SELECT,
        wait_timeout=60,
        wait_for_resource=True,
    )


def _build_module_service(candidate_ids):
    return SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        resolve_env_candidates=Mock(side_effect=candidate_ids if isinstance(candidate_ids, list) else None),
    )


def _build_runner(
    *,
    env: Environment | None,
    lease: EnvLease | None,
    module_service,
    env_lookup: Environment | None = None,
):
    rem = SimpleNamespace(
        list_envs=AsyncMock(return_value=[env] if env else []),
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(return_value=lease),
        ),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env_lookup if env_lookup is not None else env),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        recycle_env=AsyncMock(return_value=None),
        destroy_env=AsyncMock(return_value=True),
    )
    return ExecutionRunner(rem=rem, mms=module_service), rem


def _candidate_service(*results: list[int]):
    service = _build_module_service(list(results))
    if not results:
        service.resolve_env_candidates = Mock(return_value=[])
    return service


@pytest.mark.asyncio
async def test_execution_runner_waits_when_env_candidates_return_empty():
    request = _build_request()
    module_service = _candidate_service([])
    runner, rem = _build_runner(env=None, lease=None, module_service=module_service)

    await runner.run(request)

    rem.list_envs.assert_not_awaited()
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_records_waiting_since_when_env_candidates_enter_queue(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.created_at = 1_710_000_000
    waiting_since = request.task.created_at + 90
    module_service = _candidate_service([])
    runner, _rem = _build_runner(env=None, lease=None, module_service=module_service)
    monkeypatch.setattr(execution_runner.time, "time", lambda: waiting_since)

    await runner.run(request)

    assert request.task.created_at == 1_710_000_000
    assert getattr(request.task, "waiting_since", None) == waiting_since
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""


@pytest.mark.asyncio
async def test_execution_runner_requeues_when_selected_candidate_disappears():
    request = _build_request()
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service, env_lookup=None)
    rem.get_env = AsyncMock(return_value=None)

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_ignores_candidate_env_bound_to_another_module():
    request = _build_request()
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.get_metadata = AsyncMock(return_value="other.module")
    rem.set_metadata = AsyncMock(return_value=True)

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_binds_fixed_env_to_module_after_lease():
    request = _build_request()
    request.fixed_env_id = 21
    request.candidates_name = ""
    env, lease = _build_env()

    module_service = _candidate_service([])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.get_metadata = AsyncMock(return_value="")
    rem.set_metadata = AsyncMock(return_value=True)

    await runner.run(request)

    rem.get_metadata.assert_awaited()
    rem.set_metadata.assert_awaited_with(
        21,
        "scheduler.env_candidates",
        "module_name",
        "demo.module",
        "string",
    )


@pytest.mark.asyncio
async def test_execution_runner_fails_when_candidate_lease_acquire_raises():
    request = _build_request()
    request.task.message = "等待环境候选可用: bound_account_ready"
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.lease_manager.acquire = AsyncMock(side_effect=RuntimeError("lease failed"))

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.FAILED
    assert request.task.error == "Resource Error: lease failed"
    assert request.task.message == ""
    assert request.task.waiting_since is None


@pytest.mark.asyncio
async def test_execution_runner_requeues_when_selected_env_is_taken(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    rem.lease_manager.acquire = AsyncMock(
        side_effect=EnvUnavailableError("环境 21 已被占用", stage="LEASE")
    )
    monkeypatch.setattr(execution_runner.time, "time", lambda: 1_710_000_190)

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境候选可用: bound_account_ready"
    assert request.task.waiting_since == 1_710_000_090


@pytest.mark.asyncio
async def test_execution_runner_requeues_when_candidate_function_excludes_env_after_lease(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    module_service = _candidate_service([21], [])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    monkeypatch.setattr(execution_runner.time, "time", lambda: 1_710_000_190)

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    rem.release.assert_awaited_once_with(lease)
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境候选可用: bound_account_ready"
    assert request.task.waiting_since == 1_710_000_090
