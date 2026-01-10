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
