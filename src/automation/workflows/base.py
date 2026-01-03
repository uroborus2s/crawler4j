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
            await self.page.wait_for_selector(
                selector, state="visible", timeout=timeout
            )
            await self.page.click(selector)
        except Exception as e:
            logger.error(f"点击元素失败 {selector}: {e}")
            raise

    async def wait_and_type(self, selector: str, text: str, timeout: int = 10000):
        """Wait for an element to appear and then type into it."""
        try:
            await self.page.wait_for_selector(
                selector, state="visible", timeout=timeout
            )
            await self.page.fill(selector, text)
        except Exception as e:
            logger.error(f"输入文本失败 {selector}: {e}")
            raise

    async def is_visible(self, selector: str, timeout: int = 5000) -> bool:
        """Check if an element is visible within timeout."""
        try:
            await self.page.wait_for_selector(
                selector, state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    async def screenshot(self, name: str):
        """Take a screenshot for debugging.

        注意: 截图功能仅用于调试，生产环境中可禁用或跳过。
        """
        # 生产环境中跳过截图，避免文件系统错误
        import os
        if os.environ.get("DISABLE_SCREENSHOTS", "").lower() in ("1", "true", "yes"):
            logger.debug(f"截图已禁用，跳过: {name}")
            return

        try:
            from pathlib import Path
            import tempfile

            # 优先使用临时目录，避免只读文件系统问题
            screenshots_dir = os.environ.get("SCREENSHOTS_DIR")
            if screenshots_dir:
                path = Path(screenshots_dir)
            else:
                # 尝试在当前目录创建，失败则使用临时目录
                path = Path("screenshots")
                try:
                    path.mkdir(exist_ok=True)
                except OSError:
                    path = Path(tempfile.gettempdir()) / "crawler_screenshots"
                    path.mkdir(exist_ok=True)

            await self.page.screenshot(path=str(path / f"{name}.png"))
            logger.debug(f"截图已保存: {path / f'{name}.png'}")
        except Exception as e:
            logger.debug(f"截图跳过: {e}")
