"""环境提供者抽象层。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Provider 层面向具体技术栈，负责实际 spawn/keepalive/kill/healthcheck。
"""

from abc import ABC, abstractmethod
from typing import Any

from src.core.rem.models import Environment, EnvKind


class BaseProvider(ABC):
    """环境提供者抽象基类。
    
    规格 5.2.3.1: 负责实际 spawn/keepalive/kill/healthcheck
    
    子类实现特定技术栈的环境管理，如：
        - PlaywrightProvider: Playwright 浏览器
        - HttpProvider: HTTP 客户端
        - FingerprintBrowserProvider: 指纹浏览器
    """
    
    # 提供者标识
    name: str = ""
    
    # 支持的环境类型
    kind: EnvKind = EnvKind.BROWSER
    
    @abstractmethod
    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建环境实例。
        
        Args:
            config: 创建配置参数
        
        Returns:
            创建的环境实例（状态为 CREATING -> READY）
        
        Raises:
            EnvError: 创建失败
        """
        pass
    
    @abstractmethod
    async def reset(self, env: Environment) -> bool:
        """重置环境状态。
        
        在任务结束后清理环境，使其可以被复用。
        如：关闭页面、清除 Cookies、删除临时文件。
        
        Args:
            env: 环境实例
        
        Returns:
            是否重置成功
        """
        pass
    
    @abstractmethod
    async def health_check(self, env: Environment) -> bool:
        """健康检查。
        
        检测环境是否可用，不可用时应标记隔离。
        
        Args:
            env: 环境实例
        
        Returns:
            是否健康
        """
        pass
    
    @abstractmethod
    async def destroy(self, env: Environment) -> None:
        """销毁环境。
        
        释放物理资源（如 kill 进程）。
        
        Args:
            env: 环境实例
        """
        pass


class PlaywrightProvider(BaseProvider):
    """Playwright 浏览器环境提供者。
    
    提供基于 Playwright 的本地浏览器环境。
    """
    
    name = "playwright_local"
    kind = EnvKind.BROWSER
    
    def __init__(self):
        self._playwright = None
        self._browser = None
    
    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 Playwright 浏览器环境。"""
        from playwright.async_api import async_playwright

        from src.core.rem.models import Environment, EnvStatus
        
        config = config or {}
        headless = config.get("headless", True)
        browser_type = config.get("browser_type", "chromium")
        
        # 启动 Playwright
        self._playwright = await async_playwright().start()
        
        # 启动浏览器
        browser_launcher = getattr(self._playwright, browser_type)
        self._browser = await browser_launcher.launch(headless=headless)
        
        # 创建上下文
        context = await self._browser.new_context()
        page = await context.new_page()
        
        # 创建环境实例
        env = Environment(
            kind=EnvKind.BROWSER,
            provider=self.name,
            status=EnvStatus.READY,
            labels={
                "browser": browser_type,
                "headless": str(headless).lower(),
            },
            capabilities={"page", "cookies", "screenshot", "navigation"},
            handle={
                "playwright": self._playwright,
                "browser": self._browser,
                "context": context,
                "page": page,
            },
        )
        
        return env
    
    async def reset(self, env: Environment) -> bool:
        """重置浏览器环境。"""
        try:
            handle = env.handle
            if not handle:
                return False
            
            context = handle.get("context")
            if context:
                # 清除 Cookies
                await context.clear_cookies()
                
                # 关闭所有页面，只保留一个
                pages = context.pages
                for page in pages[1:]:
                    await page.close()
                
                # 导航到空白页
                if pages:
                    await pages[0].goto("about:blank")
            
            return True
        except Exception:
            return False
    
    async def health_check(self, env: Environment) -> bool:
        """检查浏览器是否可用。"""
        try:
            handle = env.handle
            if not handle:
                return False
            
            page = handle.get("page")
            if not page:
                return False
            
            # 尝试执行简单操作
            await page.evaluate("() => true")
            return True
        except Exception:
            return False
    
    async def destroy(self, env: Environment) -> None:
        """销毁浏览器环境。"""
        try:
            handle = env.handle
            if handle:
                browser = handle.get("browser")
                if browser:
                    await browser.close()
                
                playwright = handle.get("playwright")
                if playwright:
                    await playwright.stop()
        except Exception:
            pass  # 即使失败也要继续


