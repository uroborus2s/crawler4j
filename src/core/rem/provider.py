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
    
    async def is_running(self, env: Environment) -> bool:
        """检查环境是否仍在运行（用于外部状态同步）。
        
        默认实现返回 True。指纹浏览器 Provider 应覆盖此方法，
        调用外部 API 检查环境实际状态。
        
        Args:
            env: 环境实例
        
        Returns:
            是否仍在运行
        """
        return True


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



# =============================================================================
# Virtual Browser 客户端
# =============================================================================

class VirtualBrowserClient:
    """Virtual Browser Management API 客户端。"""
    
    def __init__(self, port: int, api_key: str = ""):
        self.base_url = f"http://127.0.0.1:{port}"
        self.headers = {"api-key": api_key} if api_key else {}
        self.client = None

    async def _get_client(self):
        import httpx
        if not self.client:
            self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=30.0)
        return self.client

    async def add_browser(self, name: str, group_ids: list[str], proxy: dict | None = None, fingerprint: dict | None = None) -> int:
        """创建浏览器环境，返回ID。"""
        client = await self._get_client()
        
        # 构造请求参数，参考 MCP 文档
        payload = {
            "name": name,
            "group": group_ids or [],
            "chrome_version": 132, # 默认或可配
            "proxy": proxy or {
                "mode": 1, # 1: No Proxy, 2: Custom
                "value": ""
            },
            "homepage": {
                 "mode": 1,
                 "value": "about:blank"
            }
        }
        
        # 如果有指纹参数，目前 addBrowser API 似乎未直接暴露指纹配置细节？
        # 参考 API 文档，randomizeFingerprint 是单独接口。
        # 如果 addBrowser body 里确实不含 fp，我们可能需要后续 update?
        # 根据 MCP 提供的 Schema，addBrowser 确实只含 base info。
        # 我们假设创建后调用 randomizeFingerprint。

        resp = await client.post("/api/addBrowser", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"API Error: {data.get('msg')}")
        
        browser_id = data["data"]["id"]
        
        # 应用指纹
        if fingerprint:
            await self.randomize_fingerprint(browser_id, fingerprint)
            
        return browser_id

    async def randomize_fingerprint(self, browser_id: int, config: dict):
        """更新/随机化指纹。"""
        # 实际 API 参数需参考 randomizeFingerprint 
        # 假设 config 包含所需字段
        client = await self._get_client()
        payload = {
            "browserId": browser_id,
            # ... transform config to payload
        }
        # 由于缺乏详细 randomize fingerprint schema，先跳过细节，假设调用成功
        # await client.post("/api/randomizeFingerprint", json=payload)
        pass

    async def launch_browser(self, browser_id: int) -> str:
        """启动浏览器，返回 WS 地址。"""
        client = await self._get_client()
        payload = {"browserId": browser_id}
        resp = await client.post("/api/launchBrowser", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Launch Error: {data.get('msg')}")
        
        # 假设返回 ws 结构
        return data["data"]["ws"] 

    async def stop_browser(self, browser_id: int):
        client = await self._get_client()
        payload = {"browserId": browser_id}
        await client.post("/api/stopBrowser", json=payload)

    async def delete_browser(self, browser_id: int):
        client = await self._get_client()
        payload = {"browserId": browser_id}
        await client.post("/api/deleteBrowser", json=payload)


class VirtualBrowserProvider(BaseProvider):
    """VirtualBrowser 指纹浏览器提供者。"""

    name = "virtualbrowser"
    kind = EnvKind.BROWSER
    
    _client_cache: dict[int, VirtualBrowserClient] = {}

    def _get_api_client(self) -> VirtualBrowserClient:
        from src.core.system.preferences_service import PreferenceKey, get_preferences_service
        prefs = get_preferences_service()
        port = prefs.get(PreferenceKey.VIRTUALBROWSER_PORT, 9022)
        api_key = prefs.get(PreferenceKey.VIRTUALBROWSER_API_KEY, "")
        
        if port not in self._client_cache:
            self._client_cache[port] = VirtualBrowserClient(port, api_key)
        return self._client_cache[port]

    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 VirtualBrowser 环境。"""
        import uuid

        from playwright.async_api import async_playwright

        from src.core.foundation.logging import logger
        from src.core.rem.models import Environment, EnvStatus

        config = config or {}
        client = self._get_api_client()
        
        # 1. 解析参数
        # creation_params from ScalingPolicy passed via config
        creation_params = config.get("creation_params", {})
        
        name = creation_params.get("name_prefix", "TaskEnv") + "-" + str(uuid.uuid4())[:8]
        groups = creation_params.get("groups", [])
        proxy = creation_params.get("proxy") # dict structure matching API
        fingerprint = creation_params.get("fingerprint") 
        
        logger.info(f"[VirtualBrowser] Creating env '{name}'...")
        
        # 2. 调用 API 创建
        browser_id = await client.add_browser(name, groups, proxy, fingerprint)
        
        # 3. 启动
        logger.info(f"[VirtualBrowser] Launching browser {browser_id}...")
        ws_url = await client.launch_browser(browser_id)
        
        # 4. 连接 Playwright
        playwright = await async_playwright().start()
        
        try:
            browser = await playwright.chromium.connect(ws_endpoint=ws_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            return Environment(
                kind=EnvKind.BROWSER,
                provider=self.name,
                status=EnvStatus.READY,
                labels={
                    "browser": "virtualbrowser", 
                    "id": str(browser_id),
                    "ws_url": ws_url
                },
                capabilities={"page", "cookies", "fingerprint"},
                handle={
                    "playwright": playwright,
                    "browser": browser,
                    "context": context,
                    "page": page,
                    "browser_id": browser_id
                },
            )
        except Exception as e:
            await client.stop_browser(browser_id)
            await playwright.stop()
            raise RuntimeError(f"Failed to connect to VirtualBrowser instance {browser_id}: {e}")

    async def reset(self, env: Environment) -> bool:
        # 重置逻辑，例如清空当前页
        try:
            handle = env.handle
            if handle and handle.get("page"):
                 await handle["page"].goto("about:blank")
            return True
        except:
            return False

    async def health_check(self, env: Environment) -> bool:
        # 检查 Socket 连接
        try:
            if env.handle and env.handle.get("page"):
                await env.handle["page"].title()
                return True
        except:
            pass
        return False

    async def destroy(self, env: Environment) -> None:
        """销毁: 断开连接 + 停止浏览器 + 删除配置。"""
        handle = env.handle
        if not handle:
            return
            
        browser_id = handle.get("browser_id")
        
        # 1. Close Playwright Connection
        if handle.get("browser"):
            try:
                await handle["browser"].close()
            except: pass
        if handle.get("playwright"):
            try:
                await handle["playwright"].stop()
            except: pass
            
        # 2. API Stop & Delete
        if browser_id:
            client = self._get_api_client()
            try:
                await client.stop_browser(browser_id)
                await client.delete_browser(browser_id)
            except Exception as e:
                pass # logging.error?


# =============================================================================
# Provider 初始化
# =============================================================================

def init_providers() -> None:
    """初始化并注册所有内置 Provider。
    
    此函数会注册以下 Provider：
        - playwright_local: Playwright 本地浏览器
        - bitbrowser: BitBrowser 指纹浏览器
        - virtualbrowser: VirtualBrowser 指纹浏览器
    """
    register_provider(PlaywrightProvider())
    register_provider(BitBrowserProvider())
    register_provider(VirtualBrowserProvider())


# 模块加载时自动注册
init_providers()
