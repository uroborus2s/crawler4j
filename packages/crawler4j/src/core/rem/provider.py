"""环境提供者抽象层。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Provider 层面向具体技术栈，负责实际 spawn/keepalive/kill/healthcheck。
"""

import asyncio
import json

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlsplit

from src.core.foundation.logging import logger
from src.core.rem.handle import BrowserHandle
from src.core.rem.ip_pool import IPEntry
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo, ProxyConfig, ProxyMode
from src.core.rem.proxy_probe import ProxyProbeResult, probe_ip_entry_geo
from src.core.rem.virtualbrowser_fingerprint import (
    VIRTUALBROWSER_COMMON_HARDWARE_PROFILES,
    VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY,
    build_virtualbrowser_geo_fingerprint_overrides,
    materialize_virtualbrowser_fingerprint,
)

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


def _first_proxy_text(proxy: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = proxy.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_proxy_protocol(value: object) -> str:
    protocol = str(value or "").strip().lower()
    aliases = {
        "no": "",
        "none": "",
        "noproxy": "",
        "direct": "",
        "socks": "socks5",
    }
    return aliases.get(protocol, protocol)


def _safe_proxy_port(value: object) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return 0


def _build_proxy_config(
    *,
    protocol: str,
    host: str,
    port: int,
    username: str = "",
    password: str = "",
) -> ProxyConfig | None:
    normalized_protocol = _normalize_proxy_protocol(protocol) or "socks5"
    host = str(host or "").strip()
    if not host or port <= 0:
        return None
    auth = f"{username}:{password}@" if username and password else ""
    return ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value=f"{normalized_protocol}://{auth}{host}:{port}",
        current_ip=host,
    )


def _proxy_config_from_value(value: str, *, fallback_protocol: str = "") -> ProxyConfig | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    value_for_parse = raw_value
    if "://" not in value_for_parse:
        protocol = _normalize_proxy_protocol(fallback_protocol) or "socks5"
        value_for_parse = f"{protocol}://{value_for_parse}"
    parts = urlsplit(value_for_parse)
    return _build_proxy_config(
        protocol=parts.scheme,
        host=str(parts.hostname or ""),
        port=int(parts.port or 0),
        username=str(parts.username or ""),
        password=str(parts.password or ""),
    )


def _source_proxy_config_from_payload(proxy: Any) -> ProxyConfig | None:
    if not isinstance(proxy, dict):
        return None

    protocol = _first_proxy_text(proxy, "protocol", "type", "proxyType", "scheme")
    host = _first_proxy_text(proxy, "host", "address", "ip", "server")
    port = _safe_proxy_port(_first_proxy_text(proxy, "port", "proxyPort"))
    username = _first_proxy_text(proxy, "user", "username", "proxyUserName", "proxy_username")
    password = _first_proxy_text(proxy, "pass", "password", "proxyPassword", "proxy_password")
    structured_proxy = _build_proxy_config(
        protocol=_normalize_proxy_protocol(protocol),
        host=host,
        port=port,
        username=username,
        password=password,
    )
    if structured_proxy is not None:
        return structured_proxy

    value = _first_proxy_text(proxy, "value", "proxy", "proxy_url", "proxyUrl", "url")
    if value:
        return _proxy_config_from_value(value, fallback_protocol=protocol)
    return None


def _ip_entry_from_proxy_config(proxy_config: ProxyConfig | None) -> IPEntry | None:
    if proxy_config is None:
        return None
    raw_value = str(proxy_config.static_value or "").strip()
    if not raw_value:
        return None
    value_for_parse = raw_value if "://" in raw_value else f"socks5://{raw_value}"
    parts = urlsplit(value_for_parse)
    host = str(parts.hostname or "").strip()
    port = int(parts.port or 0)
    if not host or port <= 0:
        return None
    return IPEntry(
        address=host,
        port=port,
        protocol=_normalize_proxy_protocol(parts.scheme) or "http",
        username=str(parts.username or "") or None,
        password=str(parts.password or "") or None,
    )


def _proxy_config_from_update_data(proxy: Any) -> ProxyConfig | None:
    if not isinstance(proxy, dict):
        return None
    try:
        return ProxyConfig.from_dict(proxy)
    except (TypeError, ValueError):
        return None


