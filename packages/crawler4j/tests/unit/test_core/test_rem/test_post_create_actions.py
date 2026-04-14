from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, EnvUnavailableError, PostCreateAction
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
            external_id="mock_ext_id"
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
    pool.add = AsyncMock()
    pool.update_status = AsyncMock()
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
async def test_create_env_none_action(manager):
    provider = MockProvider()
    register_provider(provider)
    
    env = await manager._create_env(
        provider=provider,
        post_action=PostCreateAction.NONE
    )
    
    assert env.status == EnvStatus.READY
    assert provider.create_called
    # open/connect/close NOT called
    assert not provider.open_called
    assert not provider.connect_called
    assert not provider.close_called

@pytest.mark.asyncio
async def test_create_env_test_action(manager):
    provider = MockProvider()
    register_provider(provider)
    
    env = await manager._create_env(
        provider=provider,
        post_action=PostCreateAction.TEST
    )
    
    assert env.status == EnvStatus.READY
    assert provider.create_called
    # open -> connect -> close
    assert provider.open_called
    assert provider.connect_called
    assert provider.close_called

@pytest.mark.asyncio
async def test_create_env_workflow_action(manager):
    provider = MockProvider()
    register_provider(provider)

    fake_caps = SimpleNamespace(
        tools=object(),
    )
    module_service = SimpleNamespace(
        call_hook=AsyncMock(return_value=None),
        run_module=AsyncMock(return_value={"ok": True}),
    )

    with patch("src.core.rem.manager.build_runtime_capabilities", return_value=fake_caps), patch(
        "src.core.rem.manager.get_module_service",
        return_value=module_service,
    ):
        env = await manager._create_env(
            provider=provider,
            post_action=PostCreateAction.WORKFLOW,
            workflow_module="demo_module.workflows.bootstrap_workflow",
        )

    assert env.status == EnvStatus.READY
    assert provider.create_called
    assert provider.open_called
    assert provider.connect_called

    hook_calls = module_service.call_hook.await_args_list
    assert [call.args[1] for call in hook_calls] == [
        "init_env",
        "before_run",
        "on_success",
        "on_cleanup",
    ]
    assert module_service.run_module.await_count == 1
    assert module_service.run_module.await_args.args[0] == "demo_module"

    ctx = module_service.run_module.await_args.args[1]
    assert ctx.env_id == env.id
    assert ctx.task_name == "demo_module"
    assert ctx.config["workflow"] == "bootstrap_workflow"
    assert ctx.tools is fake_caps.tools

    # Verify closed
    assert provider.close_called


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

    app_service.ensure_running.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER)
    app_service.wait_until_ready.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER, timeout=30)


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

    app_service.ensure_running.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER)
    app_service.wait_until_ready.assert_not_awaited()
