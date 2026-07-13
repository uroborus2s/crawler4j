from unittest.mock import AsyncMock, patch

import pytest

from src.core.persistence.database import STATE_DB, get_connection, init_database
from src.core.rem.ip_pool import IPEntry
from src.core.rem.ip_pool import IPPool
from src.core.rem.ip_pool import IPPoolManager
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
        self.last_update = config
        return True

    async def clear_cache(self, env: Environment) -> bool:
        self.last_cache_env = env
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
        assert env.proxy_config.ip_entry_id == "ip_1"


@pytest.mark.asyncio
async def test_update_env_with_selected_pool_ip_updates_provider_and_binding(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    provider = MockProvider()
    register_provider(provider)

    ip_manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池")
    ip_manager.add_pool(pool)
    old = IPEntry(
        id="ip-old",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        bound_count=1,
    )
    new = IPEntry(
        id="ip-new",
        pool_id=pool.id,
        address="2.2.2.2",
        protocol="socks5",
        port=1080,
        username="user",
        password="pass",
    )
    pool.add_entry(old)
    pool.add_entry(new)
    ip_manager._persist_entry(old)
    ip_manager._persist_entry(new)

    env = Environment(
        id=7,
        name="env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="remote-7",
        proxy_config=ProxyConfig(
            mode=ProxyMode.POOL,
            pool_id=pool.id,
            current_ip=old.address,
            ip_entry_id=old.id,
            static_value=old.to_proxy_string(),
        ),
    )
    manager = EnvironmentManager()
    manager.pool = mock_pool = AsyncMock()
    mock_pool.get = AsyncMock(return_value=env)
    mock_pool.add = AsyncMock()

    monkeypatch.setattr("src.core.rem.manager.get_ip_pool_manager", lambda: ip_manager)

    assert await manager.update_env(env.id, proxy_entry_id=new.id) is True

    expected_proxy = "socks5://user:pass@2.2.2.2:1080"
    assert provider.last_update["proxy"]["static_value"] == expected_proxy
    assert env.proxy_config.current_ip == "2.2.2.2"
    assert env.proxy_config.static_value == expected_proxy
    assert env.proxy_config.ip_entry_id == new.id
    assert old.bound_count == 0
    assert new.bound_count == 1
    mock_pool.add.assert_awaited_once_with(env)
    with get_connection(STATE_DB) as conn:
        counts = {
            row["id"]: row["bound_count"]
            for row in conn.execute("SELECT id, bound_count FROM ip_entries").fetchall()
        }
    assert counts == {"ip-old": 0, "ip-new": 1}


@pytest.mark.asyncio
async def test_clear_env_cache_delegates_to_environment_provider():
    provider = MockProvider()
    register_provider(provider)
    env = Environment(
        id=185,
        name="env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="903",
    )
    manager = EnvironmentManager()
    manager.pool = AsyncMock()
    manager.pool.get = AsyncMock(return_value=env)

    assert await manager.clear_env_cache(env.id) is True
    assert provider.last_cache_env is env
