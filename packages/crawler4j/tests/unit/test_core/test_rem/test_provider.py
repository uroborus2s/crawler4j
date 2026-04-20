"""Provider 注册测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from src.core.rem.handle import BrowserHandle
from src.core.rem.models import Environment, EnvKind, EnvStatus
from src.core.rem.provider import (
    VirtualBrowserProvider,
    get_provider,
    list_providers,
)


class TestProviderRegistry:
    """测试 Provider 自动注册。"""
    
    def test_providers_registered(self):
        """测试所有内置 Provider 自动注册。"""
        registered = list_providers()
        
        assert "playwright_local" in registered
        assert "bitbrowser" in registered
        assert "virtualbrowser" in registered
    
    def test_get_playwright_provider(self):
        """测试获取 Playwright Provider。"""
        provider = get_provider("playwright_local")
        
        assert provider is not None
        assert provider.name == "playwright_local"
    
    def test_get_bitbrowser_provider(self):
        """测试获取 BitBrowser Provider。"""
        provider = get_provider("bitbrowser")
        
        assert provider is not None
        assert provider.name == "bitbrowser"
    
    def test_get_virtualbrowser_provider(self):
        """测试获取 VirtualBrowser Provider。"""
        provider = get_provider("virtualbrowser")
        
        assert provider is not None
        assert provider.name == "virtualbrowser"
    
    def test_get_unknown_provider(self):
        """测试获取未注册的 Provider。"""
        provider = get_provider("unknown_provider")
        
        assert provider is None


@pytest.mark.asyncio
async def test_virtualbrowser_open_surfaces_launch_error(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    client = SimpleNamespace(
        launch_browser=AsyncMock(side_effect=RuntimeError("Launch Error: DevTools port not detected"))
    )

    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    with pytest.raises(
        RuntimeError,
        match="VirtualBrowser launchBrowser 失败: Launch Error: DevTools port not detected",
    ):
        await provider.open(env)


@pytest.mark.asyncio
async def test_virtualbrowser_connect_recovers_missing_ws_url_from_browser_detail(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="101"),
    )
    handle = env.handle
    assert handle is not None

    client = SimpleNamespace(
        get_browser_runtime_detail=AsyncMock(return_value={"debuggingPort": 56764}),
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(handle, "safe_connect", AsyncMock(return_value=True))

    success = await provider.connect(env)

    assert success is True
    assert handle.ws_url == "http://localhost:56764"
    handle.safe_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_virtualbrowser_connect_retries_runtime_detail_before_missing_ws_url(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=102,
        name="vb-env-retry",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="102"),
    )
    handle = env.handle
    assert handle is not None

    client = SimpleNamespace(
        get_browser_runtime_detail=AsyncMock(
            side_effect=[
                None,
                None,
                {"id": 102, "debuggingPort": 57204},
            ]
        )
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(handle, "safe_connect", AsyncMock(return_value=True))

    with patch("src.core.rem.provider.asyncio.sleep", AsyncMock()):
        success = await provider.connect(env)

    assert success is True
    assert handle.ws_url == "http://localhost:57204"
    assert client.get_browser_runtime_detail.await_count == 3
    handle.safe_connect.assert_awaited_once()
