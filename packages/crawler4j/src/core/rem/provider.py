"""环境提供者抽象层。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Provider 层面向具体技术栈，负责实际 spawn/keepalive/kill/healthcheck。
"""

import asyncio
import json

from abc import ABC, abstractmethod
from typing import Any

from src.core.foundation.logging import logger
from src.core.rem.handle import BrowserHandle
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo
from src.core.rem.virtualbrowser_fingerprint import materialize_virtualbrowser_fingerprint

VIRTUALBROWSER_SUPPORTED_CHROME_VERSIONS = tuple(range(146, 138, -1))
VIRTUALBROWSER_DEFAULT_CHROME_VERSION = 145
VIRTUALBROWSER_ADD_BROWSER_MAX_ATTEMPTS = 10
VIRTUALBROWSER_ADD_BROWSER_RETRY_DELAY_SECONDS = 1.0
_SENSITIVE_PAYLOAD_KEYS = {
    "api",
    "api-key",
    "apikey",
    "pass",
    "password",
    "proxy_password",
    "proxypassword",
}


def _mask_url_credentials(value: str) -> str:
    if "://" not in value or "@" not in value:
        return value
    scheme, rest = value.split("://", 1)
    _, suffix = rest.rsplit("@", 1)
    return f"{scheme}://***@{suffix}"


def _sanitize_payload_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key in _SENSITIVE_PAYLOAD_KEYS and item:
                sanitized[key] = "***"
            else:
                sanitized[key] = _sanitize_payload_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload_for_log(item) for item in value]
    if isinstance(value, str):
        return _mask_url_credentials(value)
    return value


