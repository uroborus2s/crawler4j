"""网络检测工具模块。

在浏览器环境中检测网络连通性，用于工作流执行前的预检查。
"""

import asyncio
from dataclasses import dataclass

from playwright.async_api import Page

from src.core.foundation.logging import logger


@dataclass
class NetworkCheckResult:
    """网络检测结果。"""

    success: bool
    latency_ms: int = 0
    error_message: str = ""


class NetworkChecker:
    """浏览器内网络检测器。

    在真实浏览器环境中检测代理和网络的连通性。
    """

    # 检测 URL（按优先级）
    CHECK_URLS = [
        ("https://www.ctrip.com/", "携程主站"),
        ("https://m.ctrip.com/", "携程移动站"),
        ("https://www.baidu.com/", "百度（通用检测）"),
    ]

    @classmethod
    async def check_connectivity(
        cls,
        page: Page,
        timeout_ms: int = 20000,
        retries: int = 2,
    ) -> NetworkCheckResult:
        """检测网络连通性。

        Args:
            page: Playwright 页面对象
            timeout_ms: 单次请求超时时间（毫秒）
            retries: 每个 URL 的重试次数

        Returns:
            NetworkCheckResult 包含检测结果
        """
        last_error = ""

        for url, name in cls.CHECK_URLS:
            for attempt in range(retries):
                try:
                    logger.debug(f"网络检测: {name} (尝试 {attempt + 1}/{retries})")

                    start_time = asyncio.get_event_loop().time()
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=timeout_ms
                    )
                    latency = int((asyncio.get_event_loop().time() - start_time) * 1000)

                    if response and response.status < 400:
                        logger.info(f"✅ 网络检测通过: {name} (延迟: {latency}ms)")
                        return NetworkCheckResult(success=True, latency_ms=latency)
                    else:
                        status = response.status if response else "无响应"
                        last_error = f"{name} 返回状态码: {status}"
                        logger.warning(f"网络检测: {last_error}")

                except Exception as e:
                    last_error = f"{name}: {str(e)[:100]}"
                    logger.warning(f"网络检测失败: {last_error}")

                    if attempt < retries - 1:
                        await asyncio.sleep(1)
                    continue

            # 当前 URL 所有重试失败，尝试下一个
            logger.debug(f"网络检测: {name} 失败，尝试备用 URL")

        # 所有 URL 均失败
        error_msg = f"网络连接失败: {last_error}"
        logger.error(f"❌ {error_msg}")
        return NetworkCheckResult(success=False, error_message=error_msg)

    @classmethod
    async def quick_check(cls, page: Page) -> bool:
        """快速检测网络是否可用。

        使用更短的超时时间，适合快速预检。

        Args:
            page: Playwright 页面对象

        Returns:
            True 如果网络可用
        """
        result = await cls.check_connectivity(page, timeout_ms=10000, retries=1)
        return result.success
