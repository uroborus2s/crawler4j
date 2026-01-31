"""环境提供者抽象层。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Provider 层面向具体技术栈，负责实际 spawn/keepalive/kill/healthcheck。
"""

from abc import ABC, abstractmethod
from typing import Any

from src.core.rem.handle import BrowserHandle
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
    
    @abstractmethod
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
    
    @abstractmethod
    async def open(self, env: Environment) -> bool:
        """打开环境窗口（用于 READY → BUSY）。
        
        Args:
            env: 环境实例
        
        Returns:
            是否打开成功
        """
        return True

    @abstractmethod
    async def connect(self, env: Environment) -> bool:
        """建立自动化控制连接 (如 Playwright)。
        
        Args:
            env: 环境实例
            
        Returns:
            是否连接成功
        """
        return True

    async def disconnect(self, env: Environment) -> bool:
        """断开 Playwright 连接（保持窗口打开）。"""    
        handle = env.handle
        if not handle:
            return True
                
        # 使用 safe_close 关闭连接
        await handle.safe_close()
        
        return True
        
    @abstractmethod
    async def close(self, env: Environment) -> bool:
        """关闭环境窗口（用于 BUSY → READY，不删除配置）。
        
        Args:
            env: 环境实例
        
        Returns:
            是否关闭成功
        """
        return True
    
    @abstractmethod
    async def is_window_open(self, env: Environment) -> bool:
        """检查窗口是否已打开（用于状态同步）。
        
        Args:
            env: 环境实例
        
        Returns:
            窗口是否已打开
        """
        return False
    
    @abstractmethod
    async def exists(self, env: Environment) -> bool:
        """检查环境是否存在于外部系统（用于状态同步）。
        
        Args:
            env: 环境实例
        
        Returns:
            环境是否存在
        """
        return True
    
    @abstractmethod
    async def update(self, env: Environment, config: dict) -> bool:
        """更新环境配置（统一更新接口）。
        
        所有环境配置更新都应通过此方法进行。
        Provider 实现应根据自身能力处理配置项，忽略不支持的项。
        
        Args:
            env: 环境实例
            config: 更新配置字典，标准键包括：
                - name: 环境名称 (str)
                - proxy: 代理配置 (dict，含 mode/host/port/user/pass 等)
                - randomize_fingerprint: 刷新指纹 (bool)
        
        Returns:
            是否更新成功（至少有一项更新成功即返回 True）
        
        Note:
            - 不支持的配置项应静默忽略，不应报错
            - 指纹浏览器 Provider 应实现完整支持
            - 普通浏览器 Provider 可返回 False 表示不支持
        """
        return False

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



# =============================================================================
# Playwright 本地提供者
# =============================================================================