def _bitbrowser_proxy_update_payload(proxy: Any) -> dict[str, Any]:
    entry = _ip_entry_from_proxy_config(_proxy_config_from_update_data(proxy))
    if entry is None:
        return {
            "proxyMethod": 2,
            "proxyType": "noproxy",
            "host": "",
            "port": 0,
            "proxyUserName": "",
            "proxyPassword": "",
        }
    return {
        "proxyMethod": 2,
        "proxyType": entry.protocol,
        "host": entry.address,
        "port": entry.port,
        "proxyUserName": entry.username or "",
        "proxyPassword": entry.password or "",
    }


def _virtualbrowser_proxy_update_payload(proxy: Any) -> dict[str, Any]:
    entry = _ip_entry_from_proxy_config(_proxy_config_from_update_data(proxy))
    if entry is None:
        return {
            "mode": 1,
            "value": "",
            "protocol": "",
            "host": "",
            "port": "",
            "user": "",
            "pass": "",
            "API": "",
        }
    return {
        "mode": 2,
        "value": entry.to_proxy_string(),
        "protocol": entry.protocol.upper(),
        "host": entry.address,
        "port": str(entry.port),
        "user": entry.username or "",
        "pass": entry.password or "",
        "API": "",
    }


def _ip_entry_from_virtualbrowser_proxy(proxy: Any) -> IPEntry | None:
    if not isinstance(proxy, dict):
        return None
    return _ip_entry_from_proxy_config(_source_proxy_config_from_payload(proxy))


def _is_random_virtualbrowser_fingerprint(fingerprint: Any) -> bool:
    return isinstance(fingerprint, dict) and bool(fingerprint.get(VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY))


def _geo_from_proxy_probe_result(result: ProxyProbeResult) -> dict[str, Any] | None:
    if not result.ok:
        return None
    return {
        "exit_ip": result.exit_ip,
        "country_code": result.country_code,
        "country": result.country,
        "region": result.region,
        "city": result.city,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "timezone": result.timezone,
        "asn": result.asn,
        "isp": result.isp,
    }


def _browser_full_parameters_entry(payload: Any, browser_id: int) -> dict[str, Any] | None:
    return VirtualBrowserClient._find_browser_entry(payload, browser_id)


def _mode_value(section: Any) -> Any:
    if isinstance(section, dict):
        return section.get("value")
    return section


def _safe_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _is_loopback_host(host: str) -> bool:
    return host.lower() in {"127.0.0.1", "localhost", "::1"}


