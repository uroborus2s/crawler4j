from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
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
    destroy_env.assert_any_await(error_env.id)
    destroy_env.assert_any_await(terminating_env.id)
    assert destroy_env.await_count == 2
