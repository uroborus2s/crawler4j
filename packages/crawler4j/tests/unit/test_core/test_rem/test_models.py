"""REM 数据模型单元测试。"""

import time

from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    ProviderEnvInfo,
    ProxyConfig,
    ProxyMode,
    EnvStatus,
)


class TestEnvironment:
    """测试 Environment 数据模型。"""
    
    def test_default_values(self):
        """测试默认值。"""
        env = Environment()
        
        assert env.id is not None
        assert env.kind == EnvKind.BROWSER
        assert env.status == EnvStatus.CREATING
        assert env.capabilities == set()
    
    def test_to_dict(self):
        """测试序列化。"""
        env = Environment(
            kind=EnvKind.HTTP,
            provider="test_provider",
            capabilities={"request", "response"},
        )
        
        data = env.to_dict()
        
        assert data["kind"] == "http"
        assert data["provider"] == "test_provider"
        assert set(data["capabilities"]) == {"request", "response"}
    
    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "id": "test-id",
            "kind": "browser",
            "provider": "playwright",
            "status": "ready",
            "capabilities": ["page", "cookies"],
            "created_at": 1234567890,
            "updated_at": 1234567890,
        }
        
        env = Environment.from_dict(data)
        
        assert env.id == "test-id"
        assert env.kind == EnvKind.BROWSER
        assert env.status == EnvStatus.READY
        assert env.capabilities == {"page", "cookies"}

    def test_provider_metadata_roundtrip(self):
        """测试来源环境字段保留。"""
        env = Environment(
            id=9,
            name="imported-env",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="321",
            provider_env_id="321",
            provider_env_name="源环境",
            provider_group="默认分组",
            provider_proxy={"host": "127.0.0.1", "port": "1080"},
            provider_raw_meta={"remark": "demo"},
            imported_at=1234567890,
        )

        restored = Environment.from_dict(env.to_dict())

        assert restored.provider_env_id == "321"
        assert restored.provider_env_name == "源环境"
        assert restored.provider_group == "默认分组"
        assert restored.provider_proxy == {"host": "127.0.0.1", "port": "1080"}
        assert restored.provider_raw_meta == {"remark": "demo"}
        assert restored.imported_at == 1234567890


class TestProxyConfig:
    """测试 ProxyConfig。"""

    def test_to_dict_and_from_dict_preserve_bind_strategy(self):
        proxy = ProxyConfig(
            mode=ProxyMode.POOL,
            pool_id="pool-1",
            bind_strategy="least_bound",
            static_value="socks5://1.2.3.4:1080",
            current_ip="1.2.3.4",
        )

        data = proxy.to_dict()
        restored = ProxyConfig.from_dict(data)

        assert data["bind_strategy"] == "least_bound"
        assert restored.bind_strategy == "least_bound"
        assert restored.pool_id == "pool-1"


class TestEnvLease:
    """测试 EnvLease 数据模型。"""
    
    def test_default_values(self):
        """测试默认值。"""
        lease = EnvLease(env_id="env-1", task_run_id="task-1")
        
        assert lease.id is not None
        assert lease.token is not None
        assert lease.expires_at is None
    
    def test_is_expired_no_expiry(self):
        """测试无过期时间。"""
        lease = EnvLease()
        
        assert lease.is_expired() is False
    
    def test_is_expired_future(self):
        """测试未过期。"""
        lease = EnvLease(expires_at=int(time.time()) + 3600)
        
        assert lease.is_expired() is False
    
    def test_is_expired_past(self):
        """测试已过期。"""
        lease = EnvLease(expires_at=int(time.time()) - 100)
        
        assert lease.is_expired() is True


class TestEnvRequirement:
    """测试 EnvRequirement。"""
    
    def test_matches_kind(self):
        """测试类型匹配。"""
        req = EnvRequirement(kind=EnvKind.BROWSER)
        env = Environment(kind=EnvKind.BROWSER, status=EnvStatus.READY)
        
        assert req.matches(env) is True
    
    def test_matches_kind_mismatch(self):
        """测试类型不匹配。"""
        req = EnvRequirement(kind=EnvKind.HTTP)
        env = Environment(kind=EnvKind.BROWSER, status=EnvStatus.READY)
        
        assert req.matches(env) is False
    
    def test_matches_capabilities(self):
        """测试能力匹配。"""
        req = EnvRequirement(
            kind=EnvKind.BROWSER,
            capabilities={"page", "cookies"},
        )
        env = Environment(
            kind=EnvKind.BROWSER,
            capabilities={"page", "cookies", "screenshot"},
        )
        
        assert req.matches(env) is True
    
    def test_matches_capabilities_missing(self):
        """测试能力不足。"""
        req = EnvRequirement(
            kind=EnvKind.BROWSER,
            capabilities={"page", "cookies", "network"},
        )
        env = Environment(
            kind=EnvKind.BROWSER,
            capabilities={"page", "cookies"},
        )
        
        assert req.matches(env) is False

    def test_matches_provider(self):
        """测试 provider 匹配。"""
        req = EnvRequirement(kind=EnvKind.BROWSER, provider="virtualbrowser")
        env = Environment(kind=EnvKind.BROWSER, provider="virtualbrowser", status=EnvStatus.READY)

        assert req.matches(env) is True

    def test_matches_provider_mismatch(self):
        """测试 provider 不匹配。"""
        req = EnvRequirement(kind=EnvKind.BROWSER, provider="virtualbrowser")
        env = Environment(kind=EnvKind.BROWSER, provider="bitbrowser", status=EnvStatus.READY)

        assert req.matches(env) is False


class TestProviderEnvInfo:
    """测试来源环境信息。"""

    def test_proxy_summary_prefers_explicit_text(self):
        info = ProviderEnvInfo(
            provider="virtualbrowser",
            provider_label="Virtual Browser",
            provider_env_id="101",
            provider_env_name="env-101",
            proxy_summary="SOCKS5 127.0.0.1:1080",
        )

        assert info.proxy_summary_text == "SOCKS5 127.0.0.1:1080"

    def test_proxy_summary_falls_back_to_proxy_fields(self):
        info = ProviderEnvInfo(
            provider="virtualbrowser",
            provider_label="Virtual Browser",
            provider_env_id="102",
            provider_env_name="env-102",
            provider_proxy={"protocol": "HTTP", "host": "10.0.0.1", "port": "8080"},
        )

        assert info.proxy_summary_text == "HTTP 10.0.0.1:8080"
