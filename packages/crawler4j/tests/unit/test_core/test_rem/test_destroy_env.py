from contextlib import ExitStack
from unittest.mock import AsyncMock, call, patch

import pytest

from src.core.persistence.database import STATE_DB, get_connection
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
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))

        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


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
def persistent_manager(temp_data_dir):
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_get_pool.return_value = AsyncMock()
        yield EnvironmentManager()


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


@pytest.mark.asyncio
async def test_destroy_env_removes_creating_placeholder_without_external_handle(
    manager,
    mock_pool,
):
    placeholder_env = Environment(
        id=77,
        name="env-creating-placeholder",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.CREATING,
        external_id="",
    )
    provider = DestroyTrackingProvider(name="virtualbrowser", destroy_result=True)
    register_provider(provider)
    mock_pool.get.return_value = placeholder_env

    with patch.object(manager, "ensure_provider_runtime", AsyncMock()) as ensure_runtime:
        success = await manager.destroy_env(placeholder_env.id)

    assert success is True
    ensure_runtime.assert_not_awaited()
    assert provider.destroy_called is False
    mock_pool.remove.assert_awaited_once_with(placeholder_env.id)
    mock_pool.update_status.assert_awaited_once_with(
        placeholder_env.id,
        EnvStatus.TERMINATING,
    )


@pytest.mark.asyncio
async def test_destroy_env_accepts_numeric_string_id_from_ui(
    persistent_manager,
):
    provider = DestroyTrackingProvider(name="destroy-string-id-provider", destroy_result=True)
    register_provider(provider)

    env = Environment(
        name="ui-string-id-env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="browser-ui-string-id",
    )
    await persistent_manager.pool.add(env)

    success = await persistent_manager.destroy_env(str(env.id))

    assert success is True
    assert provider.destroy_called is True
    assert await persistent_manager.get_env(env.id) is None

    with get_connection(STATE_DB) as conn:
        row_count = conn.execute(
            "SELECT COUNT(*) FROM environments WHERE id = ?",
            (env.id,),
        ).fetchone()[0]

    assert row_count == 0


@pytest.mark.asyncio
async def test_destroy_env_passes_runtime_timeout_to_fingerprint_runtime_check(
    manager,
    mock_pool,
    fingerprint_env,
):
    provider = DestroyTrackingProvider(name="bitbrowser", destroy_result=True)
    register_provider(provider)
    mock_pool.get.return_value = fingerprint_env

    with patch.object(manager, "ensure_provider_runtime", AsyncMock()) as ensure_runtime:
        success = await manager.destroy_env(fingerprint_env.id, runtime_timeout=3)

    assert success is True
    ensure_runtime.assert_awaited_once_with("bitbrowser", timeout=3)


@pytest.mark.asyncio
async def test_destroy_env_cascades_env_metadata_cleanup_after_row_delete(
    persistent_manager,
):
    provider = DestroyTrackingProvider(name="destroy-cascade-provider", destroy_result=True)
    register_provider(provider)

    doomed_env = Environment(
        name="doomed-env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="browser-doomed",
    )
    survivor_env = Environment(
        name="survivor-env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="browser-survivor",
    )
    await persistent_manager.pool.add(doomed_env)
    await persistent_manager.pool.add(survivor_env)

    await persistent_manager.set_metadata(
        doomed_env.id,
        "scheduler.resource_pool",
        "demo_module:bound_account_ready",
        {"eligible": False, "reason": "blacklisted"},
        value_type="json",
    )
    await persistent_manager.set_metadata(
        doomed_env.id,
        "demo.custom",
        "note",
        {"source": "manual-review"},
        value_type="json",
    )
    await persistent_manager.set_metadata(
        survivor_env.id,
        "scheduler.resource_pool",
        "demo_module:bound_account_ready",
        {"eligible": True, "reason": ""},
        value_type="json",
    )

    with get_connection(STATE_DB) as conn:
        doomed_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM env_metadata WHERE env_id = ?",
            (doomed_env.id,),
        ).fetchone()[0]
        survivor_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM env_metadata WHERE env_id = ?",
            (survivor_env.id,),
        ).fetchone()[0]

    assert doomed_metadata_count == 2
    assert survivor_metadata_count == 1

    success = await persistent_manager.destroy_env(doomed_env.id)

    assert success is True
    assert provider.destroy_called is True
    assert await persistent_manager.get_env(doomed_env.id) is None

    with get_connection(STATE_DB) as conn:
        doomed_row_count = conn.execute(
            "SELECT COUNT(*) FROM environments WHERE id = ?",
            (doomed_env.id,),
        ).fetchone()[0]
        doomed_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM env_metadata WHERE env_id = ?",
            (doomed_env.id,),
        ).fetchone()[0]
        survivor_metadata_count = conn.execute(
            "SELECT COUNT(*) FROM env_metadata WHERE env_id = ?",
            (survivor_env.id,),
        ).fetchone()[0]

    assert doomed_row_count == 0
    assert doomed_metadata_count == 0
    assert survivor_metadata_count == 1