# Provider 注册表
_providers: dict[str, BaseProvider] = {}


def register_provider(provider: BaseProvider) -> None:
    """注册环境提供者。"""
    _providers[provider.name] = provider


def get_provider(name: str) -> BaseProvider | None:
    """获取已注册的环境提供者。"""
    return _providers.get(name)


def list_providers() -> list[str]:
    """列出所有已注册的提供者。"""
    return list(_providers.keys())


class BitBrowserProvider(BaseProvider):
    """BitBrowser 指纹浏览器提供者。"""

    name = "bitbrowser"
    kind = EnvKind.BROWSER

    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 BitBrowser 环境。"""
        from playwright.async_api import async_playwright

        from src.core.foundation.logging import logger
        from src.core.rem.models import Environment, EnvStatus
        from src.core.system.preferences_service import PreferenceKey, get_preferences_service

        #读取配置
        prefs = get_preferences_service()
        port = prefs.get(PreferenceKey.BITBROWSER_PORT, 54345)
        path = prefs.get(PreferenceKey.BITBROWSER_PATH, "")

        logger.info(f"Connecting to BitBrowser at port {port} (Path: {path})")

        # 启动 Playwright
        playwright = await async_playwright().start()

        try:
            # 连接到已打开的浏览器 (CDP)
            # 真实场景可能需要先通过 API 启动浏览器窗口获取调试端口
            # 这里简化为直接连接配置的端口
            browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            
            # 获取默认上下文
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            return Environment(
                kind=EnvKind.BROWSER,
                provider=self.name,
                status=EnvStatus.READY,
                labels={"browser": "bitbrowser", "port": str(port)},
                capabilities={"page", "cookies", "fingerprint"},
                handle={
                    "playwright": playwright,
                    "browser": browser,
                    "context": context,
                    "page": page,
                },
            )
        except Exception as e:
            await playwright.stop()
            raise RuntimeError(f"Failed to connect to BitBrowser: {e}")

    async def reset(self, env: Environment) -> bool:
        # BitBrowser 通常不需要重置，或者通过 API 重置
        return True

    async def health_check(self, env: Environment) -> bool:
        return True

    async def destroy(self, env: Environment) -> None:
        # 释放连接但不关闭浏览器进程
        handle = env.handle
        if handle:
            if handle.get("browser"):
                await handle["browser"].close()
            if handle.get("playwright"):
                await handle["playwright"].stop()


class VirtualBrowserProvider(BaseProvider):
    """VirtualBrowser 指纹浏览器提供者。"""

    name = "virtualbrowser"
    kind = EnvKind.BROWSER

    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 VirtualBrowser 环境。"""
        from playwright.async_api import async_playwright

        from src.core.foundation.logging import logger
        from src.core.rem.models import Environment, EnvStatus
        from src.core.system.preferences_service import PreferenceKey, get_preferences_service

        # 读取配置
        prefs = get_preferences_service()
        port = prefs.get(PreferenceKey.VIRTUALBROWSER_PORT, 9022)
        path = prefs.get(PreferenceKey.VIRTUALBROWSER_PATH, "")
        api_key = prefs.get(PreferenceKey.VIRTUALBROWSER_API_KEY, "")

        logger.info(f"Connecting to VirtualBrowser at port {port} (Path: {path}, API Key present: {bool(api_key)})")

        playwright = await async_playwright().start()

        try:
            browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            return Environment(
                kind=EnvKind.BROWSER,
                provider=self.name,
                status=EnvStatus.READY,
                labels={"browser": "virtualbrowser", "port": str(port)},
                capabilities={"page", "cookies", "fingerprint"},
                handle={
                    "playwright": playwright,
                    "browser": browser,
                    "context": context,
                    "page": page,
                },
            )
        except Exception as e:
            await playwright.stop()
            raise RuntimeError(f"Failed to connect to VirtualBrowser: {e}")

    async def reset(self, env: Environment) -> bool:
        return True

    async def health_check(self, env: Environment) -> bool:
        return True

    async def destroy(self, env: Environment) -> None:
        handle = env.handle
        if handle:
            if handle.get("browser"):
                await handle["browser"].close()
            if handle.get("playwright"):
                await handle["playwright"].stop()

# 注册默认提供者
register_provider(PlaywrightProvider())
register_provider(BitBrowserProvider())
register_provider(VirtualBrowserProvider())

