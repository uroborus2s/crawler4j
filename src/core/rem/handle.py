"""浏览器句柄 - 封装 Playwright 对象与安全操作。

BrowserHandle 是 Core 层内部使用的抽象，用于：
1. 统一管理 Playwright 连接生命周期
2. 提供安全的连接/关闭方法
3. 暴露 page/context 属性供 SDK 层使用

注意：SDK/Module 层通过 TaskContext.page 获取原生 Page 对象，
不直接操作 BrowserHandle。
"""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from src.core.foundation.logging import logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright


class PlaywrightManager:
    """全局 Playwright 单例管理器（引用计数）。
    
    设计原理：
    - Playwright 驱动进程可以同时管理多个浏览器连接
    - 指纹浏览器已经在外部运行，Playwright 只是通过 CDP 连接
    - 共享单例避免每个环境启动独立的 Node 进程
    
    Usage:
        # 获取实例（引用计数 +1）
        playwright = await PlaywrightManager.acquire()
        browser = await playwright.chromium.connect_over_cdp(ws_url)
        
        # 释放引用（计数 -1，归零时关闭）
        await PlaywrightManager.release()
    """
    
    _instance: ClassVar["Playwright | None"] = None
    _ref_count: ClassVar[int] = 0
    _lock: ClassVar[asyncio.Lock | None] = None
    
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """延迟创建锁（避免在模块加载时创建）。"""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock
    
    @classmethod
    async def acquire(cls) -> "Playwright":
        """获取 Playwright 实例（引用计数 +1）。
        
        如果现有实例已崩溃，会自动重建。
        
        Returns:
            Playwright 实例
            
        Raises:
            RuntimeError: 启动 Playwright 失败
        """
        from playwright.async_api import async_playwright
        
        async with cls._get_lock():
            # 检查现有实例是否健康
            if cls._instance is not None:
                if not cls._is_instance_healthy():
                    logger.warning("[PlaywrightManager] 检测到 Playwright 实例已崩溃，正在重建...")
                    cls._instance = None
                    # 注意：崩溃时不重置引用计数，因为现有连接可能仍需要重连
            
            # 创建新实例（首次或崩溃后重建）
            if cls._instance is None:
                logger.info("[PlaywrightManager] 启动 Playwright 驱动进程...")
                cls._instance = await async_playwright().start()
                logger.info("[PlaywrightManager] Playwright 驱动进程已启动")
            
            cls._ref_count += 1
            logger.debug(f"[PlaywrightManager] 引用计数: {cls._ref_count}")
            return cls._instance
    
    @classmethod
    def _is_instance_healthy(cls) -> bool:
        """检查 Playwright 实例是否健康。
        
        通过访问内部属性来判断进程是否存活。
        """
        if cls._instance is None:
            return False
        try:
            # 尝试访问 chromium 属性，如果进程已死会抛异常
            _ = cls._instance.chromium
            return True
        except Exception:
            return False
    
    @classmethod
    async def release(cls) -> None:
        """释放引用（计数 -1，归零时关闭）。"""
        async with cls._get_lock():
            if cls._ref_count > 0:
                cls._ref_count -= 1
                logger.debug(f"[PlaywrightManager] 引用计数: {cls._ref_count}")
            
            if cls._ref_count <= 0 and cls._instance is not None:
                logger.info("[PlaywrightManager] 关闭 Playwright 驱动进程...")
                try:
                    await cls._instance.stop()
                except Exception as e:
                    logger.warning(f"[PlaywrightManager] 关闭时出错: {e}")
                finally:
                    cls._instance = None
                    cls._ref_count = 0
                logger.info("[PlaywrightManager] Playwright 驱动进程已关闭")
    
    @classmethod
    async def force_shutdown(cls) -> None:
        """强制关闭（应用退出时调用）。"""
        async with cls._get_lock():
            if cls._instance is not None:
                logger.info("[PlaywrightManager] 强制关闭 Playwright...")
                try:
                    await cls._instance.stop()
                except Exception:
                    pass
                finally:
                    cls._instance = None
                    cls._ref_count = 0


