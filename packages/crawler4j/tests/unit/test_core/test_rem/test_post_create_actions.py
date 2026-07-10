import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager, RECOVERY_PROVIDER_RUNTIME_TIMEOUT
from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
    ProxyConfig,
    ProxyMode,
)
from src.core.rem.provider import BaseProvider, register_provider
from src.core.system.external_app_service import AppLaunchResult, ExternalApp


class MockProvider(BaseProvider):
    name = "mock_provider"
    kind = EnvKind.BROWSER

    def __init__(self):
        self.create_called = False
        self.open_called = False
        self.connect_called = False
        self.close_called = False
        self.last_config = {}

    async def is_running(self, env: Environment) -> bool:
        return True

    async def is_window_open(self, env: Environment) -> bool:
        return False

    async def get_window_title(self, env: Environment) -> str | None:
        return "Mock Window"

    async def exists(self, env: Environment) -> bool:
        return True

    async def create(self, config: dict | None = None) -> Environment:
        self.create_called = True
        self.last_config = config or {}
        return Environment(
            id=config.get("env_id", 0),
            name=config.get("env_name", ""),
            kind=self.kind,
            provider=self.name,
            status=EnvStatus.READY,
            external_id="mock_ext_id",
        )

    async def open(self, env: Environment) -> bool:
        self.open_called = True
        return True

    async def connect(self, env: Environment) -> bool:
        self.connect_called = True
        return True

    async def close(self, env: Environment) -> bool:
        self.close_called = True
        return True

    async def disconnect(self, env: Environment) -> bool:
        return True

    async def reset(self, env: Environment) -> bool:
        return True

    async def health_check(self, env: Environment) -> bool:
        return True

    async def destroy(self, env: Environment) -> None:
        pass

    async def update(self, env: Environment, config: dict) -> bool:
        return True


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    envs: dict[int, Environment] = {}

    async def add(env: Environment):
        envs[env.id] = env

    async def get(env_id: int):
        return envs.get(env_id)

    async def update_status(env_id: int, status: EnvStatus):
        env = envs.get(env_id)
        if env:
            env.status = status

    pool.add = AsyncMock(side_effect=add)
    pool.get = AsyncMock(side_effect=get)
    pool.update_status = AsyncMock(side_effect=update_status)
    pool.remove = AsyncMock()
    return pool


@pytest.fixture
def manager(mock_pool):
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_ip_manager = AsyncMock()
        mock_get_pool.return_value = mock_ip_manager

        mgr = EnvironmentManager()
        mgr.pool = mock_pool
        return mgr


@pytest.mark.asyncio
async def test_create_env_keeps_connected_environment_running(manager):
    provider = MockProvider()
    register_provider(provider)

    env = await manager._create_env(provider=provider)

    assert env.status == EnvStatus.RUNNING
    assert provider.create_called
    assert provider.open_called
    assert provider.connect_called
    assert not provider.close_called


@pytest.mark.asyncio
async def test_create_env_runs_runtime_fingerprint_check_after_connect(manager):
    provider = MockProvider()
    provider.name = "virtualbrowser"
    register_provider(provider)
    manager._persist_runtime_fingerprint_validation = AsyncMock()  # type: ignore[attr-defined]

    env = await manager._create_env(provider=provider)

    manager._persist_runtime_fingerprint_validation.assert_awaited_once_with(env, provider)


@pytest.mark.asyncio
async def test_create_env_does_not_mutate_input_config(manager):
    provider = MockProvider()
    register_provider(provider)
    config = {
        "env_name": "custom-env",
        "labels": ["demo"],
    }

    env = await manager._create_env(provider=provider, config=config)

    assert env.name == "custom-env"
    assert config == {
        "env_name": "custom-env",
        "labels": ["demo"],
    }
    assert provider.last_config is not config
    assert provider.last_config["env_id"] == env.id
    assert provider.last_config["env_name"] == "custom-env"
    assert provider.last_config["labels"] == ["demo"]
    assert "env_id" not in config