def _url_host(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlsplit(text if "://" in text else f"http://{text}")
    return str(parsed.hostname or "").strip()


def _mode_one_dict(section: Any) -> dict[str, Any] | None:
    if isinstance(section, dict) and section.get("mode") in (1, "1"):
        return section
    return None


def _missing_keys(section: Any, keys: tuple[str, ...]) -> list[str]:
    mapping = _mode_one_dict(section)
    if mapping is None:
        return []
    return [key for key in keys if key not in mapping]


def _created_parameter_warnings(
    payload: Any,
    *,
    browser_id: int,
    geo: dict[str, Any] | None,
) -> list[str]:
    entry = _browser_full_parameters_entry(payload, browser_id)
    if not isinstance(entry, dict):
        return ["getBrowserFullParameters 未返回目标环境"]

    warnings: list[str] = []
    expected = build_virtualbrowser_geo_fingerprint_overrides(geo)
    expected_time_zone = expected.get("time-zone")
    actual_time_zone = entry.get("time-zone")
    if isinstance(expected_time_zone, dict) and isinstance(actual_time_zone, dict):
        expected_utc = str(expected_time_zone.get("utc") or "").strip()
        actual_utc = str(actual_time_zone.get("utc") or "").strip()
        if expected_utc and actual_utc and expected_utc != actual_utc:
            warnings.append(f"time-zone.utc={actual_utc!r}，预期 {expected_utc!r}")

    expected_language = expected.get("ua-language")
    actual_language = entry.get("ua-language")
    if isinstance(expected_language, dict) and isinstance(actual_language, dict):
        expected_locale = str(expected_language.get("language") or "").strip()
        actual_locale = str(actual_language.get("language") or "").strip()
        if expected_locale and actual_locale and expected_locale != actual_locale:
            warnings.append(f"ua-language.language={actual_locale!r}，预期 {expected_locale!r}")

    webrtc = entry.get("webrtc")
    if isinstance(webrtc, dict) and webrtc.get("mode") not in (0, "0", None):
        warnings.append(f"webrtc.mode={webrtc.get('mode')!r}，预期替换模式 0")

    ua_value = str(_mode_value(entry.get("ua")) or "")
    if "WOW64" in ua_value:
        warnings.append("ua.value 包含 WOW64，预期 Win64; x64")

    location = entry.get("location")
    if isinstance(location, dict):
        longitude = str(location.get("longitude") or "").strip()
        latitude = str(location.get("latitude") or "").strip()
        if longitude in {"0", "0.0"} and latitude in {"0", "0.0"}:
            warnings.append("location 为 0,0，占位定位不能作为稳定环境参数")

    cpu = _safe_int(_mode_value(entry.get("cpu")))
    memory = _safe_int(_mode_value(entry.get("memory")))
    if cpu is not None and memory is not None:
        if (cpu, memory) not in VIRTUALBROWSER_COMMON_HARDWARE_PROFILES:
            warnings.append(f"cpu/memory={cpu}/{memory} 不在常见硬件组合池")

    proxy = entry.get("proxy")
    if isinstance(proxy, dict):
        proxy_host = str(proxy.get("host") or "").strip()
        proxy_url_host = _url_host(str(proxy.get("url") or ""))
        if (
            proxy_host
            and proxy_url_host
            and not _is_loopback_host(proxy_url_host)
            and proxy_host != proxy_url_host
        ):
            warnings.append(f"proxy.host={proxy_host!r} 与 proxy.url host={proxy_url_host!r} 不一致")

    fonts = _mode_one_dict(entry.get("fonts"))
    if fonts is not None and not fonts.get("value"):
        warnings.append("fonts.mode=1 但缺少 value 字体列表")
    voices = _mode_one_dict(entry.get("speech_voices"))
    if voices is not None and not voices.get("value"):
        warnings.append("speech_voices.mode=1 但缺少 value 语音列表")

    for key, required in (
        ("canvas", ("r", "g", "b", "a")),
        ("webgl-img", ("r", "g", "b", "a")),
        ("audio-context", ("channel", "analyer")),
        ("client-rects", ("width", "height")),
    ):
        missing = _missing_keys(entry.get(key), required)
        if missing:
            warnings.append(f"{key}.mode=1 但缺少 {','.join(missing)}")
    return warnings


def _proxy_config_summary(proxy_config: ProxyConfig | None) -> str:
    if proxy_config is None:
        return "-"
    value = str(proxy_config.static_value or "").strip()
    if "://" in value:
        parts = urlsplit(value)
        protocol = str(parts.scheme or "").lower()
        host = str(parts.hostname or "")
        port = int(parts.port or 0)
        if host and port:
            return " ".join(part for part in (protocol, f"{host}:{port}") if part)
    host = str(proxy_config.current_ip or "").strip()
    return host or "-"


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

    async def validate_fingerprint_environment(self, env: Environment) -> list[str]:
        """Return fingerprint validation warnings for manual risk rechecks."""
        del env
        return []

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

    async def get_imported_env_info(self, env: Environment) -> ProviderEnvInfo | None:
        """按已导入环境回查来源系统环境摘要。"""
        external_id = str(env.external_id or "").strip()
        env_name = str(env.name or "").strip()
        for item in await self.list_existing_envs():
            if external_id and str(item.external_id or "").strip() == external_id:
                return item
            if env_name and str(item.name or "").strip() == env_name:
                return item
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
            proxy_config=info.proxy_config,
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
    _lifecycle_lock: asyncio.Lock | None = None

    def _get_lifecycle_lock(self) -> asyncio.Lock:
        if self._lifecycle_lock is None:
            self._lifecycle_lock = asyncio.Lock()
        return self._lifecycle_lock

    @staticmethod
    def _browser_id_from_env(env: Environment) -> str | None:
        handle = env.handle
        browser_id = handle.browser_id if handle and handle.browser_id else env.external_id
        if browser_id is None:
            return None
        browser_id_text = str(browser_id).strip()
        return browser_id_text or None

    @staticmethod
    def _ensure_browser_handle(env: Environment, browser_id: str) -> BrowserHandle:
        if env.handle is None:
            env.handle = BrowserHandle(browser_id=browser_id)
        elif not env.handle.browser_id:
            env.handle.browser_id = browser_id
        return env.handle
    
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
        async with self._get_lifecycle_lock():
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
        async with self._get_lifecycle_lock():
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
        async with self._get_lifecycle_lock():
            return await self._destroy_unlocked(env)

    async def _destroy_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        handle = self._ensure_browser_handle(env, browser_id)

        # 使用 safe_close 关闭连接
        await handle.safe_close()

        if not await self._exists_unlocked(env):
            return True
        
        try:
            client = self._get_api_client()
            await client.delete_browser(str(browser_id))
            if await self._exists_unlocked(env):
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

        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            logger.error("[BitBrowser] No browser_id found for open operation")
            return False
        handle = self._ensure_browser_handle(env, browser_id)

        async with self._get_lifecycle_lock():
            # 安全检查：窗口是否已打开
            if await self._is_window_open_unlocked(env):
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
        async with self._get_lifecycle_lock():
            return await self._connect_unlocked(env)

    async def _connect_unlocked(self, env: Environment) -> bool:
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
        async with self._get_lifecycle_lock():
            return await self._close_unlocked(env)

    async def _close_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        from src.core.rem.handle import BrowserHandle
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return True
        handle = self._ensure_browser_handle(env, browser_id)

        if not await self._is_window_open_unlocked(env):
            logger.info(f"[BitBrowser] 窗口已关闭，跳过关闭: id={env.id}")
            return True

        # 使用 safe_close 关闭 Playwright 连接
        await handle.safe_close()
        
        # 关闭浏览器窗口
        try:
            client = self._get_api_client()
            await client.close_browser(browser_id)
            logger.info(f"[BitBrowser] Closed window {browser_id}")
        except Exception as e:
            logger.warning(f"[BitBrowser] Failed to close window {browser_id}: {e}")
        
        # 重置 handle，保留 browser_id
        env.handle = BrowserHandle(browser_id=browser_id)
        return True
    
    async def is_window_open(self, env: Environment) -> bool:
        """检查 BitBrowser 窗口是否已打开。"""
        async with self._get_lifecycle_lock():
            return await self._is_window_open_unlocked(env)

    async def _is_window_open_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
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
        async with self._get_lifecycle_lock():
            return await self._exists_unlocked(env)

    async def _exists_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
        try:
            client = self._get_api_client()
            detail = await client.get_browser_detail(browser_id)
            return detail is not None
        except Exception as e:
            logger.warning(f"[BitBrowser] 检查环境存在失败: {e}")
            return False
    
    async def update(self, env: Environment, config: dict) -> bool:
        """更新 BitBrowser 环境配置。"""
        async with self._get_lifecycle_lock():
            return await self._update_unlocked(env, config)

    async def _update_unlocked(self, env: Environment, config: dict) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
        try:
            client = self._get_api_client()
            
            # 处理刷新指纹的特殊情况
            api_config = dict(config)
            if "proxy" in api_config:
                api_config.update(_bitbrowser_proxy_update_payload(api_config.pop("proxy")))
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
        async with self._get_lifecycle_lock():
            return await self._reset_unlocked(env)

    async def _reset_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
        try:
            client = self._get_api_client()
            
            # 1. 尝试关闭窗口 (如果已打开)，因为缓存清理通常需要窗口关闭
            #    根据文档，clearCacheWithoutExtensions 需要窗口ID，且通常是管理操作。
            #    如果窗口打开着，API 行为未明确，但通常建议先关闭。
            #    (用户未明确要求关闭，但清理缓存通常是静态操作)
            #    为了安全起见，我们先检查是否打开。
            if await self._is_window_open_unlocked(env):
                await self._close_unlocked(env)

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
        geo: dict[str, Any] | None = None,
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
        
        materialize_kwargs: dict[str, Any] = {
            "default_chrome_version": VIRTUALBROWSER_DEFAULT_CHROME_VERSION,
        }
        if geo:
            materialize_kwargs["geo"] = geo
        chrome_version, fingerprint_payload = materialize_virtualbrowser_fingerprint(
            fingerprint,
            **materialize_kwargs,
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

    @staticmethod
    def _browser_id_from_env(env: Environment) -> str | None:
        handle = env.handle
        browser_id = handle.browser_id if handle and handle.browser_id else env.external_id
        if browser_id is None:
            return None
        browser_id_text = str(browser_id).strip()
        return browser_id_text or None

    @staticmethod
    def _ensure_browser_handle(env: Environment, browser_id: str) -> BrowserHandle:
        if env.handle is None:
            env.handle = BrowserHandle(browser_id=browser_id)
        elif not env.handle.browser_id:
            env.handle.browser_id = browser_id
        return env.handle

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
        geo = await self._probe_creation_proxy_geo(proxy, fingerprint)
        
        logger.info(f"[VirtualBrowser] Creating env '{name}'...")
        
        # VirtualBrowser 的本地管理 API 对并发创建/启动不稳定，串行化避免拖死宿主 UI 事件循环。
        async with self._get_lifecycle_lock():
            browser_id = await client.add_browser(name, groups, proxy, fingerprint, geo=geo)
            validation_warnings = await self._log_created_parameter_validation(client, int(browser_id), geo)
        
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
        
        env = Environment(
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
        env.fingerprint_validation_warnings = validation_warnings
        return env

    async def _probe_creation_proxy_geo(
        self,
        proxy: Any,
        fingerprint: Any,
    ) -> dict[str, Any] | None:
        if not _is_random_virtualbrowser_fingerprint(fingerprint):
            return None
        entry = _ip_entry_from_virtualbrowser_proxy(proxy)
        if entry is None:
            return None
        result = await asyncio.to_thread(probe_ip_entry_geo, entry)
        if not result.ok:
            logger.warning(
                "[VirtualBrowser] proxy geo probe failed; using default fingerprint geo: "
                f"proxy={result.masked_proxy_url} stage={result.stage} detail={result.detail}"
            )
            return None
        logger.info(
            "[VirtualBrowser] proxy geo probe succeeded: "
            f"exit_ip={result.exit_ip} country={result.country_code or '-'} "
            f"city={result.city or '-'} timezone={result.timezone or '-'} asn={result.asn or '-'}"
        )
        return _geo_from_proxy_probe_result(result)

    async def _log_created_parameter_validation(
        self,
        client: VirtualBrowserClient,
        browser_id: int,
        geo: dict[str, Any] | None,
    ) -> list[str]:
        try:
            payload = await client.get_browser_full_parameters(browser_id)
        except Exception as exc:
            logger.warning(f"[VirtualBrowser] getBrowserFullParameters 验收失败: id={browser_id} error={exc}")
            return [f"getBrowserFullParameters 验收失败: {exc}"]
        warnings = _created_parameter_warnings(payload, browser_id=browser_id, geo=geo)
        if warnings:
            logger.warning(
                "[VirtualBrowser] created parameter validation warning: "
                f"id={browser_id} issues={'; '.join(warnings)}"
            )
        else:
            logger.info(f"[VirtualBrowser] created parameter validation passed: id={browser_id}")
        return warnings

    async def validate_fingerprint_environment(self, env: Environment) -> list[str]:
        """Validate persisted VirtualBrowser parameters without changing the environment."""
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return ["缺少 VirtualBrowser 环境 ID"]
        try:
            browser_id_int = int(browser_id)
        except (TypeError, ValueError):
            return [f"VirtualBrowser 环境 ID 无效: {browser_id!r}"]

        async with self._get_lifecycle_lock():
            client = self._get_api_client()
            try:
                payload = await client.get_browser_full_parameters(browser_id_int)
            except Exception as exc:
                return [f"getBrowserFullParameters 验收失败: {exc}"]

        return _created_parameter_warnings(payload, browser_id=browser_id_int, geo=None)

    async def repair_fingerprint_location(self, env: Environment) -> dict[str, Any]:
        """Repair only VirtualBrowser location from the current proxy geo."""
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            raise RuntimeError("缺少 VirtualBrowser 环境 ID")
        try:
            browser_id_int = int(browser_id)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"VirtualBrowser 环境 ID 无效: {browser_id!r}") from exc

        entry = _ip_entry_from_proxy_config(env.proxy_config)
        if entry is None:
            raise RuntimeError("当前环境没有可探测的代理，无法按 ip-api 修复 location")

        result = await asyncio.to_thread(probe_ip_entry_geo, entry)
        geo = _geo_from_proxy_probe_result(result)
        location = build_virtualbrowser_geo_fingerprint_overrides(geo).get("location") if geo else None
        if not isinstance(location, dict):
            raise RuntimeError("ip-api 未返回有效经纬度，无法修复 location")

        async with self._get_lifecycle_lock():
            client = self._get_api_client()
            success = await client.update_browser(browser_id_int, {"location": location})
        if not success:
            raise RuntimeError("VirtualBrowser updateBrowser 修复 location 失败")
        logger.info(f"[VirtualBrowser] location repaired from ip-api: id={browser_id} location={location}")
        return location

    async def reset(self, env: Environment) -> bool:
        """重置环境状态：清除数据 + 导航到空白页。"""
        async with self._get_lifecycle_lock():
            return await self._reset_unlocked(env)

    async def _reset_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        handle = self._ensure_browser_handle(env, browser_id)
        
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
        
        browser_id = self._browser_id_from_env(env)
        handle = self._ensure_browser_handle(env, browser_id) if browser_id else env.handle
        
        # 1. 检查外部 API 状态
        if browser_id:
            async with self._get_lifecycle_lock():
                try:
                    if not await self._is_window_open_unlocked(env):
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
            if not await self._is_window_open_unlocked(env):
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
            if not await self._exists_unlocked(env):
                return True
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
        return False

    async def destroy(self, env: Environment) -> bool:
        """销毁: 断开连接 + 停止浏览器 + 删除配置。"""
        async with self._get_lifecycle_lock():
            return await self._destroy_unlocked(env)

    async def _destroy_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        handle = self._ensure_browser_handle(env, browser_id)
        
        # 1. 使用 safe_close 关闭 Playwright 连接
        await handle.safe_close()

        if not await self._exists_unlocked(env):
            return True

        # 2. API Stop & Delete
        client = self._get_api_client()
        try:
            browser_id_int = int(browser_id)
            if await self._is_window_open_unlocked(env):
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
            if await self._is_window_open_unlocked(env):
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
        async with self._get_lifecycle_lock():
            return await self._close_unlocked(env)

    async def _close_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        from src.core.rem.handle import BrowserHandle
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return True
        handle = self._ensure_browser_handle(env, browser_id)

        # 关闭浏览器窗口
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
        async with self._get_lifecycle_lock():
            return await self._is_window_open_unlocked(env)

    async def _is_window_open_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
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
        async with self._get_lifecycle_lock():
            return await self._exists_unlocked(env)

    async def _exists_unlocked(self, env: Environment) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
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
        async with self._get_lifecycle_lock():
            return await self._list_existing_envs_unlocked()

    async def _list_existing_envs_unlocked(self) -> list[ProviderEnvInfo]:
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
            proxy_config = _source_proxy_config_from_payload(proxy)
            proxy_summary = _proxy_config_summary(proxy_config)
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
                    proxy_config=proxy_config,
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
        async with self._get_lifecycle_lock():
            return await self._update_unlocked(env, config)

    async def _update_unlocked(self, env: Environment, config: dict) -> bool:
        from src.core.foundation.logging import logger
        
        browser_id = self._browser_id_from_env(env)
        if not browser_id:
            return False
        self._ensure_browser_handle(env, browser_id)
        
        try:
            browser_id_int = int(browser_id)
            client = self._get_api_client()
            
            # 处理刷新指纹的特殊情况
            api_config = dict(config)
            if "proxy" in api_config:
                api_config["proxy"] = _virtualbrowser_proxy_update_payload(api_config["proxy"])
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
