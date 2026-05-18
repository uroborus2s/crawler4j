from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, JobType, Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, ExecutionContext, RunProfile
from src.core.rem.env_claims import CLAIM_CLAIMED, ENV_CLAIM_OWNER_MODULE, ENV_CLAIM_STATE
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


def _build_module_service(
    candidate_ids: list[int] | None = None,
    *,
    bound_env_ids: list[int] | None = None,
):
    service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        resolve_env_candidates=Mock(return_value=list(candidate_ids or [])),
        get_runtime_descriptor_v2=Mock(
            return_value=SimpleNamespace(
                data_tables={
                    "accounts": SimpleNamespace(meta=SimpleNamespace(env_binding_field="env_id")),
                }
                if bound_env_ids
                else {}
            )
        ),
    )
    return service


def _binding_capabilities(bound_env_ids: list[int]):
    class _BindingQuery:
        def select(self, field_name: str):
            self._field_name = field_name
            return self

        def execute(self):
            return [{self._field_name: env_id} for env_id in bound_env_ids]

    class _BindingDb:
        def from_(self, _table_name: str):
            return _BindingQuery()

    return SimpleNamespace(db=_BindingDb(), tools=SimpleNamespace())


@pytest.mark.asyncio
async def test_dispatcher_selects_existing_env_for_run_profile(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "env_id": 12,
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

    module_service = _build_module_service()

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

    dispatcher.rem.list_envs.assert_not_awaited()
    dispatcher.rem.get_env.assert_any_await(env.id)
    dispatcher.rem.lease_manager.acquire.assert_awaited_once_with(env, task.id, timeout=60)
    dispatcher.rem.create_env.assert_not_awaited()
    dispatcher.rem.start_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_awaited_once()
    assert task.status == TaskStatus.SUCCEEDED


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
async def test_dispatcher_service_candidates_waits_when_no_candidates(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "candidates": "bound_account_ready",
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

    module_service = _build_module_service(candidate_ids=[])

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

    task = Task(id="task-pool-18", job_id="job-pool-18")
    job = Job(id="job-pool-18", name="job-18", type=JobType.SERVICE, run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.list_envs.assert_not_awaited()
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.PENDING
    assert task.error == ""
    assert "等待环境" in (task.message or "")


@pytest.mark.asyncio
async def test_dispatcher_service_candidates_requeues_when_selected_candidate_disappears(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "candidates": "bound_account_ready",
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

    module_service = _build_module_service(candidate_ids=[19])

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
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

    dispatcher.rem.list_envs.assert_awaited_once()
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.PENDING
    assert task.error == ""
    assert task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_dispatcher_service_candidates_requeues_when_candidate_lookup_misses(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "candidates": "bound_account_ready",
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

    module_service = _build_module_service(candidate_ids=[19])

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=candidate_env),
        list_envs=AsyncMock(return_value=[candidate_env]),
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

    dispatcher.rem.list_envs.assert_awaited_once()
    dispatcher.rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.PENDING
    assert task.error == ""
    assert task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_dispatcher_service_candidates_fails_when_lease_acquire_raises(monkeypatch):
    run_profile = RunProfile(
        resource={
            "acquisition": {
                "mode": AcquisitionMode.SELECT,
                "candidates": "bound_account_ready",
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

    module_service = _build_module_service(candidate_ids=[20], bound_env_ids=[20])

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)
    monkeypatch.setattr(
        "src.core.rem.env_claims.build_runtime_capabilities",
        lambda _module_name: _binding_capabilities([20]),
    )

    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        list_metadata=AsyncMock(
            return_value={
                ENV_CLAIM_OWNER_MODULE: "demo.module",
                ENV_CLAIM_STATE: CLAIM_CLAIMED,
            }
        ),
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

    dispatcher.rem.list_envs.assert_awaited_once()
    dispatcher.rem.lease_manager.acquire.assert_awaited_once_with(env, task.id, timeout=45)
    module_service.run_module.assert_not_awaited()
    assert task.status == TaskStatus.FAILED
    assert task.error == "Resource Error: lease failed"
    assert task.message == ""
