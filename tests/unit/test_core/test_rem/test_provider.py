"""Provider 注册测试。"""

from src.core.rem.provider import (
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
