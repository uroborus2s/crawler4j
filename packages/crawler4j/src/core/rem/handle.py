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
from urllib.parse import urlsplit, urlunsplit

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
        
        Returns:
            Playwright 实例
            
        Raises:
            RuntimeError: 启动 Playwright 失败
        """
        from playwright.async_api import async_playwright
        
        async with cls._get_lock():
            # 创建新实例（仅首次）
            if cls._instance is None:
                logger.info("[PlaywrightManager] 启动 Playwright 驱动进程...")
                cls._instance = await async_playwright().start()
                logger.info("[PlaywrightManager] Playwright 驱动进程已启动")
            
            cls._ref_count += 1
            logger.info(f"[PlaywrightManager] acquire 完成, 引用计数: {cls._ref_count}")
            return cls._instance
    
    @classmethod
    async def release(cls) -> None:
        """释放引用（计数 -1，归零时关闭）。"""
        async with cls._get_lock():
            if cls._ref_count > 0:
                cls._ref_count -= 1
                logger.info(f"[PlaywrightManager] release 完成, 引用计数: {cls._ref_count}")
            
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

    @staticmethod
    def _normalize_cdp_http_path(path: str) -> str:
        """把 CDP HTTP URL 规范化为 Playwright 可接受的路径。"""
        normalized = path.rstrip("/")
        if normalized in {"", "/", "/json", "/json/version", "/json/list"}:
            return ""
        return path

    @staticmethod
    def _candidate_cdp_endpoints(endpoint: str) -> list[str]:
        """为同一个浏览器生成一组可尝试的 CDP 入口。"""
        candidates: list[str] = []
        
        def _append(candidate: str | None) -> None:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        parts = urlsplit(endpoint)
        if parts.scheme in {"http", "https"}:
            normalized_path = BrowserHandle._normalize_cdp_http_path(parts.path)
            netlocs = [parts.netloc]
            if parts.hostname == "127.0.0.1":
                netlocs.append(f"localhost:{parts.port}" if parts.port else "localhost")
            elif parts.hostname == "localhost":
                netlocs.append(f"127.0.0.1:{parts.port}" if parts.port else "127.0.0.1")

            for netloc in netlocs:
                http_endpoint = urlunsplit((parts.scheme, netloc, normalized_path, "", ""))
                _append(http_endpoint)
            return candidates

        _append(endpoint)

        return candidates

    @staticmethod
    def _extract_websocket_debugger_url(payload: Any) -> str | None:
        """从 DevTools JSON 响应中提取真实 WebSocket 调试地址。"""
        if isinstance(payload, dict):
            value = payload.get("webSocketDebuggerUrl")
            if isinstance(value, str) and value.startswith(("ws://", "wss://")):
                return value

            nested = payload.get("data")
            if nested is not None:
                return BrowserHandle._extract_websocket_debugger_url(nested)

        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                if item.get("type") not in {None, "browser"}:
                    continue
                value = item.get("webSocketDebuggerUrl")
                if isinstance(value, str) and value.startswith(("ws://", "wss://")):
                    return value

        return None

    @staticmethod
    async def _probe_websocket_debugger_url(endpoint: str) -> str | None:
        """主动探测 DevTools HTTP 入口，绕过 Playwright 对 `/json/version/` 的兼容性问题。"""
        parts = urlsplit(endpoint)
        if parts.scheme not in {"http", "https"}:
            return None

        normalized_path = BrowserHandle._normalize_cdp_http_path(parts.path).rstrip("/")
        probe_paths = [
            f"{normalized_path}/json/version" if normalized_path else "/json/version",
            f"{normalized_path}/json/list" if normalized_path else "/json/list",
        ]

        import httpx

        timeout = httpx.Timeout(2.0, connect=1.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for probe_path in probe_paths:
                probe_url = urlunsplit((parts.scheme, parts.netloc, probe_path, "", ""))
                try:
                    response = await client.get(probe_url)
                    response.raise_for_status()
                    payload = response.json()
                except Exception:
                    continue

                resolved = BrowserHandle._extract_websocket_debugger_url(payload)
                if resolved:
                    return resolved

        return None

    @staticmethod
    async def _build_connect_candidates(raw_candidates: list[str]) -> list[str]:
        """按优先级生成可直连的 Playwright 目标。"""
        candidates: list[str] = []
        http_fallbacks: list[str] = []

        def _append(candidate: str | None) -> None:
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        for endpoint in raw_candidates:
            if urlsplit(endpoint).scheme not in {"http", "https"}:
                _append(endpoint)
                continue

            resolved = await BrowserHandle._probe_websocket_debugger_url(endpoint)
            if resolved:
                _append(resolved)
            http_fallbacks.append(endpoint)

        for endpoint in http_fallbacks:
            _append(endpoint)

        return candidates
    
    async def safe_connect(self) -> bool:
        """安全连接到浏览器（使用共享 Playwright 单例）。
        
        Returns:
            是否连接成功
        """
        if not self.ws_url:
            logger.error(f"[BrowserHandle] Missing ws_url for browser {self.browser_id}")
            return False

        try:
            # 获取共享的 Playwright 实例
            playwright = await PlaywrightManager.acquire()
            self._has_playwright_ref = True
            last_error: Exception | None = None
            raw_candidates = self._candidate_cdp_endpoints(self.ws_url)
            attempt_count = max(8, len(raw_candidates) * 6)
            attempt = 0
            cycle = 0

            while attempt < attempt_count:
                candidates = await self._build_connect_candidates(raw_candidates)
                if not candidates:
                    candidates = list(raw_candidates)

                for endpoint in candidates:
                    if attempt >= attempt_count:
                        break

                    attempt += 1
                    try:
                        # 指纹浏览器在 open 后可能需要短暂时间才会暴露稳定的 CDP 端点。
                        self._browser = await playwright.chromium.connect_over_cdp(
                            endpoint,
                            timeout=300000,
                        )

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

                        logger.info(f"[BrowserHandle] Connected to {endpoint[:50]}...")
                        return True
                    except Exception as e:
                        last_error = e
                        self._page = None
                        self._context = None
                        self._browser = None
                        if attempt < attempt_count:
                            delay = min(0.5 + cycle * 0.25, 1.5)
                            logger.warning(
                                f"[BrowserHandle] Connect attempt {attempt}/{attempt_count} failed via {endpoint}, retrying in {delay:.2f}s: {e}"
                            )
                            await asyncio.sleep(delay)

                cycle += 1

            if last_error:
                raise last_error
            
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
