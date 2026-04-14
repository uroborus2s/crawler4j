from unittest.mock import AsyncMock, call, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, EnvUnavailableError
from src.core.rem.provider import BaseProvider, register_provider


class DestroyTrackingProvider(BaseProvider):
    kind = EnvKind.BROWSER

    def __init__(self, name: str, destroy_result: bool = True):
        self.name = name
        self.destroy_result = destroy_result
        self.destroy_called = False

    async def create(self, config: dict | None = None) -> Environment:
        return Environment(kind=self.kind, provider=self.name, status=EnvStatus.READY)

    async def reset(self, env: Environment) -> bool:
        return True

    async def health_check(self, env: Environment) -> bool:
        return True

    async def destroy(self, env: Environment) -> bool:
        self.destroy_called = True
        return self.destroy_result

    async def is_running(self, env: Environment) -> bool:
        return True

    async def open(self, env: Environment) -> bool:
        return True

    async def connect(self, env: Environment) -> bool:
        return True

    async def close(self, env: Environment) -> bool:
        return True

    async def is_window_open(self, env: Environment) -> bool:
        return False

    async def exists(self, env: Environment) -> bool:
        return True

    async def update(self, env: Environment, config: dict) -> bool:
        return True


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.get = AsyncMock()
    pool.update_status = AsyncMock()
    pool.remove = AsyncMock()
    return pool


@pytest.fixture
def manager(mock_pool):
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_get_pool.return_value = AsyncMock()
        mgr = EnvironmentManager()
        mgr.pool = mock_pool
        return mgr


@pytest.fixture
def fingerprint_env():
    return Environment(
        id=42,
        name="fingerprint-env",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        external_id="browser-42",
    )


@pytest.mark.asyncio
async def test_destroy_env_keeps_db_record_when_runtime_unavailable(
    manager,
    mock_pool,
    fingerprint_env,
):
    provider = DestroyTrackingProvider(name="bitbrowser")
    register_provider(provider)
    mock_pool.get.return_value = fingerprint_env

    with patch.object(
        manager,
        "ensure_provider_runtime",
        AsyncMock(side_effect=EnvUnavailableError("BitBrowser API 未就绪")),
    ):
        success = await manager.destroy_env(fingerprint_env.id)

    assert success is False
    assert provider.destroy_called is False
    mock_pool.remove.assert_not_awaited()
    mock_pool.update_status.assert_has_awaits(
        [
            call(fingerprint_env.id, EnvStatus.TERMINATING),
            call(fingerprint_env.id, EnvStatus.READY),
        ]
    )


@pytest.mark.asyncio
async def test_destroy_env_keeps_db_record_when_external_delete_fails(
    manager,
    mock_pool,
    fingerprint_env,
):
    provider = DestroyTrackingProvider(name="bitbrowser", destroy_result=False)
    register_provider(provider)
    mock_pool.get.return_value = fingerprint_env

    with patch.object(manager, "ensure_provider_runtime", AsyncMock()):
        success = await manager.destroy_env(fingerprint_env.id)

    assert success is False
    assert provider.destroy_called is True
    mock_pool.remove.assert_not_awaited()
    mock_pool.update_status.assert_has_awaits(
        [
            call(fingerprint_env.id, EnvStatus.TERMINATING),
            call(fingerprint_env.id, EnvStatus.READY),
        ]
    )


@pytest.mark.asyncio
async def test_destroy_env_removes_db_record_after_external_delete_succeeds(
    manager,
    mock_pool,
    fingerprint_env,
):
    provider = DestroyTrackingProvider(name="bitbrowser", destroy_result=True)
    register_provider(provider)
    mock_pool.get.return_value = fingerprint_env

    with patch.object(manager, "ensure_provider_runtime", AsyncMock()):
        success = await manager.destroy_env(fingerprint_env.id)

    assert success is True
    assert provider.destroy_called is True
    mock_pool.remove.assert_awaited_once_with(fingerprint_env.id)
    mock_pool.update_status.assert_awaited_once_with(
        fingerprint_env.id,
        EnvStatus.TERMINATING,
    )