@pytest.mark.asyncio
async def test_create_env_passes_manual_ip_geo_to_provider(manager, monkeypatch):
    from src.core.rem.ip_pool import IPEntry

    provider = MockProvider()
    register_provider(provider)
    entry = IPEntry(
        id="ip-1",
        pool_id="pool-1",
        address="10.0.0.8",
        protocol="http",
        port=8080,
        manual_latitude=39.9072,
        manual_longitude=116.357,
    )
    monkeypatch.setattr(entry, "random_manual_geo", lambda: {"latitude": 39.9, "longitude": 116.36})

    class FakeIPManager:
        async def bind_ip(self, *_args):
            return entry

    monkeypatch.setattr("src.core.rem.ip_pool.get_ip_pool_manager", lambda: FakeIPManager())

    await manager._create_env(
        provider=provider,
        proxy_config=ProxyConfig(mode=ProxyMode.POOL, pool_id="pool-1"),
    )

    assert provider.last_config["geo"] == {"latitude": 39.9, "longitude": 116.36}


def test_release_signature_removes_dirty_placeholder_argument():
    assert "dirty" not in inspect.signature(EnvironmentManager.release).parameters


@pytest.mark.asyncio
async def test_acquire_claims_fresh_running_environment(manager, mock_pool):
    provider = MockProvider()
    register_provider(provider)

    mock_pool.find_available = AsyncMock(return_value=None)
    mock_pool.can_create = MagicMock(return_value=True)

    requirement = EnvRequirement(task_run_id="task-create", timeout=45)

    lease = await manager.acquire(requirement, default_provider=provider.name)

    env = await mock_pool.get(lease.env_id)
    assert env is not None
    assert env.status == EnvStatus.RUNNING
    assert env.lease_id == lease.id
    assert env.task_run_id == "task-create"


@pytest.mark.asyncio
async def test_startup_can_skip_crash_recovery(mock_pool):
    with patch("src.core.rem.manager.get_ip_pool_manager") as mock_get_pool:
        mock_ip_manager = AsyncMock()
        mock_get_pool.return_value = mock_ip_manager

        manager = EnvironmentManager()
        manager.pool = mock_pool
        manager.pool.load_from_db = AsyncMock()
        manager.pool.list_all = AsyncMock(return_value=[])
        manager._recover_crashed = AsyncMock()

        await manager.startup(recover_crashed=False)

    manager.pool.load_from_db.assert_awaited_once()
    mock_ip_manager.startup.assert_awaited_once()
    manager._recover_crashed.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_env_connect_failure_closes_env_and_raises(manager):
    provider = MockProvider()
    provider.name = "virtualbrowser"
    provider.connect = AsyncMock(return_value=False)  # type: ignore[method-assign]
    register_provider(provider)

    error_event = MagicMock()
    with (
        patch.object(manager, "_emit_error", error_event),
        patch.object(manager, "destroy_env", AsyncMock(return_value=True)) as destroy_env,
        pytest.raises(EnvUnavailableError, match="Playwright 连接失败"),
    ):
        await manager._create_env(provider=provider)

    assert provider.open_called
    assert provider.close_called
    destroy_env.assert_awaited_once_with(
        provider.last_config["env_id"],
        runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
    )
    error_event.assert_called_once()


@pytest.mark.asyncio
async def test_stop_env_closes_running_environment_and_returns_ready(manager, mock_pool):
    provider = MockProvider()
    register_provider(provider)
    env = Environment(
        id=7,
        name="env-7",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.RUNNING,
        external_id="mock_ext_id",
    )
    await mock_pool.add(env)

    success = await manager.stop_env(env.id)

    assert success is True
    assert provider.close_called
    mock_pool.update_status.assert_awaited_with(env.id, EnvStatus.READY)


