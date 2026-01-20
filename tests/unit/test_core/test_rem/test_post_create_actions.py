from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, PostCreateAction
from src.core.rem.provider import BaseProvider, register_provider


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
    
    # Mock workflow module
    with patch("importlib.import_module") as mock_import:
        mock_mod = MagicMock()
        mock_mod.run = AsyncMock()
        mock_import.return_value = mock_mod
        
        env = await manager._create_env(
            provider=provider,
            post_action=PostCreateAction.WORKFLOW,
            workflow_module="test_workflow"
        )
        
        assert env.status == EnvStatus.READY
        assert provider.create_called
        assert provider.open_called
        assert provider.connect_called
        
        # Verify workflow executed
        # Note: importlib argument is f"modules.{workflow_module}"
        mock_import.assert_called() 
        args, _ = mock_import.call_args
        assert args[0] == "modules.test_workflow"
        
        mock_mod.run.assert_called_with(env)
        
        # Verify closed
        assert provider.close_called
