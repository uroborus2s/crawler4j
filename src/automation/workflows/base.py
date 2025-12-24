"""Base workflow module.

Provides common helpers for automation workflows.
"""

from playwright.async_api import Page

from src.utils.logger import logger


class BaseWorkflow:
    """Base class for all automation workflows."""
    
    def __init__(self, page: Page):
        self.page = page

    async def wait_and_click(self, selector: str, timeout: int = 10000):
        """Wait for an element to appear and then click it."""
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            await self.page.click(selector)
        except Exception as e:
            logger.error(f"点击元素失败 {selector}: {e}")
            raise

    async def wait_and_type(self, selector: str, text: str, timeout: int = 10000):
        """Wait for an element to appear and then type into it."""
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            await self.page.fill(selector, text)
        except Exception as e:
            logger.error(f"输入文本失败 {selector}: {e}")
            raise

    async def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """Check if an element is visible within timeout."""
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except Exception:
            return False
            
    async def screenshot(self, name: str):
        """Take a screenshot for debugging."""
        try:
            from pathlib import Path
            path = Path("screenshots")
            path.mkdir(exist_ok=True)
            await self.page.screenshot(path=str(path / f"{name}.png"))
        except Exception as e:
            logger.warning(f"截图失败: {e}")