@pytest.mark.asyncio
async def test_ensure_provider_runtime_for_virtualbrowser(manager):
    app_service = MagicMock()
    app_service.ensure_running = AsyncMock(return_value=AppLaunchResult(success=True))
    app_service.wait_until_ready = AsyncMock(return_value=True)

    with patch(
        "src.core.system.external_app_service.get_external_app_service",
        return_value=app_service,
    ):
        await manager.ensure_provider_runtime("virtualbrowser")

    app_service.ensure_running.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER, timeout=30)
    app_service.wait_until_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_provider_runtime_fails_when_external_app_not_ready(manager):
    app_service = MagicMock()
    app_service.ensure_running = AsyncMock(
        return_value=AppLaunchResult(
            success=False,
            error_code="PATH_NOT_CONFIGURED",
            error_message="VirtualBrowser 安装路径未配置",
        )
    )
    app_service.wait_until_ready = AsyncMock(return_value=False)

    with patch(
        "src.core.system.external_app_service.get_external_app_service",
        return_value=app_service,
    ):
        with pytest.raises(EnvUnavailableError, match="安装路径未配置"):
            await manager.ensure_provider_runtime("virtualbrowser")

    app_service.ensure_running.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER, timeout=30)
    app_service.wait_until_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_env_ensures_fingerprint_runtime_before_open(manager, mock_pool):
    provider = MockProvider()
    provider.name = "virtualbrowser"
    register_provider(provider)

    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
    )
    mock_pool.get = AsyncMock(return_value=env)

    call_order: list[str] = []

    async def ensure_runtime(provider_name: str) -> None:
        call_order.append(f"ensure:{provider_name}")

    async def open_env(target_env: Environment) -> bool:
        call_order.append(f"open:{target_env.id}")
        return True

    async def connect_env(target_env: Environment) -> bool:
        call_order.append(f"connect:{target_env.id}")
        return True

    with patch.object(manager, "ensure_provider_runtime", side_effect=ensure_runtime):
        provider.open = open_env  # type: ignore[method-assign]
        provider.connect = connect_env  # type: ignore[method-assign]

        success = await manager.start_env(env.id)

    assert success is True
    assert call_order == ["ensure:virtualbrowser", "open:101", "connect:101"]


@pytest.mark.asyncio
async def test_start_env_opens_busy_environment_when_window_is_not_open(manager, mock_pool):
    provider = MockProvider()
    provider.name = "virtualbrowser"
    register_provider(provider)

    env = Environment(
        id=102,
        name="vb-env-closed",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
    )
    mock_pool.get = AsyncMock(return_value=env)

    call_order: list[str] = []

    async def ensure_runtime(provider_name: str) -> None:
        call_order.append(f"ensure:{provider_name}")

    async def is_window_open(target_env: Environment) -> bool:
        call_order.append(f"is_window_open:{target_env.id}")
        return False

    async def open_env(target_env: Environment) -> bool:
        call_order.append(f"open:{target_env.id}")
        return True

    async def connect_env(target_env: Environment) -> bool:
        call_order.append(f"connect:{target_env.id}")
        return True

    with patch.object(manager, "ensure_provider_runtime", side_effect=ensure_runtime):
        provider.is_window_open = is_window_open  # type: ignore[method-assign]
        provider.open = open_env  # type: ignore[method-assign]
        provider.connect = connect_env  # type: ignore[method-assign]

        success = await manager.start_env(env.id)

    assert success is True
    assert call_order == [
        "ensure:virtualbrowser",
        "is_window_open:102",
        "open:102",
        "connect:102",
    ]


@pytest.mark.asyncio
async def test_start_env_propagates_runtime_failure_for_fingerprint_provider(manager, mock_pool):
    provider = MockProvider()
    provider.name = "bitbrowser"
    register_provider(provider)

    env = Environment(
        id=202,
        name="bit-env",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
    )
    mock_pool.get = AsyncMock(return_value=env)

    with patch.object(
        manager,
        "ensure_provider_runtime",
        AsyncMock(side_effect=EnvUnavailableError("BitBrowser 安装路径未配置")),
    ):
        with pytest.raises(EnvUnavailableError, match="安装路径未配置"):
            await manager.start_env(env.id)

    assert not provider.open_called
    assert not provider.connect_called


@pytest.mark.asyncio
async def test_start_env_keeps_busy_when_window_is_open_but_connect_fails(manager, mock_pool):
    provider = MockProvider()
    provider.name = "virtualbrowser"
    register_provider(provider)

    env = Environment(
        id=303,
        name="vb-opened-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
    )
    mock_pool.get = AsyncMock(return_value=env)
    provider.connect = AsyncMock(return_value=False)  # type: ignore[method-assign]
    provider.is_window_open = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with patch.object(manager, "ensure_provider_runtime", AsyncMock()):
        success = await manager.start_env(env.id)

    assert success is False
    mock_pool.update_status.assert_any_await(env.id, EnvStatus.BUSY)
    provider.is_window_open.assert_awaited_once_with(env)

    error_event = MagicMock()
    with patch.object(manager, "_emit_error", error_event):
        await manager._handle_connect_failure(env, provider, EnvStatus.READY, "Playwright 连接失败")
    error_event.assert_called_once_with(env, "connect", "Playwright 连接失败，但浏览器窗口已打开")