@dataclass
class BrowserHandle:
    """浏览器句柄 - 仅 Core 层内部使用。
    
    Attributes:
        browser_id: 外部浏览器 ID (BitBrowser/VirtualBrowser)
        ws_url: WebSocket 连接地址
    """
    
    browser_id: str = ""
    ws_url: str = ""
    
    # 运行时对象（不序列化）
    _browser: "Browser | None" = field(default=None, repr=False)
    _context: "BrowserContext | None" = field(default=None, repr=False)
    _page: "Page | None" = field(default=None, repr=False)
    _has_playwright_ref: bool = field(default=False, repr=False)  # 是否持有 Playwright 引用
    
    @property
    def page(self) -> "Page | None":
        """获取 Page 对象（供 SDK/Module 层使用）。"""
        return self._page
    
    @property
    def context(self) -> "BrowserContext | None":
        """获取 BrowserContext 对象。"""
        return self._context
    
    @property
    def browser(self) -> "Browser | None":
        """获取 Browser 对象。"""
        return self._browser
    
    def is_connected(self) -> bool:
        """安全检查连接状态。"""
        if not self._browser:
            return False
        try:
            return self._browser.is_connected()
        except Exception:
            return False
    
    async def safe_connect(self) -> bool:
        """安全连接到浏览器（使用共享 Playwright 单例）。
        
        Returns:
            是否连接成功
        """
        try:
            # 获取共享的 Playwright 实例
            playwright = await PlaywrightManager.acquire()
            self._has_playwright_ref = True
            
            # 连接到外部浏览器
            self._browser = await playwright.chromium.connect_over_cdp(self.ws_url,timeout=300000)
            
            # 获取或创建 context 和 page
            self._context = (
                self._browser.contexts[0] 
                if self._browser.contexts 
                else await self._browser.new_context()
            )
            self._page = (
                self._context.pages[0] 
                if self._context.pages 
                else await self._context.new_page()
            )
            
            logger.info(f"[BrowserHandle] Connected to {self.ws_url[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"[BrowserHandle] Failed to connect: {e}")
            await self.safe_close()
            return False
    
    async def safe_close(self) -> None:
        """安全关闭连接（忽略异常）。
        
        注意：此方法保证幂等，多次调用不会有副作用。
        即使底层连接已断开，也会正确清理资源。
        """
        browser_id = self.browser_id  # 保存用于日志
        
        # 1. 关闭浏览器连接
        if self._browser:
            try:
                # 检查连接状态（注意：is_connected 本身也可能抛异常）
                if self._browser.is_connected():
                    await asyncio.wait_for(self._browser.close(), timeout=2.0)
                    logger.info(f"[BrowserHandle] Browser 连接已关闭: {browser_id}")
                else:
                    logger.info(f"[BrowserHandle] Browser 连接已断开，跳过关闭: {browser_id}")
            except asyncio.TimeoutError:
                logger.warning(f"[BrowserHandle] 关闭 browser 超时: {browser_id}")
            except Exception as e:
                # 捕获所有异常，包括 "'NoneType' object has no attribute 'send'"
                logger.warning(f"[BrowserHandle] 关闭 browser 失败 (已忽略): {e}")
            finally:
                # 无论如何都置空资源（避免后续重复操作）
                self._page = None
                self._context = None
                self._browser = None
        
        # 2. 释放 Playwright 引用
        if self._has_playwright_ref:
            await PlaywrightManager.release()
            self._has_playwright_ref = False
            logger.debug(f"[BrowserHandle] Playwright 引用已释放: {browser_id}")
    
    async def execute_script(self, script: str, **kwargs: Any) -> Any:
        """在 Page 上安全执行 JavaScript 脚本。
        
        Args:
            script: JavaScript 代码
            **kwargs: 传递给 evaluate 的参数
            
        Returns:
            脚本执行结果
            
        Raises:
            RuntimeError: 当 Page 未连接时
        """
        if not self._page:
            raise RuntimeError("Page 未连接，无法执行脚本")
        return await self._page.evaluate(script, **kwargs)
    

    def to_dict(self) -> dict[str, str]:
        """序列化为字典（仅持久化字段）。"""
        return {
            "browser_id": self.browser_id,
            "ws_url": self.ws_url,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BrowserHandle":
        """从字典反序列化。"""
        return cls(
            browser_id=data.get("browser_id", ""),
            ws_url=data.get("ws_url", ""),
        )
