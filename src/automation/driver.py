"""Automation driver module.

Provides Playwright-based browser automation using CDP connection.
"""

from typing import AsyncGenerator
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.core.browser_api import BrowserAPI
from src.utils.logger import logger


class AutomationDriver:
    """Manages Playwright automation for a browser environment.

    Usage:
        async with AutomationDriver.connect(profile_id) as page:
            await page.goto("https://www.ctrip.com")
    """

    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.playwright = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Page, None]:
        """Context manager for a browser automation session.

        Opens the fingerprint browser, connects Playwright via CDP,
        provides a page, and ensures cleanup.
        """
        try:
            # 1. Open the fingerprint browser via local API
            logger.info(f"正在打开浏览器环境: {self.profile_id}")
            conn_info = BrowserAPI.open_browser(self.profile_id)
            ws_endpoint = conn_info["ws_endpoint"]

            # 2. Start Playwright and connect via CDP
            async with async_playwright() as p:
                self.playwright = p
                logger.info(f"正在连接 CDP: {ws_endpoint}")
                self.browser = await p.chromium.connect_over_cdp(ws_endpoint)

                # Fingerprint browsers usually have one default context/page
                if not self.browser.contexts:
                    self.context = await self.browser.new_context()
                else:
                    self.context = self.browser.contexts[0]

                if not self.context.pages:
                    page = await self.context.new_page()
                else:
                    page = self.context.pages[0]

                # Set default timeouts
                page.set_default_timeout(30000)
                page.set_default_navigation_timeout(60000)

                yield page

        except Exception as e:
            logger.error(f"浏览器驱动异常: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup browser resources."""
        try:
            if self.browser:
                await self.browser.close()

            # Note: We don't call BrowserAPI.close_browser here
            # as it might be handled by the scheduler for session persistence.
            # But if persistence is NOT needed, we could call it.
            logger.info(f"断开浏览器连接: {self.profile_id}")
        except Exception as e:
            logger.warning(f"清理浏览器资源失败: {e}")

    @classmethod
    @asynccontextmanager
    async def connect(cls, profile_id: str) -> AsyncGenerator[Page, None]:
        """Convenience method for connecting to a profile."""
        driver = cls(profile_id)
        async with driver.session() as page:
            yield page
