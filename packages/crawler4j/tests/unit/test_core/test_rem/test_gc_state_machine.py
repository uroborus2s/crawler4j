from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager, RECOVERY_PROVIDER_RUNTIME_TIMEOUT
from src.core.rem.models import Environment, EnvKind, EnvStatus


@pytest.fixture
def manager():
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_get_pool.return_value = AsyncMock()
        return EnvironmentManager()


@pytest.mark.asyncio
async def test_run_gc_reaps_shell_statuses(manager):
    error_env = Environment(
        id=11,
        name="env-error",
        kind=EnvKind.BROWSER,
        provider="mock-provider",
        status=EnvStatus.ERROR,
        external_id="ext-11",
    )
    terminating_env = Environment(
        id=12,
        name="env-terminating",
        kind=EnvKind.BROWSER,
        provider="mock-provider",
        status=EnvStatus.TERMINATING,
        external_id="ext-12",
    )
    provider = SimpleNamespace(
        exists=AsyncMock(return_value=True),
        is_window_open=AsyncMock(return_value=False),
    )
    manager.pool.list_all = AsyncMock(return_value=[error_env, terminating_env])

    with (
        patch("src.core.rem.manager.get_provider", return_value=provider),
        patch.object(manager, "destroy_env", AsyncMock(return_value=True)) as destroy_env,
    ):
        count = await manager.run_gc()

    assert count == 2
    destroy_env.assert_any_await(
        error_env.id,
        runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
    )
    destroy_env.assert_any_await(
        terminating_env.id,
        runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
    )
    assert destroy_env.await_count == 2
    provider.exists.assert_not_awaited()


@pytest.mark.asyncio
async def test_recover_crashed_reaps_creating_env_with_short_runtime_timeout(manager):
    creating_env = Environment(
        id=21,
        name="env-creating",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.CREATING,
        external_id="ext-21",
    )
    manager.pool.list_all = AsyncMock(return_value=[creating_env])

    with (
        patch("src.core.rem.manager.get_provider", return_value=SimpleNamespace()),
        patch.object(manager, "destroy_env", AsyncMock(return_value=True)) as destroy_env,
    ):
        await manager._recover_crashed()

    destroy_env.assert_awaited_once_with(
        creating_env.id,
        runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
    )