class PlaywrightProvider(BaseProvider):
    """Playwright 本地浏览器提供者。
    
    用于直接在本地机器运行 Playwright 浏览器实例。
    """
    
    name = "playwright_local"
    kind = EnvKind.BROWSER
    
    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建本地 Playwright 环境控制记录。"""
        import time

        from src.core.rem.models import Environment, EnvStatus
        
        config = config or {}
        return Environment(
            name=config.get("env_name", "local-playwright"),
            kind=self.kind,
            provider=self.name,
            status=EnvStatus.READY,
            external_id="local",
            created_at=int(time.time()),
            updated_at=int(time.time()),
        )
    
    async def reset(self, env: Environment) -> bool:
        """重置本地环境。"""
        return True
    
    async def health_check(self, env: Environment) -> bool:
        """健康检查。"""
        return True
    
    async def destroy(self, env: Environment) -> None:
        """销毁本地环境。"""
        pass
    
    async def open(self, env: Environment) -> bool:
        """打开本地浏览器。"""
        return True

    async def connect(self, env: Environment) -> bool:
        """建立自动化连接。"""
        return True
        
    async def close(self, env: Environment) -> bool:
        """关闭窗口。"""
        return True
    
    async def is_window_open(self, env: Environment) -> bool:
        """本地模式下不支持查询窗口状态。"""
        return False
    
    async def exists(self, env: Environment) -> bool:
        """本地环境始终存在。"""
        return True

    async def is_running(self, env: Environment) -> bool:
        """检查本地环境是否在运行。"""
        return True

    async def update(self, env: Environment, config: dict) -> bool:
        """更新本地环境配置。"""
        return True


# =============================================================================
# BitBrowser 客户端
# =============================================================================

class BitBrowserClient:
    """BitBrowser Local API 客户端。
    
    参考文档: https://doc2.bitbrowser.cn/jiekou/liu-lan-qi-jie-kou.html
    """
    
    def __init__(self, port: int = 54345):
        self._port = port
        self._client: Any = None
    
    async def _get_client(self) -> Any:

        import httpx
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{self._port}",
                timeout=30.0,
            )
        return self._client
    
    async def create_browser(
        self,
        name: str,
        group_id: str | None = None,
        proxy: dict | None = None,
    ) -> str:
        """创建浏览器窗口，返回窗口 ID。"""
        client = await self._get_client()
        
        payload: dict[str, Any] = {
            "name": name,
            "proxyMethod": 2,  # 必须设置: 2=自定义, 3=提取IP
            "proxyType": "noproxy",  # 默认直连
            "browserFingerPrint": {
                "coreVersion": "130",
                "ostype": "PC",
                "os": "Win32",
            },
        }
        
        if group_id:
            payload["groupId"] = group_id
        
        if proxy:
            payload["proxyType"] = proxy.get("type", "noproxy")
            payload["host"] = proxy.get("host", "")
            payload["port"] = proxy.get("port", 0)
            payload["proxyUserName"] = proxy.get("username", "")
            payload["proxyPassword"] = proxy.get("password", "")

        
        resp = await client.post("/browser/update", json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("success"):
            raise RuntimeError(f"BitBrowser API Error: {data.get('msg')}")
        
        return data["data"]["id"]
    
    async def open_browser(self, browser_id: str) -> str:
        """打开浏览器窗口，返回 WebSocket 地址。"""
        client = await self._get_client()
        payload = {"id": browser_id}
        
        resp = await client.post("/browser/open", json=payload)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("success"):
            raise RuntimeError(f"BitBrowser Open Error: {data.get('msg')}")
        
        result_data = data.get("data", {})
        ws_url = result_data.get("ws")
        if not ws_url:
            raise KeyError(f"Missing 'ws' in BitBrowser API response: {result_data}")
        
        return ws_url
    
    async def close_browser(self, browser_id: str) -> None:
        """关闭浏览器窗口。"""
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/browser/close", json=payload)
    
    async def delete_browser(self, browser_id: str) -> None:
        """删除浏览器窗口。"""
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/browser/delete", json=payload)
    
    async def get_browser_pids(self, browser_ids: list[str]) -> dict[str, int]:
        """查询浏览器窗口的进程 ID。
        
        Args:
            browser_ids: 浏览器 ID 列表
        
        Returns:
            browser_id -> pid 的映射，如果窗口未打开则不在结果中
        """
        client = await self._get_client()
        payload = {"ids": browser_ids}
        resp = await client.post("/browser/pids", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return {}
        # data.data 是 {browser_id: pid} 的映射
        return data.get("data", {})
    
    async def get_browser_detail(self, browser_id: str) -> dict | None:
        """获取浏览器窗口详情。
        
        Args:
            browser_id: 浏览器 ID
        
        Returns:
            浏览器详情字典，如果不存在返回 None
        """
        client = await self._get_client()
        payload = {"id": browser_id}
        resp = await client.post("/browser/detail", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return None
        return data.get("data")
    
    async def update_browser(self, browser_id: str, config: dict) -> bool:
        """更新浏览器窗口配置。
        
        Args:
            browser_id: 浏览器 ID
            config: 更新配置（name, proxy, fingerprint 等）
        
        Returns:
            是否更新成功
        """
        client = await self._get_client()
        payload = {"id": browser_id, **config}
        resp = await client.post("/browser/update", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False)
    
    async def clear_cache_except_extensions(self, browser_ids: list[str]) -> bool:
        """保留扩展数据，删除窗口缓存。
        
        Args:
            browser_ids: 浏览器 ID 列表
            
        Returns:
            是否成功
        """
        client = await self._get_client()
        payload = {"ids": browser_ids}
        resp = await client.post("/cache/clear/exceptExtensions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False)


class BitBrowserProvider(BaseProvider):
    """BitBrowser 指纹浏览器提供者。"""

    name = "bitbrowser"
    kind = EnvKind.BROWSER
    
    _client_cache: BitBrowserClient | None = None
    _client_port: int | None = None
    
    def _get_api_client(self) -> BitBrowserClient:
        from src.core.system.preferences_service import PreferenceKey, get_preferences_service
        prefs = get_preferences_service()
        port = prefs.get(PreferenceKey.BITBROWSER_PORT, 54345)
        
        # 配置变化时重建 Client
        if self._client_cache is None or self._client_port != port:
            self._client_cache = BitBrowserClient(port)
            self._client_port = port
        return self._client_cache

    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 BitBrowser 环境。
        
        Args:
            config: 配置参数，必须包含:
                - env_name: 环境名称（由 Manager 生成）
            可选:
                - proxy: 代理配置 (mode, static_value)
                - creation_params: 额外创建参数
        
        Returns:
            Environment 对象（id 为默认值 0，由 Manager 覆盖）
        """

        from src.core.foundation.logging import logger
        from src.core.rem.models import Environment, EnvStatus, ProxyConfig, ProxyMode

        config = config or {}
        client = self._get_api_client()
        
        # 使用 Manager 传入的 env_name（必须）
        name = config.get("env_name")
        if not name:
            import uuid
            name = f"bit-env-{uuid.uuid4().hex[:8]}"
            logger.warning("[BitBrowser] env_name not provided, using generated name")
        
        # 解析代理配置（仅 STATIC 和 NONE/SYSTEM）
        proxy_data = config.get("proxy", {})
        proxy_mode = ProxyMode(proxy_data.get("mode", ProxyMode.NONE))
        
        bit_proxy = {"type": "noproxy"}  # 默认无代理
        final_proxy_config = ProxyConfig(mode=proxy_mode)
        
        if (proxy_mode == ProxyMode.STATIC or proxy_mode == ProxyMode.POOL) and (raw_val := proxy_data.get("static_value")):
            # 解析静态代理字符串（POOL 模式下由 Manager 填充）
            final_proxy_config.static_value = raw_val
            
            from urllib.parse import urlparse
            try:
                if "://" not in raw_val:
                    raw_val = "socks5://" + raw_val
                parsed = urlparse(raw_val)
                
                bit_proxy = {
                    "type": parsed.scheme,
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "username": parsed.username or "",
                    "password": parsed.password or "",
                }
            except Exception as e:
                logger.warning(f"[BitBrowser] Failed to parse proxy '{raw_val}': {e}")
                bit_proxy = {"type": "noproxy"}
        
        # 注意: POOL 模式的 IP 绑定由 Manager 层处理，Provider 不参与

        logger.info(f"[BitBrowser] Creating env '{name}' with proxy mode {proxy_mode}...")
        browser_id = await client.create_browser(name, proxy=bit_proxy)
        logger.info(f"[BitBrowser] Created browser {browser_id}")
        
        if not config.get("launch", True):
             # launch parameter is now ignored in create, but we keep the logic structure as create only creates record now
             pass

        return Environment(
            name=name,
            kind=EnvKind.BROWSER,
            provider=self.name,
            status=EnvStatus.READY,
            external_id=str(browser_id),
            capabilities={"page", "cookies", "fingerprint"},
            handle=BrowserHandle(browser_id=str(browser_id)),
            proxy_config=final_proxy_config
        )

    async def health_check(self, env: Environment) -> bool:
        try:
            handle = env.handle
            if not handle:
                return False
            # 简单检查 handle.page 是否存在且连接正常
            if handle.page and not handle.page.is_closed():
                await handle.page.evaluate("() => true")
                return True
            return False
        except Exception:
            return False

    async def destroy(self, env: Environment) -> None:
        """销毁 BitBrowser 环境。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return

        if not await self.exists(env):
            return
            
        browser_id = handle.browser_id
        
        # 使用 safe_close 关闭连接
        await handle.safe_close()
        
        if browser_id:
            try:
                # 注意：这里 self.exists 可能会因为连接关闭而失败吗？
                # exists 使用 API，与 internal connection 无关。
                # 但 destroy 逻辑通常是先 delete API resource。
                client = self._get_api_client()
                await client.delete_browser(browser_id) # API expects ID
                logger.info(f"[BitBrowser] Closed browser {browser_id}")
            except Exception as e:
                logger.warning(f"[BitBrowser] Failed to close browser {browser_id}: {e}")
    


    async def open(self, env: Environment) -> bool:
        """打开 BitBrowser 窗口。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            logger.error("[BitBrowser] No browser_id found for open operation")
            return False
        
        browser_id = handle.browser_id
        
        # 安全检查：窗口是否已打开
        if await self.is_window_open(env):
            logger.info(f"[BitBrowser] 窗口已打开，跳过重复打开: id={browser_id}")
            return True
        
        try:
            client = self._get_api_client()
            ws_url = await client.open_browser(browser_id)
            logger.info(f"[BitBrowser] Opened browser {browser_id}, ws: {ws_url[:50]}...")
            
            # 仅存储 ws_url，不连接 Playwright
            handle.ws_url = ws_url
            return True
        except Exception as e:
            logger.error(f"[BitBrowser] Failed to open browser {browser_id}: {e}")
            return False

    async def connect(self, env: Environment) -> bool:
        """连接 Playwright。"""
        from src.core.foundation.logging import logger

        handle = env.handle
        if not handle:
            logger.error("[BitBrowser] Cannot connect: No handle")
            return False
        
        ws_url = handle.ws_url
        browser_id = handle.browser_id

        if not ws_url:
            logger.error("[BitBrowser] Cannot connect: No ws_url in handle")
            return False

        # 使用 BrowserHandle 的 safe_connect 方法
        result = await handle.safe_connect()
        if result:
            logger.info(f"[BitBrowser] Connected Playwright to browser {browser_id}")
        return result
    

    async def close(self, env: Environment) -> bool:
        """关闭 BitBrowser 窗口（不删除配置）。"""
        from src.core.foundation.logging import logger
        from src.core.rem.handle import BrowserHandle
        
        client = self._get_api_client()
        if not await self.is_window_open(env):
            logger.info(f"[BitBrowser] 窗口已关闭，跳过关闭: id={env.id}")
            return True
        
        handle = env.handle
        if not handle:
            return True
        
        browser_id = handle.browser_id
        
        # 使用 safe_close 关闭 Playwright 连接
        await handle.safe_close()
        
        # 关闭浏览器窗口
        if browser_id:
            try:
                await client.close_browser(browser_id)
                logger.info(f"[BitBrowser] Closed window {browser_id}")
            except Exception as e:
                logger.warning(f"[BitBrowser] Failed to close window {browser_id}: {e}")
        
        # 重置 handle，保留 browser_id
        env.handle = BrowserHandle(browser_id=browser_id)
        return True
    
    async def is_window_open(self, env: Environment) -> bool:
        """检查 BitBrowser 窗口是否已打开。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            client = self._get_api_client()
            pids = await client.get_browser_pids([browser_id])
            return browser_id in pids
        except Exception as e:
            logger.warning(f"[BitBrowser] 检查窗口状态失败: {e}")
            return False

    async def is_running(self, env: Environment) -> bool:
        """检查 Playwright 连接是否存在。"""
        handle = env.handle
        if not handle:
            return False
        return handle.is_connected()

    async def exists(self, env: Environment) -> bool:
        """检查 BitBrowser 环境是否存在。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            client = self._get_api_client()
            detail = await client.get_browser_detail(browser_id)
            return detail is not None
        except Exception as e:
            logger.warning(f"[BitBrowser] 检查环境存在失败: {e}")
            return False
    
    async def update(self, env: Environment, config: dict) -> bool:
        """更新 BitBrowser 环境配置。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:

            return False
        
        try:
            client = self._get_api_client()
            
            # 处理刷新指纹的特殊情况
            api_config = dict(config)
            if api_config.pop("randomize_fingerprint", False):
                api_config["refreshFingerprint"] = True
            
            success = await client.update_browser(browser_id, api_config)
            if success:
                logger.info(f"[BitBrowser] 更新环境成功: id={browser_id}")
            return success
        except Exception as e:
            logger.error(f"[BitBrowser] 更新环境失败: {e}")
            return False

    async def reset(self, env: Environment) -> bool:
        """重置环境状态：保留扩展数据，删除窗口缓存 + 导航到空白页。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        
        if not browser_id:
            return False
        
        try:
            client = self._get_api_client()
            
            # 1. 尝试关闭窗口 (如果已打开)，因为缓存清理通常需要窗口关闭
            #    根据文档，clearCacheWithoutExtensions 需要窗口ID，且通常是管理操作。
            #    如果窗口打开着，API 行为未明确，但通常建议先关闭。
            #    (用户未明确要求关闭，但清理缓存通常是静态操作)
            #    为了安全起见，我们先检查是否打开。
            if await self.is_window_open(env):
                await self.close(env)

            # 2. 调用 API 清除浏览器缓存（保留扩展）
            success = await client.clear_cache_except_extensions([browser_id])
            if success:
                logger.info(f"[BitBrowser] 已清除环境缓存(保留扩展): id={browser_id}")
            else:
                logger.warning(f"[BitBrowser] 清除环境缓存失败: id={browser_id}")
                return False

            # 3. 导航到空白页 (需要重新打开浏览器？)
            #    reset 的语义是"重置环境状态"，通常意味着"为下次使用做好准备"。
            #    如果我们关闭了浏览器，那么下次打开自然是新的。
            #    如果用户期望 reset 后浏览器仍然开着且在空白页，我们需要重新打开。
            #    参考 VirtualBrowser 实现：它清理数据后导航到 about:blank。
            #    但 VirtualBrowser 的 clear_browser_data 似乎不需要关闭浏览器？
            #    (API deleteBrowserData 可能是运行时)
            #    BitBrowser 的 clearCacheWithoutExtensions 位于 /cache/ 路径下，很可能是管理 API。
            #    
            #    策略：清理缓存后，如果之前是打开的，或者是为了reset而打开？
            #    BaseProvider.reset 文档: "在任务结束后清理环境，使其可以被复用。如：关闭页面、清除 Cookies、删除临时文件。"
            #    如果完全关闭了浏览器，也算由于"复用"准备好了（下次 open 会加载新状态）。
            #    
            #    但为了与 VirtualBrowser 行为一致（如果可能）：
            #    如果 reset 被调用时浏览器开着，我们可能希望它保持开启但由新状态？
            #    不，BitBrowser 清理缓存必须关闭窗口(通常)。
            #    我们假设清理缓存后处于"干净的关闭状态"即可。
            #    如果用户需要打开，会再次调用 open。
            
            return True
        except Exception as e:
            logger.error(f"[BitBrowser] 重置环境失败: {e}")
            return False





