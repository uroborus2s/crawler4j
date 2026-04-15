from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.ip_pool import IPEntry
from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProxyConfig, ProxyMode
from src.core.rem.provider import BaseProvider, register_provider


class MockProvider(BaseProvider):
    name = "mock_provider"
    kind = EnvKind.BROWSER
    
    async def is_running(self, env: Environment) -> bool:
        return True
        
    async def is_window_open(self, env: Environment) -> bool:
        return True
        
    async def get_window_title(self, env: Environment) -> str:
        return "Mock Window"
        
    async def exists(self, env: Environment) -> bool:
        return True
        
    async def connect(self, env: Environment) -> bool:
        return True

    async def create(self, config: dict | None = None) -> Environment:
        # 验证 config 中是否包含了预期的代理配置
        self.last_config = config or {}
        env = Environment(
            id=self.last_config.get("env_id", 0),
            name=self.last_config.get("env_name", ""),
            kind=self.kind,
            provider=self.name,
            status=EnvStatus.READY
        )
        if self.last_config.get("proxy"):
            env.proxy_config = ProxyConfig.from_dict(self.last_config["proxy"])
        return env
        
    async def close(self, env: Environment) -> None:
        pass

    async def disconnect(self, env: Environment) -> bool:
        return True
        
    async def reset(self, env: Environment) -> bool:
        return True
        
    async def open(self, env: Environment) -> bool:
        return True
        
    async def health_check(self, env: Environment) -> bool:
        return True
        
    async def destroy(self, env: Environment) -> None:
        pass
        
    async def update(self, env: Environment, config: dict) -> bool:
        return True

@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.add = AsyncMock()
    pool.update_status = AsyncMock()
    pool.remove = AsyncMock()
    return pool

@pytest.fixture
def mock_ip_manager():
    manager = AsyncMock()
    manager.bind_ip = AsyncMock()
    return manager

@pytest.mark.asyncio
async def test_create_env_with_pool_proxy(mock_pool, mock_ip_manager):
    # Setup
    provider = MockProvider()
    manager = EnvironmentManager()
    manager.pool = mock_pool
    
    # Mock IP Pool behavior
    mock_ip = IPEntry(
        id="ip_1",
        address="1.2.3.4",
        port=8080,
        protocol="socks5",
        username="user",
        password="pass"
    )
    mock_ip_manager.bind_ip.return_value = mock_ip
    
    # Mock get_ip_pool_manager to return our mock
    with patch("src.core.rem.ip_pool.get_ip_pool_manager", return_value=mock_ip_manager):
        # Prepare Proxy Config
        proxy_config = ProxyConfig(
            mode=ProxyMode.POOL,
            pool_id="test_pool",
            bind_strategy="least_bound",
        )
        
        # Execute
        provider = MockProvider()
        register_provider(provider)
        env = await manager._create_env(provider, proxy_config=proxy_config)
        
        # Verify
        # 1. IP Manager called
        mock_ip_manager.bind_ip.assert_called_once_with(env.id, "test_pool", "least_bound")
        
        # 2. Provider config received correct proxy
        provider_config = provider.last_config
        assert "proxy" in provider_config
        assert provider_config["proxy"]["mode"] == "pool"
        # 验证 static_value 是否生成正确
        expected_url = "socks5://user:pass@1.2.3.4:8080"
        assert provider_config["proxy"]["static_value"] == expected_url
        
        # 3. Environment object updated
        assert env.proxy_config.current_ip == "1.2.3.4"
        assert env.proxy_config.static_value == expected_url
