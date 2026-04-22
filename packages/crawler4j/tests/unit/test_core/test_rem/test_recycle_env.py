from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus


@pytest.fixture
def mock_pool():
    return MagicMock(update_status=AsyncMock())


@pytest.fixture
def manager(mock_pool):
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_get_pool.return_value = AsyncMock()
        mgr = EnvironmentManager()
        mgr.pool = mock_pool
        return mgr


def _make_env(status: EnvStatus = EnvStatus.BUSY) -> Environment:
    return Environment(
        id=7,
        name="env-7",
        kind=EnvKind.BROWSER,
        provider="mock-provider",
        status=status,
        lease_id="lease-7",
        task_run_id="task-7",
    )


@pytest.mark.asyncio
async def test_recycle_env_keeps_original_state_when_close_returns_false(manager, mock_pool):
    env = _make_env()

    async def update_status(env_id: int, status: EnvStatus) -> None:
        assert env_id == env.id
        env.status = status

    mock_pool.update_status.side_effect = update_status
    provider = SimpleNamespace(close=AsyncMock(return_value=False))

    with (
        patch("src.core.rem.manager.get_provider", return_value=provider),
        patch.object(manager, "_emit_error") as emit_error,
    ):
        success = await manager.recycle_env(env)

    assert success is False
    assert env.status == EnvStatus.BUSY
    assert env.lease_id == "lease-7"
    assert env.task_run_id == "task-7"
    assert all(call.args[1] != EnvStatus.READY for call in mock_pool.update_status.await_args_list)
    emit_error.assert_not_called()


@pytest.mark.asyncio
async def test_recycle_env_keeps_original_state_when_close_raises(manager, mock_pool):
    env = _make_env(status=EnvStatus.RUNNING)

    async def update_status(env_id: int, status: EnvStatus) -> None:
        assert env_id == env.id
        env.status = status

    mock_pool.update_status.side_effect = update_status
    provider = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("close boom")))

    with (
        patch("src.core.rem.manager.get_provider", return_value=provider),
        patch.object(manager, "_emit_error") as emit_error,
    ):
        success = await manager.recycle_env(env)

    assert success is False
    assert env.status == EnvStatus.RUNNING
    assert env.lease_id == "lease-7"
    assert env.task_run_id == "task-7"
    assert all(call.args[1] != EnvStatus.READY for call in mock_pool.update_status.await_args_list)
    emit_error.assert_called_once_with(env, "close", "close boom")
