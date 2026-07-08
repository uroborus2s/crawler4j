from contextlib import ExitStack
from unittest.mock import patch

import pytest

from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_DETAIL,
    FINGERPRINT_VALIDATION_NAMESPACE,
    FINGERPRINT_VALIDATION_PASSED,
    FINGERPRINT_VALIDATION_REASON,
    FINGERPRINT_VALIDATION_RISK,
    FINGERPRINT_VALIDATION_STATUS,
)
from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvRequirement, EnvStatus, EnvUnavailableError
from src.core.rem.pool import EnvPool, LeaseManager


@pytest.fixture
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))

        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


async def _add_ready_env(pool: EnvPool, name: str) -> Environment:
    env = Environment(
        name=name,
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        capabilities={"page"},
    )
    await pool.add(env)
    return env


def _mark_risk(pool: EnvPool, env_id: int) -> None:
    pool.set_metadata(
        env_id,
        FINGERPRINT_VALIDATION_NAMESPACE,
        FINGERPRINT_VALIDATION_STATUS,
        FINGERPRINT_VALIDATION_RISK,
        "string",
    )


@pytest.mark.asyncio
async def test_env_pool_find_available_skips_fingerprint_risk_env(temp_data_dir):
    pool = EnvPool(max_instances=10)
    risk_env = await _add_ready_env(pool, "risk-env")
    safe_env = await _add_ready_env(pool, "safe-env")
    _mark_risk(pool, risk_env.id)

    selected = await pool.find_available(EnvRequirement(kind=EnvKind.BROWSER, capabilities={"page"}))

    assert selected is not None
    assert selected.id == safe_env.id


@pytest.mark.asyncio
async def test_lease_manager_rejects_fingerprint_risk_env(temp_data_dir):
    pool = EnvPool(max_instances=10)
    env = await _add_ready_env(pool, "risk-env")
    _mark_risk(pool, env.id)
    lease_manager = LeaseManager(pool)

    with pytest.raises(EnvUnavailableError, match="指纹风险待复检"):
        await lease_manager.acquire(env, "task-1")


@pytest.mark.asyncio
async def test_atomic_lease_skips_fingerprint_risk_env(temp_data_dir):
    pool = EnvPool(max_instances=10)
    risk_env = await _add_ready_env(pool, "risk-env")
    safe_env = await _add_ready_env(pool, "safe-env")
    _mark_risk(pool, risk_env.id)
    lease_manager = LeaseManager(pool)

    lease = await lease_manager.acquire_atomic(
        EnvRequirement(kind=EnvKind.BROWSER, capabilities={"page"}, task_run_id="task-1")
    )

    assert lease.env_id == safe_env.id


@pytest.mark.asyncio
async def test_manual_recheck_updates_only_validation_metadata(temp_data_dir, monkeypatch):
    manager = EnvironmentManager()
    env = await _add_ready_env(manager.pool, "risk-env")
    original_provider = env.provider

    class FakeProvider:
        async def validate_fingerprint_environment(self, checked_env):
            assert checked_env.id == env.id
            return []

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda provider: FakeProvider())

    await manager.mark_fingerprint_validation_risk(
        env.id,
        reason="WebRTC 泄漏",
        detail="candidate=1.2.3.4",
    )

    summary = await manager.recheck_env_fingerprint_validation(env.id)

    metadata = manager.pool.list_metadata(env.id, FINGERPRINT_VALIDATION_NAMESPACE)
    assert summary.status == FINGERPRINT_VALIDATION_PASSED
    assert metadata[FINGERPRINT_VALIDATION_STATUS] == FINGERPRINT_VALIDATION_PASSED
    assert metadata[FINGERPRINT_VALIDATION_REASON] == ""
    assert metadata[FINGERPRINT_VALIDATION_DETAIL] == "手动重新检测通过"
    assert (await manager.get_env(env.id)).provider == original_provider


@pytest.mark.asyncio
async def test_repair_env_fingerprint_location_updates_and_rechecks(temp_data_dir, monkeypatch):
    manager = EnvironmentManager()
    env = await _add_ready_env(manager.pool, "risk-env")
    calls: list[str] = []

    class FakeProvider:
        async def repair_fingerprint_location(self, checked_env):
            calls.append(f"repair:{checked_env.id}")

        async def validate_fingerprint_environment(self, checked_env):
            calls.append(f"validate:{checked_env.id}")
            return []

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda provider: FakeProvider())

    await manager.mark_fingerprint_validation_risk(
        env.id,
        reason="location 为 0,0",
        detail="location 为 0,0，占位定位不能作为稳定环境参数",
    )

    summary = await manager.repair_env_fingerprint_location(env.id)

    metadata = manager.pool.list_metadata(env.id, FINGERPRINT_VALIDATION_NAMESPACE)
    assert calls == [f"repair:{env.id}", f"validate:{env.id}"]
    assert summary.status == FINGERPRINT_VALIDATION_PASSED
    assert metadata[FINGERPRINT_VALIDATION_STATUS] == FINGERPRINT_VALIDATION_PASSED


@pytest.mark.asyncio
async def test_created_validation_warnings_mark_env_risk_metadata(temp_data_dir):
    manager = EnvironmentManager()
    env = await _add_ready_env(manager.pool, "created-risk-env")
    env.fingerprint_validation_warnings = ["WebRTC mode mismatch", "timezone mismatch"]

    await manager._persist_created_fingerprint_validation(env)

    metadata = manager.pool.list_metadata(env.id, FINGERPRINT_VALIDATION_NAMESPACE)
    assert metadata[FINGERPRINT_VALIDATION_STATUS] == FINGERPRINT_VALIDATION_RISK
    assert metadata[FINGERPRINT_VALIDATION_REASON] == "WebRTC mode mismatch"
    assert metadata[FINGERPRINT_VALIDATION_DETAIL] == "WebRTC mode mismatch; timezone mismatch"
    assert not hasattr(env, "fingerprint_validation_warnings")