# =============================================================================
# Virtual Browser 客户端
# =============================================================================

class VirtualBrowserClient:
    """Virtual Browser Management API 客户端。"""
    
    def __init__(self, port: int, api_key: str = ""):
        self.base_url = f"http://localhost:{port}"
        self.headers = {"api-key": api_key} if api_key else {}
        self.client = None

    async def _get_client(self):
        import httpx
        if not self.client:
            self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=30.0)
        return self.client

    async def add_browser(self, name: str, group_ids: list[str], proxy: dict | None = None, fingerprint: dict | None = None) -> int:
        """创建浏览器环境，返回ID。
        
        Args:
            name: 环境名称
            group_ids: 分组 ID 列表
            proxy: 代理配置，支持以下格式：
                - {"mode": 1} 无代理
                - {"mode": 2, "protocol": "socks5", "host": "...", "port": "...", "user": "...", "pass": "..."}
            fingerprint: 指纹配置（创建后调用 randomizeFingerprint）
        
        Returns:
            环境 ID
        """
        client = await self._get_client()
        
        # 构造默认代理参数（完整字段）
        default_proxy = {
            "mode": 2,          # 1: No Proxy, 2: Custom
            "value": "",        # 完整代理字符串（备用）
            "protocol": "",     # socks5/http 等
            "host": "",
            "port": "",
            "user": "",
            "pass": "",
            "API": "",          # 动态代理 API 地址
        }
        
        # 合并传入的代理参数
        if proxy:
            default_proxy.update(proxy)
        
        # 构造请求参数
        payload = {
            "name": name,
            "group": group_ids or [],
            "chrome_version": 132,
            "proxy": default_proxy,
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

    async def randomize_fingerprint(self, browser_id: int, config: dict | None = None) -> bool:
        """更新/随机化指纹。
        
        Args:
            browser_id: 浏览器 ID
            config: 可选的指纹配置（当前 API 仅需 id）
        
        Returns:
            是否成功
        """
        client = await self._get_client()
        payload = {"id": browser_id}
        
        try:
            resp = await client.post("/api/randomizeFingerprint", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("success", False)
        except Exception:
            return False

    async def launch_browser(self, browser_id: int) -> str:
        """启动浏览器，返回 WS 地址。"""
        import httpx

        from src.core.foundation.logging import logger
        
        client = await self._get_client()
        payload = {"id": browser_id}
        resp = await client.post("/api/launchBrowser", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Launch Error: {data.get('msg')}")
        
        # 兼容不同版本的 API 返回
        result_data = data.get("data", {})
        if "ws" in result_data:
            return result_data["ws"]
        
        port = result_data.get("debuggingPort")
        if port:
            logger.info(f"[VirtualBrowser] 尝试从端口 {port} 获取 WebSocket 地址...")
            # try:
            #     # 访问 /json/version 获取真正的 WS 地址
            #     async with httpx.AsyncClient(timeout=10.0) as fetcher:
            #         version_resp = await fetcher.get(f"http://localhost:{port}/json/version")
            #         version_resp.raise_for_status()
            #         version_data = version_resp.json()
            #         ws_url = version_data.get("webSocketDebuggerUrl")
            #         ws_url = ws_url.replace("localhost", "127.0.0.1")
            #         if ws_url:
            #             logger.info(f"[VirtualBrowser] 成功获取 WS 地址: {ws_url}")
            #             return ws_url
            # except Exception as e:
            #     logger.warning(f"[VirtualBrowser] 无法通过端口 {port} 获取 WS 地址: {e}")
            
            # 回退方案: 如果获取失败，仍然返回端口形式的连接地址
            return f"http://localhost:{port}"
        
        raise KeyError(f"Missing 'ws' or 'debuggingPort' in API response: {result_data}")
    
    async def stop_browser(self, browser_id: int):
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/api/stopBrowser", json=payload)

    async def delete_browser(self, browser_id: int):
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/api/deleteBrowser", json=payload)
    
    async def delete_browser_data(self, browser_id: int) -> bool:
        """删除浏览器环境数据（Cookies、缓存等）。
        
        用于重置环境状态，不删除环境本身。
        
        Args:
            browser_id: 浏览器 ID
        
        Returns:
            是否删除成功
        """
        client = await self._get_client()
        payload = {"id": browser_id}
        resp = await client.post("/api/deleteBrowserData", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False)
    
    async def is_browser_running(self, browser_id: int) -> bool:
        """查询指定浏览器是否正在运行。
        
        Note: 由于 /api/isBrowserRunning 返回 404，改为从运行列表中查询。
        """
        client = await self._get_client()
        resp = await client.get("/api/getBrowserRunningList")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return False
            
        # data.data 是运行中的 对象列表，例如 [{"id": 1, "name": "1"}]
        running_envs = data.get("data", [])
        for env_info in running_envs:
            if isinstance(env_info, dict) and env_info.get("id") == browser_id:
                return True
        return False
    
    async def get_browser_detail(self, browser_id: int) -> dict | None:
        """获取浏览器环境详情。
        
        Args:
            browser_id: 浏览器 ID
        
        Returns:
            环境详情字典，如果不存在返回 None
        """
        client = await self._get_client()
        resp = await client.get("/api/getBrowserList")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return None
        # data.data 是列表，找到匹配 ID 的环境
        for env in data.get("data", []):
            if env.get("id") == browser_id:
                return env
        return None
    
    async def update_browser(self, browser_id: int, config: dict) -> bool:
        """更新浏览器环境配置。
        
        Args:
            browser_id: 浏览器 ID
            config: 更新配置（name, proxy 等）
        
        Returns:
            是否更新成功
        """
        client = await self._get_client()
        payload = {"id": browser_id, **config}
        resp = await client.post("/api/updateBrowser", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("success", False)


class VirtualBrowserProvider(BaseProvider):
    """VirtualBrowser 指纹浏览器提供者。"""

    name = "virtualbrowser"
    kind = EnvKind.BROWSER
    
    _client_cache: VirtualBrowserClient | None = None
    _client_config: tuple[int, str] | None = None  # (port, api_key)

    def _get_api_client(self) -> VirtualBrowserClient:
        from src.core.system.preferences_service import PreferenceKey, get_preferences_service
        prefs = get_preferences_service()
        port = prefs.get(PreferenceKey.VIRTUALBROWSER_PORT, 9002)
        api_key = prefs.get(PreferenceKey.VIRTUALBROWSER_API_KEY, "")
        
        current_config = (port, api_key)
        
        # 配置变化时重建 Client
        if self._client_cache is None or self._client_config != current_config:
            self._client_cache = VirtualBrowserClient(port, api_key)
            self._client_config = current_config
        return self._client_cache



    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建 VirtualBrowser 环境。"""
        import uuid

        from src.core.foundation.logging import logger
        from src.core.rem.models import Environment, EnvStatus

        config = config or {}
        client = self._get_api_client()
        
        # 使用 Manager 传入的 env_name（必须）
        name = config.get("env_name")
        if not name:
            name = f"vb-env-{uuid.uuid4().hex[:8]}"
            logger.warning("[VirtualBrowser] env_name not provided, using generated name")
        
        # 解析额外参数
        creation_params = config.get("creation_params", {})
        groups = creation_params.get("groups", [])
        proxy = creation_params.get("proxy")  # 默认使用 creation_params 中的代理

        # 解析标准代理配置 (Manager 传入，优先级更高)
        proxy_data = config.get("proxy", {})
        from src.core.rem.models import ProxyMode
        proxy_mode = ProxyMode(proxy_data.get("mode", ProxyMode.NONE))
        
        if (proxy_mode == ProxyMode.STATIC or proxy_mode == ProxyMode.POOL) and (raw_val := proxy_data.get("static_value")):
            from urllib.parse import urlparse
            try:
                if "://" not in raw_val:
                    raw_val = "socks5://" + raw_val
                parsed = urlparse(raw_val)
                proxy = {
                    "type": parsed.scheme,
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "username": parsed.username or "",
                    "password": parsed.password or "",
                }
            except Exception as e:
                logger.warning(f"[VirtualBrowser] Failed to parse proxy '{raw_val}': {e}")
        
        fingerprint = creation_params.get("fingerprint") 
        
        logger.info(f"[VirtualBrowser] Creating env '{name}'...")
        
        # 调用 API 创建
        browser_id = await client.add_browser(name, groups, proxy, fingerprint)
        
        if config.get("launch", True):
             # launch parameter is now ignored in create
             pass
        else:
             pass
        
        # 还原代理配置
        final_proxy_config = None
        if config.get("proxy"):
            from src.core.rem.models import ProxyConfig
            final_proxy_config = ProxyConfig.from_dict(config["proxy"])
        
        from src.core.rem.handle import BrowserHandle
        
        return Environment(
            # id 使用默认值 0，由 Manager 覆盖为数据库自增 ID
            name=name,
            kind=EnvKind.BROWSER,
            provider=self.name,
            status=EnvStatus.READY,
            external_id=str(browser_id),  # 持久化 browser_id
            capabilities={"page", "cookies", "fingerprint"},
            proxy_config=final_proxy_config,
            handle=BrowserHandle(browser_id=str(browser_id)),
        )

    async def reset(self, env: Environment) -> bool:
        """重置环境状态：清除数据 + 导航到空白页。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            
            # 1. 调用 API 清除浏览器数据（Cookies、缓存等）
            await client.delete_browser_data(browser_id_int)
            logger.info(f"[VirtualBrowser] 已清除环境数据: id={browser_id}")
            
            # 2. 导航到空白页
            if handle.page:
                await handle.page.goto("about:blank")
            
            return True
        except Exception as e:
            logger.error(f"[VirtualBrowser] 重置环境失败: {e}")
            return False

    async def health_check(self, env: Environment) -> bool:
        """健康检查：结合 Playwright 连接状态和外部 API 状态。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        
        # 1. 检查外部 API 状态
        if browser_id:
            try:
                browser_id_int = int(browser_id)
                client = self._get_api_client()
                if not await client.is_browser_running(browser_id_int):
                    logger.warning(f"[VirtualBrowser] 健康检查失败: 外部浏览器未运行 id={browser_id}")
                    return False
            except Exception as e:
                logger.warning(f"[VirtualBrowser] 健康检查 API 调用失败: {e}")
                return False
        
        # 2. 检查 Playwright 连接
        try:
            if handle.page:
                await handle.page.title()
                return True
        except Exception as e:
            logger.warning(f"[VirtualBrowser] 健康检查失败: Playwright 连接异常 {e}")
        
        return False

    async def destroy(self, env: Environment) -> None:
        """销毁: 断开连接 + 停止浏览器 + 删除配置。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return
            
        browser_id = handle.browser_id
        
        # 1. 使用 safe_close 关闭 Playwright 连接
        await handle.safe_close()
            
        # 2. API Stop & Delete
        if browser_id:
            client = self._get_api_client()
            try:
                if await self.is_window_open(env):
                    await client.stop_browser(int(browser_id))
                await client.delete_browser(int(browser_id))
                logger.info(f"[VirtualBrowser] 环境已销毁: id={browser_id}")
            except Exception as e:
                logger.warning(f"[VirtualBrowser] API 销毁环境失败: {e}")
    
    async def open(self, env: Environment) -> bool:
        """打开 VirtualBrowser 窗口。"""
        from src.core.foundation.logging import logger
        from src.core.rem.handle import BrowserHandle
        
        handle = env.handle
        if not handle:
            handle = BrowserHandle()
            env.handle = handle
        
        browser_id = handle.browser_id
        
        if not browser_id:
            logger.error("[VirtualBrowser] No browser_id found for open operation")
            return False
        
        # 安全检查：窗口是否已打开
        if await self.is_window_open(env):
            logger.info(f"[VirtualBrowser] 窗口已打开，跳过重复打开: id={browser_id}")
            return True
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            ws_url = await client.launch_browser(browser_id_int)
            logger.info(f"[VirtualBrowser] Opened browser {browser_id}")
            
            # 存储 ws_url 到 BrowserHandle
            handle.ws_url = ws_url
            return True
        except Exception as e:
            logger.error(f"[VirtualBrowser] Failed to open browser {browser_id}: {e}")
            return False

    async def connect(self, env: Environment) -> bool:
        """连接 Playwright。"""
        from src.core.foundation.logging import logger

        handle = env.handle
        if not handle:
            logger.error("[VirtualBrowser] Cannot connect: No handle")
            return False
        
        # 使用 BrowserHandle 的 safe_connect 方法
        result = await handle.safe_connect()
        if result:
            logger.info(f"[VirtualBrowser] Connected Playwright to browser {handle.browser_id}")
        return result
        
    async def close(self, env: Environment) -> bool:
        """关闭 VirtualBrowser 窗口（不删除配置）。"""
        from src.core.foundation.logging import logger
        from src.core.rem.handle import BrowserHandle
        
        handle = env.handle
        if not handle:
            return True
        
        browser_id = handle.browser_id
        
        
        
        # 关闭浏览器窗口
        if browser_id:
            try:
                # 使用 safe_close 关闭 Playwright 连接
                await handle.safe_close()
                browser_id_int = int(browser_id)
                client = self._get_api_client()
                await client.stop_browser(browser_id_int)
                logger.info(f"[VirtualBrowser] Closed window {browser_id}")
            except Exception as e:
                logger.warning(f"[VirtualBrowser] Failed to close window {browser_id}: {e}")
        
        # 重置 handle，保留 browser_id
        env.handle = BrowserHandle(browser_id=browser_id)
        return True
    
    async def is_window_open(self, env: Environment) -> bool:
        """检查 VirtualBrowser 窗口是否已打开。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            # 转换为 int (VirtualBrowser 使用数字 ID)
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            is_running = await client.is_browser_running(browser_id_int)
            return is_running
        except Exception as e:
            logger.warning(f"[VirtualBrowser] 检查窗口状态失败: {e}")
            return False

    async def is_running(self, env: Environment) -> bool:
        """检查 Playwright 连接是否存在。"""
        handle = env.handle
        if not handle:
            return False
        return handle.is_connected()

    async def exists(self, env: Environment) -> bool:
        """检查 VirtualBrowser 环境是否存在。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            detail = await client.get_browser_detail(browser_id_int)
            return detail is not None
        except Exception as e:
            logger.warning(f"[VirtualBrowser] 检查环境存在失败: {e}")
            return False
    
    async def update(self, env: Environment, config: dict) -> bool:
        """更新 VirtualBrowser 环境配置。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        if not handle:
            return False
        
        browser_id = handle.browser_id
        if not browser_id:
            return False
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            
            # 处理刷新指纹的特殊情况
            api_config = dict(config)
            should_randomize = api_config.pop("randomize_fingerprint", False)
            
            # 如果有其他配置项，先更新
            if api_config:
                success = await client.update_browser(browser_id_int, api_config)
                if not success:
                    logger.error(f"[VirtualBrowser] 更新环境失败: id={browser_id}")
                    return False
            
            # 如果需要刷新指纹
            if should_randomize:
                await client.randomize_fingerprint(browser_id_int, {})
                logger.info(f"[VirtualBrowser] 指纹已刷新: id={browser_id}")
            
            logger.info(f"[VirtualBrowser] 更新环境成功: id={browser_id}")
            return True
        except Exception as e:
            logger.error(f"[VirtualBrowser] 更新环境失败: {e}")
            return False
        
        if not browser_id:
            return False
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            
            # 处理刷新指纹的特殊情况
            api_config = dict(config)
            should_randomize = api_config.pop("randomize_fingerprint", False)
            
            # 如果有其他配置项，先更新
            if api_config:
                success = await client.update_browser(browser_id_int, api_config)
                if not success:
                    logger.error(f"[VirtualBrowser] 更新环境失败: id={browser_id}")
                    return False
            
            # 如果需要刷新指纹
            if should_randomize:
                await client.randomize_fingerprint(browser_id_int, {})
                logger.info(f"[VirtualBrowser] 指纹已刷新: id={browser_id}")
            
            logger.info(f"[VirtualBrowser] 更新环境成功: id={browser_id}")
            return True
        except Exception as e:
            logger.error(f"[VirtualBrowser] 更新环境失败: {e}")
            return False


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
