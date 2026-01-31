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
from typing import TYPE_CHECKING, Any

from src.core.foundation.logging import logger

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright


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
    _playwright: "Playwright | None" = field(default=None, repr=False)
    _browser: "Browser | None" = field(default=None, repr=False)
    _context: "BrowserContext | None" = field(default=None, repr=False)
    _page: "Page | None" = field(default=None, repr=False)
    
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
        """安全连接到浏览器。
        
        Args:
            ws_url: WebSocket 连接地址
            
        Returns:
            是否连接成功
        """
        from playwright.async_api import async_playwright
        
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self.ws_url)
            
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
            try:
                # 测试执行简单指令
                page= await self._context.new_page()
                await page.goto("https://www.baidu.com")
                await page.close()
            except Exception as e:
                logger.error(f"关闭页面超时或失败，可能是连接已断开，直接丢弃引用：${e}")
            
            logger.info(f"[BrowserHandle] Connected to {self.ws_url}...")
            return True
            
        except Exception as e:
            logger.error(f"[BrowserHandle] Failed to connect: {e}")
            await self.safe_close()
            return False
    
    async def safe_close(self) -> None:
        """安全关闭连接（忽略异常）。"""
        if self._browser:
            if not self._browser.is_connected() :
                logger.info("浏览器已断开，停止操作")
                return
            try:
                if self._context:
                    await self._context.close()
                await asyncio.wait_for(self._browser.close(), timeout=2.0)
            except Exception as e:
                logger.error(f"关闭context失败，可能是连接已断开，直接丢弃引用：${e}")
            try:
                if self._browser:
                    await self._browser.close()
            except Exception as e:
                logger.error(f"关闭brower失败，可能是连接已断开，直接丢弃引用：${e}")
            finally:
                self._context = None
                self._browser = None
        
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            finally:
                self._playwright = None
        logger.info(f"[BrowserHandle] Closed connection for {self.browser_id}")
    
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