def _payload_for_log(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(_sanitize_payload_for_log(payload), ensure_ascii=False)
    except TypeError:
        return str(_sanitize_payload_for_log(payload))


def _normalize_cdp_endpoint(value: Any) -> str | None:
    """把各类浏览器调试返回值归一为 Playwright 可接受的 CDP 入口。"""
    if value is None:
        return None

    if isinstance(value, int):
        return f"http://localhost:{value}"

    text = str(value).strip()
    if not text:
        return None

    if text.startswith(("ws://", "wss://", "http://", "https://")):
        return text

    if text.isdigit():
        return f"http://localhost:{text}"

    if ":" in text:
        return f"http://{text}"

    return None


def _extract_cdp_endpoint(payload: dict[str, Any]) -> str | None:
    """从不同宿主 API 返回结构中提取 CDP 入口。"""
    if not isinstance(payload, dict):
        return None

    for key in (
        "ws",
        "wsUrl",
        "ws_url",
        "wsEndpoint",
        "ws_endpoint",
        "browserWs",
        "browserWsUrl",
        "browserWsEndpoint",
        "browserWSEndpoint",
        "browser_ws",
        "browser_wse",
        "browser_websocket_url",
        "webSocketDebuggerUrl",
        "websocketDebuggerUrl",
        "websocketDebuggerURL",
        "debuggingPort",
        "debugPort",
        "remoteDebuggingPort",
        "port",
        "cdpUrl",
        "cdp_url",
        "debuggerUrl",
        "debugger_url",
        "remoteDebuggingUrl",
        "remote_debugging_url",
    ):
        if key in payload:
            endpoint = _normalize_cdp_endpoint(payload.get(key))
            if endpoint:
                return endpoint

    host = payload.get("host") or payload.get("hostname") or payload.get("address")
    port = payload.get("port") or payload.get("debuggingPort") or payload.get("debugPort")
    if host and port is not None:
        normalized_port = _normalize_cdp_endpoint(port)
        if normalized_port and normalized_port.startswith("http://localhost:"):
            return f"http://{host}:{normalized_port.rsplit(':', 1)[-1]}"

    for value in payload.values():
        if isinstance(value, dict):
            endpoint = _extract_cdp_endpoint(value)
            if endpoint:
                return endpoint
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    endpoint = _extract_cdp_endpoint(item)
                    if endpoint:
                        return endpoint
    return None


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
    display_name: str = ""
    
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
    async def destroy(self, env: Environment) -> bool:
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

    def supports_existing_env_import(self) -> bool:
        """是否支持从来源系统导入已有环境。"""
        return False

    async def list_existing_envs(self) -> list[ProviderEnvInfo]:
        """列出来源系统中的环境。"""
        return []

    async def get_existing_env(self, name: str) -> ProviderEnvInfo | None:
        """按环境名称获取来源系统中的单个环境。"""
        del name
        return None

    async def build_imported_environment(self, info: ProviderEnvInfo) -> Environment:
        """把来源系统环境信息映射为宿主环境记录。"""
        return Environment(
            name=info.name,
            kind=self.kind,
            provider=self.name,
            status=EnvStatus.READY,
            external_id=info.external_id,
            handle=BrowserHandle(browser_id=str(info.external_id)),
        )

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
    display_name = "Playwright Local"
    kind = EnvKind.BROWSER
    
    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        """创建本地 Playwright 环境控制记录。"""
        import time

        from src.core.rem.models import Environment, EnvStatus
        
        config = config or {}
        browser_id = str(config.get("env_name") or "local-playwright")
        return Environment(
            name=config.get("env_name", "local-playwright"),
            kind=self.kind,
            provider=self.name,
            status=EnvStatus.READY,
            external_id=browser_id,
            capabilities={"page", "cookies"},
            handle=BrowserHandle(browser_id=browser_id),
            created_at=int(time.time()),
            updated_at=int(time.time()),
        )
    
    async def reset(self, env: Environment) -> bool:
        """重置本地环境。"""
        handle = env.handle
        if not handle:
            return True

        try:
            if handle.context:
                clear_cookies = getattr(handle.context, "clear_cookies", None)
                if callable(clear_cookies):
                    await clear_cookies()
            if handle.page and not handle.page.is_closed():
                await handle.page.goto("about:blank", wait_until="domcontentloaded")
            return True
        except Exception:
            return False
    
    async def health_check(self, env: Environment) -> bool:
        """健康检查。"""
        handle = env.handle
        if not handle or not handle.page or handle.page.is_closed():
            return False
        try:
            await handle.page.title()
            return True
        except Exception:
            return False
    
    async def destroy(self, env: Environment) -> bool:
        """销毁本地环境。"""
        return await self.close(env)
    
    async def open(self, env: Environment) -> bool:
        """打开本地浏览器。"""
        handle = env.handle
        if handle is None:
            browser_id = str(env.external_id or env.name or "local-playwright")
            handle = BrowserHandle(browser_id=browser_id)
            env.handle = handle

        if handle.browser and handle.is_connected():
            return True

        launch_candidates = (
            {"headless": False},
            {"channel": "chrome", "headless": False},
            {"headless": True},
            {"channel": "chrome", "headless": True},
        )
        try:
            from src.core.rem.handle import PlaywrightManager

            playwright = await PlaywrightManager.acquire()
            handle._has_playwright_ref = True
            last_error: Exception | None = None
            for launch_options in launch_candidates:
                try:
                    handle._browser = await playwright.chromium.launch(**launch_options)
                    return True
                except Exception as exc:
                    last_error = exc
            if last_error is not None:
                raise last_error
            return False
        except Exception as exc:
            from src.core.foundation.logging import logger

            logger.error(f"[PlaywrightProvider] Failed to launch local browser: {exc}")
            if handle._has_playwright_ref:
                from src.core.rem.handle import PlaywrightManager

                await PlaywrightManager.release()
                handle._has_playwright_ref = False
            handle._browser = None
            handle._context = None
            handle._page = None
            return False

    async def connect(self, env: Environment) -> bool:
        """建立自动化连接。"""
        handle = env.handle
        if not handle or not handle.browser:
            return False

        try:
            handle._context = (
                handle.browser.contexts[0]
                if handle.browser.contexts
                else await handle.browser.new_context()
            )
            handle._page = (
                handle.context.pages[0]
                if handle.context and handle.context.pages
                else await handle.context.new_page()
            )
            return handle.page is not None
        except Exception:
            handle._context = None
            handle._page = None
            return False
        
    async def close(self, env: Environment) -> bool:
        """关闭窗口。"""
        handle = env.handle
        if not handle:
            return True
        browser_id = handle.browser_id
        await handle.safe_close()
        env.handle = BrowserHandle(browser_id=browser_id)
        return True
    
    async def is_window_open(self, env: Environment) -> bool:
        """本地模式下不支持查询窗口状态。"""
        handle = env.handle
        return bool(handle and handle.browser and handle.is_connected())
    
    async def exists(self, env: Environment) -> bool:
        """本地环境始终存在。"""
        return True

    async def is_running(self, env: Environment) -> bool:
        """检查本地环境是否在运行。"""
        handle = env.handle
        return bool(handle and handle.browser and handle.is_connected())

    async def update(self, env: Environment, config: dict) -> bool:
        """更新本地环境配置。"""
        del env, config
        return False


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
        fingerprint: dict | None = None,
    ) -> str:
        """创建浏览器窗口，返回窗口 ID。"""
        client = await self._get_client()
        
        payload: dict[str, Any] = {
            "name": name,
            "proxyMethod": 2,  # 必须设置: 2=自定义, 3=提取IP
            "proxyType": "noproxy",  # 默认直连
            "browserFingerPrint": fingerprint or {
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
        ws_url = _extract_cdp_endpoint(result_data)
        if not ws_url:
            raise KeyError(f"Missing 'ws' in BitBrowser API response: {result_data}")
        
        return ws_url
    
    async def close_browser(self, browser_id: str) -> None:
        """关闭浏览器窗口。"""
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/browser/close", json=payload)
    
    async def delete_browser(self, browser_id: str) -> bool:
        """删除浏览器窗口。"""
        client = await self._get_client()
        payload = {"id": browser_id}
        resp = await client.post("/browser/delete", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"BitBrowser Delete Error: {data.get('msg')}")
        return True
    
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
    display_name = "BitBrowser"
    kind = EnvKind.BROWSER
    
    _client_cache: BitBrowserClient | None = None
    _client_port: int | None = None
    
    def _get_api_client(self) -> BitBrowserClient:
        from src.core.system.config_center import get_config_center

        port = get_config_center().get("browser.bitbrowser.port")
        
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
        creation_params = config.get("creation_params", {})
        
        # 使用 Manager 传入的 env_name（必须）
        name = config.get("env_name")
        if not name:
            import uuid
            name = f"bit-env-{uuid.uuid4().hex[:8]}"
            logger.warning("[BitBrowser] env_name not provided, using generated name")
        
        # 解析代理配置（仅 STATIC 和 NONE/SYSTEM）
        proxy_data = config.get("proxy") or creation_params.get("proxy") or {}
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
        
        # 3. 提取额外创建参数 (params)
        # creation_params = config.get("config", {})  # Unused
        
        group_id = config.get("group_id") or creation_params.get("group_id")
        if not group_id and isinstance(creation_params.get("groups"), list) and creation_params["groups"]:
            group_id = creation_params["groups"][0]
        fingerprint = config.get("fingerprint") or creation_params.get("fingerprint")

        logger.info(f"[BitBrowser] Creating env '{name}' with proxy mode {proxy_mode}...")
        browser_id = await client.create_browser(
            name, 
            proxy=bit_proxy,
            group_id=group_id,
            fingerprint=fingerprint
        )
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

    async def destroy(self, env: Environment) -> bool:
        """销毁 BitBrowser 环境。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        browser_id = handle.browser_id if handle and handle.browser_id else env.external_id
        if not browser_id:
            return False

        # 使用 safe_close 关闭连接
        if handle:
            await handle.safe_close()
        else:
            env.handle = BrowserHandle(browser_id=str(browser_id))

        if not await self.exists(env):
            return True
        
        try:
            client = self._get_api_client()
            await client.delete_browser(str(browser_id))
            if await self.exists(env):
                logger.warning(f"[BitBrowser] 浏览器删除后仍存在: id={browser_id}")
                return False
            logger.info(f"[BitBrowser] Closed browser {browser_id}")
            return True
        except Exception as e:
            logger.warning(f"[BitBrowser] Failed to close browser {browser_id}: {e}")
            return False
    


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
        self.base_url = f"http://127.0.0.1:{port}"
        self.headers = {"api-key": api_key} if api_key else {}
        self.client = None

    async def _get_client(self):
        import httpx
        if not self.client:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
                trust_env=False,
            )
        return self.client

    @staticmethod
    def _response_body(resp: Any, data: Any) -> str:
        body = (getattr(resp, "text", "") or "").strip()
        if not body and data is not None:
            try:
                body = json.dumps(data, ensure_ascii=False)
            except TypeError:
                body = str(data)
        return body

    @staticmethod
    def _build_add_browser_detail(resp: Any, body: str) -> str:
        detail = f"status={getattr(resp, 'status_code', 'unknown')}"
        if body:
            detail = f"{detail} body={body}"
        return detail

    @staticmethod
    def _is_retryable_add_browser_failure(resp: Any, body: str) -> bool:
        status_code = getattr(resp, "status_code", 0)
        if status_code not in {500, 502, 503, 504}:
            return False
        return "relay failed" in body.lower()

    async def add_browser(
        self,
        name: str,
        group_ids: list[str],
        proxy: dict | None = None,
        fingerprint: dict | None = None,
    ) -> int:
        """创建浏览器环境，返回ID。
        
        Args:
            name: 环境名称
            group_ids: 分组 ID 列表
            proxy: 代理配置，支持以下格式：
                - {"mode": 1} 无代理
                - {"mode": 2, "protocol": "socks5", "host": "...", "port": "...", "user": "...", "pass": "..."}
            fingerprint: 指纹模板。会在创建前展开为本次创建真正下发的指纹参数，
                不再支持 post-create 的兼容随机化链路。
        
        Returns:
            环境 ID
        """
        client = await self._get_client()
        
        # 构造默认代理参数（无代理）
        default_proxy = {
            "mode": 1,          # 1: No Proxy, 2: Custom
            "value": "",        # 完整代理字符串（备用）
            "protocol": "",     # socks5/http 等
            "host": "",
            "port": "",
            "user": "",
            "pass": "",
            "API": "",          # 动态代理 API 地址
        }

        if proxy:
            normalized_proxy = dict(proxy)

            if "protocol" in normalized_proxy and isinstance(normalized_proxy["protocol"], str):
                normalized_proxy["protocol"] = normalized_proxy["protocol"].strip().upper()

            default_proxy.update(normalized_proxy)

            has_custom_proxy = any(
                bool(default_proxy.get(k))
                for k in ("host", "port", "value", "API")
            )
            default_proxy["mode"] = 2 if has_custom_proxy else 1
        
        chrome_version, fingerprint_payload = materialize_virtualbrowser_fingerprint(
            fingerprint,
            default_chrome_version=VIRTUALBROWSER_DEFAULT_CHROME_VERSION,
        )

        # 构造请求参数
        payload = {
            "name": name,
            "group": group_ids or [],
            "chrome_version": chrome_version,
            "proxy": default_proxy,
        }

        for key, value in fingerprint_payload.items():
            payload[key] = value

        safe_payload = _payload_for_log(payload)
        max_attempts = VIRTUALBROWSER_ADD_BROWSER_MAX_ATTEMPTS

        for attempt in range(1, max_attempts + 1):
            logger.debug(
                f"[VirtualBrowser] addBrowser request: endpoint={self.base_url} "
                f"attempt={attempt}/{max_attempts} payload={safe_payload}"
            )
            resp = await client.post("/api/addBrowser", json=payload)
            try:
                data = resp.json()
            except Exception:
                data = None

            body = self._response_body(resp, data)
            if resp.is_success and isinstance(data, dict) and data.get("success"):
                return data["data"]["id"]

            detail = self._build_add_browser_detail(resp, body)
            if attempt < max_attempts and self._is_retryable_add_browser_failure(resp, body):
                logger.warning(
                    f"[VirtualBrowser] addBrowser transient failure, retrying: "
                    f"endpoint={self.base_url} attempt={attempt}/{max_attempts} "
                    f"detail={detail} payload={safe_payload}"
                )
                await asyncio.sleep(VIRTUALBROWSER_ADD_BROWSER_RETRY_DELAY_SECONDS)
                continue

            logger.error(
                f"[VirtualBrowser] addBrowser failed: endpoint={self.base_url} "
                f"attempts={attempt}/{max_attempts} detail={detail} payload={safe_payload}"
            )
            raise RuntimeError(f"VirtualBrowser addBrowser 失败: {detail}")

        raise RuntimeError("VirtualBrowser addBrowser 失败: retry loop exhausted")

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
        client = await self._get_client()
        payload = {"id": browser_id}
        last_error = ""

        for attempt in range(2):
            resp = await client.post("/api/launchBrowser", json=payload)
            try:
                data = resp.json()
            except Exception:
                data = {}

            launch_error = str(
                data.get("error")
                or data.get("msg")
                or resp.text
                or f"HTTP {resp.status_code}"
            )

            if resp.is_success and data.get("success"):
                result_data = data.get("data", {})
                ws_url = _extract_cdp_endpoint(result_data)
                if not ws_url:
                    raise KeyError(f"Missing 'ws' in VirtualBrowser API response: {result_data}")
                return ws_url

            last_error = launch_error
            if attempt == 0 and self._is_recoverable_launch_error(resp.status_code, launch_error):
                logger.warning(
                    "[VirtualBrowser] launchBrowser failed with recoverable error; "
                    f"stopping browser and retrying once: id={browser_id} "
                    f"status={resp.status_code} error={launch_error}"
                )
                await self.stop_browser(browser_id)
                await asyncio.sleep(1)
                continue

            logger.error(
                "[VirtualBrowser] launchBrowser failed: "
                f"id={browser_id} status={resp.status_code} error={launch_error}"
            )
            if not resp.is_success:
                resp.raise_for_status()
            break

        raise RuntimeError(f"Launch Error: {last_error}")

    @staticmethod
    def _is_recoverable_launch_error(status_code: int, message: str) -> bool:
        text = message.strip().lower()
        if status_code == 400 and "is running" in text:
            return True
        if status_code == 500 and "devtools port" in text:
            return True
        if "remote debugging" in text:
            return True
        if "browser process closed before devtools port was detected" in text:
            return True
        return False
    
    async def stop_browser(self, browser_id: int):
        client = await self._get_client()
        payload = {"id": browser_id}
        await client.post("/api/stopBrowser", json=payload)

    async def delete_browser(self, browser_id: int) -> bool:
        client = await self._get_client()
        payload = {"id": browser_id}
        resp = await client.post("/api/deleteBrowser", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"VirtualBrowser Delete Error: {data.get('msg')}")
        return True
    
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
        return self._find_browser_entry(data.get("data", []), browser_id)

    async def list_browsers(self) -> list[dict[str, Any]]:
        """获取全部浏览器环境列表。"""
        client = await self._get_client()
        resp = await client.get("/api/getBrowserList")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        payload = data.get("data", [])
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            nested = payload.get("data")
            if isinstance(nested, list):
                return nested
        return []

    async def get_browser_full_parameters(
        self,
        browser_id: int | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """获取浏览器完整参数。"""
        client = await self._get_client()
        path = "/api/getBrowserFullParameters"
        if browser_id is not None:
            path = f"{path}?id={browser_id}"
        resp = await client.get(path)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return None
        return data.get("data")

    async def list_running_browsers(self) -> list[dict[str, Any]]:
        """获取当前运行中的浏览器环境列表。"""
        client = await self._get_client()
        resp = await client.get("/api/getBrowserRunningList")
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return []
        payload = data.get("data", [])
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            nested = payload.get("data")
            if isinstance(nested, list):
                return nested
        return []

    async def get_browser_running_detail(self, browser_id: int) -> dict | None:
        """获取运行中的浏览器详情。

        运行列表通常比完整列表更接近实时状态，适合作为 CDP 入口兜底。
        """
        return self._find_browser_entry(await self.list_running_browsers(), browser_id)

    async def get_browser_runtime_detail(self, browser_id: int) -> dict | None:
        """获取可用于连接的运行时详情。

        运行态调试入口以 getBrowserRunningList 为准，只有拿不到运行态记录时才回退静态详情。
        """
        running_detail = await self.get_browser_running_detail(browser_id)
        if running_detail:
            return running_detail
        return await self.get_browser_detail(browser_id)

    @staticmethod
    def _match_browser_id(candidate: dict[str, Any], browser_id: int) -> bool:
        target = str(browser_id)
        for key in ("id", "browserId", "browser_id", "envId", "environmentId"):
            value = candidate.get(key)
            if value is not None and str(value) == target:
                return True
        return False

    @classmethod
    def _find_browser_entry(cls, payload: Any, browser_id: int) -> dict | None:
        if isinstance(payload, dict):
            if cls._match_browser_id(payload, browser_id):
                return payload
            for value in payload.values():
                found = cls._find_browser_entry(value, browser_id)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = cls._find_browser_entry(item, browser_id)
                if found:
                    return found
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
    display_name = "Virtual Browser"
    kind = EnvKind.BROWSER
    
    _client_cache: VirtualBrowserClient | None = None
    _client_config: tuple[int, str] | None = None  # (port, api_key)
    _lifecycle_lock: asyncio.Lock | None = None

    def _get_lifecycle_lock(self) -> asyncio.Lock:
        if self._lifecycle_lock is None:
            self._lifecycle_lock = asyncio.Lock()
        return self._lifecycle_lock

    def _get_api_client(self) -> VirtualBrowserClient:
        from src.core.system.config_center import get_config_center

        config = get_config_center()
        port = config.get("browser.virtualbrowser.port")
        api_key = config.get("browser.virtualbrowser.apikey")
        
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
                    "protocol": parsed.scheme,
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "user": parsed.username or "",
                    "pass": parsed.password or "",
                }
            except Exception as e:
                logger.warning(f"[VirtualBrowser] Failed to parse proxy '{raw_val}': {e}")
        
        fingerprint = (
            creation_params.get("virtualbrowser")
            or creation_params.get("fingerprint")
        )
        
        logger.info(f"[VirtualBrowser] Creating env '{name}'...")
        
        # VirtualBrowser 的本地管理 API 对并发创建/启动不稳定，串行化避免拖死宿主 UI 事件循环。
        async with self._get_lifecycle_lock():
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

    async def _wait_until_window_closed(
        self,
        env: Environment,
        *,
        attempts: int = 5,
        delay: float = 0.3,
    ) -> bool:
        for attempt in range(attempts):
            if not await self.is_window_open(env):
                return True
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
        return False

    async def _wait_until_missing(
        self,
        env: Environment,
        *,
        attempts: int = 6,
        delay: float = 0.5,
    ) -> bool:
        for attempt in range(attempts):
            if not await self.exists(env):
                return True
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
        return False

    async def destroy(self, env: Environment) -> bool:
        """销毁: 断开连接 + 停止浏览器 + 删除配置。"""
        from src.core.foundation.logging import logger
        
        handle = env.handle
        browser_id = handle.browser_id if handle and handle.browser_id else env.external_id
        if not browser_id:
            return False
        
        # 1. 使用 safe_close 关闭 Playwright 连接
        if handle:
            await handle.safe_close()
        else:
            env.handle = BrowserHandle(browser_id=str(browser_id))

        if not await self.exists(env):
            return True

        # 2. API Stop & Delete
        client = self._get_api_client()
        try:
            browser_id_int = int(browser_id)
            if await self.is_window_open(env):
                await client.stop_browser(browser_id_int)
                await self._wait_until_window_closed(env)
            await client.delete_browser(browser_id_int)
            if not await self._wait_until_missing(env):
                logger.warning(f"[VirtualBrowser] 删除后环境仍存在: id={browser_id}")
                return False
            logger.info(f"[VirtualBrowser] 环境已销毁: id={browser_id}")
            return True
        except Exception as e:
            logger.warning(f"[VirtualBrowser] API 销毁环境失败: {e}")
            return False
    
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
        
        async with self._get_lifecycle_lock():
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
                message = f"VirtualBrowser launchBrowser 失败: {e}"
                logger.error(f"[VirtualBrowser] Failed to open browser {browser_id}: {e}")
                raise RuntimeError(message) from e

    async def _hydrate_ws_url(self, handle: BrowserHandle) -> str | None:
        """尽量从 VirtualBrowser 详情中恢复可连接的 ws_url。"""
        from src.core.foundation.logging import logger

        if handle.ws_url:
            return handle.ws_url

        if not handle.browser_id:
            return None

        try:
            browser_id_int = int(handle.browser_id)
        except (TypeError, ValueError):
            logger.warning(f"[VirtualBrowser] 无法解析 browser_id: {handle.browser_id}")
            return None

        client = self._get_api_client()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                detail = await client.get_browser_runtime_detail(browser_id_int)
            except Exception as e:
                last_error = e
                detail = None

            if detail:
                ws_url = _extract_cdp_endpoint(detail)
                if ws_url:
                    handle.ws_url = ws_url
                    logger.info(f"[VirtualBrowser] 已恢复 ws_url: id={handle.browser_id}")
                    return ws_url

            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))

        if last_error:
            logger.warning(f"[VirtualBrowser] 读取浏览器运行时详情失败: id={handle.browser_id} error={last_error}")
        return None

    async def connect(self, env: Environment) -> bool:
        """连接 Playwright。"""
        from src.core.foundation.logging import logger

        handle = env.handle
        if not handle:
            logger.error("[VirtualBrowser] Cannot connect: No handle")
            return False

        async with self._get_lifecycle_lock():
            if not handle.ws_url:
                if not await self._hydrate_ws_url(handle):
                    logger.error(
                        f"[VirtualBrowser] Cannot connect: Missing ws_url and cannot resolve browser detail "
                        f"for browser {handle.browser_id}"
                    )
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

    def supports_existing_env_import(self) -> bool:
        return True

    async def list_existing_envs(self) -> list[ProviderEnvInfo]:
        client = self._get_api_client()
        browser_rows = await client.list_browsers()
        full_payload = await client.get_browser_full_parameters()
        running_rows = await client.list_running_browsers()

        full_map: dict[str, dict[str, Any]] = {}
        if isinstance(full_payload, list):
            for item in full_payload:
                if isinstance(item, dict) and item.get("id") is not None:
                    full_map[str(item["id"])] = item
        elif isinstance(full_payload, dict) and full_payload.get("id") is not None:
            full_map[str(full_payload["id"])] = full_payload

        running_ids = {
            str(item.get("id"))
            for item in running_rows
            if isinstance(item, dict) and item.get("id") is not None
        }

        items: list[ProviderEnvInfo] = []
        for entry in browser_rows:
            if not isinstance(entry, dict) or entry.get("id") is None:
                continue
            external_id = str(entry["id"])
            merged = dict(entry)
            merged.update(full_map.get(external_id, {}))
            proxy = merged.get("proxy") if isinstance(merged.get("proxy"), dict) else None
            proxy_summary = "-"
            if isinstance(proxy, dict):
                protocol = str(proxy.get("protocol") or "").strip()
                host = str(proxy.get("host") or "").strip()
                port = str(proxy.get("port") or "").strip()
                if host and port:
                    proxy_summary = " ".join(part for part in (protocol, f"{host}:{port}") if part)
            timestamp = merged.get("timestamp")
            last_used_at = None
            if timestamp is not None:
                try:
                    last_used_at = int(int(timestamp) / 1000)
                except (TypeError, ValueError):
                    last_used_at = None
            is_running = bool(merged.get("isRunning")) or external_id in running_ids
            items.append(
                ProviderEnvInfo(
                    provider=self.name,
                    provider_label=self.display_name,
                    external_id=external_id,
                    name=str(merged.get("name") or external_id),
                    proxy_summary=proxy_summary,
                    remark=str(merged.get("remark") or ""),
                    is_running=is_running,
                    running_status="运行中" if is_running else "未运行",
                    last_used_at=last_used_at,
                )
            )
        items.sort(key=lambda item: (item.name.lower(), item.external_id))
        return items

    async def get_existing_env(self, name: str) -> ProviderEnvInfo | None:
        target = str(name).strip()
        for item in await self.list_existing_envs():
            if item.name == target:
                return item
        return None

    async def build_imported_environment(self, info: ProviderEnvInfo) -> Environment:
        imported = await super().build_imported_environment(info)
        imported.capabilities = {"page", "cookies", "fingerprint"}
        imported.handle = BrowserHandle(browser_id=str(info.external_id))
        return imported

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
