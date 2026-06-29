from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.atm.models import Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode
from src.core.rem.env_claims import (
    CLAIM_ABANDONED,
    CLAIM_CLAIMED,
    ENV_CLAIM_NAMESPACE,
    ENV_CLAIM_OWNER_MODULE,
    ENV_CLAIM_STATE,
)
from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_NAMESPACE,
    FINGERPRINT_VALIDATION_RISK,
    FINGERPRINT_VALIDATION_STATUS,
)
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
        get_runtime_descriptor_v2=Mock(return_value=SimpleNamespace(data_tables={})),
    )


def _build_runner(
    *,
    env: Environment | None,
    lease: EnvLease | None,
    module_service,
    env_lookup: Environment | None = None,
):
    metadata_store: dict[tuple[int, str, str], object] = {}

    async def set_metadata(env_id: int, namespace: str, key: str, value, value_type: str = "string"):
        metadata_store[(int(env_id), namespace, key)] = value

    async def list_metadata(env_id: int, namespace: str):
        return {
            key: value
            for (stored_env_id, stored_namespace, key), value in metadata_store.items()
            if stored_env_id == int(env_id) and stored_namespace == namespace
        }

    rem = SimpleNamespace(
        list_envs=AsyncMock(return_value=[env] if env else []),
        set_metadata=AsyncMock(side_effect=set_metadata),
        list_metadata=AsyncMock(side_effect=list_metadata),
        metadata_store=metadata_store,
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


async def _seed_claim(rem, env_id: int, owner: str, state: str = CLAIM_CLAIMED) -> None:
    await rem.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await rem.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, state, "string")


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
async def test_execution_runner_requeues_when_selected_candidate_disappears(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service, env_lookup=None)
    await _seed_claim(rem, 21, "demo.module")
    monkeypatch.setattr(execution_runner, "is_env_bound_by_module", lambda *_args, **_kwargs: True)
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
    await _seed_claim(rem, 21, "other.module")

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_ignores_fingerprint_risk_candidate_env(monkeypatch):
    import src.core.atm.execution_runner as execution_runner

    request = _build_request()
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    await _seed_claim(rem, 21, "demo.module")
    await rem.set_metadata(
        21,
        FINGERPRINT_VALIDATION_NAMESPACE,
        FINGERPRINT_VALIDATION_STATUS,
        FINGERPRINT_VALIDATION_RISK,
        "string",
    )
    monkeypatch.setattr(execution_runner, "is_env_bound_by_module", lambda *_args, **_kwargs: True)

    await runner.run(request)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_not_awaited()
    module_service.run_module.assert_not_awaited()
    assert request.task.status == TaskStatus.PENDING
    assert request.task.error == ""
    assert request.task.message == "等待环境候选可用: bound_account_ready"


@pytest.mark.asyncio
async def test_execution_runner_refreshes_unbound_fixed_env_claim_after_task():
    request = _build_request()
    request.fixed_env_id = 21
    request.candidates_name = ""
    env, lease = _build_env()

    module_service = _candidate_service([])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)

    await runner.run(request)

    assert rem.metadata_store[(21, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE)] == "demo.module"
    assert rem.metadata_store[(21, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE)] == CLAIM_ABANDONED


@pytest.mark.asyncio
async def test_execution_runner_keeps_fixed_env_claimed_when_business_binding_exists():
    request = _build_request()
    request.fixed_env_id = 21
    request.candidates_name = ""
    request.runtime_capabilities = _binding_capabilities([21])
    env, lease = _build_env()

    module_service = _candidate_service([])
    module_service.get_runtime_descriptor_v2 = Mock(
        return_value=SimpleNamespace(
            data_tables={
                "accounts": SimpleNamespace(meta=SimpleNamespace(env_binding_field="env_id")),
            }
        )
    )
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)

    await runner.run(request)

    assert rem.metadata_store[(21, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE)] == "demo.module"
    assert rem.metadata_store[(21, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE)] == CLAIM_CLAIMED


@pytest.mark.asyncio
async def test_execution_runner_fails_when_candidate_lease_acquire_raises():
    request = _build_request()
    request.task.message = "等待环境候选可用: bound_account_ready"
    request.task.waiting_since = 1_710_000_090
    env, lease = _build_env()

    module_service = _candidate_service([21])
    runner, rem = _build_runner(env=env, lease=lease, module_service=module_service)
    await _seed_claim(rem, 21, "demo.module")
    runner._is_env_candidate_authorized = AsyncMock(return_value=True)
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
    await _seed_claim(rem, 21, "demo.module")
    monkeypatch.setattr(execution_runner, "is_env_bound_by_module", lambda *_args, **_kwargs: True)
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
    await _seed_claim(rem, 21, "demo.module")
    monkeypatch.setattr(execution_runner, "is_env_bound_by_module", lambda *_args, **_kwargs: True)
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
